# Enhanced SST.py - Modified for server-side processing (no hardware dependencies)

import speech_recognition as sr
# import pyttsx3 # Removed pyttsx3
from typing import Optional, Dict, List, Tuple
import re
from difflib import SequenceMatcher
# import threading # Removed threading, as TTS is removed
import time

class EnhancedVoiceRouter:
    # Enhanced route mapping with multiple keywords and synonyms
    ROUTE_MAP = {
        "tv_shows": {
            "keywords": ["search show", "tv shows", "television", "show search", "find show", "tv series"],
            "url": "/tvmaze/",
            "response": "Navigating TV show search.",
            "confidence_threshold": 0.6
        },
        "episode_details": {
            "keywords": ["episode details", "episode info", "show details", "episode data", "show episodes"],
            "url": "/tvmaze/",
            "response": "This feature will be added soon, navigating to TV show search.",
            "confidence_threshold": 0.6
        },
        "radio": {
            "keywords": ["radio", "radio station", "music", "audio", "listen radio", "tune radio"],
            "url": "/radio/",
            "response": "Navigating to Radio Browser.Search and stream any radio station globally .",
            "confidence_threshold": 0.7
        },
        "satellite": {
            "keywords": ["satellite", "satellites", "satellite data", "space data", "orbital data"],
            "url": "/satellites/",
            "response": "navigating to SatSearch, use this web tool to search for satellite orbits and more.",
            "confidence_threshold": 0.7
        },
        "home": {
    "keywords": ["home", "homepage", "start", "main page", "go back", "landing page", "dashboard", "initial screen","index"],
            "url": "/",
            "response": "Returning to the home page of ViTalk. We are a web-based voice assistant that can help you with navigating around ViTalk.",
            "confidence_threshold": 0.7
}

    }

    def __init__(self, debug_mode: bool = True): # Removed listening_timeout
        self.debug_mode = debug_mode
        self.recognizer = sr.Recognizer()
        # self.microphone = sr.Microphone() # Removed microphone
        
        # Recognizer settings for microphone are no longer needed here
        # self.recognizer.energy_threshold = 4000
        # self.recognizer.dynamic_energy_threshold = True
        # self.recognizer.pause_threshold = 0.8
        # self.recognizer.phrase_threshold = 0.3
        
        # self._init_engine() # TTS engine removed
        # self._calibrate_microphone() # Microphone calibration removed

    # def _init_engine(self): # Removed TTS engine
        # ... (TTS engine code removed) ...

    # def _calibrate_microphone(self): # Removed microphone calibration
        # ... (microphone calibration code removed) ...

    # def talk(self, text: str) -> None: # Removed TTS talk method
        # ... (TTS talk code removed) ...

    def preprocess_text(self, text: str) -> str:
        """Clean and normalize text for better matching"""
        text = text.lower()
        text = re.sub(r'\b(um|uh|ah|er)\b', '', text)
        replacements = {
            'tv': 'television',
            'tee vee': 'television',
            'teevee': 'television',
            'show me': 'show',
            'find me': 'find',
            'get me': 'get',
            'open up': 'open',
            'pull up': 'show',
            "pull up": "show",
            "show me": "show",
            "display": "show",
            "find me": "find",
            "look for": "find",
            "get me": "get",
            "bring me": "get",
            "open up": "open",
            "go to": "open",
            "take me to": "open",
            "head to": "open",
            "navigate to": "open"

        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = ' '.join(text.split())
        return text

    def fuzzy_match_score(self, text: str, keyword: str) -> float:
        """Calculate fuzzy matching score between text and keyword"""
        if keyword in text:
            return 1.0
        text_words = text.split()
        keyword_words = keyword.split()
        if all(any(kw in tw or SequenceMatcher(None, kw, tw).ratio() > 0.8 
                  for tw in text_words) for kw in keyword_words):
            return 0.9
        similarity = SequenceMatcher(None, text, keyword).ratio()
        word_matches = sum(1 for kw in keyword_words 
                          if any(kw in tw for tw in text_words))
        word_bonus = word_matches / len(keyword_words) * 0.3
        return min(similarity + word_bonus, 1.0)

    def recognize_audio_data(self, audio_data: sr.AudioData) -> str:
        """
        Recognize speech from an sr.AudioData object.
        """
        if not isinstance(audio_data, sr.AudioData):
            if self.debug_mode:
                print("Error: recognize_audio_data received invalid audio_data type.")
            return ""
            
        try:
            # Try Google Speech Recognition
            command = self.recognizer.recognize_google(audio_data, language='en-US')
            if self.debug_mode:
                print(f"Google STT heard: '{command}'")
            return command.lower()
        except sr.UnknownValueError:
            if self.debug_mode:
                print("Google STT could not understand audio")
        except sr.RequestError as e:
            if self.debug_mode:
                print(f"Google STT request error: {e}")
        
        # Fallback to Sphinx (offline) if available and configured
        # Note: Sphinx might require model files and may not be ideal for all server setups
        # For simplicity, we'll primarily rely on Google STT here.
        # If you need Sphinx, ensure it's properly set up in your Docker environment.
        try:
            command = self.recognizer.recognize_sphinx(audio_data)
            if self.debug_mode:
                print(f"Sphinx STT heard: '{command}'")
            return command.lower()
        except sr.UnknownValueError:
            if self.debug_mode:
                print("Sphinx STT could not understand audio")
        except sr.RequestError as e:
            if self.debug_mode:
                print(f"Sphinx STT request error: {e}")
        except Exception as e: # Catch other potential Sphinx errors (e.g., missing models)
            if self.debug_mode:
                print(f"Sphinx STT general error: {e}")
                
        return ""

    def process_command_from_audio(self, audio_data: sr.AudioData) -> Optional[Dict[str, str]]:
        """
        Process a command from an sr.AudioData object.
        Recognizes speech, matches route, and returns match info.
        """
        command = self.recognize_audio_data(audio_data)
        
        if not command:
            if self.debug_mode:
                print("No speech recognized from audio data.")
            return None
        
        if self.debug_mode:
            print(f"Command recognized: '{command}'")
        
        match_result = self.match_route(command)
        
        if match_result:
            route_key, route_info = match_result
            # self.talk(route_info["response"]) # TTS removed
            if self.debug_mode:
                print(f"Match found: {route_key}. Response: {route_info['response']}")
            return {
                "url": route_info["url"],
                "response": route_info["response"], # Textual response
                "route_key": route_key,
                "original_command": command
            }
        
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

    def process(self, audio_data: sr.AudioData) -> Optional[Dict[str, str]]: # Modified to accept audio_data
        """
        Main processing method. Takes audio_data and returns match.
        """
        return self.process_command_from_audio(audio_data)

    def cleanup(self):
        """Cleanup resources (if any). Currently none after removing TTS."""
        if self.debug_mode:
            print("EnhancedVoiceRouter cleanup called.")
        # if self.engine: # TTS engine removed
            # ...
        pass

    # def run_continuous_loop(self, feedback_enabled: bool = False): # Removed, relies on microphone
        # ... (continuous loop code removed) ...

    # def test_recognition(self, duration: float = 10.0): # Removed, relies on microphone
        # ... (test recognition code removed) ...


# The if __name__ == "__main__": block is removed as it's designed for direct microphone input.
# This class is now intended to be imported and used by a server application (like app.py)
# which will handle receiving audio data.