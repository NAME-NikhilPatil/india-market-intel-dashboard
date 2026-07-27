FROM python:3.12-slim

ARG APP_IMAGE_VERSION=unknown

ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    SCRAPER_SEED_DIR=/app \
    SCRAPER_WORKSPACE_DIR=/home/site/dashboard-workspace \
    SCRAPER_RUNTIME_DIR=/home/site/scraper-runtime \
    CHROME_BIN=/usr/bin/chromium \
    WEB_CONCURRENCY=1 \
    GUNICORN_THREADS=4 \
    GUNICORN_TIMEOUT=900 \
    ENABLE_SCRAPER_SCHEDULER=true \
    SOLAR_DAILY_UTC=02:30 \
    VAHAN_DAILY_UTC=03:30 \
    APP_IMAGE_VERSION=${APP_IMAGE_VERSION}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      chromium \
      chromium-driver \
      xvfb \
      xauth \
      ca-certificates \
      fonts-liberation \
      libnss3 \
      libx11-6 \
      libxcomposite1 \
      libxdamage1 \
      libxrandr2 \
      libgbm1 \
      libasound2 \
      libatk-bridge2.0-0 \
      libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/startup.sh

EXPOSE 80 8000

CMD ["/app/startup.sh"]
