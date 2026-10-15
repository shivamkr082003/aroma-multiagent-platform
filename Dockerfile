# Aroma AI — one container: FastAPI backend + the Next.js frontend as static files.
# Built for Hugging Face Spaces (Docker SDK), works on any Docker host.

# ---- 1. Frontend → static files (frontend/out) ----
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Empty API URL = same origin: the backend below serves these files itself.
ENV NEXT_OUTPUT=export NEXT_PUBLIC_API_URL=""
RUN npm run build

# ---- 2. Backend ----
FROM python:3.12-slim

# ffmpeg converts browser voice recordings.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch: the default wheel bundles CUDA (several GB) that a CPU host can't use.
COPY requirements.txt /tmp/requirements.txt
# Generous timeout/retries: one slow download shouldn't fail a 10-minute build.
RUN pip install --no-cache-dir --timeout 120 --retries 8 -r /tmp/requirements.txt \
        --extra-index-url https://download.pytorch.org/whl/cpu \
    && python -m playwright install-deps chromium

# Hugging Face Spaces runs containers as user 1000.
RUN useradd -m -u 1000 user && mkdir -p /home/user/app && chown user:user /home/user/app
USER user
ENV HOME=/home/user \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface \
    PLAYWRIGHT_BROWSERS_PATH=/home/user/.cache/ms-playwright \
    AUTH_COOKIE_SECURE=true
WORKDIR /home/user/app

# Bake the browser (JS-heavy page scraping) and both models into the image,
# so the first request doesn't wait for ~250 MB of downloads.
RUN python -m playwright install chromium \
    && python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('BAAI/bge-small-en-v1.5'); CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

COPY --chown=user . .
COPY --chown=user --from=frontend /frontend/out ./frontend/out

EXPOSE 7860
# Migrations are safe to repeat (see scripts/migrate.py), so they run on every start.
CMD ["sh", "-c", "python scripts/migrate.py && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
