from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.internal.deps import CurrentUser, DbSession
from app.schemas.auth import LoginRequest, UserOut
from app.services.auth import AuthError, LockedError, authenticate, create_session, delete_session

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_PATH = "/api"


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        key=s.session_cookie_name,
        value=token,
        max_age=s.session_ttl_hours * 3600,
        path=COOKIE_PATH,
        httponly=True,
        secure=s.cookie_secure,
        samesite="strict",
    )


def _clear_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(
        key=s.session_cookie_name, path=COOKIE_PATH,
        httponly=True, secure=s.cookie_secure, samesite="strict",
    )


@router.post("/login", response_model=UserOut)
async def login(body: LoginRequest, request: Request, response: Response, session: DbSession):
    try:
        user = await authenticate(session, body.email, body.password, body.otp)
    except LockedError:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try again later.")
    except AuthError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email, password or code.")

    token = await create_session(
        session, user,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, session: DbSession) -> None:
    token = request.cookies.get(get_settings().session_cookie_name)
    if token:
        await delete_session(session, token)
    _clear_cookie(response)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user
