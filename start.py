#!/usr/bin/env python3
import os
import sys
from app import app

if __name__ == "__main__":
    # Configure environment for audio
    os.environ['AUDIODEV'] = 'null'
    os.environ['ALSA_CONFIG_PATH'] = '/usr/share/alsa/alsa.conf'
    
    # Get port from environment variable with explicit fallback
    try:
        port = int(os.environ.get("PORT", 5000))
    except ValueError:
        port = 5000
        print(f"Invalid PORT value, using default port {port}")
    
    # Start the application
    if 'gunicorn' in sys.modules:
        # Running under Gunicorn - let Gunicorn handle the server
        pass
    else:
        # Running directly - use Flask's development server
        app.run(host='0.0.0.0', port=port, debug=False)
