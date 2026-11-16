"""Entry point for hosts that start FastAPI apps with `uvicorn main:app` (Railway / Railpack).

It is the same server as `uvicorn field_shift.api.main:app`; run either from `api/`.
"""

from field_shift.api.main import app

__all__ = ["app"]
