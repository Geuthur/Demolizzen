# The web panel of Demolizzen. The bot itself is not part of this image.
#
#   docker compose up -d --build
#
# See docs/web-panel.md for the settings it needs.

FROM python:3.13-slim AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY pyproject.toml README.md ./
COPY demolizzen ./demolizzen
RUN pip wheel --no-cache-dir --wheel-dir /wheels ".[web]"

FROM python:3.13-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 panel
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

USER panel
WORKDIR /home/panel
ENV DJANGO_SETTINGS_MODULE=demolizzen.web.settings \
    PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status != 200)"]
# The panel sits behind a proxy that ends TLS; its forwarding headers are trusted.
CMD ["uvicorn", "demolizzen.web.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
