#!/usr/bin/env python3
import os
import sys
import subprocess

if __name__ == "__main__":
    # Get port from environment variable, default to 5000
    # Gunicorn's --bind expects the port as a string.
    port = os.environ.get("PORT", "5000")
    
    # Basic validation for the port number
    try:
        if not (0 < int(port) < 65536):
            raise ValueError("Port out of valid range")
    except ValueError:
        print(f"Warning: Invalid PORT environment variable '{port}'. Using default port 5000.")
        port = "5000"

    # Define Gunicorn command
    # app:app refers to the 'app' instance in your 'app.py' file
    gunicorn_command = [
        "gunicorn",
        "--bind", f"0.0.0.0:{port}",
        "--workers", os.environ.get("WEB_CONCURRENCY", "2"), # Use WEB_CONCURRENCY or default
        "--threads", "4", # Or make configurable via ENV
        "app:app"
    ]

    print(f"🚀 Launching Gunicorn with command: {' '.join(gunicorn_command)}")
    
    # Execute Gunicorn, replacing the current Python process
    # This is good practice for containerized applications
    try:
        os.execvp(gunicorn_command[0], gunicorn_command)
    except FileNotFoundError:
        print("Error: 'gunicorn' command not found. Make sure Gunicorn is installed and in your PATH.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred while trying to start Gunicorn: {e}")
        sys.exit(1)

    # The following lines will not be reached if os.execvp is successful
    print("Error: os.execvp failed to start Gunicorn.")
    sys.exit(1)
