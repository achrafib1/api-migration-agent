"""Behavior tests for the AtlasPay v1 HTTP client."""

from __future__ import annotations

import json

import httpx

from atlaspay_client.client import AtlasPayClient
from atlaspay_client.models import CustomerCreate
from tests.fixtures import CREATE_CUSTOMER_RESPONSE


def test_create_customer_uses_v1_contract() -> None:
    """The client sends and validates the exact synthetic v1 representation."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/customers/create"
        assert json.loads(request.content) == {
            "customer_name": "Example Customer",
            "country": "TN",
        }
        assert request.headers.get("X-API-Key") == "example-not-a-real-key"
        return httpx.Response(201, json=CREATE_CUSTOMER_RESPONSE)

    http_client = httpx.Client(
        base_url="https://atlaspay.invalid",
        headers={"X-API-Key": "example-not-a-real-key"},
        transport=httpx.MockTransport(handler),
    )
    client = AtlasPayClient(http_client=http_client)
    try:
        customer = client.create_customer(
            CustomerCreate(customer_name="Example Customer", country="TN")
        )
    finally:
        http_client.close()

    assert customer.customer_id == "customer-example"
    assert customer.status == "active"
