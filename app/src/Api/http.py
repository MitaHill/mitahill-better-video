"""Compatibility shim.

Historically `create_app` lived in this module.
The API implementation has been split into `app.src.Api.routes` and
`app.src.Api.services`; keep this import path stable for existing callers.
"""

from .app_factory import create_app

__all__ = ["create_app"]
