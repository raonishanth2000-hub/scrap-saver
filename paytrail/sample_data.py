"""Made-up demo receipts so the app can be shown without connecting a real inbox."""

SAMPLES = [
    {"id": "sample-nst-sem1", "nickname": "NST Fees - Sem 1 - Aug 2026", "payee": "Newton School of Technology", "amount": 150000, "currency": "INR",
     "paid_on": "2026-08-04", "category": "Education", "is_subscription": False, "billing_period": "one-time",
     "summary": "Semester 1 tuition / college fee payment receipt for the AI/ML programme.",
     "subject": "Payment successful - Order #PG82731", "sender": "Payment Gateway <no-reply@payments.example>", "attachments": ["Receipt_PG82731.pdf"]},
    {"id": "sample-hostel-aug", "nickname": "Hostel Rent - Aug 2026", "payee": "Campus Stay Hostel", "amount": 14000, "currency": "INR",
     "paid_on": "2026-08-06", "category": "Rent", "is_subscription": True, "billing_period": "monthly",
     "summary": "Monthly hostel rent including food (mess) for August.", "subject": "Rent received - August", "sender": "Campus Stay <accounts@campusstay.example>", "attachments": []},
    {"id": "sample-hostel-sep", "nickname": "Hostel Rent - Sep 2026", "payee": "Campus Stay Hostel", "amount": 14000, "currency": "INR",
     "paid_on": "2026-09-05", "category": "Rent", "is_subscription": True, "billing_period": "monthly",
     "summary": "Monthly hostel rent including food (mess) for September.", "subject": "Rent received - September", "sender": "Campus Stay <accounts@campusstay.example>", "attachments": []},
    {"id": "sample-hostel-oct", "nickname": "Hostel Rent - Oct 2026", "payee": "Campus Stay Hostel", "amount": 15000, "currency": "INR",
     "paid_on": "2026-10-05", "category": "Rent", "is_subscription": True, "billing_period": "monthly",
     "summary": "Monthly hostel rent including food (mess) for October.", "subject": "Rent received - October", "sender": "Campus Stay <accounts@campusstay.example>", "attachments": []},
    {"id": "sample-netflix-sep", "nickname": "Netflix Standard - Sep 2026", "payee": "Netflix", "amount": 499, "currency": "INR",
     "paid_on": "2026-09-12", "category": "Subscription", "is_subscription": True, "billing_period": "monthly",
     "summary": "Netflix monthly membership renewal, movies and shows.", "subject": "Your Netflix membership has been renewed", "sender": "Netflix <info@account.netflix.example>", "attachments": []},
    {"id": "sample-netflix-oct", "nickname": "Netflix Standard - Oct 2026", "payee": "Netflix", "amount": 499, "currency": "INR",
     "paid_on": "2026-10-12", "category": "Subscription", "is_subscription": True, "billing_period": "monthly",
     "summary": "Netflix monthly membership renewal, movies and shows.", "subject": "Your Netflix membership has been renewed", "sender": "Netflix <info@account.netflix.example>", "attachments": []},
    {"id": "sample-netflix-nov", "nickname": "Netflix Standard - Nov 2026", "payee": "Netflix", "amount": 549, "currency": "INR",
     "paid_on": "2026-11-12", "category": "Subscription", "is_subscription": True, "billing_period": "monthly",
     "summary": "Netflix monthly membership renewal at the new price.", "subject": "Your Netflix membership has been renewed", "sender": "Netflix <info@account.netflix.example>", "attachments": []},
    {"id": "sample-spotify-oct", "nickname": "Spotify Student - Oct 2026", "payee": "Spotify", "amount": 59, "currency": "INR",
     "paid_on": "2026-10-20", "category": "Subscription", "is_subscription": True, "billing_period": "monthly",
     "summary": "Spotify Premium Student plan, music streaming.", "subject": "Your Spotify receipt", "sender": "Spotify <no-reply@spotify.example>", "attachments": []},
    {"id": "sample-spotify-nov", "nickname": "Spotify Student - Nov 2026", "payee": "Spotify", "amount": 59, "currency": "INR",
     "paid_on": "2026-11-20", "category": "Subscription", "is_subscription": True, "billing_period": "monthly",
     "summary": "Spotify Premium Student plan, music streaming.", "subject": "Your Spotify receipt", "sender": "Spotify <no-reply@spotify.example>", "attachments": []},
    {"id": "sample-bescom-oct", "nickname": "BESCOM Electricity Bill - Oct 2026", "payee": "BESCOM", "amount": 1240, "currency": "INR",
     "paid_on": "2026-10-28", "category": "Utilities", "is_subscription": True, "billing_period": "monthly",
     "summary": "Electricity (power) bill paid for the flat, account ending 4471.", "subject": "Electricity bill payment successful", "sender": "BESCOM Payments <noreply@bescom.example>", "attachments": ["BESCOM_Receipt_Oct.pdf"]},
    {"id": "sample-airtel-nov", "nickname": "Airtel Prepaid Recharge - Nov 2026", "payee": "Airtel", "amount": 349, "currency": "INR",
     "paid_on": "2026-11-02", "category": "Telecom", "is_subscription": True, "billing_period": "monthly",
     "summary": "Mobile phone prepaid recharge, 28 days unlimited plan.", "subject": "Recharge successful", "sender": "Airtel <noreply@airtel.example>", "attachments": []},
    {"id": "sample-amazon-laptopstand", "nickname": "Amazon Laptop Stand - Sep 2026", "payee": "Amazon", "amount": 899, "currency": "INR",
     "paid_on": "2026-09-18", "category": "Shopping", "is_subscription": False, "billing_period": "one-time",
     "summary": "Order of an adjustable laptop stand for the hostel desk.", "subject": "Your Amazon order has been placed", "sender": "Amazon <order-update@amazon.example>", "attachments": []},
    {"id": "sample-swiggy-nov", "nickname": "Swiggy Dinner Order - Nov 2026", "payee": "Swiggy", "amount": 412, "currency": "INR",
     "paid_on": "2026-11-15", "category": "Food", "is_subscription": False, "billing_period": "one-time",
     "summary": "Food delivery order from a restaurant, dinner.", "subject": "Your Swiggy order was delivered", "sender": "Swiggy <noreply@swiggy.example>", "attachments": []},
    {"id": "sample-devfolio-hack", "nickname": "Hackathon Travel - Bus to Delhi - Oct 2026", "payee": "RedBus", "amount": 2150, "currency": "INR",
     "paid_on": "2026-10-02", "category": "Travel", "is_subscription": False, "billing_period": "one-time",
     "summary": "Bus ticket booking for travel to a hackathon.", "subject": "Your bus ticket is confirmed", "sender": "redBus <tickets@redbus.example>", "attachments": ["Ticket.pdf"]},
]


def sample_receipts() -> list[dict]:
    out = []
    for s in SAMPLES:
        r = dict(s)
        r.setdefault("email_date", r["paid_on"])
        r["gmail_link"] = ""
        r["source"] = "sample"
        r["embedding"] = None
        out.append(r)
    return out
