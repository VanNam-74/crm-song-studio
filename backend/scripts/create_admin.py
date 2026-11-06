"""Create an admin user, reset a password, or turn on 2FA.

    python -m scripts.create_admin --email you@company.com --name "Your Name" --role admin --totp
    python -m scripts.create_admin --email you@company.com --reset-password
    python -m scripts.create_admin --email you@company.com --reset-totp

The password is asked interactively (never pass it on the command line).
With --totp / --reset-totp an otpauth:// link is printed: open it as a QR code
(e.g. `qrencode -t ansiutf8 '<link>'`) and scan it with Google Authenticator / 1Password.
"""
import argparse
import asyncio
import getpass

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.passwords import hash_password, new_totp_secret, totp_uri
from app.core.security import encrypt
from app.models import AdminUser, UserRole
from app.services.auth import delete_all_sessions, normalize_email


def ask_password() -> str:
    while True:
        pw = getpass.getpass("Password (min 12 chars): ")
        if len(pw) < 12:
            print("Too short.")
            continue
        if pw != getpass.getpass("Repeat password: "):
            print("Passwords do not match.")
            continue
        return pw


def enable_totp(user: AdminUser) -> str:
    secret = new_totp_secret()
    user.totp_secret_enc = encrypt(secret)
    return totp_uri(secret, user.email, get_settings().totp_issuer)


async def main(a: argparse.Namespace) -> None:
    email = normalize_email(a.email)
    uri = None
    async with SessionLocal() as session:
        user = await session.scalar(select(AdminUser).where(func.lower(AdminUser.email) == email))

        if user is None:
            if a.reset_password or a.reset_totp:
                raise SystemExit(f"No user {email}.")
            user = AdminUser(email=email, full_name=a.name, role=UserRole(a.role),
                             password_hash=hash_password(ask_password()))
            session.add(user)
            if a.totp:
                uri = enable_totp(user)
            print(f"Created {a.role} {email}.")
        else:
            if not (a.reset_password or a.reset_totp or a.totp):
                raise SystemExit(f"{email} already exists. Use --reset-password or --reset-totp.")
            if a.reset_password:
                user.password_hash = hash_password(ask_password())
                user.failed_login_count = 0
                user.locked_until = None
                print("Password updated.")
            if a.reset_totp or a.totp:
                uri = enable_totp(user)
            await session.flush()
            await delete_all_sessions(session, user.id)
            print("All existing sessions were signed out.")
        await session.commit()
    await engine.dispose()

    if uri:
        print("\nScan this in your authenticator app (shown once):\n")
        print(f"  {uri}\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--name")
    p.add_argument("--role", choices=[r.value for r in UserRole], default="admin")
    p.add_argument("--totp", action="store_true", help="turn on 2FA")
    p.add_argument("--reset-password", action="store_true")
    p.add_argument("--reset-totp", action="store_true")
    asyncio.run(main(p.parse_args()))
