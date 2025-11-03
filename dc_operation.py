from typing import Dict, Any, List, Tuple, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "http://192.168.10.100/api"   # change if your device IP changes

# Device name → relay index (allowing synonyms)
DEVICE_TO_RELAY: Dict[str, int] = {
    "switch1": 0, "lamp": 0,
    "bulb": 1,
    "light": 2,
    "switch2": 3, "fan": 3,
}

# Allowed actions and API wiring
VALID_ACTIONS = {"on", "off", "toggle", "status", "all_on", "all_off", "switch"}

# --- HTTP session with retries & short timeouts (fast + resilient) ---
_session = None
def _session_get() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        retries = Retry(
            total=2, backoff_factor=0.1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
        )
        s.mount("http://", HTTPAdapter(max_retries=retries, pool_connections=4, pool_maxsize=8))
        _session = s
    return _session

def _api(params: Dict[str, Any], timeout: float = 1.5) -> requests.Response:
    return _session_get().get(BASE_URL, params=params, timeout=timeout)

# --- Low-level helpers mapping to your firmware API ---
def get_status() -> Dict[str, Any]:
    """Returns bitmask and per-relay boolean states."""
    r = _api({"action": "status"})
    r.raise_for_status()
    bitmask_str = r.text.strip()
    try:
        mask = int(bitmask_str)
    except ValueError:
        mask = int("".join(ch for ch in bitmask_str if ch.isdigit()) or "0")
    states = {i: bool((mask >> i) & 1) for i in range(4)}  # 4 relays
    return {"bitmask": mask, "relays": states}

def set_relay(relay: int, state: str) -> requests.Response:
    # state: "on" or "off"
    return _api({"action": "set", "relay": relay, "state": state})

def toggle_relay(relay: int) -> requests.Response:
    return _api({"action": "toggle", "relay": relay})

def set_scene(all_state: str) -> requests.Response:
    # all_state: "on" or "off"
    return _api({"action": "scene", "state": all_state})

# --- Core dispatcher that your brain will call ---
def handle_dc(
    decision: str,
    payload: Dict[str, Any],
    scores: Dict[str, float],
) -> Dict[str, Any]:
    """
    Examples:
      handle_dc('DC', {'device': 'light', 'action': 'toggle'}, scores)
      handle_dc('DC', {'device': 'bulb', 'action': 'on'}, scores)
      handle_dc('DC', {'intents': [{'device':'light','action':'on'},
                                   {'device':'fan','action':'off'}]}, scores)
      handle_dc('DC', {'action':'status'}, scores)
      handle_dc('DC', {'action':'all_off'}, scores)
    """
    out: Dict[str, Any] = {"ok": True, "decision": decision, "scores": scores, "results": []}

    # Normalize to a list of intents
    intents: List[Dict[str, str]] = []
    if "intents" in payload and isinstance(payload["intents"], list):
        intents = payload["intents"]
    else:
        # single-action payloads (device+action) or global actions (status/all_on/all_off)
        if "device" in payload or "action" in payload:
            intents = [payload]  # treat as one intent

    if not intents:
        return {"ok": False, "error": "No intents provided.", **out}

    # Pre-read status to be idempotent when possible (skip unnecessary writes)
    try:
        before = get_status()
    except Exception as e:
        # We can still try to perform actions, but note the read failure.
        before = {"bitmask": None, "relays": {}}
        out["status_read_error"] = str(e)

    for intent in intents:
        action = str(intent.get("action", "")).lower().strip()
        device = intent.get("device")
        res_entry = {"device": device, "action": action}

        # Global actions (no specific device)
        if device is None and action in ("status", "all_on", "all_off"):
            try:
                if action == "status":
                    res_entry["status"] = get_status()
                elif action == "all_on":
                    r = set_scene("on"); res_entry["http"] = r.status_code
                elif action == "all_off":
                    r = set_scene("off"); res_entry["http"] = r.status_code
                    res_entry["post_status"] = get_status()
            except Exception as e:
                out["ok"] = False
                res_entry["error"] = f"{type(e).__name__}: {e}"
            out["results"].append(res_entry)
            continue

        # Validate
        if action not in VALID_ACTIONS:
            out["ok"] = False
            res_entry["error"] = f"Unknown action '{action}'."
            out["results"].append(res_entry)
            continue

        if device is None:
            out["ok"] = False
            res_entry["error"] = "Missing 'device' for this action."
            out["results"].append(res_entry)
            continue

        relay = DEVICE_TO_RELAY.get(str(device).lower().strip())
        if relay is None:
            out["ok"] = False
            res_entry["error"] = f"Unknown device '{device}'."
            out["results"].append(res_entry)
            continue

        # Idempotency: if we're setting on/off and it's already that, skip the write
        prior_state = None
        try:
            prior_state = before["relays"].get(relay) if isinstance(before, dict) else None
        except Exception:
            pass

        try:
            if action in ("on", "off"):
                if prior_state is not None and ((action == "on" and prior_state) or (action == "off" and not prior_state)):
                    res_entry["skipped"] = True
                    res_entry["reason"] = "Already in requested state"
                    res_entry["pre_state"] = prior_state
                else:
                    r = set_relay(relay, action)
                    res_entry["http"] = r.status_code
                    res_entry["pre_state"] = prior_state
                    res_entry["post_status"] = get_status()
            elif action == "toggle" or action == "switch":
                r = toggle_relay(relay)
                res_entry["http"] = r.status_code
                res_entry["pre_state"] = prior_state
                res_entry["post_status"] = get_status()
            elif action == "status":
                res_entry["status"] = get_status()
            elif action in ("all_on", "all_off"):
                r = set_scene("on" if action == "all_on" else "off")
                res_entry["http"] = r.status_code
                res_entry["post_status"] = get_status()
        except Exception as e:
            out["ok"] = False
            res_entry["error"] = f"{type(e).__name__}: {e}"

        out["results"].append(res_entry)

    return out



# import requests
#
# BASE_URL = "http://192.168.10.100/api"   # change if your device IP changes
#
# # Device name → relay index (allowing synonyms)
# DEVICE_TO_RELAY = {
#     "switch1": 0, "lamp": 0,
#     "bulb": 1,
#     "light": 2,
#     "switch2": 3, "fan": 3,
# }
#
# # Allowed actions
# VALID_ACTIONS = {"on", "off", "toggle", "status", "all_on", "all_off", "switch"}
#
# def _api(params, timeout=1.5):
#     # print(f"GET {BASE_URL} params={params}")  # ← uncomment for debug
#     return requests.get(BASE_URL, params=params, timeout=timeout)
#
# # --- Low-level helpers mapping to your firmware API ---
# def get_status():
#     r = _api({"action": "status"})
#     r.raise_for_status()
#     bitmask_str = r.text.strip()
#     try:
#         mask = int(bitmask_str)
#     except ValueError:
#         mask = int("".join(ch for ch in bitmask_str if ch.isdigit()) or "0")
#     return {"bitmask": mask, "relays": {i: bool((mask >> i) & 1) for i in range(4)}}
#
# def set_relay(relay, state):
#     return _api({"action": "set", "relay": relay, "state": state})
#
# def toggle_relay(relay):
#     return _api({"action": "toggle", "relay": relay})
#
# def set_scene(state):
#     return _api({"action": "scene", "state": state})
#
# # --- Core dispatcher ---
# def handle_dc(decision, payload, scores):
#     out = {"ok": True, "decision": decision, "scores": scores, "results": []}
#
#     # Normalize intents
#     if isinstance(payload.get("intents"), list):
#         intents = payload["intents"]
#     elif "device" in payload or "action" in payload:
#         intents = [payload]
#     else:
#         return {"ok": False, "error": "No intents provided.", **out}
#
#     for intent in intents:
#         action = str(intent.get("action", "")).lower().strip()
#         device = intent.get("device")
#         res = {"device": device, "action": action}
#
#         # Global actions (no device)
#         if device is None and action in ("status", "all_on", "all_off"):
#             if action == "status":
#                 res["status"] = get_status()
#             elif action == "all_on":
#                 res["http"] = set_scene("on").status_code
#             else:  # all_off
#                 res["http"] = set_scene("off").status_code
#             out["results"].append(res)
#             continue
#
#         # Validation (no per-intent error text; just mark top-level ok=False)
#         if action not in VALID_ACTIONS:
#             out["ok"] = False
#             out["results"].append(res)
#             continue
#         if device is None:
#             out["ok"] = False
#             out["results"].append(res)
#             continue
#
#         relay = DEVICE_TO_RELAY.get(str(device).lower().strip())
#         if relay is None:
#             out["ok"] = False
#             out["results"].append(res)
#             continue
#
#         # Execute
#         if action in ("on", "off"):
#             res["http"] = set_relay(relay, action).status_code
#         elif action in ("toggle", "switch"):
#             res["http"] = toggle_relay(relay).status_code
#         elif action == "status":
#             res["status"] = get_status()
#         elif action in ("all_on", "all_off"):
#             res["http"] = set_scene("on" if action == "all_on" else "off").status_code
#
#         out["results"].append(res)
#
#     return out
