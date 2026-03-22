FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY cmd/ cmd/

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ---- API server (default) ----
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "app.api.server:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- CLI / Indexer ----
FROM base AS cli
ENTRYPOINT ["python", "-m", "cmd.cli"]

# ---- MCP server ----
FROM base AS mcp
CMD ["python", "-m", "cmd.cli", "mcp"]
