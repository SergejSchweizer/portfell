FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS runtime

WORKDIR /app
ENV UV_SYSTEM_PYTHON=1
COPY pyproject.toml README.md ./
COPY src ./src
COPY apps/api/requirements-ui.txt /tmp/requirements-ui.txt
RUN uv pip install --system . \
    && uv pip install --system --requirement /tmp/requirements-ui.txt

RUN useradd --system --create-home --uid 10001 portfell \
    && mkdir -p /srv/portfell/shared-data \
    && chown portfell:portfell /srv/portfell/shared-data
USER portfell

EXPOSE 8000
CMD ["python", "-m", "portfell.hosted_runtime", "api"]
