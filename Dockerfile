# dndkit as a server of its own: MCP over HTTP at :8000/mcp (a token is
# required) and the live web pages at :8765. Campaigns live in /data.
# Base images are pinned by digest; the comment names the version.

FROM ghcr.io/astral-sh/uv:0.12.17@sha256:10787c682e4184e4f290de1171fd4703dc63de99221f10fe1c99002ce7fa9acc AS uv

FROM python:3.12.15-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
# The same path as at run time: the environment's scripts name their interpreter.
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-editable
COPY README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-editable

FROM python:3.12.15-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
LABEL org.opencontainers.image.title="dndkit" \
      org.opencontainers.image.description="A D&D 5e game master's MCP server, for voice play" \
      org.opencontainers.image.source="https://github.com/sboily/dndkit" \
      org.opencontainers.image.licenses="MIT"
RUN useradd --uid 1000 --create-home dndkit && mkdir /data && chown dndkit:dndkit /data
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DNDKIT_STORAGE_DIR=/data \
    DNDKIT_TRANSPORT=http \
    DNDKIT_HTTP_HOST=0.0.0.0 \
    DNDKIT_HTTP_PORT=8000 \
    DNDKIT_WEB_HOST=0.0.0.0 \
    DNDKIT_WEB_PORT=8765
USER dndkit
VOLUME /data
EXPOSE 8000 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['DNDKIT_HTTP_PORT'] + '/health', timeout=3)"]
ENTRYPOINT ["dndkit"]
