FROM node:20-bookworm-slim AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY backend/data/seed.db backend/data/seed.db
# SPA build: app.main DIST = /app/frontend/dist (parents[2] dari backend/app/main.py)
COPY --from=web /src/frontend/dist frontend/dist
RUN mkdir -p backend/data && chmod 777 backend/data && test -f backend/data/seed.db
WORKDIR /app/backend
ENV PORT=8000
ENV TZ=Asia/Jakarta
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
