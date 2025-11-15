import csv
import os
from difflib import get_close_matches
from typing import Optional, Dict, List

# 👇 change this to your real path
CSV_PATH = r"C:\Users\romme\Documents\Google Passwords.csv"

_password_rows: List[Dict[str, str]] = []
_loaded: bool = False


def _load_passwords() -> None:
    """Internal: load the CSV once into memory."""
    global _loaded, _password_rows
    if _loaded:
        return

    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Password CSV not found at: {CSV_PATH}")

    rows = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # normalize keys and strip whitespace
            rows.append({
                "name":     (row.get("name") or "").strip(),
                "url":      (row.get("url") or "").strip(),
                "username": (row.get("username") or "").strip(),
                "password": (row.get("password") or "").strip(),
            })
    _password_rows = rows
    _loaded = True


def find_account(query: str) -> Optional[Dict[str, str]]:
    """
    Find the best-matching account entry for a user query like:
      - 'password for survivmo'
      - 'what is my movies shows password'
      - 'login for movies-shows.online'

    Returns a dict with keys: name, url, username, password
    or None if nothing matches.
    """
    _load_passwords()
    q = query.lower().strip()

    # 1) direct substring matches (strong)
    candidates = []
    for row in _password_rows:
        name_l = row["name"].lower()
        url_l = row["url"].lower()
        user_l = row["username"].lower()

        score = 0
        if name_l and name_l in q:
            score += 3
        if url_l and url_l in q:
            score += 3
        # if user email is mentioned in the question
        if user_l and user_l in q:
            score += 2

        if score > 0:
            candidates.append((score, row))

    if candidates:
        # sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    # 2) fuzzy match against name + domain part of URL
    names = []
    mapping = {}
    for row in _password_rows:
        key_name = row["name"].lower()
        if key_name:
            mapping[key_name] = row
            names.append(key_name)

        # try also domain from URL
        url = row["url"].lower()
        if url.startswith("http"):
            # crude extract between '//' and next '/'
            try:
                domain = url.split("//", 1)[1].split("/", 1)[0]
            except Exception:
                domain = url
            mapping[domain] = row
            names.append(domain)

    if not names:
        return None

    best = get_close_matches(q, names, n=1, cutoff=0.4)  # 0.4 = quite tolerant
    if best:
        return mapping[best[0]]

    return None


def get_password_info(query: str) -> Optional[Dict[str, str]]:
    """
    Public helper used by the assistant:
    returns a clean dict or None.
    """
    return find_account(query)


if __name__ == "__main__":
    # quick manual test
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
