"""Field Shift: crop rotations chosen with the climate twin of the farm.

The package has four parts:
  - `algorithm`  the algorithm itself (field_shift v5.1), with no web code;
  - `contract`   the wire format (Pydantic models of FarmInput and FarmPlan);
  - `services`   what the web layer calls (weather source, algorithm cache);
  - `api`        the FastAPI application.
"""

__version__ = "3.0.0"
