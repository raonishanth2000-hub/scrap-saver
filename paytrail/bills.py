"""Fake-bill check: compare a suspicious SMS/message with the real bills already stored."""

import re

from . import config, db, llm
from .history import payee_key

RED_FLAGS = [
    (r"https?://|www\.|bit\.ly|tinyurl", "Contains a link: real billers rarely ask you to pay through an SMS link"),
    (r"\b(tonight|today|immediately|within \d+ ?(hours?|hrs?|minutes?|mins?))\b", "Creates urgency with a short deadline"),
    (r"\b(disconnect|disconnected|cut ?off|suspend|blocked|deactivat)", "Threatens to cut off service or block your account"),
    (r"\b(otp|pin|cvv|password)\b", "Asks for an OTP, PIN, CVV or password"),
    (r"\b(call|contact|whatsapp)\b.{0,25}\b\d{10}\b|\+?\d{2}[\s-]?\d{10}", "Asks you to call or message a personal mobile number"),
    (r"\b(kyc|update your details|verify your account)\b", "Asks for KYC or account verification by message"),
    (r"\b(anydesk|teamviewer|quicksupport|screen ?share)\b", "Asks you to install a screen-sharing app"),
]

SYSTEM = """You protect a user from fake bill / payment scam messages common in India
(electricity disconnection, KYC expiry, courier customs fee, fake refunds).
You get a suspicious message and the user's REAL bills found in their email.
Reply with ONLY JSON:
{
 "verdict": "likely_scam" | "matches_real_bill" | "unsure",
 "matched_bill_id": "id of the matching real bill or null",
 "reason": "2 short sentences in simple English a parent can understand",
 "advice": "one clear action, e.g. 'Do not click the link. Pay only through the official BESCOM app.'"
}
A message is 'matches_real_bill' only if a real bill from the same payee with a similar amount exists
AND the message has no scam red flags. Links to unknown sites, personal phone numbers, threats of
disconnection tonight, or requests for OTP/KYC mean 'likely_scam' even if a real bill exists."""


def red_flags(message: str) -> list[str]:
    return [label for pattern, label in RED_FLAGS if re.search(pattern, message or "", re.I)]


def _amounts(message: str) -> list[float]:
    out = []
    for m in re.finditer(r"(?:₹|rs\.?|inr)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", message or "", re.I):
        try:
            out.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return out


def candidate_bills(message: str, receipts: list[dict]) -> list[dict]:
    """Real bills whose payee is mentioned in the message, or whose amount matches."""
    msg = (message or "").lower()
    amounts = _amounts(message)
    hits = []
    for r in receipts:
        key = payee_key(r.get("payee"))
        words = [w for w in key.split() if len(w) >= 3]
        payee_hit = any(w in msg for w in words)
        cat_hit = (r.get("category") or "").lower() in msg if r.get("category") else False
        amount_hit = r.get("amount") is not None and any(abs(a - r["amount"]) <= max(1.0, 0.02 * r["amount"]) for a in amounts)
        if payee_hit or amount_hit or (cat_hit and r.get("category") == "Utilities"):
            hits.append(r)
    hits.sort(key=lambda r: r.get("paid_on") or "", reverse=True)
    return hits[:8]


def _rule_verdict(flags: list[str], candidates: list[dict], amounts: list[float]) -> dict:
    if flags:
        return {
            "verdict": "likely_scam",
            "matched_bill_id": None,
            "reason": "This message shows common scam signs. Real billers don't threaten you or send payment links by SMS.",
            "advice": "Don't click any link or call the number. Pay only through the official app or website.",
        }
    exact = [c for c in candidates if c.get("amount") is not None and any(abs(a - c["amount"]) <= max(1.0, 0.02 * c["amount"]) for a in amounts)]
    if exact:
        return {
            "verdict": "matches_real_bill",
            "matched_bill_id": exact[0]["id"],
            "reason": f"A real bill from {exact[0].get('payee')} for the same amount is in your email.",
            "advice": "It looks genuine, but still pay through the official app, not a link.",
        }
    return {
        "verdict": "unsure",
        "matched_bill_id": None,
        "reason": "No matching real bill was found in your email, but there are no obvious scam signs either.",
        "advice": "Check the amount in the official app before paying.",
    }


def check_bill(message: str, path=None) -> dict:
    receipts = db.all_receipts(path)
    for r in receipts:
        r.pop("embedding", None)
    flags = red_flags(message)
    candidates = candidate_bills(message, receipts)
    amounts = _amounts(message)
    result = None
    if config.has_openai():
        bills_text = "\n".join(
            f"- id={c['id']} | {c.get('payee')} | {c.get('currency')} {c.get('amount')} | paid/billed {c.get('paid_on')} | {c.get('nickname')}"
            for c in candidates
        ) or "(no related bills found in email)"
        try:
            result = llm.chat_json(
                SYSTEM,
                f"Suspicious message:\n{message}\n\nRed flags detected by rules: {flags or 'none'}\n\nUser's real bills:\n{bills_text}",
            )
        except (llm.LLMError, ValueError):
            result = None
    if not result or result.get("verdict") not in {"likely_scam", "matches_real_bill", "unsure"}:
        result = _rule_verdict(flags, candidates, amounts)
    # Rules win if they found clear scam signs.
    if flags and result.get("verdict") == "matches_real_bill":
        result = _rule_verdict(flags, candidates, amounts)
    matched = next((c for c in candidates if c["id"] == result.get("matched_bill_id")), None)
    return {
        "verdict": result["verdict"],
        "reason": result.get("reason", ""),
        "advice": result.get("advice", ""),
        "red_flags": flags,
        "matched_bill": matched,
        "related_bills": candidates,
    }
