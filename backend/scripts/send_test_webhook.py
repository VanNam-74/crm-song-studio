"""Send a signed test webhook, exactly like the WordPress plugin does.

    python -m scripts.send_test_webhook --url http://localhost:8000/webhooks/heartintosong \
        --secret <secret> --event ping
    python -m scripts.send_test_webhook --url ... --secret ... --event order.paid --order-id 10482 --package 1_day
"""
import argparse
import json
import time
import uuid
from datetime import datetime, timezone

import httpx

from app.core.security import compute_signature


def sample_order(order_id: int, package: str) -> dict:
    return {
        "id": order_id,
        "number": str(order_id),
        "status": "processing",
        "paid_at": datetime.now(timezone.utc).isoformat(),
        "currency": "USD",
        "total": "99.00",
        "customer": {"name": "Daniel W.", "email": "daniel@example.com"},
        "package": "Custom Song – Standard",
        "delivery_option": package,
        "items": [{"product_id": 123, "name": "Custom Song – Standard", "quantity": 1,
                   "meta": {"Delivery": "1 Day" if package == "1_day" else "3 Days"}}],
        "story": {
            "tnm_recipient_name": "Margaret",
            "tnm_relationship": "Wife",
            "tnm_occasion": "40th anniversary",
            "tnm_genre": "Acoustic folk",
            "tnm_story": "We met at Lake Tahoe in 1985...",
        },
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--secret", required=True)
    p.add_argument("--event", choices=["ping", "order.paid"], default="ping")
    p.add_argument("--order-id", type=int, default=10482)
    p.add_argument("--package", choices=["1_day", "3_day"], default="1_day")
    a = p.parse_args()

    payload = {"event": a.event, "delivery_id": str(uuid.uuid4()),
               "sent_at": datetime.now(timezone.utc).isoformat()}
    if a.event == "order.paid":
        payload["order"] = sample_order(a.order_id, a.package)

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-TNM-Event": a.event,
        "X-TNM-Delivery": payload["delivery_id"],
        "X-TNM-Timestamp": ts,
        "X-TNM-Signature": compute_signature(a.secret, ts, body),
    }
    r = httpx.post(a.url, content=body, headers=headers, timeout=15)
    print(r.status_code, r.text)


if __name__ == "__main__":
    main()
