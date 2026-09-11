# Control plane and import gateway image.
#
# Two stages so the runtime carries no build toolchain, a non-root user, and a
# read-only root filesystem in compose. The image includes contract/ and
# profiles/ because the governance configuration is part of the deployment, not
# something mounted in later and hoped for.
FROM python:3.13-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --upgrade pip build \
 && python -m pip wheel --no-deps --wheel-dir /wheels . \
 && python -m pip wheel --wheel-dir /wheels ".[platform]"

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FSSAI_PROFILE=profiles/student_support.yaml

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=build /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels fssaira[platform] && rm -rf /wheels

COPY profiles ./profiles
COPY contract ./contract

RUN useradd --create-home --uid 10001 fssaira && chown -R 10001 /app
USER 10001

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=4s --start-period=20s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8080/health || exit 1

CMD ["uvicorn", "fssaira.api:create_default_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
