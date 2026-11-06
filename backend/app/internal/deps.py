from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import AdminUser, UserRole
from app.services.auth import get_session_user

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(request: Request, session: DbSession) -> AdminUser:
    token = request.cookies.get(get_settings().session_cookie_name)
    user = await get_session_user(session, token) if token else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    return user


CurrentUser = Annotated[AdminUser, Depends(get_current_user)]


def require_role(*roles: UserRole):
    async def checker(user: CurrentUser) -> AdminUser:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
        return user

    return checker


AdminOnly = Annotated[AdminUser, Depends(require_role(UserRole.ADMIN))]
CanOperate = Annotated[AdminUser, Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR))]
