# Dockerfile — Lucky Puppy Bot (Python worker)

# Use official slim Python image
FROM python:3.11-slim

# Faster logs, no pip cache
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Set working directory
WORKDIR /app

# Install CA certs, Rust compiler, and build tools (needed for some Python wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    curl \
    gcc \
    rustc \
 && rm -rf /var/lib/apt/lists/*

# Force rebuild for clean requirements.txt ☁️
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy all project files into the container
COPY . .

# Create writable logs folder in case we use persistent volume
RUN mkdir -p /data/logs

# Run the bot (via polling)
CMD ["python", "-u", "bot.py"]
