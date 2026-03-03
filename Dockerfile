FROM python:3.12-slim

# Install system dependencies for Bluetooth
RUN apt-get update && apt-get install -y --no-install-recommends \
    bluez \
    libglib2.0-dev \
    libdbus-1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY pyproject.toml .
COPY bluehood/ bluehood/
COPY README.md .

RUN pip install --no-cache-dir -e ".[metrics]"

# Create data directory for database and cache
RUN mkdir -p /data

# Bundle MAC vendor database at build time as fallback
RUN python -c "from mac_vendor_lookup import MacLookup; MacLookup().update_vendors()" \
    && cp /root/.cache/mac-vendors.txt /data/mac-vendors.txt \
    || echo "Warning: could not bundle vendor DB"

# Environment variables
ENV BLUEHOOD_DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

# Expose web dashboard and metrics ports
EXPOSE 8080
EXPOSE 9199

# Entrypoint handles PUID/PGID data directory ownership
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "-m", "bluehood.daemon"]
