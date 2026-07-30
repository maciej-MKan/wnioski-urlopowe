"""Production entry point (uvicorn `app.main:app`).

All logic lives in the domain/application/infrastructure/interface layers; here we only run
the composition root with the default (production) dependency wiring.
"""
from __future__ import annotations

from .composition import create_app

app = create_app()
