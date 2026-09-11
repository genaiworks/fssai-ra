FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY profiles ./profiles
RUN python -m pip install --upgrade pip && python -m pip install ".[platform]"

RUN useradd --create-home --uid 10001 fssaira
USER 10001

EXPOSE 8080
CMD ["uvicorn", "fssaira.api:create_default_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
