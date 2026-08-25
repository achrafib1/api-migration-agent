"""Typed Python client for the synthetic AtlasPay v1 contract."""

from atlaspay_client.client import AtlasPayClient
from atlaspay_client.models import Customer, CustomerCreate
from atlaspay_client.service import CustomerService

__all__ = ["AtlasPayClient", "Customer", "CustomerCreate", "CustomerService"]
