"""Backfill journal_entries from billing_records (NOWPayments + Stripe history).

For every paid/activated billing record we post:
  DR cash                       (asset increased)
  CR subscription_revenue       (revenue earned)

Only entries with status in ('finished','confirmed','activated','succeeded') and amount_usd > 0.
"""
import sqlite3, sys, os
sys.path.insert(0, "/opt/Murphy-System")
from src.murphy_treasury import get_treasury

t = get_treasury()
with sqlite3.connect("/var/lib/murphy-production/billing.db", timeout=10) as b:
    b.row_factory = sqlite3.Row
    rows = b.execute("""
        SELECT id, tenant_id, email, tier, amount_usd, status, created_at, payment_id
        FROM billing_records
        ORDER BY created_at ASC
    """).fetchall()

posted = skipped = 0
for r in rows:
    amt = float(r["amount_usd"] or 0)
    status = (r["status"] or "").lower()
    paid = status in ("finished", "confirmed", "activated", "succeeded", "paid", "completed")
    if amt <= 0 or not paid:
        skipped += 1
        continue
    t._journal(
        description    = f"Subscription payment — {r['tier']} ({r['email']})",
        debit_account  = "cash",
        credit_account = "subscription_revenue",
        amount_usd     = amt,
        reference      = r["payment_id"] or r["id"],
        category       = "subscription",
        business_line  = "platform",
    )
    posted += 1

print(f"Backfill complete: posted={posted}, skipped (unpaid/zero)={skipped}, total billing rows={len(rows)}")

# Show current state
with sqlite3.connect("/var/lib/murphy-production/treasury.db") as t2:
    n = t2.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
    tot = t2.execute("SELECT COALESCE(SUM(amount_usd),0) FROM journal_entries").fetchone()[0]
    print(f"journal_entries now: {n} entries, ${tot:.2f} total volume")
