# VERIDEX AI Backend Container Configuration
# Optimized for Python 3.12 and Render.com deployment
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code and scripts
COPY . /app

# Expose service port
EXPOSE 8000

# Deep container readiness check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/ready || exit 1

# Execute Uvicorn with dynamic $PORT expansion for Render compatibility
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
