"""Git-style payment history: group by payee and flag price changes."""

import re
from collections import defaultdict

from . import db


def payee_key(payee: str) -> str:
    key = re.sub(r"[^a-z0-9 ]", " ", (payee or "").lower())
    key = re.sub(r"\b(pvt|ltd|limited|inc|india|private|llp|technologies|services)\b", " ", key)
    return re.sub(r"\s+", " ", key).strip() or "unknown"


def payee_histories(path=None) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for r in db.all_receipts(path):
        r.pop("embedding", None)
        groups[payee_key(r.get("payee"))].append(r)
    for items in groups.values():
        items.sort(key=lambda x: x.get("paid_on") or "")
    return dict(groups)


def price_changes(items: list[dict]) -> list[dict]:
    """Compare each payment with the previous one from the same payee."""
    changes = []
    prev = None
    for r in items:
        if r.get("amount") is None:
            continue
        if prev is not None and prev["amount"] and r["amount"] != prev["amount"]:
            diff = round(r["amount"] - prev["amount"], 2)
            changes.append(
                {
                    "on": r.get("paid_on"),
                    "from": prev["amount"],
                    "to": r["amount"],
                    "diff": diff,
                    "pct": round(100 * diff / prev["amount"], 1),
                    "nickname": r.get("nickname"),
                }
            )
        prev = r
    return changes


def subscriptions(path=None) -> list[dict]:
    """One row per recurring payee, newest first, with its history and latest price change."""
    rows = []
    for key, items in payee_histories(path).items():
        recurring = any(i.get("is_subscription") for i in items) or len(items) >= 2
        if not recurring:
            continue
        latest = items[-1]
        changes = price_changes(items)
        rows.append(
            {
                "payee": latest.get("payee"),
                "category": latest.get("category"),
                "currency": latest.get("currency") or "INR",
                "latest_amount": latest.get("amount"),
                "last_paid": latest.get("paid_on"),
                "billing_period": latest.get("billing_period") or "",
                "payments": len(items),
                "total": round(sum(i.get("amount") or 0 for i in items), 2),
                "latest_change": changes[-1] if changes else None,
                "history": [
                    {"paid_on": i.get("paid_on"), "amount": i.get("amount"), "nickname": i.get("nickname"), "id": i.get("id")}
                    for i in items
                ],
            }
        )
    rows.sort(key=lambda x: x.get("last_paid") or "", reverse=True)
    return rows


def find_payee_history(payee: str, path=None) -> list[dict]:
    """History for the payee whose name best matches the given text."""
    want = payee_key(payee)
    histories = payee_histories(path)
    if want in histories:
        return histories[want]
    for key, items in histories.items():
        if want in key or key in want:
            return items
    want_words = set(want.split())
    best = max(histories.items(), key=lambda kv: len(want_words & set(kv[0].split())), default=None)
    if best and want_words & set(best[0].split()):
        return best[1]
    return []
