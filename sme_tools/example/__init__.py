"""SanMar SME domain code.

This package exposes the client and error classes used by
`sme_tools.example.tools`.
"""

from sme_tools.example.client import (
    ExampleAPIError,
    ExampleClient,
    ExampleConnectionError,
    example_client_from_env,
)

__all__ = [
    "ExampleAPIError",
    "ExampleClient",
    "ExampleConnectionError",
    "example_client_from_env",
]
