################ KB operations #####################
import json
import os
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ITEMS = []
IDS = []
VECT = None
MATRIX = None

KB_JSON = "kb.json"

def load_kb(path: str=KB_JSON):
    global ITEMS
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            ITEMS = json.load(f)
    else:
        ITEMS = []
    return ITEMS

def load_or_build_index(items, cache_path="kbtfid.pkl", kb_path = KB_JSON):
    global VECT, MATRIX, IDS
    if os.path.exists(cache_path):
        kb_time = os.path.getmtime(kb_path)
        cache_time = os.path.getmtime(cache_path)
        cache_fresh = cache_time >= kb_time

    else:
        cache_fresh = False


    if cache_fresh:
        try:
            with open(cache_path, "rb") as f:
                packed = pickle.load(f)
            VECT = packed["vectorizer"]
            MATRIX = packed["matrix"]
            IDS = packed["ids"]
            return
        except Exception as e:
            pass

    else:
        IDS = [item["id"] for item in items]
        corps = [item["question"] + " " + item["answer"] for item in items]

        VECT = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            max_features=5000
        )
        MATRIX = VECT.fit_transform(corps)
        with open(cache_path, "wb") as f:
            pickle.dump({"vectorizer": VECT, "matrix": MATRIX, "ids": IDS}, f)







    # 5) build results
    results = []
    for i in idxs:
        item_id = IDS[i]
        it = id_to_item.get(item_id)
        if not it:
            continue
        results.append({
            "score": float(sims[i]),
            "id": it["id"],
            "question": it["question"],
            "answer": it["answer"]
        })

    if results:
        return results[0]["answer"]
    else:
        return None
