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
    jackd2 \
    libjack-jackd2-0 \
    && rm -rf /var/lib/apt/lists/*

# Configure jackd to run without realtime privileges
RUN echo "JACK_NO_AUDIO_RESERVATION=1" >> /etc/environment \
    && echo "JACK_NO_START_SERVER=1" >> /etc/environment

# Set up ALSA and JACK configuration
COPY alsa-config.conf /usr/share/alsa/alsa.conf
ENV AUDIODEV=null
ENV JACK_NO_AUDIO_RESERVATION=1
ENV JACK_NO_START_SERVER=1
ENV ESPEAK_DATA_PATH=/usr/lib/x86_64-linux-gnu/espeak-ng-data

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
