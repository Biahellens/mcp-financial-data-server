FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

# MCP servers speak their protocol over stdio, so run this container with
# `docker run -i` (or configure your MCP client to invoke it that way).
ENTRYPOINT ["mcp-financial-data-server"]
