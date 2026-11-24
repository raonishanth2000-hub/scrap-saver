"""Find receipts by meaning (embeddings) with a keyword fallback that always works."""

import math
import re

from . import db, llm

# Words people use vs words that appear in receipts.
SYNONYMS = {
    "college": ["fee", "fees", "tuition", "education", "semester", "university", "school", "institute"],
    "fee": ["fees", "tuition", "education", "semester"],
    "fees": ["fee", "tuition", "education", "semester"],
    "tuition": ["fee", "fees", "education", "college"],
    "electricity": ["power", "bescom", "kseb", "electric", "utilities", "energy"],
    "current": ["electricity", "power", "bescom", "kseb"],
    "phone": ["mobile", "recharge", "airtel", "jio", "vi", "telecom", "postpaid", "prepaid"],
    "recharge": ["mobile", "phone", "airtel", "jio", "telecom"],
    "wifi": ["broadband", "internet", "fiber", "act", "airtel", "telecom"],
    "internet": ["broadband", "wifi", "fiber", "telecom"],
    "music": ["spotify", "subscription"],
    "movies": ["netflix", "prime", "hotstar", "subscription"],
    "food": ["swiggy", "zomato", "order", "restaurant"],
    "rent": ["hostel", "pg", "accommodation", "house"],
    "hostel": ["rent", "accommodation", "pg"],
    "subscription": ["subscription", "renewal", "membership", "plan"],
}
STOP = {"my", "the", "a", "an", "of", "for", "to", "where", "is", "show", "find", "me", "receipt", "receipts", "bill", "invoice", "payment", "paid", "last", "did", "i", "get", "and", "in", "on"}


def search_text(r: dict) -> str:
    return " | ".join(
        str(x) for x in [r.get("nickname"), r.get("payee"), r.get("category"), r.get("summary"), r.get("subject"), r.get("sender")] if x
    )


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _expand(query: str) -> tuple[set[str], set[str]]:
    core = {t for t in _tokens(query) if t not in STOP}
    extra = set()
    for t in core:
        extra.update(SYNONYMS.get(t, []))
    return core, extra - core


def keyword_score(r: dict, query: str) -> float:
    core, extra = _expand(query)
    if not core and not extra:
        return 0.0
    weighted = [
        (_tokens(r.get("nickname")), 3.0),
        (_tokens(r.get("payee")), 3.0),
        (_tokens(r.get("category")), 1.5),
        (_tokens(r.get("summary")), 1.5),
        (_tokens(r.get("subject")), 1.0),
        (_tokens(r.get("sender")), 0.5),
    ]
    score = 0.0
    for words, w in weighted:
        bag = set(words)
        score += w * sum(1 for t in core if t in bag or any(b.startswith(t) for b in bag if len(t) >= 3))
        score += 0.5 * w * sum(1 for t in extra if t in bag)
    # Month / year mentions like "aug" or "2026"
    for t in core:
        if t in (r.get("paid_on") or "") or t[:3] in (r.get("nickname") or "").lower():
            score += 0.5
    return score


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def ensure_embeddings(receipts: list[dict], path=None) -> int:
    """Embed receipts that do not have an embedding yet. Returns how many were added."""
    missing = [r for r in receipts if not r.get("embedding")]
    if not missing:
        return 0
    vectors = llm.embed([search_text(r) for r in missing])
    if not vectors:
        return 0
    for r, v in zip(missing, vectors):
        r["embedding"] = v
    db.upsert(missing, path)
    return len(missing)


def search(query: str, limit: int = 5, path=None) -> list[dict]:
    """Return the best-matching receipts, each with a 'score' between 0 and 1."""
    query = (query or "").strip()
    receipts = db.all_receipts(path)
    if not query or not receipts:
        return []

    kw = {r["id"]: keyword_score(r, query) for r in receipts}
    max_kw = max(kw.values()) or 1.0

    sem = {}
    if any(r.get("embedding") for r in receipts):
        qv = llm.embed([query])
        if qv:
            for r in receipts:
                if r.get("embedding"):
                    sem[r["id"]] = _cosine(qv[0], r["embedding"])

    ranked = []
    for r in receipts:
        k = kw[r["id"]] / max_kw
        if sem:
            s = sem.get(r["id"], 0.0)
            score = 0.6 * s + 0.4 * k
            relevant = k > 0 or s >= 0.35
        else:
            score = k
            relevant = k > 0
        if relevant:
            out = dict(r)
            out.pop("embedding", None)
            out["score"] = round(score, 3)
            ranked.append(out)
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:limit]
