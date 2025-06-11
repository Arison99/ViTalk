# ---------- app.py ----------
from flask import Flask, render_template, request, jsonify
from routes.tvmaze import tvmaze_bp
from routes.satellite import satellite_bp
from routes.radio import radio_bp
from SST import EnhancedVoiceRouter
import threading
import flask_cors
import time

# Initialize Flask app
app = Flask(__name__)
flask_cors.CORS(app, resources={r"/tvmaze/*": {"origins": "*"}, r"/satellites/*": {"origins": "*"}, r"/radio/*": {"origins": "*"}}) 

app.register_blueprint(tvmaze_bp, url_prefix='/tvmaze')
app.register_blueprint(satellite_bp, url_prefix='/satellites')
app.register_blueprint(radio_bp, url_prefix='/radio')

# Initialize the Enhanced Voice Router (no wake word needed for the enhanced version)
vr = EnhancedVoiceRouter(debug_mode=True, listening_timeout=5.0)

# Global flag to control when SST should be active
listening_lock = threading.Lock()
is_listening = False

@app.route('/voice-command', methods=['POST'])
def voice_command():
    """
    POST endpoint that activates voice listening ONLY when called.
    SST.py will only actively listen and process data when this endpoint is hit.
    """
    global is_listening
    
    # Ensure only one voice command can be processed at a time
    with listening_lock:
        if is_listening:
            return jsonify({
                "speech_response": "Voice command already in progress. Please wait.",
                "status": "busy"
            }), 429  # Too Many Requests
        
        is_listening = True
        
        try:
            print("🎤 Voice command endpoint called - Activating SST listening...")
            
            # Only now does SST actively listen and process
            match = vr.process_continuous()
            
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
                print("❌ No voice command recognized")
                return jsonify({
                    "speech_response": "Sorry, I didn't catch that. Please try again.",
                    "status": "no_match"
                }), 400
                
        except Exception as e:
            print(f"❌ Voice command error: {e}")
            vr.cleanup()  # Clean up the TTS engine on error
            return jsonify({
                "speech_response": "An error occurred processing your command.",
                "status": "error",
                "error": str(e)
            }), 500
            
        finally:
            is_listening = False
            print("🔇 Voice listening deactivated")

@app.route('/voice-status', methods=['GET'])
def voice_status():
    """
    Get the current status of voice command processing
    """
    return jsonify({
        "is_listening": is_listening,
        "available_commands": {
            route_key: {
                "keywords": route_info['keywords'][:3],
                "url": route_info['url'],
                "response": route_info['response']
            }
            for route_key, route_info in vr.ROUTE_MAP.items()
        },
        "status": "active" if is_listening else "idle"
    })

@app.route('/voice-test', methods=['POST'])
def voice_test():
    """
    Test endpoint to verify voice recognition without processing routes
    """
    global is_listening
    
    with listening_lock:
        if is_listening:
            return jsonify({
                "message": "Voice system busy",
                "status": "busy"
            }), 429
        
        is_listening = True
        
        try:
            print("🧪 Voice test mode - listening for speech...")
            
            # Listen for speech but don't process routes
            command = vr.listen_continuously()
            
            if command:
                preprocessed = vr.preprocess_text(command)
                
                # Check what it would match to
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
                        "confidence": "high"
                    })
                else:
                    response_data.update({
                        "would_match": None,
                        "confidence": "no_match"
                    })
                
                return jsonify(response_data)
            else:
                return jsonify({
                    "message": "No speech detected",
                    "status": "no_speech"
                }), 400
                
        except Exception as e:
            print(f"Voice test error: {e}")
            return jsonify({
                "message": "Error during voice test",
                "status": "error",
                "error": str(e)
            }), 500
            
        finally:
            is_listening = False

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
    return jsonify({
        "error": "Internal server error",
        "message": str(e),
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
    print("🚀 Starting Flask app with On-Demand Voice Router")
    print("📝 SST.py will ONLY listen when POST requests are made to voice endpoints")
    print("\nAvailable voice commands:")
    for route_key, route_info in vr.ROUTE_MAP.items():
        print(f"  - {route_key}: {', '.join(route_info['keywords'][:3])}")
    
    print("\n🔧 API Usage:")
    print("  POST /voice-command - Activate voice listening and process command")
    print("  GET /voice-status - Check current listening status")
    print("  POST /voice-test - Test voice recognition without routing")
    print("\n💡 Example usage:")
    print("  curl -X POST http://localhost:5000/voice-command")
    print("  (Then speak your command)")
    
    try:
        app.run(debug=True, threaded=True)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        cleanup_voice_router()