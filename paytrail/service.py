"""High-level actions shared by the web app and the MCP server."""

from . import config, db, extractor, gmail_sync, search
from .sample_data import sample_receipts


def load_samples(path=None) -> int:
    n = db.upsert(sample_receipts(), path)
    search.ensure_embeddings(db.all_receipts(path), path)
    return n


def sync_gmail(limit: int | None = None, path=None, progress=None) -> dict:
    """Fetch new receipt emails, extract + nickname them, store and index. Returns counts."""
    say = progress or (lambda msg: None)
    say("Connecting to Gmail...")
    known = db.existing_ids(path)
    mails = gmail_sync.fetch_receipt_emails(limit=limit, skip_ids=known)
    say(f"Found {len(mails)} new payment-like emails. Reading them with AI...")
    receipts = extractor.extract_many(mails)
    db.upsert(receipts, path)
    say("Building the search index...")
    indexed = search.ensure_embeddings(db.all_receipts(path), path)
    return {"emails_checked": len(mails), "receipts_saved": len(receipts), "indexed": indexed}


def status() -> dict:
    return {"openai": config.has_openai(), "gmail": config.has_gmail(), "db": str(config.DB_PATH)}
