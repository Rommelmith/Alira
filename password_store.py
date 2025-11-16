import csv
import os
import re
from urllib.parse import urlparse
from typing import List, Dict, Optional


# 👇 change this to your real path
CSV_PATH = r"C:\Users\romme\Desktop\Google Passwords.csv"

_rows: List[Dict[str, str]] = []
_loaded: bool = False


# --- helpers to normalise domains / services --- #

PREFIXES = [
    "www.", "login.", "auth.", "accounts.", "account.",
    "idmsa.", "sso.", "portal.", "cpanel.", "dashboard.",
    "authn.", "m."
]

SERVICE_SYNONYMS = {
    "gmail": "google",
    "yt": "youtube",
    "youtube": "youtube",
    "fb": "facebook",
    "insta": "instagram",
    "ig": "instagram",
}


def _extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        if "://" not in url:
            url = "http://" + url
        netloc = urlparse(url).netloc
        return netloc.lower()
    except Exception:
        return url.lower()


def _strip_prefixes(domain: str) -> str:
    for p in PREFIXES:
        if domain.startswith(p):
            return domain[len(p):]
    return domain


def _service_from_domain(domain: str) -> str:
    """
    accounts.google.com -> 'google'
    www.dominos.com.pk -> 'dominos'
    login.live.com     -> 'live'
    """
    if not domain:
        return ""
    domain = _strip_prefixes(domain)
    parts = domain.split(":" ,1)[0].split(".")
    if len(parts) >= 2:
        core = parts[-2]
    else:
        core = parts[0]

    # handle co.uk, com.pk etc.
    if core in ("co", "com", "org", "net", "gov", "edu") and len(parts) >= 3:
        core = parts[-3]
    return core.lower()


def _normalise_service_token(token: str) -> str:
    token = token.lower()
    if token in SERVICE_SYNONYMS:
        return SERVICE_SYNONYMS[token]
    return token


# --- loading --- #

def _load_passwords() -> None:
    global _loaded, _rows
    if _loaded:
        return

    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Password CSV not found at: {CSV_PATH}")

    rows: List[Dict[str, str]] = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or "").strip()
            url = (row.get("url") or "").strip()
            username = (row.get("username") or "").strip()
            password = (row.get("password") or "").strip()

            domain = _extract_domain(url)
            service = _service_from_domain(domain)

            rows.append({
                "name": name,
                "url": url,
                "username": username,
                "password": password,
                "domain": domain,
                "service": service,
            })

    _rows = rows
    _loaded = True


# --- core matching logic --- #

_email_regex = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)


def _parse_query(query: str):
    q = query.lower().strip()
    email_match = _email_regex.search(q)
    email = email_match.group(0) if email_match else None

    tokens = re.findall(r"[a-z0-9]+", q)
    tokens = [t for t in tokens if t]  # no empty
    return q, email, tokens


def _score_row(
    row: Dict[str, str],
    query_lower: str,
    email_in_query: Optional[str],
    tokens: List[str],
    requested_services: Optional[set],
) -> int:
    service = row["service"]
    domain = row["domain"]
    name_l = (row["name"] or "").lower()
    username = (row["username"] or "").lower()

    score = 0

    # If service filter is active, only consider matching services
    if requested_services is not None and service not in requested_services:
        return 0

    # strong: exact email match
    if email_in_query:
        if username == email_in_query:
            score += 100
        else:
            # match on local-part
            local = email_in_query.split("@", 1)[0]
            if local and local in username:
                score += 40

    # service keyword in query
    if service:
        for t in tokens:
            t_norm = _normalise_service_token(t)
            if t_norm == service:
                score += 80  # very strong
            elif service in t_norm or t_norm in service:
                score += 40

    # domain or name literally mentioned
    if domain and domain in query_lower:
        score += 40
    if name_l and name_l in query_lower:
        score += 40

    return score


def find_account(query: str) -> Optional[Dict[str, str]]:
    """
    Safe, strict matching:
      - if query mentions a service (google, dominos, netflix...), only those rows are considered
      - email helps pick among those rows
      - if nothing reaches a decent score, returns None
    """
    _load_passwords()
    q_lower, email, tokens = _parse_query(query)

    # detect which services are explicitly requested
    all_services = {row["service"] for row in _rows if row["service"]}
    requested_services: set = set()
    for t in tokens:
        t_norm = _normalise_service_token(t)
        if t_norm in all_services:
            requested_services.add(t_norm)

    if not requested_services:
        # no explicit service in query: allow all, but we will require higher email match
        requested_services = None

    best_row = None
    best_score = 0

    for row in _rows:
        s = _score_row(row, q_lower, email, tokens, requested_services)
        if s > best_score:
            best_score = s
            best_row = row

    # thresholds: if service mentioned -> require higher certainty
    if best_row is None:
        return None

    if requested_services is not None:
        if best_score < 80:
            # not confident enough, better say "no match"
            return None
    else:
        # no explicit service; rely mostly on email or literal mention
        if best_score < 60:
            return None

    # return only the core fields
    return {
        "name": best_row["name"],
        "url": best_row["url"],
        "username": best_row["username"],
        "password": best_row["password"],
    }


def get_password_info(query: str) -> Optional[Dict[str, str]]:
    return find_account(query)


if __name__ == "__main__":
    while True:
        try:
            q = input("Query (or blank to exit): ").strip()
        except EOFError:
            break
        if not q:
            break
        res = get_password_info(q)
        if res is None:
            print("No matching account found.")
        else:
            print("Matched:")
            print(f"  Name:     {res['name']}")
            print(f"  URL:      {res['url']}")
            print(f"  Username: {res['username']}")
            print(f"  Password: {res['password']}")
