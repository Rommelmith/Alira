import re
from typing import Dict, Tuple, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---- 0) Vocabulary (edit later) ----
DEVICES = ["fan", "light", "bulb", "desk light"]
ACTIONS = ["on", "off", "turn", "switch", "set", "increase", "decrease"]
MACRO_KEYWORDS = ["focus", "security"]

# Seed KB (short Q/A only for MVP)
KB_ITEMS = [
    ("what is 1kz head bolt torque", "118 Nm"),
    ("wifi ssid name", "Nova"),
    ("wifi password", "roomi100"),
    ("wifi credentials", "Nova and the password is roomi100"),
    ("fan relay pin", "D1"),
    ("desk light pin", "D2"),
    ("focus recipe", "Desk light 30%, fan 30%, 50-minute timer."),
    ("camera lab steps", "Power capture card, start viewer, check Coral USB, run pipeline."),
]

# Build a TF-IDF vector index once
_KB_QUERIES = [q for (q, _) in KB_ITEMS]
_VECT = TfidfVectorizer().fit(_KB_QUERIES)
_KB_MATRIX = _VECT.transform(_KB_QUERIES)

# --- Multi-device parsing helpers ---
_AND_SPLIT_RE = re.compile(r"\band\b")
_ON_RE  = re.compile(r"\b(?:turn on|switch on|on)\b")
_OFF_RE = re.compile(r"\b(?:turn off|switch off|off)\b")

def _devices_union_pattern(devices):
    # longest-first so "desk light" matches before "light"
    parts = [re.escape(d) for d in sorted(devices, key=len, reverse=True)]
    return re.compile(r"(?:%s)" % "|".join(parts))

_DEVICES_RE = None  # lazy-initialized on first use


# ---- helpers ----
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def _has_number_0_100(text: str) -> Tuple[bool, int]:
    m = re.search(r"(\d{1,3})\s*%?", text)
    if not m: return (False, -1)
    val = int(m.group(1))
    return (0 <= val <= 100, val)

def parse_multi_dc(text: str, devices, actions):
    """
    Returns a list of intents:
      [{"device": <name>, "action": "on"/"off"/"set"} , ...]
    Splits on 'and', inherits the last action if a clause omits it.
    """
    global _DEVICES_RE
    t = _norm(text)

    if _DEVICES_RE is None:
        _DEVICES_RE = _devices_union_pattern(devices)

    clauses = [c.strip() for c in _AND_SPLIT_RE.split(t) if c.strip()]
    intents, last_action = [], None

    def detect_action(s: str):
        if _OFF_RE.search(s): return "off"
        if _ON_RE.search(s):  return "on"
        for a in actions:  # fallback: set/increase/decrease
            if re.search(rf"\b{re.escape(a)}\b", s):
                return a
        return None

    def detect_devices(s: str):
        return list({m.group(0) for m in _DEVICES_RE.finditer(s)})

    for c in clauses:
        act  = detect_action(c) or last_action
        devs = detect_devices(c)

        # clause only sets action (e.g., "turn off")
        if act and not devs:
            last_action = act
            continue

        # clause lists devices → pair with current/last action
        if devs:
            if act:
                last_action = act
            for d in devs:
                if act:
                    intents.append({"device": d, "action": act})
                else:
                    intents.append({"device": d})  # device but no action yet

    # keep only intents that have an action
    intents = [x for x in intents if x.get("action")]
    return intents

# ---- detectors (scores 0..1 with tiny logic) ----
def detect_dc(text: str) -> Tuple[float, Dict[str, Any]]:
    t = _norm(text)

    # 0) Try multi-device parsing first
    multi_intents = parse_multi_dc(t, DEVICES, ACTIONS)
    if len(multi_intents) >= 2:
        # We have multiple device actions → return them as a list
        return 0.95, {"intents": multi_intents}

    # If exactly one intent came back, use it; otherwise fall back to old logic
    if len(multi_intents) == 1:
        single = multi_intents[0]
        # Optional: support % level on single-intent using your helper
        has_num, level = _has_number_0_100(t)
        if single["action"] == "set" and has_num:
            single["value"] = level
        return 0.95, single

    # ---- fallback to your original single-device logic ----
    # device present?
    dev = next((d for d in DEVICES if d in t), None)
    if not dev:
        return 0.1, {}
    # action present?
    act = next((a for a in ACTIONS if re.search(rf"\b{re.escape(a)}\b", t)), None)
    if not act:
        return 0.6, {"device": dev}  # device but unclear action
    # optional level
    has_num, level = _has_number_0_100(t)
    if ("set" in t or "%" in t) and has_num:
        return 0.95, {"device": dev, "action": "set", "value": level}
    if act in {"on", "turn", "switch"} and "off" not in t:
        return 0.95, {"device": dev, "action": "on"}
    if "off" in t:
        return 0.95, {"device": dev, "action": "off"}
    return 0.85, {"device": dev, "action": act}

def detect_kb(text: str) -> Tuple[float, Dict[str, Any]]:
    t = _norm(text)
    q_vec = _VECT.transform([t])
    sims = cosine_similarity(q_vec, _KB_MATRIX)[0]
    best_i = int(sims.argmax())
    best_score = float(sims[best_i])
    if best_score < 0.0:  # never happens; here for completeness
        return 0.0, {}
    return best_score, {"answer": KB_ITEMS[best_i][1], "kb_query": KB_ITEMS[best_i][0]}

def detect_macro(text: str) -> Tuple[float, Dict[str, Any]]:
    t = _norm(text)
    if any(kw in t for kw in MACRO_KEYWORDS):
        # MVP: only two macros by keyword
        if "focus" in t:
            return 0.90, {"macro": "focus"}
        if "security" in t:
            return 0.90, {"macro": "security"}
    return 0.1, {}

def detect_gpt_need(text: str) -> Tuple[float, Dict[str, Any]]:
    t = _norm(text)
    abstract_phrases = ["make it better", "plan my", "explain", "summarize", "comfortable"]
    return (0.80, {"reason": "abstract"}) if any(p in t for p in abstract_phrases) else (0.20, {})

# ---- router ----
TH_DC = 0.85
TH_KB = 0.50
TH_MACRO = 0.75

def decide(text: str) -> Tuple[str, Dict[str, Any], Dict[str, float]]:
    s_dc, p_dc = detect_dc(text)
    s_kb, p_kb = detect_kb(text)
    s_ma, p_ma = detect_macro(text)
    s_gp, p_gp = detect_gpt_need(text)

    scores = {"DC": s_dc, "KB": s_kb, "MACRO": s_ma, "GPT": s_gp}

    if s_dc >= TH_DC:
        return "DC", p_dc, scores
    if s_kb >= TH_KB:
        return "KB", p_kb, scores
    if s_ma >= TH_MACRO:
        return "MACRO", p_ma, scores
    return "GPT", p_gp, scores
