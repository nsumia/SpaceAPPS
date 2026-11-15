# Metalimnion: one image, one port (8000). Stage 1 builds the React frontend, stage 2 serves it with the API.
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8000
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY backend ./backend
COPY data ./data
COPY --from=web /app/frontend/dist ./frontend/dist
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import os, urllib.request as u; u.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8000'), timeout=4)"
# Render injects $PORT; locally it defaults to 8000. Shell form so the variable is expanded; exec keeps uvicorn as PID 1.
CMD exec uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
