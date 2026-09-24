# ---- UI build
FROM node:22-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN npx vite build

# ---- API + agent
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY pyproject.toml ./
COPY verdict ./verdict
COPY graph ./graph
RUN pip install --no-cache-dir -e . tabulate
COPY --from=ui /ui/dist ./ui/dist
EXPOSE 8000
CMD ["verdict", "serve", "--port", "8000"]
