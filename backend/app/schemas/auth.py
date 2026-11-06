from pydantic import BaseModel, ConfigDict, Field

from app.models import UserRole


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)
    otp: str | None = Field(default=None, max_length=10)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    role: UserRole
