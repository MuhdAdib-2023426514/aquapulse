# ==============================================================================
# Stage 1: Build the Vue 3 Frontend Single-Page App
# ==============================================================================
FROM node:20-slim AS frontend-builder
WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: AquaPulse FastAPI Runtime (CPU PyTorch + OpenCV Headless)
# ==============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    AQUAPULSE_PROJECT_ROOT=/app \
    AQUAPULSE_ASSETS_DIR=/app/assets \
    AQUAPULSE_FRONTEND_DIST=/app/frontend/dist

# Install essential system packages for OpenCV, FFmpeg video processing, and audio
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces runs as user 1000
RUN useradd -m -u 1000 user
WORKDIR /app

# Install CPU-only PyTorch first (efficient layer caching)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      "torch>=2.5.0" "torchvision>=0.20.0"

# Copy package config, documentation, backend code, and assets
COPY pyproject.toml README.md ./
COPY src/ /app/src/
COPY assets/ /app/assets/

# Install AquaPulse package
RUN pip install --no-cache-dir .

# Copy compiled Vue 3 production bundle into frontend/dist
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Ensure the non-root user has write access to SQLite database and uploads directory
RUN chown -R user:user /app && \
    chmod -R 775 /app/assets

USER user

# Hugging Face Spaces uses 7860; Google Cloud Run uses 8080; default to 7860
EXPOSE 7860 8080

CMD ["sh", "-c", "uvicorn aquapulse.api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
