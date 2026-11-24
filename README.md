# 🧾 Scrap Saver

**Your Gmail, turned into a searchable record of every payment.**
wHACKiest 2026 · Track 1: Make MCP Matter

## The problem

One of us paid his college fees online. The receipt arrived by email, he didn't save it, and when he needed it later he couldn't find it. Gmail search only works if you remember the exact words, and payment emails often come from a payment gateway, not the college.

## What Scrap Saver does

| Feature | What it means |
|---|---|
| **Auto-capture + nicknames** | Reads payment emails from Gmail and gives each one a simple name like `NST Fees - Sem 1 - Aug 2026` |
| **Search the way you remember** | "Where's my college fee receipt?" finds it even if the email never says "college" |
| **Git-style payment history** | Every payee gets a history, and price changes are flagged ("Netflix +₹50") |
| **Fake-bill check** | Paste a "pay now or your power will be cut" SMS and Scrap Saver checks it against your real bills |
| **MCP server** | All of this is available as MCP tools, so Claude or any MCP assistant can use it |

## Architecture

```
User (Streamlit web app)
        │
        ▼
 AI agent (OpenAI)  ◄──►  Scrap Saver MCP server (FastMCP)
                              ├─ find_receipt
                              ├─ list_subscriptions
                              ├─ price_history
                              ├─ check_bill
                              ├─ rename_receipt
                              └─ sync_gmail
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              Gmail (IMAP,    SQLite +        (Hack day)
              read-only)      embeddings      AWS Lambda + S3,
                                              ElevenLabs voice
```

Flow: **fetch emails → detect receipts → extract + nickname (LLM) → store + index (embeddings) → ask + answer**

## Quick start (5 minutes)

```bash
git clone <this repo>
cd paytrail
python -m venv .venv
# Windows: .venv\Scripts\activate    Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Open `.env` and add your `OPENAI_API_KEY`. Then:

```bash
streamlit run app.py
```

Click **✨ Load demo receipts** in the sidebar and try searching *college fee receipt*.

### Connect your real Gmail (optional)

1. Turn on 2-Step Verification for your Google account.
2. Go to Google Account → Security → **App passwords**, create one called "Scrap Saver".
3. Put your address and the 16-character app password in `.env` (`GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`).
4. Restart the app and click **🔄 Sync Gmail**.

Scrap Saver only **reads** emails that look like receipts. It never sends, deletes or changes anything. Your receipts are stored locally in `data/paytrail.db`, which is not uploaded to GitHub.

### Use it from Claude Desktop (MCP)

Add this to Claude Desktop's `claude_desktop_config.json` (use your own full paths):

```json
{
  "mcpServers": {
    "paytrail": {
      "command": "/full/path/to/paytrail/.venv/bin/python",
      "args": ["/full/path/to/paytrail/mcp_server.py"]
    }
  }
}
```

Then ask Claude: *"Find my college fee receipt"* or *"Is this SMS a scam: ..."*.

## Tests

```bash
python -m pytest -q
```

The tests run fully offline (no API key or Gmail needed): search, price history, fake-bill rules, email parsing, Gmail sync against a fake mail server, and OpenAI model fallback.

## Works without an API key too

With no OpenAI key, Scrap Saver still runs in **keyword mode**: rule-based extraction, keyword search with synonyms (e.g. "college" → fees, tuition), and rule-based scam checks. With a key, it uses AI extraction, meaning-based search and AI scam explanations.

## Roadmap (24-hour build)

- 🎙️ Voice questions and answers with **ElevenLabs** (speech-to-text + text-to-speech)
- ☁️ **AWS Lambda** daily inbox scan + **S3** storage for receipt PDFs
- 📲 Telegram alerts for renewals, price hikes and fake bills
- 📦 "Proof pack": export all receipts for one purpose (fees, tax, reimbursement) as a PDF
- 👨‍👩‍👧 Family mode for parents' bills

## Project structure

```
app.py               Streamlit web app
mcp_server.py        MCP server exposing Scrap Saver tools
paytrail/
  config.py          settings from .env
  gmail_sync.py      read receipt emails from Gmail (IMAP, read-only)
  extractor.py       AI extraction + nicknames (with rule fallback)
  search.py          meaning + keyword search
  history.py         payee history and price changes
  bills.py           fake-bill check
  db.py              SQLite storage
  llm.py             OpenAI wrapper with model fallback
  sample_data.py     demo receipts
tests/test_core.py   offline tests
```
