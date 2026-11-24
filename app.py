"""Scrap Saver web app. Run with:  streamlit run app.py"""

import streamlit as st

from paytrail import bills, config, db, history, llm, search, service
from paytrail.gmail_sync import GmailError

st.set_page_config(page_title="Scrap Saver", page_icon="🧾", layout="wide")

CUR = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def money(amount, currency="INR"):
    if amount is None:
        return "—"
    sym = CUR.get((currency or "INR").upper(), (currency or "") + " ")
    return f"{sym}{amount:,.0f}" if float(amount).is_integer() else f"{sym}{amount:,.2f}"


def receipt_card(r, key_prefix=""):
    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            st.markdown(f"**{r['nickname']}**")
            st.caption(f"{r.get('payee') or ''} · {r.get('category') or ''} · {r.get('paid_on') or ''}")
            if r.get("summary"):
                st.write(r["summary"])
            meta = []
            if r.get("subject"):
                meta.append(f"Email: *{r['subject']}*")
            if r.get("attachments"):
                meta.append("📎 " + ", ".join(r["attachments"]))
            if meta:
                st.caption(" · ".join(meta))
        with right:
            st.markdown(f"### {money(r.get('amount'), r.get('currency'))}")
            if r.get("gmail_link"):
                st.link_button("Open in Gmail", r["gmail_link"], width="stretch")
            elif r.get("source") == "sample":
                st.caption("Demo receipt")
        with st.expander("Rename"):
            new = st.text_input("Nickname", value=r["nickname"], key=f"{key_prefix}rn-{r['id']}")
            if st.button("Save name", key=f"{key_prefix}save-{r['id']}") and new.strip():
                db.rename(r["id"], new)
                st.success("Saved")
                st.rerun()


# ---------------- Sidebar ----------------
with st.sidebar:
    st.title("🧾 Scrap Saver")
    st.caption("Your Gmail, turned into a searchable record of every payment.")
    st.divider()
    st.markdown(f"**AI ({config.LLM_PROVIDER.title()}):** {'✅ connected' if config.has_openai() else '⚠️ no key (keyword mode)'}")
    st.markdown(f"**Gmail:** {'✅ configured' if config.has_gmail() else '⚠️ not configured'}")

    if st.button("🔄 Sync Gmail", width="stretch", disabled=not config.has_gmail()):
        box = st.empty()
        try:
            with st.spinner("Syncing..."):
                result = service.sync_gmail(progress=lambda m: box.info(m))
            box.success(f"Checked {result['emails_checked']} emails, saved {result['receipts_saved']} receipts.")
        except GmailError as err:
            box.error(str(err))
        except llm.LLMError as err:
            box.error(str(err))
        except Exception as err:  # noqa: BLE001 - show any problem instead of crashing the page
            box.error(f"Sync failed: {err}")

    if st.button("✨ Load demo receipts", width="stretch"):
        with st.spinner("Loading demo data..."):
            n = service.load_samples()
        st.success(f"Loaded {n} demo receipts.")

    with st.expander("Danger zone"):
        if st.button("Delete all saved receipts"):
            db.clear()
            st.warning("All receipts deleted.")

    count = len(db.all_receipts())
    st.caption(f"{count} receipts saved · model: {llm.active_model() if config.has_openai() else 'none'}")

# ---------------- Main ----------------
st.header("Find any payment in seconds")
tab_search, tab_subs, tab_bill, tab_all = st.tabs(["🔍 Search", "🔁 Subscriptions & history", "🚨 Fake-bill check", "📚 All receipts"])

with tab_search:
    st.write("Ask the way you remember it, e.g. *college fee receipt*, *electricity bill*, *what did I pay Netflix*.")
    with st.form("search"):
        q = st.text_input("Search", placeholder="Where's my college fee receipt?", label_visibility="collapsed")
        go = st.form_submit_button("Search", type="primary")
    if go:
        if not q.strip():
            st.info("Type something to search for.")
        elif count == 0:
            st.warning("No receipts yet. Click **Sync Gmail** or **Load demo receipts** in the sidebar.")
        else:
            results = search.search(q, limit=5)
            if not results:
                st.info("No matching receipts. Try different words, like the shop or college name.")
            for i, r in enumerate(results):
                receipt_card(r, key_prefix=f"s{i}-")

with tab_subs:
    subs = history.subscriptions()
    if not subs:
        st.info("No recurring payments found yet.")
    else:
        monthly = sum((s["latest_amount"] or 0) for s in subs if (s["billing_period"] or "monthly").lower().startswith("month"))
        c1, c2, c3 = st.columns(3)
        c1.metric("Recurring payees", len(subs))
        c2.metric("Monthly spend (latest)", money(monthly))
        c3.metric("Price changes found", sum(1 for s in subs if s["latest_change"]))
        for s in subs:
            with st.container(border=True):
                a, b = st.columns([3, 2])
                with a:
                    st.markdown(f"**{s['payee']}** · {s['category'] or ''}")
                    st.caption(f"{s['payments']} payments · last paid {s['last_paid']} · total {money(s['total'], s['currency'])}")
                with b:
                    st.markdown(f"#### {money(s['latest_amount'], s['currency'])}")
                ch = s["latest_change"]
                if ch:
                    arrow = "⬆️ went up" if ch["diff"] > 0 else "⬇️ went down"
                    msg = f"Price {arrow} by {money(abs(ch['diff']), s['currency'])} ({ch['pct']:+}%) on {ch['on']}: {money(ch['from'], s['currency'])} → {money(ch['to'], s['currency'])}"
                    (st.warning if ch["diff"] > 0 else st.success)(msg)
                with st.expander("History (like git log)"):
                    for h in reversed(s["history"]):
                        st.markdown(f"`{h['paid_on']}`  **{money(h['amount'], s['currency'])}**  {h['nickname']}")

with tab_bill:
    st.write("Got a scary *\"pay now or your power will be cut\"* message? Paste it here. Scrap Saver checks it against your real bills.")
    example = "Dear customer, your BESCOM electricity will be disconnected TONIGHT at 9:30 PM due to unpaid bill of Rs 1,240. Pay immediately: http://bescom-pay.example/x Call 9876543210"
    with st.form("bill"):
        msg = st.text_area("Message", height=120, placeholder=example)
        c1, c2 = st.columns([1, 4])
        check = c1.form_submit_button("Check message", type="primary")
        use_example = c2.form_submit_button("Try an example scam")
    if use_example:
        msg = example
        st.code(example, language=None)
    if (check or use_example) and msg.strip():
        with st.spinner("Checking..."):
            res = bills.check_bill(msg)
        verdict = res["verdict"]
        if verdict == "likely_scam":
            st.error(f"🚨 Likely a scam. {res['reason']}")
        elif verdict == "matches_real_bill":
            st.success(f"✅ Matches a real bill. {res['reason']}")
        else:
            st.warning(f"🤔 Not sure. {res['reason']}")
        if res.get("advice"):
            st.markdown(f"**What to do:** {res['advice']}")
        if res["red_flags"]:
            st.markdown("**Warning signs found:**")
            for f in res["red_flags"]:
                st.markdown(f"- {f}")
        if res.get("matched_bill"):
            st.markdown("**Your real bill:**")
            receipt_card(res["matched_bill"], key_prefix="bill-")
        elif res.get("related_bills"):
            with st.expander("Related real bills in your email"):
                for i, r in enumerate(res["related_bills"]):
                    receipt_card(r, key_prefix=f"rel{i}-")
    elif check:
        st.info("Paste a message first.")

with tab_all:
    rows = db.all_receipts()
    if not rows:
        st.info("No receipts yet.")
    else:
        st.dataframe(
            [
                {"Nickname": r["nickname"], "Payee": r["payee"], "Amount": money(r["amount"], r["currency"]),
                 "Date": r["paid_on"], "Category": r["category"], "Recurring": "Yes" if r["is_subscription"] else ""}
                for r in rows
            ],
            width="stretch",
            hide_index=True,
        )
