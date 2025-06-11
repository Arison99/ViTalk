def run_continuous_loop(self, feedback_enabled: bool = False):
        """
        Main continuous listening loop
        """
        print("🎤 Continuous Voice Router Active!")
        print("Available commands:")
        for route_key, route_info in self.ROUTE_MAP.items():
            print(f"  - {route_key}: {', '.join(route_info['keywords'][:3])}")
        print("\nListening continuously... (Press Ctrl+C to stop)")
        
        try:
            while True:
                result = self.process_continuous()
                
                if result:
                    print(f"✅ SUCCESS! Routing to: {result['url']}")
                    print(f"   Command: '{result['original_command']}'")
                    print(f"   Route: {result['route_key']}")
                    
                    # Optional: Add a brief pause after successful routing
                    time.sleep(1)
                else:
                    # Continue listening without verbose feedback unless enabled
                    if feedback_enabled:
                        print("⚪ Continuing to listen...")
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping continuous listening...")
        except Exception as e:
            print(f"❌ Error in continuous loop: {e}")
        finally:
            self.cleanup()# Enhanced SST.py

import speech_recognition as sr
import pyttsx3
from typing import Optional, Dict, List, Tuple
import re
from difflib import SequenceMatcher
import threading
import time

class EnhancedVoiceRouter:
    # Enhanced route mapping with multiple keywords and synonyms
    ROUTE_MAP = {
        "tv_shows": {
            "keywords": ["search show", "tv shows", "television", "show search", "find show", "tv series"],
            "url": "/tvmaze/",
            "response": "Opening TV show search.",
            "confidence_threshold": 0.6
        },
        "episode_details": {
            "keywords": ["episode details", "episode info", "show details", "episode data", "show episodes"],
            "url": "/tvmaze/show/<show_id>",
            "response": "Here are the episode details.",
            "confidence_threshold": 0.6
        },
        "radio": {
            "keywords": ["radio", "radio station", "music", "audio", "listen radio", "tune radio"],
            "url": "/radio/",
            "response": "Tuning into radio section.",
            "confidence_threshold": 0.7
        },
        "satellite": {
            "keywords": ["satellite", "satellites", "satellite data", "space data", "orbital data"],
            "url": "/satellites/",
            "response": "Displaying satellite data.",
            "confidence_threshold": 0.7
        }
    }

    def __init__(self, debug_mode: bool = True, listening_timeout: float = 3.0):
        self.debug_mode = debug_mode
        self.listening_timeout = listening_timeout
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Enhanced recognizer settings
        self.recognizer.energy_threshold = 4000  # Adjust based on your environment
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        self.recognizer.phrase_threshold = 0.3
        
        self._init_engine()
        self._calibrate_microphone()

    def _init_engine(self):
        """Initialize the TTS engine with better error handling"""
        try:
            self.engine = pyttsx3.init()
            
            # Configure voice settings
            voices = self.engine.getProperty('voices')
            if voices and len(voices) > 1:
                # Prefer female voice if available
                self.engine.setProperty('voice', voices[1].id)
            
            # Adjust speech rate and volume
            self.engine.setProperty('rate', 180)  # Slightly slower for clarity
            self.engine.setProperty('volume', 0.9)
            
        except Exception as e:
            print(f"TTS engine initialization error: {e}")
            self.engine = None

    def _calibrate_microphone(self):
        """Calibrate microphone for ambient noise"""
        try:
            with self.microphone as source:
                print("Calibrating microphone for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
                print("Microphone calibrated.")
        except Exception as e:
            print(f"Microphone calibration error: {e}")

    def talk(self, text: str) -> None:
        """Enhanced TTS with threading to prevent blocking"""
        def speak():
            if not self.engine:
                self._init_engine()
            if self.engine:
                try:
                    self.engine.say(text)
                    self.engine.runAndWait()
                except Exception as e:
                    if self.debug_mode:
                        print(f"TTS error: {e}")
                    # Try to reinitialize
                    try:
                        self.engine.stop()
                        self._init_engine()
                        if self.engine:
                            self.engine.say(text)
                            self.engine.runAndWait()
                    except:
                        pass
        
        # Run TTS in separate thread to avoid blocking
        thread = threading.Thread(target=speak)
        thread.daemon = True
        thread.start()

    def preprocess_text(self, text: str) -> str:
        """Clean and normalize text for better matching"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove common speech recognition artifacts
        text = re.sub(r'\b(um|uh|ah|er)\b', '', text)
        
        # Handle common misrecognitions
        replacements = {
            'tv': 'television',
            'tee vee': 'television',
            'teevee': 'television',
            'show me': 'show',
            'find me': 'find',
            'get me': 'get',
            'open up': 'open',
            'pull up': 'show'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text

    def fuzzy_match_score(self, text: str, keyword: str) -> float:
        """Calculate fuzzy matching score between text and keyword"""
        # Direct substring match gets highest score
        if keyword in text:
            return 1.0
        
        # Check word-by-word matching
        text_words = text.split()
        keyword_words = keyword.split()
        
        # If all keyword words are found in text
        if all(any(kw in tw or SequenceMatcher(None, kw, tw).ratio() > 0.8 
                  for tw in text_words) for kw in keyword_words):
            return 0.9
        
        # Fuzzy string matching
        similarity = SequenceMatcher(None, text, keyword).ratio()
        
        # Bonus for partial word matches
        word_matches = sum(1 for kw in keyword_words 
                          if any(kw in tw for tw in text_words))
        word_bonus = word_matches / len(keyword_words) * 0.3
        
        return min(similarity + word_bonus, 1.0)

    def listen_continuously(self) -> str:
        """Continuously listen for speech input without timeout"""
        attempts = 0
        max_attempts = 3
        
        while attempts < max_attempts:
            try:
                with self.microphone as source:
                    if self.debug_mode and attempts == 0:
                        print("Listening continuously for voice commands...")
                    elif self.debug_mode:
                        print(f"Retrying... (Attempt {attempts + 1}/{max_attempts})")
                    
                    # Listen continuously - no timeout, but with phrase limit
                    audio = self.recognizer.listen(
                        source, 
                        phrase_time_limit=self.listening_timeout
                    )
                
                # Try Google Speech Recognition first
                try:
                    command = self.recognizer.recognize_google(audio, language='en-US')
                    if self.debug_mode:
                        print(f"Google STT heard: '{command}'")
                    return command.lower()
                except sr.UnknownValueError:
                    if self.debug_mode:
                        print("Google STT could not understand audio")
                
                # Fallback to Sphinx (offline) if available
                try:
                    command = self.recognizer.recognize_sphinx(audio)
                    if self.debug_mode:
                        print(f"Sphinx STT heard: '{command}'")
                    return command.lower()
                except (sr.UnknownValueError, sr.RequestError):
                    if self.debug_mode:
                        print("Sphinx STT also failed")
                
            except Exception as e:
                if self.debug_mode:
                    print(f"Listening error: {e}")
                attempts += 1
                if attempts < max_attempts:
                    time.sleep(0.5)  # Brief pause before retry
        
        return ""

    def process_continuous(self) -> Optional[Dict[str, str]]:
        """
        Continuous processing pipeline - always listening for commands
        """
        # Listen for any command
        command = self.listen_continuously()
        
        if not command:
            if self.debug_mode:
                print("No speech detected, continuing to listen...")
            return None
        
        if self.debug_mode:
            print(f"Command received: '{command}'")
        
        # Preprocess and match route directly
        match_result = self.match_route(command)
        
        if match_result:
            route_key, route_info = match_result
            # Speak confirmation
            self.talk(route_info["response"])
            return {
                "url": route_info["url"],
                "response": route_info["response"],
                "route_key": route_key,
                "original_command": command
            }
        
        # No match found - provide gentle feedback
        if self.debug_mode:
            print(f"No route match for: '{command}'")
        
        return None

    def match_route(self, text: str) -> Optional[Tuple[str, Dict]]:
        """Enhanced route matching with fuzzy logic and confidence scoring"""
        preprocessed_text = self.preprocess_text(text)
        best_match = None
        best_score = 0
        best_route_key = None
        
        if self.debug_mode:
            print(f"Matching against preprocessed text: '{preprocessed_text}'")
        
        for route_key, route_info in self.ROUTE_MAP.items():
            keywords = route_info["keywords"]
            threshold = route_info.get("confidence_threshold", 0.6)
            
            for keyword in keywords:
                score = self.fuzzy_match_score(preprocessed_text, keyword)
                
                if self.debug_mode:
                    print(f"  '{keyword}' -> score: {score:.2f} (threshold: {threshold})")
                
                if score >= threshold and score > best_score:
                    best_score = score
                    best_match = route_info
                    best_route_key = route_key
        
        if best_match:
            if self.debug_mode:
                print(f"Best match: {best_route_key} with score {best_score:.2f}")
            return best_route_key, best_match
        
        return None

    def process(self) -> Optional[Dict[str, str]]:
        """
        Legacy method - now just calls process_continuous for backward compatibility
        """
        return self.process_continuous()

    def cleanup(self):
        """Enhanced cleanup"""
        if self.engine:
            try:
                self.engine.stop()
            except:
                pass
            finally:
                self.engine = None

    def test_recognition(self, duration: float = 10.0):
        """Test method to check speech recognition quality"""
        print(f"Testing continuous speech recognition for {duration} seconds...")
        print("Speak naturally and see what gets recognized:")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            text = self.listen_continuously()
            if text:
                print(f"Recognized: '{text}'")
                preprocessed = self.preprocess_text(text)
                print(f"Preprocessed: '{preprocessed}'")
                
                match_result = self.match_route(text)
                if match_result:
                    route_key, route_info = match_result
                    print(f"Would route to: {route_info['url']}")
                else:
                    print("No route match found")
                print("-" * 30)
            
            time.sleep(0.1)  # Brief pause to prevent excessive CPU usage


# Example usage and testing
if __name__ == "__main__":
    # Create enhanced voice router (no wake word needed)
    vr = EnhancedVoiceRouter(debug_mode=True, listening_timeout=3.0)
    
    print("Enhanced Voice Router initialized!")
    print("No wake word needed - just speak your commands!")
    print("Try saying: 'search show' or 'open radio' or 'satellite data'")
    
    # Run the continuous listening loop
    vr.run_continuous_loop(feedback_enabled=False)