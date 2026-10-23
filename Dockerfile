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
    PATH=/home/user/.local/bin:$PATH

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

# Install dependencies using CPU-only PyTorch (reduces image size from 3GB to ~500MB)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      "torch>=2.5.0" "torchvision>=0.20.0" && \
    pip install --no-cache-dir .

# Copy backend source code and runtime assets
COPY src/ /app/src/
COPY assets/ /app/assets/

# Copy compiled Vue 3 production bundle into frontend/dist
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Ensure the non-root user has write access to SQLite database and uploads directory
RUN chown -R user:user /app && \
    chmod -R 775 /app/assets

USER user

# Hugging Face Spaces exposes port 7860
EXPOSE 7860

CMD ["uvicorn", "aquapulse.api.main:app", "--host", "0.0.0.0", "--port", "7860"]
