"""Example SME domain code.

Rename this package to match your SaaS (e.g. ``sme_tools/salesforce/``)
and re-export the client + error classes you actually use. Public class
names and method signatures should be held stable across releases so
callers never break on a rebuild.
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
