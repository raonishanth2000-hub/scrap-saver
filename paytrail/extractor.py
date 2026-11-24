"""Turn a raw email into a clean receipt record with a human nickname."""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import config, llm

SYSTEM = """You read one email and decide if it is a payment receipt, invoice, bill, fee payment,
order confirmation or subscription charge/renewal. Reply with ONLY a JSON object:
{
  "is_receipt": true/false,
  "payee": "who was paid, short brand or institution name, e.g. 'Newton School of Technology', 'Netflix'",
  "amount": number or null (total paid, no currency symbol),
  "currency": "INR" | "USD" | ... ,
  "paid_on": "YYYY-MM-DD" or null,
  "category": one of ["Education","Subscription","Utilities","Shopping","Food","Travel","Telecom","Rent","Insurance","Health","Other"],
  "is_subscription": true/false (recurring plan, membership or renewal),
  "billing_period": "monthly" | "yearly" | "one-time" | ...,
  "nickname": "short memorable name a student would search for, format '<Payee short> <What> - <Mon YYYY>', e.g. 'NST Fees - Sem 1 - Aug 2026', 'Netflix Premium - Oct 2026', 'BESCOM Electricity Bill - Sep 2026'",
  "summary": "one sentence: what was paid for, include words people might search (e.g. 'college fee', 'tuition', 'electricity')"
}
Promotional emails, OTPs, newsletters and failed payments are NOT receipts."""

AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr|\$|usd)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.I)


def _clean_amount(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    m = re.search(r"[0-9][0-9,]*(?:\.[0-9]+)?", str(value))
    return round(float(m.group(0).replace(",", "")), 2) if m else None


def _clean_date(value, fallback: str) -> str:
    if value and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
        try:
            date.fromisoformat(str(value))
            return str(value)
        except ValueError:
            pass
    return fallback or ""


def _sender_name(sender: str) -> str:
    name = re.sub(r"<.*?>", "", sender or "").strip().strip('"')
    if not name and "@" in (sender or ""):
        name = sender.split("@")[-1].split(".")[0]
    return name or "Unknown"


def _heuristic(mail: dict) -> dict:
    """Used when no OpenAI key is set: rough but never crashes."""
    text = f"{mail.get('subject', '')} {mail.get('body', '')}"
    m = AMOUNT_RE.search(text)
    payee = _sender_name(mail.get("sender", ""))
    when = mail.get("date", "")
    month = ""
    if when:
        try:
            month = date.fromisoformat(when).strftime("%b %Y")
        except ValueError:
            month = ""
    return {
        "is_receipt": True,
        "payee": payee,
        "amount": _clean_amount(m.group(1)) if m else None,
        "currency": "INR" if (m and m.group(0).strip()[:1] in "₹rRiI") else ("USD" if m else ""),
        "paid_on": when,
        "category": "Other",
        "is_subscription": bool(re.search(r"subscription|renew|membership|plan", text, re.I)),
        "billing_period": "",
        "nickname": f"{payee} - {mail.get('subject', '')[:40]}{' - ' + month if month else ''}".strip(" -"),
        "summary": mail.get("subject", ""),
    }


def extract(mail: dict) -> dict | None:
    """Return a receipt dict ready for the database, or None if the email is not a receipt."""
    if config.has_openai():
        prompt = (
            f"From: {mail.get('sender', '')}\nDate: {mail.get('date', '')}\n"
            f"Subject: {mail.get('subject', '')}\nAttachments: {', '.join(mail.get('attachments', [])) or 'none'}\n\n"
            f"Body:\n{mail.get('body', '')[:4000]}"
        )
        try:
            data = llm.chat_json(SYSTEM, prompt)
        except (llm.LLMError, ValueError):
            data = _heuristic(mail)
    else:
        data = _heuristic(mail)

    if not data.get("is_receipt"):
        return None
    payee = (data.get("payee") or _sender_name(mail.get("sender", ""))).strip()
    nickname = (data.get("nickname") or "").strip() or f"{payee} - {mail.get('subject', '')[:40]}"
    return {
        "id": mail["id"],
        "nickname": nickname[:120],
        "payee": payee[:80],
        "amount": _clean_amount(data.get("amount")),
        "currency": (data.get("currency") or "INR").upper()[:5],
        "paid_on": _clean_date(data.get("paid_on"), mail.get("date", "")),
        "category": data.get("category") or "Other",
        "is_subscription": bool(data.get("is_subscription")),
        "billing_period": data.get("billing_period") or "",
        "summary": (data.get("summary") or "")[:300],
        "subject": mail.get("subject", ""),
        "sender": mail.get("sender", ""),
        "email_date": mail.get("date", ""),
        "attachments": mail.get("attachments", []),
        "gmail_link": mail.get("link", ""),
        "source": mail.get("source", "gmail"),
        "embedding": None,
    }


def extract_many(mails: list[dict], workers: int = 5) -> list[dict]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(extract, mails))
    return [r for r in results if r]
