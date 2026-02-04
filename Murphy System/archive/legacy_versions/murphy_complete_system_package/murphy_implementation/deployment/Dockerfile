# Murphy System - Production Dockerfile

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY murphy_implementation/ ./murphy_implementation/

# Create necessary directories
RUN mkdir -p /app/data/checkpoints \
    /app/data/model_registry \
    /app/data/corrections \
    /app/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV MURPHY_ENV=production
ENV MURPHY_DATA_DIR=/app/data
ENV MURPHY_LOG_DIR=/app/logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "-m", "murphy_implementation.main"]