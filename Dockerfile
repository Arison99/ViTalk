FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    gcc \
    libasound2-dev \
    python3-dev \
    libportaudio2 \
    libportaudiocpp0 \
    ffmpeg \
    alsa-utils \
    espeak \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# Configure audio
RUN mkdir -p /usr/share/alsa/ && \
    echo 'pcm.!default { type null }' > /usr/share/alsa/alsa.conf && \
    echo 'ctl.!default { type null }' >> /usr/share/alsa/alsa.conf

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV AUDIODEV=null
ENV ESPEAK_DATA_PATH=/usr/lib/x86_64-linux-gnu/espeak-ng-data

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy the application
COPY . .

# Make start script executable
RUN chmod +x start.py

# Default command (will be overridden by Railway)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "app:app"]
