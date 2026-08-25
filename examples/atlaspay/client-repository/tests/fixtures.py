"""Synthetic, credential-free AtlasPay v1 test fixtures."""

from __future__ import annotations

CREATE_CUSTOMER_REQUEST = {
    "customer_name": "Example Customer",
    "country": "TN",
}

CREATE_CUSTOMER_RESPONSE = {
    "customer_id": "customer-example",
    "customer_name": "Example Customer",
    "status": "active",
}
