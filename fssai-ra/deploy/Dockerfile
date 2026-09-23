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
# Run every failure test the shipped packs cite, and record only those that
# passed. A failing, skipped or missing test fails the build. The server checks
# each pack's failure_test against this list, because tests/ is not shipped.
COPY tests ./tests
COPY profiles ./profiles
COPY conference ./conference
COPY contract ./contract
COPY scripts/failure_test_manifest.py ./
# PYTHONPATH=src tests this source tree; the installed copy supplies dependencies.
RUN python -m pip install --find-links=/wheels ".[platform,privacy,dev]" pyyaml \
 && PYTHONPATH=/build/src python failure_test_manifest.py --run profiles > /build/failure-tests.txt

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
COPY --from=build /build/failure-tests.txt ./contract/failure-tests.txt

RUN useradd --create-home --uid 10001 fssaira \
 && mkdir -p /var/lib/fssaira \
 && chown -R 10001 /app /var/lib/fssaira
USER 10001

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=4s --start-period=20s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8080/health || exit 1

CMD ["uvicorn", "fssaira.api:create_default_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
