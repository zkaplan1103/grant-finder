# Multi-stage: build the React SPA, then run FastAPI serving it + the API.

FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # emits frontend/dist

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY eval/ ./eval/
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Railway injects $PORT. Bind to it; default 8000 for local `docker run`.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.web.app:app --host 0.0.0.0 --port ${PORT}"]
