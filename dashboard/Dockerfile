# Build the React dashboard, then serve it (and the API) from the FastAPI
# backend as a single container. Build context is the dashboard/ directory.

# --- stage 1: build the frontend ---
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- stage 2: backend + built frontend ---
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
# app.py serves ../frontend/dist relative to backend/, i.e. /app/frontend/dist
COPY --from=frontend /app/frontend/dist ./frontend/dist

ENV DASHBOARD_FEED=demo
EXPOSE 8000
CMD ["uvicorn", "app:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
