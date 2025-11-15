# Use the official Playwright *Python* image (includes Python + OS deps for browsers)
FROM   mcr.microsoft.com/playwright/python:v1.55.0-noble

WORKDIR /app

# Copy requirements and install Python dependencies
# (The base image already has 'playwright' package, but pinning in requirements.txt is OK)
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir -r /app/requirements.txt

# Ensure browser binaries are installed for the installed Playwright version
# Use python -m playwright to call the module directly (works even if 'playwright' CLI isn't on PATH)
RUN python -m playwright install chromium

# Copy the bot script
COPY instahyre_playwright_bot.py /app/instahyre_playwright_bot.py

# Non-root user can be used if desired; the official Playwright image uses root by default.
# Expose nothing by default. Run with --env-file to pass credentials.
CMD ["python", "instahyre_playwright_bot.py"]
