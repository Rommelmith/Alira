import re
import json
import spacy
import numpy as np
import datetime
from typing import Dict, List, Any, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import pipeline
from sentence_transformers import SentenceTransformer
import torch


class AdvancedPersonalAssistant:
    def __init__(self):
        self.setup_models()
        self.setup_knowledge_base()
        self.setup_memory()
        self.setup_user_profile()

    def setup_models(self):
        """Initialize all AI models"""
        print("Loading AI models...")
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Please install spaCy model: python -m spacy download en_core_web_sm")
            self.nlp = None

        self.sentiment_analyzer = pipeline("sentiment-analysis")
        self.emotion_analyzer = pipeline("text-classification",
                                         model="j-hartmann/emotion-english-distilroberta-base")
        self.sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
        self.conversational_ai = pipeline("text-generation",
                                          model="microsoft/DialoGPT-medium")

    def setup_knowledge_base(self):
        """Initialize knowledge base and devices"""
        self.DEVICES = {
            "fan": {"pin": "D1", "state": "off", "level": 0},
            "light": {"pin": "D2", "state": "off", "level": 0},
            "bulb": {"pin": "D3", "state": "off", "level": 0},
            "ac": {"pin": "D4", "state": "off", "temp": 22}
        }

        self.ACTIONS = ["on", "off", "turn", "switch", "set", "increase", "decrease", "adjust"]
        self.MACROS = {
            "focus": {"light": 70, "fan": 30, "duration": 50},
            "security": {"all_lights": "on", "alert": "enabled"},
            "relax": {"light": 40, "fan": 20},
            "sleep": {"light": 10, "fan": 50}
        }

        # Enhanced knowledge base
        self.KB_ITEMS = [
            ("what is 1kz head bolt torque", "118 Nm"),
            ("wifi ssid name", "Nova"),
            ("wifi password", "roomi100"),
            ("wifi credentials", "SSID: Nova, Password: roomi100"),
            ("fan relay pin", "D1"),
            ("desk light pin", "D2"),
            ("focus recipe", "Desk light 70%, fan 30%, 50-minute timer."),
            ("security setup", "All lights on, motion alerts enabled."),
            ("camera setup", "Power capture card, start viewer, check Coral USB, run pipeline."),
            ("your name", "I'm Nova, your personal assistant!"),
            ("who are you", "I'm Nova, your AI assistant designed to help with devices, information, and more!"),
        ]

        # Build TF-IDF index
        self._KB_QUERIES = [q for (q, _) in self.KB_ITEMS]
        self._VECT = TfidfVectorizer().fit(self._KB_QUERIES)
        self._KB_MATRIX = self._VECT.transform(self._KB_QUERIES)

    def setup_memory(self):
        """Initialize conversation memory"""
        self.conversation_history = []
        self.user_preferences = {}
        self.learned_patterns = {}

    def setup_user_profile(self):
        """Initialize user profile and preferences"""
        self.user_profile = {
            "name": "User",
            "preferred_devices": [],
            "usual_times": {},
            "temperature_preference": 22,
            "light_preference": 70
        }

    # Core NLP Functions
    def advanced_text_analysis(self, text: str) -> Dict[str, Any]:
        """Comprehensive text analysis with multiple NLP techniques"""
        analysis = {
            "entities": self.extract_entities(text),
            "sentiment": self.analyze_sentiment(text),
            "emotion": self.analyze_emotion(text),
            "semantic_roles": self.extract_semantic_roles(text),
            "complexity": self.analyze_complexity(text)
        }
        return analysis

    def extract_entities(self, text: str) -> Dict[str, List]:
        """Extract entities with context"""
        if not self.nlp:
            return {}

        doc = self.nlp(text)
        entities = {
            "devices": [],
            "actions": [],
            "locations": [],
            "time_references": [],
            "quantities": [],
            "people": []
        }

        for ent in doc.ents:
            if ent.label_ in ["ORG", "PRODUCT"]:
                entities["devices"].append(ent.text)
            elif ent.label_ == "GPE":
                entities["locations"].append(ent.text)
            elif ent.label_ == "PERSON":
                entities["people"].append(ent.text)
            elif ent.label_ == "TIME":
                entities["time_references"].append(ent.text)
            elif ent.label_ == "QUANTITY":
                entities["quantities"].append(ent.text)

        return entities

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze text sentiment"""
        try:
            result = self.sentiment_analyzer(text)[0]
            return {"label": result["label"], "score": result["score"]}
        except:
            return {"label": "NEUTRAL", "score": 0.5}

    def analyze_emotion(self, text: str) -> Dict[str, Any]:
        """Analyze emotional content"""
        try:
            result = self.emotion_analyzer(text)[0]
            return {"emotion": result["label"], "confidence": result["score"]}
        except:
            return {"emotion": "neutral", "confidence": 0.5}

    def extract_semantic_roles(self, text: str) -> Dict[str, List]:
        """Extract basic semantic roles"""
        if not self.nlp:
            return {}

        doc = self.nlp(text)
        roles = {"agent": [], "action": [], "patient": [], "target": []}

        for token in doc:
            if token.dep_ in ["nsubj", "nsubjpass"]:
                roles["agent"].append(token.text)
            elif token.dep_ in ["dobj", "attr"]:
                roles["patient"].append(token.text)
            elif token.dep_ == "ROOT":
                roles["action"].append(token.lemma_)

        return roles

    def analyze_complexity(self, text: str) -> Dict[str, Any]:
        """Analyze text complexity"""
        if not self.nlp:
            return {"sentence_count": 1, "word_count": len(text.split())}

        doc = self.nlp(text)
        return {
            "sentence_count": len(list(doc.sents)),
            "word_count": len(doc),
            "is_question": any(token.dep_ == "aux" for token in doc)
        }

    # Intent Detection Functions
    def detect_intent_advanced(self, text: str) -> Tuple[str, Dict[str, Any], Dict[str, float]]:
        """Advanced multi-dimensional intent detection"""
        analysis = self.advanced_text_analysis(text)
        t = self._norm(text)

        # Calculate scores for all intent types
        scores = {}
        payloads = {}

        # Device Control
        dc_score, dc_payload = self.detect_device_control_advanced(t, analysis)
        scores["DC"] = dc_score
        payloads["DC"] = dc_payload

        # Knowledge Base
        kb_score, kb_payload = self.detect_knowledge_query(t)
        scores["KB"] = kb_score
        payloads["KB"] = kb_payload

        # Macro Detection
        macro_score, macro_payload = self.detect_macro_advanced(t, analysis)
        scores["MACRO"] = macro_score
        payloads["MACRO"] = macro_payload

        # Conversational
        conv_score, conv_payload = self.detect_conversational(t, analysis)
        scores["CONV"] = conv_score
        payloads["CONV"] = conv_payload

        # Learning Intent
        learn_score, learn_payload = self.detect_learning_intent(t, analysis)
        scores["LEARN"] = learn_score
        payloads["LEARN"] = learn_payload

        # Determine primary intent
        primary_intent = max(scores, key=scores.get)
        confidence = scores[primary_intent]

        # Apply thresholds
        if confidence < 0.3:
            primary_intent = "CONV"  # Default to conversational
            confidence = 0.8

        return primary_intent, payloads[primary_intent], scores

    def detect_device_control_advanced(self, text: str, analysis: Dict) -> Tuple[float, Dict]:
        """Advanced device control detection with context"""
        confidence = 0.0
        details = {}

        # Check for device mentions
        devices_found = []
        for device in self.DEVICES:
            if re.search(rf"\b{re.escape(device)}\b", text):
                devices_found.append(device)
                confidence += 0.3

        if not devices_found:
            return 0.1, {}

        details["devices"] = devices_found

        # Check for actions
        actions_found = []
        for action in self.ACTIONS:
            if re.search(rf"\b{re.escape(action)}\b", text):
                actions_found.append(action)
                confidence += 0.4

        if actions_found:
            details["actions"] = actions_found

        # Check for numerical values
        num_match = re.search(r"(\d{1,3})\s*%?", text)
        if num_match:
            value = int(num_match.group(1))
            if 0 <= value <= 100:
                details["value"] = value
                confidence += 0.2

        # Contextual boosting
        if analysis["semantic_roles"].get("action"):
            confidence += 0.1

        return min(confidence, 1.0), details

    def detect_knowledge_query(self, text: str) -> Tuple[float, Dict]:
        """Enhanced knowledge base query with semantic search"""
        t = self._norm(text)
        q_vec = self._VECT.transform([t])
        sims = cosine_similarity(q_vec, self._KB_MATRIX)[0]
        best_i = int(sims.argmax())
        best_score = float(sims[best_i])

        if best_score < 0.3:
            return 0.0, {}

        return best_score, {
            "answer": self.KB_ITEMS[best_i][1],
            "question": self.KB_ITEMS[best_i][0],
            "confidence": best_score
        }

    def detect_macro_advanced(self, text: str, analysis: Dict) -> Tuple[float, Dict]:
        """Advanced macro detection with context"""
        t = self._norm(text)
        confidence = 0.1
        details = {}

        for macro_name, macro_config in self.MACROS.items():
            if macro_name in t:
                confidence = 0.9
                details = {"macro": macro_name, "config": macro_config}
                break

        # Check for macro-like patterns
        if any(word in t for word in ["routine", "preset", "mode", "setting"]):
            confidence = max(confidence, 0.7)

        return confidence, details

    def detect_conversational(self, text: str, analysis: Dict) -> Tuple[float, Dict]:
        """Detect conversational intent"""
        t = self._norm(text)
        confidence = 0.5
        details = {"type": "general_chat"}

        # Greetings
        if any(word in t for word in ["hello", "hi", "hey", "greetings"]):
            confidence = 0.9
            details["type"] = "greeting"

        # Questions about the assistant
        if any(word in t for word in ["who are you", "your name", "what are you"]):
            confidence = 0.9
            details["type"] = "about_assistant"

        # Personal questions
        if any(word in t for word in ["how are you", "how do you feel"]):
            confidence = 0.8
            details["type"] = "personal_inquiry"

        return confidence, details

    def detect_learning_intent(self, text: str, analysis: Dict) -> Tuple[float, Dict]:
        """Detect learning and adaptation requests"""
        t = self._norm(text)
        confidence = 0.1
        details = {}

        learning_phrases = [
            "remember that", "i like", "i prefer", "always", "never",
            "from now on", "my preference", "i usually"
        ]

        if any(phrase in t for phrase in learning_phrases):
            confidence = 0.8
            details["type"] = "preference_learning"

        return confidence, details

    # Action Execution
    def execute_intent(self, intent: str, payload: Dict, original_text: str) -> str:
        """Execute the detected intent and return response"""
        if intent == "DC":
            return self.execute_device_control(payload)
        elif intent == "KB":
            return payload.get("answer", "I don't have an answer for that.")
        elif intent == "MACRO":
            return self.execute_macro(payload)
        elif intent == "CONV":
            return self.generate_conversational_response(payload, original_text)
        elif intent == "LEARN":
            return self.learn_user_preference(original_text)
        else:
            return self.generate_fallback_response(original_text)

    def execute_device_control(self, payload: Dict) -> str:
        """Execute device control commands"""
        devices = payload.get("devices", [])
        actions = payload.get("actions", [])
        value = payload.get("value")

        if not devices:
            return "Which device would you like me to control?"

        device = devices[0]
        action = actions[0] if actions else "toggle"

        # Update device state
        if device in self.DEVICES:
            if action in ["on", "turn", "switch"] and "off" not in actions:
                self.DEVICES[device]["state"] = "on"
                if value:
                    self.DEVICES[device]["level"] = value
                    return f"Turned {device} on and set to {value}%"
                return f"Turned {device} on"
            elif "off" in actions:
                self.DEVICES[device]["state"] = "off"
                return f"Turned {device} off"
            elif value is not None:
                self.DEVICES[device]["level"] = value
                return f"Set {device} to {value}%"

        return f"Controlled {device} with {action}"

    def execute_macro(self, payload: Dict) -> str:
        """Execute macro commands"""
        macro_name = payload.get("macro")
        if macro_name in self.MACROS:
            config = self.MACROS[macro_name]
            # Apply macro configuration to devices
            for device, setting in config.items():
                if device in self.DEVICES:
                    if isinstance(setting, int):
                        self.DEVICES[device]["state"] = "on"
                        self.DEVICES[device]["level"] = setting
            return f"Activated {macro_name} mode with preferred settings"
        return "Macro not found"

    def generate_conversational_response(self, payload: Dict, original_text: str) -> str:
        """Generate conversational responses"""
        response_type = payload.get("type", "general_chat")

        if response_type == "greeting":
            return self.get_greeting_response()
        elif response_type == "about_assistant":
            return "I'm Nova, your advanced personal AI assistant! I can control devices, answer questions, and learn your preferences."
        elif response_type == "personal_inquiry":
            return "I'm functioning well, thank you for asking! How can I assist you today?"
        else:
            return self.generate_contextual_response(original_text)

    def learn_user_preference(self, text: str) -> str:
        """Learn from user preferences mentioned in text"""
        # Simple pattern matching for preference learning
        if "i like" in text.lower():
            if "bright" in text.lower():
                self.user_profile["light_preference"] = 80
                return "I've noted that you prefer brighter lighting"
            elif "dim" in text.lower():
                self.user_profile["light_preference"] = 40
                return "I've noted that you prefer dimmer lighting"

        return "I'll remember that preference for future reference"

    def generate_contextual_response(self, text: str) -> str:
        """Generate contextual response using AI"""
        try:
            # Use the conversational AI for complex queries
            response = self.conversational_ai(
                text,
                max_length=100,
                num_return_sequences=1,
                pad_token_id=50256
            )[0]['generated_text']

            # Clean up response
            response = response.replace(text, "").strip()
            if not response:
                return self.generate_fallback_response(text)
            return response

        except Exception as e:
            return self.generate_fallback_response(text)

    def generate_fallback_response(self, text: str) -> str:
        """Generate fallback response when intent is unclear"""
        fallbacks = [
            "I'm not sure I understand. Could you rephrase that?",
            "I'm still learning. Could you try asking in a different way?",
            "I want to make sure I help you correctly. Could you provide more details?",
            "That's an interesting question. Let me think about how best to assist you."
        ]
        return np.random.choice(fallbacks)

    # Utility Functions
    def _norm(self, s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower())

    def get_greeting_response(self) -> str:
        """Get time-appropriate greeting"""
        hour = datetime.datetime.now().hour
        if hour < 12:
            return "Good morning! How can I assist you today?"
        elif hour < 18:
            return "Good afternoon! What can I help you with?"
        else:
            return "Good evening! How can I be of service?"

    def get_device_status(self) -> str:
        """Get current status of all devices"""
        status = []
        for device, info in self.DEVICES.items():
            if info["state"] == "on":
                if info.get("level"):
                    status.append(f"{device}: on at {info['level']}%")
                else:
                    status.append(f"{device}: on")
            else:
                status.append(f"{device}: off")
        return " | ".join(status)

    # Main Interface
    def process_query(self, text: str) -> str:
        """Main method to process user queries"""
        if not text.strip():
            return "Please provide a query."

        # Store in conversation history
        self.conversation_history.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "user_input": text,
            "response": ""
        })

        # Detect intent
        intent, payload, scores = self.detect_intent_advanced(text)

        # Generate response
        response = self.execute_intent(intent, payload, text)

        # Store response in history
        self.conversation_history[-1]["response"] = response
        self.conversation_history[-1]["intent"] = intent

        # Keep history manageable
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]

        return response


# Quick test interface
if __name__ == "__main__":
    assistant = AdvancedPersonalAssistant()
    print("Nova AI Assistant initialized!")
    print("I can control devices, answer questions, and have conversations.")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("Nova: Goodbye! Have a great day!")
                break

            response = assistant.process_query(user_input)
            print(f"Nova: {response}")

        except KeyboardInterrupt:
            print("\nNova: Goodbye!")
            break
        except Exception as e:
            print(f"Nova: I encountered an error. Please try again. ({str(e)})")