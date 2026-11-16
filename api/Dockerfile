# The algorithm server (FastAPI), ready for any host that runs a container: Render, Railway,
# Fly.io, Google Cloud Run, Azure Container Apps, a VPS… See docs/DEPLOIEMENT.md.
#
#   docker build -t field-shift-api api
#   docker run -p 8000:8000 -e FIELD_SHIFT_CORS_ORIGINS=https://mon-site.vercel.app field-shift-api
#
# Python 3.14: the version the server and its tests run on (numpy and scipy have wheels for it).
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# The dependencies first: they stay in the build cache while the code changes.
COPY pyproject.toml README.md ./
RUN python -c "import subprocess, sys, tomllib; deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; subprocess.check_call([sys.executable, '-m', 'pip', 'install', *deps])"

COPY field_shift ./field_shift
COPY water_use ./water_use
RUN pip install --no-deps . \
    && useradd --create-home --uid 1000 fieldshift \
    && mkdir -p /data \
    && chown fieldshift /data

# What the data services answered is kept here (a request is made once). Mount a volume on
# /data to keep it across deployments; without one, the first plan of a place reads everything
# again after a restart.
ENV FIELD_SHIFT_CACHE_DIR=/data/field_shift \
    ALGO_CACHE_DIR=/data/yield_model \
    WATER_USE_CACHE=/data/water_use \
    PORT=8000

USER fieldshift
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"

# Most hosts give the port in $PORT. The host's proxy terminates HTTPS in front of the server.
CMD ["sh", "-c", "exec uvicorn field_shift.api.main:app --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips '*'"]
