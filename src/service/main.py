"""ASGI entry point for the Occlusion API."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from src.service.app import create_app

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = create_app()

__all__ = ["app"]
