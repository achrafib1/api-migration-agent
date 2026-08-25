"""Synchronous HTTP client for the trusted AtlasPay demonstration."""

from __future__ import annotations

import httpx

from atlaspay_client.auth import ATLASPAY_V1_AUTH
from atlaspay_client.models import Customer, CustomerCreate


class AtlasPayClient:
    """Call the narrow AtlasPay v1 customer API through an injected transport."""

    def __init__(
        self,
        *,
        http_client: httpx.Client,
    ) -> None:
        """Create a client without performing network access.

        Args:
            http_client: Preconfigured HTTP client. The host owns authentication
                configuration and credential handling.

        Raises:
            ValueError: If the client lacks the non-sensitive v1 authentication
                header name. The header value is never read or exposed.
        """

        if ATLASPAY_V1_AUTH.header_name not in http_client.headers:
            raise ValueError("The HTTP client is missing AtlasPay authentication configuration.")
        self._http = http_client

    def create_customer(self, request: CustomerCreate) -> Customer:
        """Create a customer using the AtlasPay v1 endpoint and field names."""

        response = self._http.post(
            "/customers/create",
            json={
                "customer_name": request.customer_name,
                "country": request.country,
            },
        )
        response.raise_for_status()
        return Customer.model_validate(response.json())
