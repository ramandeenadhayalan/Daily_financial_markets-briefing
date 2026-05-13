import smtplib
from email.message import EmailMessage

def send_email(markdown_content):
    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT", "465"))
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipients = os.getenv("EMAIL_RECIPIENTS", "")

    if not all([host, port, sender, password, recipients]):
        print("Email settings not fully configured; skipping email send.")
        return

    recipient_list = [r.strip() for r in recipients.split(",") if r.strip()]

    msg = EmailMessage()
    msg["Subject"] = "Daily Macro Briefing"
    msg["From"] = sender
    msg["To"] = ", ".join(recipient_list)
    msg.set_content(markdown_content)

    with smtplib.SMTP_SSL(host, port) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)

    print("Email sent successfully.")

def main():
    items = fetch_market_news()
    md = build_markdown(items)
    OUT_FILE.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_FILE}")
    send_email(md)

import os
from datetime import datetime, timezone
from pathlib import Path
import requests

API_KEY = os.getenv("FINNHUB_API_KEY")
if not API_KEY:
    raise SystemExit("Missing FINNHUB_API_KEY environment variable")

OUT_DIR = Path("output")
OUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUT_DIR / "daily_briefing.md"

KEYWORDS_RISK_OFF = [
    "iran", "war", "conflict", "sanctions", "oil", "hormuz", "inflation",
    "tariff", "taiwan", "missile", "attack", "rates", "hawkish"
]
KEYWORDS_RISK_ON = [
    "soft landing", "rate cut", "cooling inflation", "stimulus", "deal",
    "ceasefire", "disinflation", "growth"
]

def fetch_market_news(category: str = "general", limit: int = 12):
    url = "https://finnhub.io/api/v1/news"
    params = {"category": category, "token": API_KEY}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    items = r.json()
    return items[:limit]

def score_text(text: str):
    t = (text or "").lower()
    risk_off = sum(1 for k in KEYWORDS_RISK_OFF if k in t)
    risk_on = sum(1 for k in KEYWORDS_RISK_ON if k in t)
    return risk_off, risk_on

def classify_tone(items):
    off = 0
    on = 0
    for item in items:
        text = f"{item.get('headline', '')} {item.get('summary', '')}"
        a, b = score_text(text)
        off += a
        on += b
    if off >= on + 2:
        return "Risk-off"
    if on >= off + 2:
        return "Risk-on"
    return "Neutral"

def top_bullets(items, n=8):
    scored = []
    for item in items:
        text = f"{item.get('headline', '')} {item.get('summary', '')}"
        off, on = score_text(text)
        score = off + on
        scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [item for _, item in scored[:n]]
    bullets = []
    for item in top:
        headline = item.get("headline", "No headline").strip()
        source = item.get("source", "Unknown source")
        url = item.get("url", "")
        bullets.append(f"- {headline} ({source}) - {url}")
    return bullets

def build_markdown(items):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tone = classify_tone(items)
    bullets = top_bullets(items)
    body = [
        "# Daily Macro Briefing",
        "",
        f"Generated: {now}",
        f"Market tone: **{tone}**",
        "",
        "## Top headlines",
        *bullets,
        "",
        "## Notes",
        "- This is a rules-based starter version using Finnhub market news.",
        "- Next step: add indices, oil, FX and UK gilts for a richer signal.",
    ]
    return "\n".join(body)

def main():
    items = fetch_market_news()
    md = build_markdown(items)
    OUT_FILE.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_FILE}")

if __name__ == "__main__":
    main()
