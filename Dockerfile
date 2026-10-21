# One service: builds the frontend, then runs the API which also serves it.
# Same origin = the session cookie works (separate *.onrender.com services would break sign-in).

# ── 1. Build the frontend ─────────────────────
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── 2. Run the API ────────────────────────────
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist ./frontend-dist
ENV FRONTEND_DIST=/app/frontend-dist

# Apply migrations, then start. Render provides $PORT; --proxy-headers trusts its HTTPS proxy.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
