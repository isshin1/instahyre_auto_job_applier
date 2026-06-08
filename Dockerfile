# Use the official Playwright *Python* image (includes Python + OS deps for browsers)
FROM   mcr.microsoft.com/playwright/python:v1.55.0-noble

WORKDIR /app

# Ensure logs are flushed immediately (useful for `docker logs`)
ENV PYTHONUNBUFFERED=1

# Install Python dependencies using uv
# We copy only dependency manifests first for better layer caching.
COPY pyproject.toml uv.lock /app/

# Install uv (and sync deps from uv.lock)
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir uv && \
    uv sync --frozen --no-install-project

# Ensure browser binaries are installed for the installed Playwright version
# Use python -m playwright to call the module directly (works even if 'playwright' CLI isn't on PATH)
RUN .venv/bin/python -m playwright install chromium

# Copy the bot script
COPY instahyre_playwright_bot.py /app/instahyre_playwright_bot.py

# Non-root user can be used if desired; the official Playwright image uses root by default.
# Expose nothing by default. Run with --env-file to pass credentials.
CMD [".venv/bin/python", "-u", "instahyre_playwright_bot.py"]
