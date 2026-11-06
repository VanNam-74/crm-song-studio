from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Customer(BaseModel):
    name: str | None = None
    email: str | None = None


class OrderItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    product_id: int | None = None
    name: str
    quantity: int = 1
    meta: dict[str, Any] = Field(default_factory=dict)


class OrderPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    number: str
    status: str | None = None
    paid_at: datetime | None = None
    created_at: datetime | None = None
    currency: str | None = None
    total: str | None = None
    customer: Customer = Field(default_factory=Customer)
    package: str | None = None
    delivery_option: Literal["1_day", "3_day"] | None = None
    items: list[OrderItem] = Field(default_factory=list)
    story: dict[str, Any] = Field(default_factory=dict)


class WebhookPayload(BaseModel):
    event: Literal["ping", "order.paid"]
    delivery_id: str = Field(min_length=8, max_length=100)
    sent_at: datetime | None = None
    order: OrderPayload | None = None

    @model_validator(mode="after")
    def _order_required(self) -> "WebhookPayload":
        if self.event == "order.paid" and self.order is None:
            raise ValueError("order is required for order.paid")
        return self


class WebhookResponse(BaseModel):
    status: Literal["pong", "created", "exists", "duplicate"]
    job_id: int | None = None
    message: str | None = None
