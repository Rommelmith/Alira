# CLAUDE.md - AI Assistant Development Guide for Alira

## Project Overview

**Alira** is a multi-modal personal AI assistant system (Jarvis-inspired) that integrates:
- Computer vision (face recognition, object detection)
- Voice recognition and natural language processing
- IoT home automation (smart device control)
- Knowledge base querying
- Session-based presence awareness

**Target User**: Rommel (nickname: "Roomi")
**Deployment**: Raspberry Pi with WebSocket server
**Primary Entry Point**: `working.py`
**Language**: Python 3.x with asyncio

---

## System Architecture

### High-Level Flow
```
[Android App (Vision)]
    ↓ WebSocket (ws://0.0.0.0:8765)
[working.py] ←→ [bus.py (asyncio queues)]
    ↓                    ↓
[session_logic.py] ──→ [SpeechRecognitionFile.py]
    ↓                          ↓ (voice text)
[decider.py] ──→ Multi-intent NLP parser
    ↓
    ├──→ [dc_operation.py] → NodeMCU ESP8266 (192.168.10.100) → Relays
    ├──→ [kb_operation.py] → kb.json (TF-IDF search)
    ├──→ [password_store.py] → Google Passwords CSV
    └──→ Macro/GPT routing
```

### Core Design Patterns

1. **Event-Driven Architecture**: WebSocket events → asyncio queues → consumers
2. **Session-Based State Management**: Binary state (active/inactive) with 30s timeout
3. **Multi-Stage NLP Pipeline**: Intent classification → extraction → routing → execution
4. **Lazy Loading & Caching**: KB vectorizer, password CSV, Chrome driver persistence
5. **Resilient Communication**: HTTP retries, connection pooling, graceful degradation

---

## Module Descriptions

### `/working.py` (60 lines)
**Purpose**: Main entry point and WebSocket server

**Responsibilities**:
- Listen for vision events on ws://0.0.0.0:8765
- Parse JSON messages from Android app
- Route face events to `bus.face_q`
- Route object detection events to `bus.object_q` (only if session active + confidence > 50%)
- Throttle events (process every 3rd event to reduce load)
- Launch three concurrent tasks: `session_starter()`, `object_loop()`, `watch_dog()`

**Key Logic**:
```python
# Face events: "face_recognized", "face_unknown"
if etype in ("face_recognized", "face_unknown") and index % 3 == 0:
    bus.face_q.put_nowait({"type":etype, "name":name, "confidence":confidence})

# Object events: "object_seen:label"
elif etype.startswith("object_seen:") and index % 3 == 0:
    if float(score) > 0.50 and bus.session_active:
        bus.object_q.put_nowait({"Object":label, "Confidence":score})
```

---

### `/bus.py` (25 lines)
**Purpose**: Central message bus and shared state

**Global State**:
- `face_q`: asyncio.Queue for face recognition events
- `object_q`: asyncio.Queue for object detection events
- `session_active`: asyncio.Event (binary flag)
- `TARGET_NAME = "Rommel"` (hardcoded target user)
- `TIMEOUT_S = 30` (session timeout in seconds)
- `_last_seen_ts`: timestamp of last face detection

**Key Functions**:
- `mark_target_seen()`: Set session active and update timestamp
- `rommel_seen()`: Update timestamp (session already active)
- `time_out()`: Check if 30 seconds elapsed since last face event

---

### `/session_logic.py` (62 lines)
**Purpose**: Session lifecycle management

**Three Concurrent Coroutines**:

1. **`session_starter()`**:
   - Monitors `bus.face_q`
   - Activates session when Rommel detected
   - Updates timestamp on subsequent detections

2. **`watch_dog()`**:
   - Polls every 0.5 seconds
   - Clears session if timeout exceeded
   - Prints timeout notification

3. **`object_loop()`**:
   - Waits for session activation
   - Continuously captures voice input via `SpeechRecognition()`
   - Passes text to `decider.decide()`
   - Prints response
   - Sleeps briefly between loops

---

### `/SpeechRecognitionFile.py` (72 lines)
**Purpose**: Voice-to-text using Web Speech API

**Implementation**:
- Selenium with headless Chrome
- Loads local `voice.html` (Web Speech API integration)
- Non-blocking with 7-second timeout
- Browser persists across calls (avoids restart overhead)

**Returns**: `str` (transcript) or `None` (timeout/error)

---

### `/decider.py` (168 lines)
**Purpose**: Multi-domain NLP intent classifier

**Four Detection Methods**:

1. **Device Control (DC)** - `detect_dc(text)`:
   - Vocabulary: `DEVICES = ["fan", "light", "bulb", "desk light", "lamp"]`
   - Actions: `["on", "off", "turn", "switch", "set", "increase", "decrease", "toggle", "all on", "all off", "status"]`
   - Multi-intent parser: handles compound commands ("turn on the light and turn off the fan")
   - Returns: score (0.85-0.95) + payload `{"device": str, "action": str}` or `{"intents": [...]}`

2. **Knowledge Base (KB)** - `detect_kb(text)`:
   - TF-IDF cosine similarity against `kb.json`
   - Returns: score (0.0-1.0) + `{"answer": str}`

3. **Macro Detection** - `detect_macro(text)`:
   - Keywords: `["focus", "security"]`
   - Returns: score (0.90) + `{"macro": str}` or score 0.1

4. **GPT Need Detection** - `detect_gpt_need(text)`:
   - Abstract phrases: "make it better", "plan my", "explain", "summarize", "comfortable"
   - Returns: score (0.80/0.20) + `{"reason": "abstract"}`

**Routing Logic** (thresholds):
```python
TH_DC = 0.85     # Device control
TH_KB = 0.10     # Knowledge base
TH_MACRO = 0.75  # Macro triggers
```

**Decision Flow**:
1. If DC score ≥ 0.85 → call `dc_operation.handle_dc()` immediately
2. Else if KB score ≥ 0.10 → return KB answer
3. Else if Macro score ≥ 0.75 → return `("MACRO", payload, scores)`
4. Else → return `("GPT", payload, scores)` for LLM processing

---

### `/dc_operation.py` (273 lines, includes legacy code)
**Purpose**: IoT device control via NodeMCU ESP8266

**Hardware**:
- NodeMCU at `http://192.168.10.100/api`
- 4-channel relay module
- Device mapping: `lamp(0), bulb(1), light(2), fan(3)`

**Key Features**:
- Idempotent operations (checks state before switching)
- HTTP session with retry logic (exponential backoff)
- Connection pooling, 1.5s timeout
- Supports: on, off, toggle, status, all_on, all_off
- Multi-intent processing (handles lists of commands)

**Returns**: Detailed status dict with pre-state, post-state, HTTP codes, errors

**Important**: Bottom half contains commented legacy implementations (preserved for reference)

---

### `/kb_operation.py` (107 lines)
**Purpose**: Personal knowledge base search

**Implementation**:
- TF-IDF vectorization with scikit-learn
- Features: lowercase, English stopwords, 1-2 word n-grams, max 5000 features
- Cosine similarity search
- Caches vectorizer/matrix in `kbtfid.pkl` (rebuilds if `kb.json` modified)

**Data Source**: `/kb.json` (53KB, ~100+ personal facts)

**Query Function**: `query_kb(question)` → `{"answer": str, "score": float}`

---

### `/password_store.py` (129 lines)
**Purpose**: Password retrieval from Google Passwords CSV export

**Matching Strategy**:
- Fuzzy substring matching + `difflib.get_close_matches()`
- Searches: account name, URL, username
- Scoring: name match (+3), URL match (+3), username match (+2)
- Returns best match with credentials

**Returns**: `{"name": str, "url": str, "username": str, "password": str}`

---

### `/kb.json` (53KB)
**Purpose**: Personal knowledge base entries

**Format**: JSON array of `{"question": str, "answer": str}` pairs

**Content**: Identity, education, goals, projects, skills, personal facts

---

### `/voice.html` (1.4KB)
**Purpose**: Web Speech API interface for browser-based speech recognition

**Used by**: `SpeechRecognitionFile.py` via Selenium

---

### `/test.py` (181 bytes)
**Purpose**: Basic test script for KB operations

---

## Key Constants & Configuration

### Session Settings (`bus.py`)
```python
TARGET_NAME = "Rommel"  # Recognized user
TIMEOUT_S = 30          # Session timeout in seconds
```

### NLP Vocabulary (`decider.py`)
```python
DEVICES = ["fan", "light", "bulb", "desk light", "lamp"]
ACTIONS = ["on", "off", "turn", "switch", "set", "increase", "decrease", "toggle", "all on", "all off", "status"]
MACRO_KEYWORDS = ["focus", "security"]
```

### Detection Thresholds (`decider.py`)
```python
TH_DC = 0.85     # Device control confidence
TH_KB = 0.10     # Knowledge base minimum score
TH_MACRO = 0.75  # Macro keyword confidence
```

### Device Control (`dc_operation.py`)
```python
ESP8266_URL = "http://192.168.10.100/api"
DEVICE_RELAY_MAP = {"lamp": 0, "bulb": 1, "light": 2, "fan": 3}
HTTP_TIMEOUT = 1.5  # seconds
```

### Speech Recognition (`SpeechRecognitionFile.py`)
```python
RECOGNITION_TIMEOUT = 7  # seconds
```

### WebSocket Server (`working.py`)
```python
PORT = 8765
HOST = "0.0.0.0"
EVENT_THROTTLE = 3        # Process every 3rd event
OBJECT_CONFIDENCE_MIN = 0.50  # 50% minimum confidence
```

---

## Python Dependencies

**Core Libraries** (inferred from imports):
```
asyncio            # Async I/O, coroutines
websockets         # WebSocket server
scikit-learn       # TF-IDF, cosine similarity
selenium           # Browser automation
chromedriver-autoinstaller  # Chrome WebDriver
requests           # HTTP client
urllib3            # Connection pooling, retries
pyttsx3            # Text-to-speech (imported but not actively used)
```

**Standard Library**:
```
json, re, time, typing, difflib
```

---

## External Integrations

### 1. Android Vision App
- **Protocol**: WebSocket (ws://raspberry_pi_ip:8765)
- **Events**: `face_recognized`, `face_unknown`, `object_seen:*`
- **Technology**: CameraX + MediaPipe (face recognition), TFLite + MobileNet (object detection)
- **Face Embeddings**: 128-dimensional vectors

### 2. NodeMCU ESP8266 (IoT Controller)
- **Endpoint**: `http://192.168.10.100/api`
- **Protocol**: HTTP REST
- **Hardware**: 4-channel relay module controlling physical devices
- **Response Format**: JSON with device states

### 3. Chrome Browser (Headless)
- **Purpose**: Web Speech API access
- **Mode**: Headless (background operation)
- **Lifecycle**: Persistent across recognition calls

---

## Development Workflows

### Starting the System
```bash
cd /home/user/Alira
python working.py
```

**Initialization Sequence**:
1. WebSocket server starts on port 8765
2. Three async tasks launch: `session_starter()`, `object_loop()`, `watch_dog()`
3. System waits for Android app connection
4. Prints: "🚀 server listening on ws://0.0.0.0:8765"

### Typical Interaction Flow

1. **Activation**:
   - Android app detects Rommel's face
   - Sends `face_recognized` event via WebSocket
   - `session_starter()` activates session
   - Prints: "Rommel Seen"

2. **Voice Command**:
   - `object_loop()` wakes up
   - Calls `SpeechRecognition()` (7s timeout)
   - User speaks: "Turn on the light and turn off the fan"
   - `decider.decide()` parses multi-intent
   - `handle_dc()` executes HTTP calls to NodeMCU
   - Prints response status

3. **Session Timeout**:
   - No face detected for 30 seconds
   - `watch_dog()` clears session
   - Prints: "🛌 Session ended (timeout)"
   - `object_loop()` returns to waiting state

### Testing Individual Modules

**Test Knowledge Base**:
```bash
python test.py
# OR
python -c "from kb_operation import query_kb; print(query_kb('What is my main goal?'))"
```

**Test Decider**:
```bash
python decider.py  # Runs built-in test: "What is my main long-term learning goal"
# OR
python -c "from decider import decide; print(decide('turn on the light'))"
```

**Test Device Control** (requires NodeMCU online):
```python
from dc_operation import handle_dc
result = handle_dc("DC", {"device": "light", "action": "on"}, {})
print(result)
```

---

## Code Conventions

### Style
- **Type Hints**: Extensive use of `typing` module (`Dict`, `List`, `Tuple`, `Optional`, `Any`)
- **Naming**:
  - Functions: `snake_case`, verb-based (`handle_dc`, `query_kb`, `mark_target_seen`)
  - Constants: `UPPER_CASE` (`DEVICES`, `ACTIONS`, `TARGET_NAME`, `TIMEOUT_S`)
  - Private functions: Leading underscore (`_norm`, `_api`, `_load_passwords`)
  - Module names: Descriptive, action-oriented (`dc_operation`, `kb_operation`)
- **Async/Await**: Consistent async pattern throughout session management
- **Error Handling**: Try-except with graceful degradation

### Key Patterns

1. **Throttling**: Process only every 3rd event to reduce load
   ```python
   if index % 3 == 0:  # working.py:26, 36
   ```

2. **Idempotency**: Check device state before switching
   ```python
   # dc_operation.py checks current relay state before on/off operations
   ```

3. **Timeouts**: All I/O operations have timeouts
   - Speech recognition: 7 seconds
   - HTTP requests: 1.5 seconds
   - Session timeout: 30 seconds

4. **Confidence Thresholds**: Quality filters for events
   ```python
   if float(score) > 0.50 and bus.session_active:  # working.py:41
   ```

5. **Global State Management**: Centralized in `bus.py`
   - All session state accessed via `bus.session_active`
   - Queues shared across modules

6. **Legacy Code Preservation**: Old implementations commented at file bottom (e.g., `dc_operation.py`)

### Personal Context
- **Target User**: Hardcoded as "Rommel" (nickname "Roomi")
- **Development Environment**: Windows (development) → Linux/Raspberry Pi (deployment)
- **Network**: Local network (192.168.10.x range)
- **Knowledge Base**: Deeply personalized (academic goals, running targets, project details)

---

## File Structure

```
/home/user/Alira/
├── working.py              # Main entry point (WebSocket server)
├── bus.py                  # Message bus and shared state
├── session_logic.py        # Session lifecycle management
├── SpeechRecognitionFile.py  # Voice-to-text (Selenium + Web Speech API)
├── decider.py              # NLP intent classifier
├── dc_operation.py         # IoT device control (NodeMCU ESP8266)
├── kb_operation.py         # Knowledge base search (TF-IDF)
├── password_store.py       # Password retrieval (Google Passwords CSV)
├── kb.json                 # Personal knowledge base (53KB)
├── kbtfid.pkl             # Cached TF-IDF vectorizer (auto-generated)
├── voice.html              # Web Speech API interface
├── test.py                 # Basic test script
└── .gitignore              # Standard Python gitignore + custom exclusions
```

---

## Important Notes for AI Assistants

### When Making Changes

1. **Session State**: Always use `bus.session_active` for state checks (never create local copies)

2. **Async Contexts**: All session logic is async; use `await` properly
   ```python
   # Correct
   text = await asyncio.to_thread(SpeechRecognition)

   # Incorrect (blocks event loop)
   text = SpeechRecognition()
   ```

3. **Device Names**: Use exact vocabulary from `decider.py:DEVICES`
   - "desk light" is TWO words (longest-first matching)
   - Adding new devices: Update `DEVICES` list AND `dc_operation.py` relay mapping

4. **Multi-Intent Commands**: The system supports compound commands
   - Example: "turn on the light and turn off the fan"
   - Parser splits on "and", inherits last action if omitted

5. **Error Handling**: Always include try-except in async coroutines
   ```python
   try:
       # async operation
   except Exception as e:
       print(f"[context] {e}")
       await asyncio.sleep(0.2)  # backoff on errors
   ```

6. **HTTP Resilience**: Device control has built-in retries; don't add duplicate retry logic

7. **Cache Invalidation**: `kbtfid.pkl` auto-rebuilds if `kb.json` modified (timestamp check)

8. **Throttling**: WebSocket handler throttles events (every 3rd); respect this pattern if adding new event types

### Common Tasks

**Add New Device**:
1. Add to `decider.py:DEVICES`
2. Add relay mapping in `dc_operation.py`
3. Test with: `python -c "from decider import decide; print(decide('turn on <device>'))"`

**Update Knowledge Base**:
1. Edit `kb.json` (add/modify `{"question": ..., "answer": ...}`)
2. Delete `kbtfid.pkl` (will auto-rebuild)
3. Test: `python -c "from kb_operation import query_kb; print(query_kb('your question'))"`

**Change Timeout**:
1. Edit `bus.py:TIMEOUT_S`
2. Restart `working.py`

**Add Macro**:
1. Add keyword to `decider.py:MACRO_KEYWORDS`
2. Add detection logic in `detect_macro()`
3. Handle in calling code (currently returns to `object_loop()`)

**Debug WebSocket Events**:
- Uncomment line 16 in `working.py` to see raw messages
- Check Android app connectivity
- Verify port 8765 is not blocked

### Testing Checklist

Before committing changes:
- [ ] Test imports: `python -c "import working, bus, session_logic, decider"`
- [ ] Test syntax: `python -m py_compile *.py`
- [ ] Test device control (if modified): Verify NodeMCU responds
- [ ] Test KB queries (if modified): Ensure TF-IDF returns expected results
- [ ] Test session logic: Verify timeout behavior
- [ ] Check for hardcoded paths (avoid Windows paths in production code)

### Performance Considerations

- **Event Throttling**: Current 1/3 processing rate is intentional (reduces load)
- **Chrome Persistence**: `SpeechRecognitionFile.py` keeps browser alive (avoid restarting)
- **Connection Pooling**: `dc_operation.py` uses session pooling (reuses TCP connections)
- **Lazy Loading**: KB vectorizer loads once, cached until file changes
- **Queue Sizes**: Asyncio queues are unbounded; consider adding maxsize if memory constrained

### Security Notes

- **Hardcoded IP**: NodeMCU at 192.168.10.100 (local network only, no auth)
- **No TLS**: WebSocket is unencrypted (ws://, not wss://)
- **Password Storage**: CSV in plaintext (assumed local filesystem, not committed)
- **Knowledge Base**: Contains personal info (keep `kb.json` in .gitignore if needed)

---

## Troubleshooting

### "client disconnected" immediately
- Check Android app WebSocket URL matches Raspberry Pi IP
- Verify port 8765 is not blocked by firewall
- Ensure `working.py` is running

### Session won't activate
- Verify `TARGET_NAME` in `bus.py` matches Android app face label
- Check face recognition confidence threshold in Android app
- Look for "Rommel Seen" print statement

### Speech recognition times out
- Check Chrome/Chromedriver versions compatibility
- Verify `voice.html` exists and is accessible
- Ensure microphone permissions (if running on desktop)
- Check 7-second timeout is sufficient for speech

### Device commands fail
- Verify NodeMCU is online: `curl http://192.168.10.100/api`
- Check relay mapping in `dc_operation.py`
- Look for HTTP error codes in response
- Ensure device name exactly matches `DEVICES` vocabulary

### Knowledge base returns low scores
- Check question phrasing matches KB entries
- Rebuild cache: `rm kbtfid.pkl && python test.py`
- Verify `kb.json` format is valid JSON
- Consider lowering `TH_KB` threshold (current: 0.10)

### Multi-intent parsing fails
- Ensure "and" conjunction is present
- Check device names don't contain "and"
- Verify action words are in `ACTIONS` list
- Test with: `python -c "from decider import parse_multi_dc, DEVICES, ACTIONS; print(parse_multi_dc('turn on light and turn off fan', DEVICES, ACTIONS))"`

---

## Git Workflow

### Current Branch
- Development branch: `claude/claude-md-mi0l9ne965x05im3-019srdBVKDKWnKpdYK9xj8tX`
- All commits and pushes should go to this branch

### Committing Changes
```bash
git add <files>
git commit -m "Brief description of changes"
git push -u origin claude/claude-md-mi0l9ne965x05im3-019srdBVKDKWnKpdYK9xj8tX
```

### .gitignore Highlights
- Standard Python excludes: `__pycache__/`, `*.pyc`, `.venv/`
- IDE: `.idea/`, `.vscode/`
- Caches: `.ruff_cache/`, `kbtfid.pkl` (should be included, but regenerates if missing)
- Sensitive: `.env`, `.streamlit/secrets.toml`

---

## Future Enhancement Ideas

### Suggested Improvements
1. **Configuration File**: Move constants (TARGET_NAME, TIMEOUT_S, ESP8266_URL) to YAML/JSON config
2. **Logging**: Replace `print()` with proper logging module (levels: DEBUG, INFO, WARN, ERROR)
3. **Unit Tests**: Add pytest suite for `decider.py`, `kb_operation.py`, `dc_operation.py`
4. **Dependency Management**: Create `requirements.txt` or `pyproject.toml`
5. **Error Recovery**: Add reconnection logic for WebSocket disconnections
6. **TLS**: Implement wss:// for encrypted WebSocket communication
7. **Multi-User**: Support multiple recognized users (expand beyond "Rommel")
8. **Web Dashboard**: Real-time status view (active session, last command, device states)
9. **Command History**: Log all commands and responses to database
10. **Voice Feedback**: Enable `pyttsx3` for spoken responses

### Architecture Enhancements
- **Message Broker**: Replace asyncio queues with Redis Pub/Sub for distributed deployment
- **State Machine**: Formalize session states (IDLE → ACTIVE → PROCESSING → IDLE)
- **Plugin System**: Modular detectors (DC, KB, Macro, GPT) as pluggable handlers
- **Metrics**: Prometheus instrumentation for response times, success rates
- **Circuit Breaker**: Protect against NodeMCU failures with fallback logic

---

## Glossary

- **DC**: Device Control (home automation domain)
- **KB**: Knowledge Base (personal facts/Q&A)
- **NLP**: Natural Language Processing
- **TF-IDF**: Term Frequency-Inverse Document Frequency (text similarity algorithm)
- **NodeMCU**: ESP8266-based microcontroller (WiFi + GPIO)
- **Relay**: Electromagnetic switch for controlling high-voltage devices
- **WebSocket**: Full-duplex communication protocol over TCP
- **Session**: Active state when target user (Rommel) is detected
- **Intent**: Parsed command with action and target (e.g., `{device: "light", action: "on"}`)
- **Macro**: Predefined complex command (e.g., "focus" mode)
- **Confidence**: Probability score for detection accuracy (0.0-1.0)

---

## Version History

- **Current State** (2025-11-15): Initial CLAUDE.md creation
  - Comprehensive analysis of codebase
  - Documentation of all modules and workflows
  - Development guidelines for AI assistants

---

## Contact & Support

**Project Owner**: Rommel
**Repository**: Alira (Personal AI Assistant)
**Last Updated**: 2025-11-15

For questions about specific modules or features, refer to inline comments in source files or test the functionality directly using the command-line examples provided above.
