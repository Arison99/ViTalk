#!/usr/bin/env python3
import os
import sys
from app import app

if __name__ == "__main__":
    # Configure environment for audio
    os.environ['AUDIODEV'] = 'null'
    os.environ['ALSA_CONFIG_PATH'] = '/usr/share/alsa/alsa.conf'
      # Start the Flask app
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
