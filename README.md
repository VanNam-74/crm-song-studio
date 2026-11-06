# Create Song – Webhook (WordPress → FastAPI)

Bước đầu của hệ thống: WordPress gửi đơn đã thanh toán sang server create-song, server kiểm tra chữ ký và tạo job.

```
create-song/
├── backend/                       FastAPI
│   ├── app/
│   │   ├── main.py                app + /health
│   │   ├── config.py              đọc .env
│   │   ├── db.py                  async SQLAlchemy
│   │   ├── models.py              schema (bản rút gọn: không tự giao bài, trạng thái cuối = done)
│   │   ├── schemas.py             payload webhook
│   │   ├── security.py            HMAC + mã hoá secret (Fernet)
│   │   ├── routers/webhooks.py    POST /webhooks/{slug}
│   │   ├── services/jobs.py       tạo order + job, tính due_at, đẩy Celery
│   │   ├── celery_app.py, tasks.py  (generate_lyrics đang là placeholder)
│   ├── scripts/                   init_db, create_site, send_test_webhook
│   └── tests/test_webhook.py      10 test
├── wordpress/tnm-song-webhook/    plugin WordPress
└── docker-compose.yml             PostgreSQL + Redis
```

## 1. Chạy server create-song

```bash
cd create-song
docker compose up -d                 # PostgreSQL + Redis

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # điền FERNET_KEY, PUBLIC_BASE_URL
python -m scripts.init_db            # tạo bảng (dev; production dùng Alembic)

python -m scripts.create_site --name "Heart Into Song" --slug heartintosong \
    --base-url https://heartintosong.com
# -> in ra Webhook URL + Secret (chỉ hiện 1 lần)

uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Chưa có Celery worker thì đặt `ENQUEUE_TASKS=false`. Job vẫn được tạo ở trạng thái `queued`.

Thử không cần WordPress:

```bash
python -m scripts.send_test_webhook --url http://127.0.0.1:8000/webhooks/heartintosong --secret <SECRET> --event ping
python -m scripts.send_test_webhook --url ... --secret <SECRET> --event order.paid --order-id 10482 --package 1_day
pytest -q
```

WordPress phải gọi được server này qua HTTPS. Server ở công ty thì mở bằng Cloudflare Tunnel, **chỉ public đường dẫn `/webhooks/*`**.

## 2. Cài plugin WordPress

1. Copy `wordpress/tnm-song-webhook/` vào `wp-content/plugins/`, kích hoạt.
2. **WooCommerce → Song Studio Webhook**:
   - Enable
   - Webhook URL + Secret (lấy từ bước `create_site`)
   - **Song product IDs**: ID sản phẩm bài hát. Để trống = mọi đơn đều gửi, kể cả đơn add-on/enhance.
   - **Story meta prefixes**: prefix của meta chứa câu chuyện khách (mặc định `tnm_, _tnm_`). Sửa cho đúng key mà `tnm-song-order-bundle` lưu.
3. Bấm **Send test ping** → phải thấy "Connected — Connected to Heart Into Song".

## 3. Luồng hoạt động

```
Đơn → Processing
  └─ plugin: _tnm_sw_status = queued, tạo delivery_id
     └─ Action Scheduler (chạy nền, không làm chậm checkout)
        └─ POST /webhooks/heartintosong
             headers: X-TNM-Event, X-TNM-Delivery, X-TNM-Timestamp,
                      X-TNM-Signature = sha256=HMAC(secret, "<timestamp>.<body>")
FastAPI:
  1. tìm site theo slug (không có / inactive → 404)
  2. kiểm chữ ký + timestamp ±5 phút (sai → 401, ghi webhook_logs)
  3. validate payload (sai → 422)
  4. delivery_id đã xử lý → 200 "duplicate"
  5. ping → 200 "pong"
  6. order.paid → tạo song_orders + song_jobs (queued, due_at, priority)
     đơn đã có job → 200 "exists" (không tạo trùng)
  7. đẩy task generate_lyrics vào Celery (Redis lỗi → job vẫn queued, ghi event lỗi)
```

**Plugin retry:** lỗi mạng hoặc HTTP 5xx/408/429 thì thử lại sau 1, 2, 4, 8 phút (tối đa 5 lần, giữ nguyên `delivery_id`). Lỗi 401/404/422 là lỗi cấu hình nên không retry; plugin ghi order note và đặt `_tnm_sw_status = failed`. Gửi lại tay ở trang đơn: **Order actions → Send to Song Studio**.

**Kết quả trên đơn WordPress:** order note "Song Studio: created (job #12)", meta `_tnm_sw_status`, `_tnm_sw_job_id`. Log ở WooCommerce → Status → Logs → `tnm-song-webhook`.

## 4. Payload `order.paid`

```json
{
  "event": "order.paid",
  "delivery_id": "6f1c…",
  "sent_at": "2026-10-31T04:00:05+00:00",
  "order": {
    "id": 10482, "number": "10482", "status": "processing",
    "paid_at": "2026-10-31T11:00:00+07:00",
    "currency": "USD", "total": "99.00",
    "customer": {"name": "Daniel W.", "email": "…"},
    "package": "Custom Song – Standard",
    "delivery_option": "1_day",
    "items": [{"product_id": 123, "name": "…", "quantity": 1, "meta": {"Delivery": "1 Day"}}],
    "story": {"tnm_recipient_name": "Margaret", "tnm_story": "…"}
  }
}
```

**Gói 1-day / 3-day** được plugin tự dò từ chữ "1 day / 24h / 3 days / 72h" trong item meta và story. Không dò được thì server dùng `DEFAULT_DELIVERY_OPTION` và ghi cảnh báo vào job. Muốn chính xác thì thêm filter trong theme/plugin:

```php
add_filter( 'tnm_sw_delivery_option', function ( $option, $order ) {
    $value = $order->get_meta( '_tnm_delivery' );          // key thật của bạn
    return $value === 'express' ? '1_day' : '3_day';
}, 10, 2 );
```

Các filter khác: `tnm_sw_should_send` (quyết định đơn nào được gửi), `tnm_sw_order_payload` (thêm/bớt field trong payload).

`due_at = paid_at + 24h` (1-day) hoặc `+ 72h` (3-day), `priority` = 9 / 5.
