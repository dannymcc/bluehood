FROM python:3.12-slim

# Install system dependencies for Bluetooth
RUN apt-get update && apt-get install -y --no-install-recommends \
    bluez \
    libglib2.0-dev \
    libdbus-1-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (but we'll need bluetooth group access)
RUN useradd -m -s /bin/bash bluehood && \
    usermod -aG bluetooth bluehood

WORKDIR /app

# Copy and install Python dependencies
COPY pyproject.toml .
COPY bluehood/ bluehood/
COPY README.md .

RUN pip install --no-cache-dir -e .

# Create data directory for database
RUN mkdir -p /data && chown bluehood:bluehood /data

# Create directory for mac addresses cache
RUN mkdir -p /home/bluehood/.cache \
    && chown bluehood:bluehood /home/bluehood/.cache

# Environment variables
ENV BLUEHOOD_DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

# Expose web dashboard port
EXPOSE 8080

# Run as bluehood user
USER bluehood

# Start the daemon
CMD ["python", "-m", "bluehood.daemon"]
