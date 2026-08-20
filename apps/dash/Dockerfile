FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS runtime

WORKDIR /app
ENV UV_SYSTEM_PYTHON=1
COPY pyproject.toml README.md ./
COPY src ./src
COPY apps/dash/requirements.txt /tmp/dash-requirements.txt
RUN uv pip install --system . \
    && uv pip install --system --requirement /tmp/dash-requirements.txt

RUN useradd --system --create-home --uid 10002 portfell
USER portfell

EXPOSE 8050
CMD ["python", "-m", "portfell.dash_ui.runtime"]
