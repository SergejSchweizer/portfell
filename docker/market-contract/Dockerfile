FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY tests/market_contract ./tests/market_contract
RUN uv pip install --system .

CMD ["python", "tests/market_contract/contract_qa.py"]