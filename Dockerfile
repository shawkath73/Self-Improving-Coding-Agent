FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml README.md ./
COPY src ./src
COPY --from=frontend /frontend/dist ./frontend/dist
RUN pip install --no-cache-dir ".[postgres,gemini,anthropic]"
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "uvicorn verified_agent.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
