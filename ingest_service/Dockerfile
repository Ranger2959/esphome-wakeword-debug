ARG BUILD_FROM=ghcr.io/home-assistant/base:3.23
FROM ${BUILD_FROM} AS webui-builder

RUN apk add --no-cache nodejs npm

WORKDIR /build

# Copy web UI source files
COPY web_ui/package*.json ./web_ui/
COPY web_ui/tsconfig.json ./web_ui/
COPY web_ui/.eslintrc.cjs ./web_ui/
COPY web_ui/.prettierrc.json ./web_ui/
COPY web_ui/src ./web_ui/src

# Create the app/static directory structure for the build output
RUN mkdir -p app/static

# Install dependencies and build the web UI
WORKDIR /build/web_ui
RUN npm ci && npm run build

# Python runtime stage
FROM ${BUILD_FROM}

ARG BUILD_ARCH=amd64
ARG BUILD_VERSION=dev

LABEL \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}" \
    org.opencontainers.image.title="Home Assistant Add-on: Wake Word Debug Pipeline" \
    org.opencontainers.image.description="Capture and review ESPHome wake word audio" \
    org.opencontainers.image.source="https://github.com/constructorfleet/esphome-wakeword-debug"

WORKDIR /app

# Install runtime and build dependencies in a virtual environment.
RUN apk add --no-cache python3 py3-pip gcc musl-dev python3-dev \
    && python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:${PATH}"

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Copy built web UI from the builder stage
COPY --from=webui-builder /build/app/static ./app/static

# Clips live under /data, which the Supervisor mounts as a persistent,
# backup-included volume. The service creates the directory at startup, so
# creating it here would only be shadowed by that mount.

COPY run.sh /run.sh
RUN chmod a+x /run.sh

# Expose port
EXPOSE 8000

# Supervisor reads this instead of the obsolete `watchdog` config option.
# Uses the venv Python already on PATH so no extra HTTP client is needed.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).status == 200 else 1)"

# Run the application through the add-on-aware launcher.
CMD ["/run.sh"]
