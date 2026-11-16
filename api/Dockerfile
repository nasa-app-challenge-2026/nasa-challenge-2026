FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    FIELD_SHIFT_WORKERS=0 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    FIELD_SHIFT_CACHE_DIR=/var/data/field-shift \
    WATER_USE_CACHE=/var/data/water-use \
    ALGO_CACHE_DIR=/var/data/yield

WORKDIR /app/api
COPY api/ ./
RUN pip install .

EXPOSE 8000
CMD ["sh", "-c", "exec python -m uvicorn field_shift.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
