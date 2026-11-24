"""Offline tests: no OpenAI key or Gmail needed.  Run:  python -m pytest -q"""

import email
from email.message import EmailMessage

import pytest

from paytrail import bills, config, db, extractor, gmail_sync, history, llm, search, service


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    yield


def test_samples_load_and_keyword_search():
    assert service.load_samples() > 10
    top = search.search("where is my college fee receipt")
    assert top and top[0]["payee"] == "Newton School of Technology"
    assert search.search("electricity bill")[0]["payee"] == "BESCOM"
    assert search.search("phone recharge")[0]["payee"] == "Airtel"
    assert search.search("") == []
    assert search.search("zzzzqqq") == []


def test_subscriptions_and_price_change():
    service.load_samples()
    subs = {s["payee"]: s for s in history.subscriptions()}
    assert subs["Netflix"]["latest_change"]["diff"] == 50
    assert subs["Spotify"]["latest_change"] is None
    assert subs["Campus Stay Hostel"]["payments"] == 3
    assert history.find_payee_history("netflix")[-1]["amount"] == 549
    assert history.find_payee_history("nonexistent payee") == []


def test_fake_bill_rules():
    service.load_samples()
    scam = bills.check_bill("Your BESCOM power will be disconnected tonight. Pay Rs 1240 now at http://x.example call 9876543210")
    assert scam["verdict"] == "likely_scam"
    assert scam["red_flags"]
    real = bills.check_bill("BESCOM: your bill of Rs 1,240 for account 4471 is generated.")
    assert real["verdict"] == "matches_real_bill"
    assert real["matched_bill"]["payee"] == "BESCOM"
    unsure = bills.check_bill("Water board bill of Rs 300 is due on 10th.")
    assert unsure["verdict"] == "unsure"


def test_rename_and_clear():
    service.load_samples()
    assert db.rename("sample-nst-sem1", "My college fees")
    assert db.get("sample-nst-sem1")["nickname"] == "My college fees"
    assert not db.rename("missing", "x")
    db.clear()
    assert db.all_receipts() == []


def test_extract_with_fake_llm(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        llm,
        "chat_json",
        lambda system, user: {
            "is_receipt": True, "payee": "Netflix", "amount": "₹1,299.00", "currency": "inr",
            "paid_on": "2026-13-45", "category": "Subscription", "is_subscription": True,
            "billing_period": "monthly", "nickname": "Netflix Premium - Nov 2026", "summary": "renewal",
        },
    )
    mail = {"id": "<a@b>", "subject": "Renewed", "sender": "Netflix <x@y>", "date": "2026-11-01", "body": "Thanks", "attachments": [], "link": ""}
    r = extractor.extract(mail)
    assert r["amount"] == 1299.0 and r["currency"] == "INR"
    assert r["paid_on"] == "2026-11-01"  # invalid model date falls back to email date
    monkeypatch.setattr(llm, "chat_json", lambda s, u: {"is_receipt": False})
    assert extractor.extract(mail) is None


def test_extract_without_key_uses_heuristic():
    mail = {"id": "<h@1>", "subject": "Payment of Rs. 2,500 received", "sender": "Acme Coaching <billing@acme.example>",
            "date": "2026-07-01", "body": "We received INR 2,500.00 for your course.", "attachments": [], "link": ""}
    r = extractor.extract(mail)
    assert r["amount"] == 2500.0 and r["payee"] == "Acme Coaching"


def test_semantic_search_with_fake_embeddings(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")

    def fake_embed(texts):
        vecs = []
        for t in texts:
            t = t.lower()
            vecs.append([1.0 if ("tuition" in t or "college" in t or "newton" in t) else 0.0,
                         1.0 if ("netflix" in t or "movies" in t) else 0.0, 0.1])
        return vecs

    monkeypatch.setattr(llm, "embed", fake_embed)
    service.load_samples()
    assert all(r["embedding"] for r in db.all_receipts())
    assert search.search("tuition")[0]["payee"] == "Newton School of Technology"


def test_llm_parse_json_variants():
    assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('Sure! {"a": 2} hope that helps') == {"a": 2}
    with pytest.raises(Exception):
        llm.parse_json("")


def test_email_parsing():
    msg = EmailMessage()
    msg["Subject"] = "=?utf-8?q?Payment_received_=E2=82=B9500?="
    msg["From"] = "Shop <s@shop.example>"
    msg.set_content("Plain text short")
    msg.add_alternative("<html><body><p>Thanks for paying <b>Rs 500</b> for your order number 123.</p><script>x()</script></body></html>", subtype="html")
    msg.add_attachment(b"%PDF-1.4", maintype="application", subtype="pdf", filename="invoice.pdf")
    parsed = email.message_from_bytes(msg.as_bytes())
    body, att = gmail_sync._body_and_attachments(parsed)
    assert "Rs 500" in body and "x()" not in body
    assert att == ["invoice.pdf"]
    assert "₹500" in gmail_sync._decode(parsed["Subject"])
    assert gmail_sync.gmail_link("<abc@mail>").endswith("rfc822msgid%3Aabc%40mail")


def test_gmail_requires_config(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_ADDRESS", "")
    with pytest.raises(gmail_sync.GmailError):
        gmail_sync.fetch_receipt_emails()


class _FakeResp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]


class _FakeClient:
    def __init__(self, bad_models):
        self.bad = set(bad_models)
        self.calls = []
        outer = self

        class _Completions:
            def create(self, model, messages, response_format):
                outer.calls.append(model)
                if model in outer.bad:
                    raise RuntimeError(f"The model `{model}` does not exist or you do not have access to it.")
                return _FakeResp('{"ok": true}')

        self.chat = type("Chat", (), {"completions": _Completions()})()


def test_model_fallback(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "OPENAI_MODEL", "gpt-unknown")
    fake = _FakeClient({"gpt-unknown", "gpt-5-mini"})
    monkeypatch.setattr(llm, "_client", fake)
    monkeypatch.setattr(llm, "_working_model", None)
    assert llm.chat_json("s", "u") == {"ok": True}
    assert fake.calls == ["gpt-unknown", "gpt-5-mini", "gpt-4.1-mini"]
    assert llm.active_model() == "gpt-4.1-mini"


def test_non_model_error_does_not_loop(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")

    class Boom:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    raise RuntimeError("Rate limit reached, try again")

    monkeypatch.setattr(llm, "_client", Boom())
    monkeypatch.setattr(llm, "_working_model", None)
    with pytest.raises(llm.LLMError):
        llm.chat_json("s", "u")
    # extractor falls back to rules instead of crashing
    mail = {"id": "<z@1>", "subject": "Paid Rs 99", "sender": "Shop <a@b>", "date": "2026-11-01", "body": "", "attachments": [], "link": ""}
    assert extractor.extract(mail)["amount"] == 99.0


def test_gmail_fetch_with_fake_imap(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_ADDRESS", "me@gmail.com")
    monkeypatch.setattr(config, "GMAIL_APP_PASSWORD", "abcdabcdabcdabcd")

    def make(i, subject):
        m = EmailMessage()
        m["Subject"], m["From"], m["Message-ID"] = subject, "Netflix <n@x>", f"<id{i}@x>"
        m["Date"] = "Tue, 12 Nov 2026 10:00:00 +0530"
        m.set_content(f"You paid Rs {i}00")
        return m.as_bytes()

    store = {b"1": make(1, "Receipt one"), b"2": make(2, "Receipt two"), b"3": make(3, "Receipt three")}
    seen = {}

    class FakeIMAP:
        error = Exception

        def __init__(self, host, port):
            pass

        def login(self, u, p):
            seen["login"] = (u, p)

        def select(self, box, readonly=True):
            return ("OK", [b"3"])

        def uid(self, cmd, *args):
            if cmd == "SEARCH":
                seen["query"] = args
                return ("OK", [b"1 2 3"])
            return ("OK", [(b"x", store[args[0]])])

        def logout(self):
            pass

    monkeypatch.setattr(gmail_sync.imaplib, "IMAP4_SSL", FakeIMAP)
    mails = gmail_sync.fetch_receipt_emails(limit=2, skip_ids={"<id3@x>"})
    assert [m["subject"] for m in mails] == ["Receipt two", "Receipt one"]
    assert mails[0]["date"] == "2026-11-12" and "Rs 200" in mails[0]["body"]
    assert seen["query"][0] == "X-GM-RAW" and b"after:" in seen["query"][1]


def test_provider_selection(monkeypatch):
    import importlib

    for k in ("LLM_PROVIDER", "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "LLM_MODEL", "OPENAI_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    cfg = importlib.reload(config)
    assert cfg.LLM_PROVIDER == "gemini" and cfg.OPENAI_API_KEY == "g-key"
    assert "generativelanguage" in cfg.BASE_URL and cfg.EMBEDDING_MODEL
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "q-key")
    cfg = importlib.reload(config)
    assert cfg.LLM_PROVIDER == "groq" and cfg.OPENAI_API_KEY == "q-key" and cfg.EMBEDDING_MODEL == ""
    assert llm.embed(["x"]) is None  # no embeddings on groq -> keyword search
    monkeypatch.delenv("LLM_PROVIDER")
    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.delenv("GEMINI_API_KEY")
    cfg = importlib.reload(config)
    assert cfg.LLM_PROVIDER == "openai" and cfg.BASE_URL is None


def test_json_mode_unsupported_retries_without(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "k")
    calls = []

    class C:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    calls.append("response_format" in kw)
                    if "response_format" in kw:
                        raise RuntimeError("response_format json_object is not supported for this model")
                    return _FakeResp('Here you go: {"ok": 1}')

    monkeypatch.setattr(llm, "_client", C())
    monkeypatch.setattr(llm, "_working_model", None)
    assert llm.chat_json("s", "u") == {"ok": 1}
    assert calls == [True, False]
