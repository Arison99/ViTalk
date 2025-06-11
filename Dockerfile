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
    && rm -rf /var/lib/apt/lists/*

# Set up ALSA loopback device
RUN mkdir -p /usr/share/alsa/ && \
    echo 'pcm.!default { type null }' > /usr/share/alsa/alsa.conf && \
    echo 'ctl.!default { type null }' >> /usr/share/alsa/alsa.conf

# Set environment variables for audio
ENV PYTHONUNBUFFERED=1
ENV AUDIODEV=null

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port your Flask app runs on
EXPOSE 5000

# Make start script executable
RUN chmod +x start.py

# Install gunicorn
RUN pip install gunicorn

# Command to run the application with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "start:app"]
