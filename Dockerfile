FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    SCRAPER_SEED_DIR=/app \
    SCRAPER_WORKSPACE_DIR=/home/site/dashboard-workspace \
    SCRAPER_RUNTIME_DIR=/home/site/scraper-runtime \
    CHROME_BIN=/usr/bin/chromium

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      chromium \
      chromium-driver \
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

EXPOSE 8000

CMD ["/app/startup.sh"]
