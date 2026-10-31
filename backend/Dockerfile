# ==============================================================================
# AI Facial Asymmetry Analysis Platform — Backend Dockerfile
# ==============================================================================
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for OpenCV and MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt requirements-ai.txt ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-ai.txt || true

# Copy backend source code and AI models
COPY . .

# Ensure storage and models directories exist
RUN mkdir -p storage models/mediapipe

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
