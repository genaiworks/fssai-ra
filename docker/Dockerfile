# Research toolchain. The checkout is mounted at runtime, never baked into layers.
FROM python:3.13.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends git make nodejs \
    && rm -rf /var/lib/apt/lists/*
COPY docker/research-requirements.txt /opt/research-requirements.txt
RUN python -m pip install -r /opt/research-requirements.txt && python -m pip check
ENV PYTHONPATH=/workspace/fssai-ra/src HOME=/tmp
WORKDIR /workspace/fssai-ra
CMD ["python", "scripts/reproduce.py", "--full"]
