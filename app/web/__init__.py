"""Web layer (FastAPI + Jinja). `app` is the ASGI application."""

from app.web.app import app

__all__ = ["app"]
