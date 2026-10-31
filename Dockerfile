# One image: the React app is built, then served by Django (WhiteNoise) next to the API.

FROM node:24-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=false \
    FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
# Pre-compressed .gz siblings let WhiteNoise serve the SPA bundles gzipped.
RUN python -m whitenoise.compress /app/frontend/dist && \
    DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput

EXPOSE 8000
# One worker with threads: the in-process cache (routes, weather) is then shared by every request,
# which matters for staying inside the free weather API quota. Requests are I/O-bound (provider calls).
CMD python manage.py migrate --noinput && \
    gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 8 --timeout 120
