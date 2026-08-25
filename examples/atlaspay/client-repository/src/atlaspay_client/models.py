"""Pydantic request and response models for AtlasPay v1."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    """Represent the v1 customer-creation request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    customer_name: str = Field(min_length=1)
    country: str = Field(min_length=2, max_length=2)


class Customer(BaseModel):
    """Represent the v1 customer response returned by AtlasPay."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    customer_id: str
    customer_name: str
    status: str
