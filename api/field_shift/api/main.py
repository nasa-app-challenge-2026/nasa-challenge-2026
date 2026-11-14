"""Entry point of the server: `python -m uvicorn field_shift.api.main:app`."""

from field_shift.api.app import create_app

app = create_app()
