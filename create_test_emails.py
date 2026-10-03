#!/usr/bin/env python3
"""Generate synthetic test emails for P2 demo (EML format)."""

import os
from pathlib import Path
from datetime import datetime, timedelta
from email.message import EmailMessage

EMAILS_DIR = Path(__file__).parent / "Emails" / "test_emails"
EMAILS_DIR.mkdir(parents=True, exist_ok=True)

def create_email(name_stem, from_addr, to_addr, subject, body, sent_at=None):
    """Create an .eml file (RFC 5322 email format)."""
    if sent_at is None:
        sent_at = datetime.now()

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = sent_at.strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg.set_content(body)

    # Save as .eml (can be opened by Outlook and "Save As" to .msg)
    path = EMAILS_DIR / f"{name_stem}.eml"
    with open(path, "w") as f:
        f.write(msg.as_string())
    print(f"✅ {path.name}")
    return path

# P1 Alert: Q4 order cancellation (should be Priority 1)
create_email(
    "P1_ALERT_q4_order",
    "Mark Chen <mark.chen@client.com>",
    "jacky@yarnscolors.com",
    "URGENT: Q4 Order Cancelled - Customer Escalation",
    """Mark,

Our largest Q4 customer just cancelled their entire order. We're looking at a $500K revenue loss.

Who: Jackie needs to call this customer by EOD
What: Q4 order cancelled by customer, material revenue impact
Why: If we don't engage today, they'll move to competitors
Action: Call customer + strategy meeting with sales leadership

Deadline: Today at 5 PM

Mark Chen
VP Sales""",
    datetime.now() - timedelta(hours=1)
)

# P2 Alert: Supplier decision (should be Priority 2)
create_email(
    "P2_ALERT_supplier_price",
    "Linda Zhou <linda.zhou@supplier.com>",
    "jacky@yarnscolors.com",
    "Supplier Price Increase - Decision Required",
    """Hi Jacky,

Our main dye supplier is raising prices 15% effective next month. We need to decide:
1. Accept new prices
2. Switch suppliers (3-month lead time)
3. Lock in current prices for 6 months (costs us 5%)

Who: You need to decide on supplier strategy
What: 15% price increase from our main supplier
Why: Without a decision, we auto-accept at higher cost
Action: Decide by Friday which option works for us

Deadline: Friday COB

Linda
Supply Chain""",
    datetime.now() - timedelta(hours=2)
)

# P3 Reference: Market update (just FYI)
create_email(
    "P3_REFERENCE_market_update",
    "analyst@marketresearch.com",
    "jacky@yarnscolors.com",
    "Market Report: Q4 Textile Trends",
    """Industry Alert,

Our Q4 textile market analysis shows:
- 12% decline in luxury segment
- 8% growth in sustainable fabrics
- New entrant from Vietnam gaining 3% share

No action required. FYI for strategic planning.

See attached full report.

Analytics Team""",
    datetime.now() - timedelta(days=1)
)

# P4 Filter: Promotional email
create_email(
    "P4_FILTER_vip_summit",
    "events@globalleadersummit.com",
    "jacky@yarnscolors.com",
    "URGENT: Action required – your VIP seat expires at midnight",
    """Dear Jackie,

You've been selected for an exclusive VIP pass to the Global Leaders Summit 2026 at 40% off. This offer expires at midnight tonight and won't be repeated.

Immediate action required: secure your seat now before it's released to the waitlist.

[Claim My Seat]

Global Leaders Summit Team
You're receiving this because you subscribed to our updates. Unsubscribe here.""",
    datetime.now() - timedelta(hours=3)
)

# Uncertain: Vague warning (should be uncertain/needs evidence)
create_email(
    "UNCERTAIN_vague_warning",
    "Tom Yeh <tom.yeh@ops.com>",
    "jacky@yarnscolors.com",
    "Heads up — something you should know about",
    """Jacky,

I think there's a real problem brewing with one of our bigger accounts. It's not going to resolve itself, honestly.

I think it's worth a conversation soon to hear the details.

Tom""",
    datetime.now() - timedelta(hours=4)
)

# Threading: Original message + reply (same thread)
original = create_email(
    "THREAD_original_fabric_samples",
    "jack@supplier.com",
    "jacky@yarnscolors.com",
    "New Fabric Samples - Spring 2026 Collection",
    """Hi Jacky,

We've prepared 5 new fabric samples for your Spring 2026 collection. They're ready for review.

Quality improvements:
- 20% better durability
- 15% cost reduction
- Same aesthetic

Can you review and give feedback? Timeline matters for production.

Jack
Supplier""",
    datetime.now() - timedelta(days=2)
)

# Reply to original (should be grouped as same thread)
create_email(
    "THREAD_reply_fabric_samples",
    "jacky@yarnscolors.com",
    "jack@supplier.com",
    "RE: New Fabric Samples - Spring 2026 Collection",
    """Jack,

Thanks for the samples. I'll review this week and get back to you by Friday.

The durability improvement is key for us.

Jacky

On 2026-10-01, Jack wrote:
> We've prepared 5 new fabric samples for your Spring 2026 collection...
""",
    datetime.now() - timedelta(days=1)
)

# Forward (should be grouped with original)
create_email(
    "THREAD_fwd_fabric_samples",
    "jacky@yarnscolors.com",
    "sarah@design.com",
    "FWD: New Fabric Samples - Spring 2026 Collection",
    """Sarah,

FYI - new samples from Jack's team. Can you review the durability specs?

---
Original message:
We've prepared 5 new fabric samples for your Spring 2026 collection...
""",
    datetime.now() - timedelta(hours=12)
)

print("\n✅ All test emails created in:", EMAILS_DIR)
