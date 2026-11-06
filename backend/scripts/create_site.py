"""Register a WordPress site and print its webhook URL + secret (until the admin UI exists).

    python -m scripts.create_site --name "Heart Into Song" --slug heartintosong \
        --base-url https://heartintosong.com

Re-running with an existing slug rotates the secret (use --rotate).
"""
import argparse
import asyncio
import re

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.models import Site
from app.core.security import encrypt, new_secret


async def main(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", args.slug):
        raise SystemExit("Slug must be lowercase letters, digits and dashes.")

    secret = new_secret()
    async with SessionLocal() as session:
        site = await session.scalar(select(Site).where(Site.slug == args.slug))
        if site and not args.rotate:
            raise SystemExit(f"Site '{args.slug}' already exists. Use --rotate to issue a new secret.")
        if site is None:
            site = Site(name=args.name, slug=args.slug, base_url=args.base_url.rstrip("/"),
                        webhook_secret_enc=encrypt(secret))
            session.add(site)
        else:
            site.webhook_secret_enc = encrypt(secret)
        await session.commit()
    await engine.dispose()

    base = get_settings().public_base_url.rstrip("/")
    print("\nPaste these into WooCommerce > Song Studio Webhook:\n")
    print(f"  Webhook URL : {base}/webhooks/{args.slug}")
    print(f"  Secret      : {secret}\n")
    print("The secret is stored encrypted and will not be shown again.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--base-url", required=True)
    p.add_argument("--rotate", action="store_true")
    asyncio.run(main(p.parse_args()))
