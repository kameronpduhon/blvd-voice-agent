FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base
ENV PYTHONUNBUFFERED=1

FROM base AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ python3-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked
COPY . .
RUN uv run src/agent.py download-files

FROM base AS production
RUN adduser --disabled-password --gecos "" --home /nonexistent --shell /sbin/nologin --no-create-home --uid 10001 appuser
COPY --from=build --chown=appuser:appuser /app /app
WORKDIR /app
USER appuser
CMD ["uv", "run", "src/agent.py", "start"]
