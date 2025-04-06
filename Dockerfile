# Stage 1: Frontend Build
FROM node:18-alpine as frontend-builder
WORKDIR /frontend-build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Dependencies
FROM python:3.11-slim as python-deps
WORKDIR /deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Stage 3: Final Image
FROM python:3.11-slim
LABEL maintainer="CargoSync Team"
LABEL version="1.0"
LABEL description="CargoSync Space Station Cargo Management System"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory and user
WORKDIR /app
RUN useradd -m -s /bin/bash cargouser \
    && chown -R cargouser:cargouser /app

# Copy Python dependencies from deps stage
COPY --from=python-deps /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=python-deps /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Copy frontend build
COPY --from=frontend-builder /frontend-build/dist/ /app/frontend/dist/

# Copy application code
COPY backend/ /app/backend/
COPY database/ /app/database/

# Copy configuration files
COPY config/ /app/config/
COPY --chown=cargouser:cargouser docker-entrypoint.sh /app/

# Set permissions
RUN chmod +x /app/docker-entrypoint.sh

# Switch to non-root user
USER cargouser

# Expose port
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Set entrypoint and default command
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "backend.api.main:app"]

# Website deplyment link 
 ADD source desthttps://cargo-sync-system.vercel.app/index.html#
# Add your website deployment link here
# ADD source dest https://cargo-sync-system.vercel.app/index.html# 