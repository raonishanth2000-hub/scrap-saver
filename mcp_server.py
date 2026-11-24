"""Scrap Saver MCP server: lets Claude Desktop or any MCP client use Scrap Saver's tools.

Run:  python mcp_server.py        (stdio transport)
"""

from mcp.server.fastmcp import FastMCP

from paytrail import bills, db, history, search, service

mcp = FastMCP("Scrap Saver")


def _slim(r: dict) -> dict:
    keys = ["id", "nickname", "payee", "amount", "currency", "paid_on", "category", "summary", "attachments", "gmail_link"]
    return {k: r.get(k) for k in keys}


@mcp.tool()
def find_receipt(query: str, limit: int = 5) -> list[dict]:
    """Find payment receipts by what the user remembers, e.g. 'college fee receipt' or 'electricity bill October'."""
    return [_slim(r) | {"score": r.get("score")} for r in search.search(query, limit=max(1, min(limit, 20)))]


@mcp.tool()
def list_subscriptions() -> list[dict]:
    """List recurring payments (subscriptions, rent, bills) with latest amount and any price change."""
    return [{k: v for k, v in s.items() if k != "history"} for s in history.subscriptions()]


@mcp.tool()
def price_history(payee: str) -> dict:
    """Show every payment made to one payee (like git log) and the price changes between them."""
    items = history.find_payee_history(payee)
    return {"payee": payee, "payments": [_slim(i) for i in items], "changes": history.price_changes(items)}


@mcp.tool()
def check_bill(message: str) -> dict:
    """Check a suspicious bill/payment SMS against the user's real bills and flag likely scams."""
    res = bills.check_bill(message)
    res["matched_bill"] = _slim(res["matched_bill"]) if res.get("matched_bill") else None
    res["related_bills"] = [_slim(r) for r in res.get("related_bills", [])]
    return res


@mcp.tool()
def rename_receipt(receipt_id: str, nickname: str) -> str:
    """Give a receipt a new nickname so it is easier to find later."""
    return "Renamed." if db.rename(receipt_id, nickname) else "No receipt with that id."


@mcp.tool()
def sync_gmail(limit: int = 30) -> dict:
    """Read new receipt emails from Gmail, nickname them and add them to the search index."""
    return service.sync_gmail(limit=max(1, min(limit, 200)))


if __name__ == "__main__":
    mcp.run()
