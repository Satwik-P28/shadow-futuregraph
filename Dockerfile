FROM node:22-alpine AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY pyproject.toml README.md LICENSE ./
COPY backend ./backend
COPY fixtures ./fixtures
COPY openshell ./openshell
COPY shadowbench ./shadowbench
RUN pip install --no-cache-dir .
COPY --from=frontend /src/frontend/dist ./frontend/dist
ENV PORT=8000
ENV SHADOW_ROOT=/app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn shadow.api.app:app --host 0.0.0.0 --port ${PORT}"]
