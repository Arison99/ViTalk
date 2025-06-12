# ---------- app.py ----------
from flask import Flask, render_template, request, jsonify
from routes.tvmaze import tvmaze_bp
from routes.satellite import satellite_bp
from routes.radio import radio_bp
from SST import EnhancedVoiceRouter
import speech_recognition as sr
import threading
import flask_cors
import time
import os
import tempfile
from pydub import AudioSegment # Import pydub

# Initialize Flask app
app = Flask(__name__)
flask_cors.CORS(app, resources={r"/tvmaze/*": {"origins": "*"}, r"/satellites/*": {"origins": "*"}, r"/radio/*": {"origins": "*"}})

app.register_blueprint(tvmaze_bp, url_prefix='/tvmaze')
app.register_blueprint(satellite_bp, url_prefix='/satellites')
app.register_blueprint(radio_bp, url_prefix='/radio')

# Initialize the Enhanced Voice Router
vr = EnhancedVoiceRouter(debug_mode=False)

# Global flag
listening_lock = threading.Lock()
is_processing_voice = False

@app.route('/voice-command', methods=['POST'])
def voice_command():
    global is_processing_voice
    
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file part in the request", "status": "error"}), 400
    
    audio_file = request.files['audio']
    
    if audio_file.filename == '':
        return jsonify({"error": "No selected audio file", "status": "error"}), 400

    with listening_lock:
        if is_processing_voice:
            return jsonify({
                "speech_response": "Voice command already in progress. Please wait.",
                "status": "busy"
            }), 429
        is_processing_voice = True
        
    temp_webm_file_path = None
    temp_wav_file_path = None
            
    try:
        print("🎤 Voice command endpoint called - Processing uploaded audio...")
        
        # 1. Save uploaded WebM file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_webm_file:
            audio_file.save(temp_webm_file)
            temp_webm_file_path = temp_webm_file.name
        
        # 2. Convert WebM to WAV using pydub
        sound = AudioSegment.from_file(temp_webm_file_path, format="webm")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav_file:
            sound.export(temp_wav_file.name, format="wav")
            temp_wav_file_path = temp_wav_file.name

        # 3. Process the WAV file with speech_recognition
        audio_data = None
        with sr.AudioFile(temp_wav_file_path) as source:
            audio_data = vr.recognizer.record(source)

        if not audio_data:
            return jsonify({
                "speech_response": "Could not process audio file after conversion.",
                "status": "audio_error"
            }), 400

        match = vr.process(audio_data)
            
        if match:
            print(f"✅ Voice command processed: {match['route_key']}")
            return jsonify({
                "speech_response": match["response"],
                "redirect_url": match["url"],
                "route_key": match["route_key"],
                "original_command": match["original_command"],
                "status": "success"
            })
        else:
            print("❌ No voice command recognized from uploaded audio")
            return jsonify({
                "speech_response": "Sorry, I didn't catch that from the audio. Please try again.",
                "status": "no_match"
            }), 400
                
    except sr.UnknownValueError:
        print("❌ Speech recognition could not understand audio")
        return jsonify({
            "speech_response": "Sorry, I couldn't understand the audio.",
            "status": "recognition_error"
        }), 400
    except sr.RequestError as e:
        print(f"❌ Speech recognition service error: {e}")
        return jsonify({
            "speech_response": "Sorry, there was an issue with the speech recognition service.",
            "status": "recognition_service_error",
            "error": str(e)
        }), 500
    except Exception as e:
        print(f"❌ Voice command error: {e}")
        return jsonify({
            "speech_response": "An error occurred processing your command.",
            "status": "error",
            "error": str(e)
        }), 500
            
    finally:
        if temp_webm_file_path and os.path.exists(temp_webm_file_path):
            os.remove(temp_webm_file_path)
        if temp_wav_file_path and os.path.exists(temp_wav_file_path):
            os.remove(temp_wav_file_path)
        with listening_lock:
            is_processing_voice = False
        print("🔇 Voice processing finished for this request.")

@app.route('/voice-status', methods=['GET'])
def voice_status():
    """
    Get the current status of voice command processing
    """
    return jsonify({
        "is_processing_voice": is_processing_voice,
        "available_commands": {
            route_key: {
                "keywords": route_info['keywords'][:3],
                "url": route_info['url'],
                "response": route_info['response']
            }
            for route_key, route_info in vr.ROUTE_MAP.items()
        },
        "status": "processing" if is_processing_voice else "idle"
    })


@app.route('/voice-test', methods=['POST'])
def voice_test():
    global is_processing_voice
    
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file part in the request", "status": "error"}), 400
    
    audio_file = request.files['audio']
    
    if audio_file.filename == '':
        return jsonify({"error": "No selected audio file", "status": "error"}), 400

    with listening_lock:
        if is_processing_voice:
            return jsonify({
                "message": "Voice system busy",
                "status": "busy"
            }), 429
        is_processing_voice = True

    temp_webm_file_path = None
    temp_wav_file_path = None

    try:
        print("🧪 Voice test mode - processing uploaded audio...")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_webm_file:
            audio_file.save(temp_webm_file)
            temp_webm_file_path = temp_webm_file.name
        
        sound = AudioSegment.from_file(temp_webm_file_path, format="webm")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav_file:
            sound.export(temp_wav_file.name, format="wav")
            temp_wav_file_path = temp_wav_file.name

        audio_data = None
        with sr.AudioFile(temp_wav_file_path) as source:
            audio_data = vr.recognizer.record(source)

        if not audio_data:
            return jsonify({
                "message": "Could not process audio file for testing after conversion.",
                "status": "audio_error"
            }), 400
            
        command = vr.recognize_audio_data(audio_data)
            
        if command:
            preprocessed = vr.preprocess_text(command)
            match_result = vr.match_route(command)
                
            response_data = {
                "original_speech": command,
                "preprocessed_speech": preprocessed,
                "status": "speech_detected"
            }
                
            if match_result:
                route_key, route_info = match_result
                response_data.update({
                    "would_match": route_key,
                    "would_route_to": route_info['url'],
                })
            else:
                response_data.update({"would_match": None})
                
            return jsonify(response_data)
        else:
            return jsonify({
                "message": "No speech detected in the uploaded audio",
                "status": "no_speech"
            }), 400
                
    except sr.UnknownValueError:
        print("❌ Speech recognition could not understand audio during test")
        return jsonify({
            "message": "Sorry, I couldn't understand the audio.",
            "status": "recognition_error"
        }), 400
    except sr.RequestError as e:
        print(f"❌ Speech recognition service error during test: {e}")
        return jsonify({
            "message": "Sorry, there was an issue with the speech recognition service.",
            "status": "recognition_service_error",
            "error": str(e)
        }), 500
    except Exception as e:
        print(f"Voice test error: {e}")
        return jsonify({
            "message": "Error during voice test",
            "status": "error",
            "error": str(e)
        }), 500
            
    finally:
        if temp_webm_file_path and os.path.exists(temp_webm_file_path):
            os.remove(temp_webm_file_path)
        if temp_wav_file_path and os.path.exists(temp_wav_file_path):
            os.remove(temp_wav_file_path)
        with listening_lock:
            is_processing_voice = False
        print("🔇 Voice test processing finished.")

@app.route('/')
def index():
    """
    Main index route serving home page
    """
    return render_template('home.html')

# Error handler for busy voice system
@app.errorhandler(429)
def handle_too_many_requests(e):
    return jsonify({
        "error": "Voice system busy",
        "message": "Another voice command is being processed. Please wait and try again.",
        "status": "busy"
    }), 429

# General error handler
@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Unhandled exception: {e}")
    # Ensure the error response is JSON
    error_message = str(e)
    if isinstance(e, (sr.UnknownValueError, sr.RequestError)): # More specific handling if needed
        error_message = "A speech recognition error occurred."

    return jsonify({
        "error": "Internal server error",
        "message": error_message, # Send the actual error message
        "status": "error"
    }), 500

# Cleanup function
def cleanup_voice_router():
    """Clean up voice router resources"""
    try:
        vr.cleanup()
        print("🧹 Voice router cleaned up")
    except Exception as e:
        print(f"Cleanup error: {e}")

# Register cleanup function
import atexit
atexit.register(cleanup_voice_router)

if __name__ == '__main__':
    print("🚀 Starting Flask app with On-Demand Voice Router (Audio File Upload)")
    print("📝 SST.py will process uploaded audio files when POST requests are made to voice endpoints")
    print("\nAvailable voice commands (based on recognized speech from audio):")
    for route_key, route_info in vr.ROUTE_MAP.items():
        print(f"  - {route_key}: {', '.join(route_info['keywords'][:3])}")
    
    print("\n🔧 API Usage:")
    print("  POST /voice-command (with 'audio' file part) - Process uploaded audio and route")
    print("  GET /voice-status - Check current processing status")
    print("  POST /voice-test (with 'audio' file part) - Test voice recognition from uploaded audio")
    print("\n💡 Example usage (using curl to upload an audio.webm or audio.wav file):")
    print("  curl -X POST -F \"audio=@path/to/your/audio.webm\" http://localhost:5000/voice-command")
    try:
        app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        cleanup_voice_router()