"""Application service coordinating AtlasPay customer creation."""

from __future__ import annotations

from atlaspay_client.client import AtlasPayClient
from atlaspay_client.models import Customer, CustomerCreate


class CustomerService:
    """Expose a business-facing customer creation operation."""

    def __init__(self, client: AtlasPayClient) -> None:
        """Inject the HTTP client dependency."""

        self._client = client

    def create_customer(self, customer_name: str, country: str) -> Customer:
        """Create a customer from the values available in the v1 application."""

        request = CustomerCreate(customer_name=customer_name, country=country)
        return self._client.create_customer(request)
