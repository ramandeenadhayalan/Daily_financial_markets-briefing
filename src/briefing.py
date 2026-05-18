import os
import re
import html
import smtplib
from datetime import datetime, timezone
from pathlib import Path
from email.message import EmailMessage

import requests
import nltk
from newspaper import Article

API_KEY = os.getenv("FINNHUB_API_KEY")
if not API_KEY:
    raise SystemExit("Missing FINNHUB_API_KEY environment variable")

OUT_DIR = Path("output")
OUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUT_DIR / "daily_briefing.md"

KEYWORDS_RISK_OFF = [
    "artificial intelligence", "investment management", "iran", "war", "conflict", "sanctions", "oil", "hormuz", "inflation",
    "tariff", "taiwan", "missile", "attack", "rates", "hawkish", "gold"
]
KEYWORDS_RISK_ON = [
    "soft landing", "rate cut", "cooling inflation", "stimulus", "deal",
    "ceasefire", "disinflation", "growth"
]

CATEGORY_KEYWORDS = {
    "Macro & Central Banks": [
        "inflation", "cpi", "ppi", "rate", "rates", "fed", "ecb", "boe",
        "bank of england", "central bank", "yield", "recession", "growth",
        "gdp", "jobs", "payrolls", "hawkish", "dovish", "disinflation", "gold" 
    ],
    "Geopolitics": [
        "iran", "israel", "gaza", "ukraine", "russia", "china", "taiwan",
        "war", "truce", "sanctions", "attack", "military", "missile",
        "hormuz", "netanyahu", "trump", "white house", "india"
    ],
    "Energy & Commodities": [
        "oil", "brent", "crude", "gas", "lng", "opec", "refining",
        "supply", "demand", "gold", "copper", "commodity", "commodities"
    ],
    "Markets & Credit": [
        "stocks", "equities", "bond", "bonds", "credit", "spread", "market",
        "shares", "profit", "earnings", "hedge", "volatility", "vix",
        "default", "fund", "treasury", "investors", "retail investors"
    ],
}

CATEGORY_ORDER = [
    "Macro & Central Banks",
    "Geopolitics",
    "Energy & Commodities",
    "Markets & Credit",
]

NLTK_READY = False


def ensure_nltk():
    global NLTK_READY
    if NLTK_READY:
        return

    resources = [
        ("tokenizers/punkt", "punkt"),
        ("corpora/stopwords", "stopwords"),
    ]

    for path_name, download_name in resources:
        try:
            nltk.data.find(path_name)
        except LookupError:
            nltk.download(download_name, quiet=True)

    NLTK_READY = True


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


def classify_category(item):
    text = f"{item.get('headline', '')} {item.get('summary', '')}".lower()
    best_category = "Markets & Credit"
    best_score = 0

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category


def grouped_headlines(items, max_per_section=3):
    buckets = {category: [] for category in CATEGORY_ORDER}

    scored_items = []
    for item in items:
        text = f"{item.get('headline', '')} {item.get('summary', '')}"
        off, on = score_text(text)
        relevance = off + on
        category = classify_category(item)
        scored_items.append((relevance, category, item))

    scored_items.sort(key=lambda x: x[0], reverse=True)

    for _, category, item in scored_items:
        if len(buckets[category]) < max_per_section:
            buckets[category].append(item)

    return buckets


def split_summary_into_bullets(summary_text, max_bullets=3):
    if not summary_text:
        return []

    parts = re.split(r'(?<=[.!?])\s+', summary_text.strip())
    bullets = []

    for part in parts:
        cleaned = part.strip().replace("\n", " ")
        if len(cleaned) < 40:
            continue
        bullets.append(cleaned)
        if len(bullets) >= max_bullets:
            break

    return bullets


def extract_article_bullets(url, max_bullets=3):
    if not url:
        return []

    try:
        ensure_nltk()
        article = Article(url)
        article.download()
        article.parse()

        if not article.text or len(article.text.strip()) < 300:
            return []

        try:
            article.nlp()
            summary_text = article.summary
        except Exception:
            summary_text = ""

        bullets = split_summary_into_bullets(summary_text, max_bullets=max_bullets)

        if bullets:
            return bullets

        fallback_sentences = split_summary_into_bullets(article.text, max_bullets=max_bullets)
        return fallback_sentences

    except Exception as exc:
        print(f"Article extraction failed for {url}: {exc}")
        return []


def enrich_grouped_headlines(grouped_items):
    enriched = {}

    for category in CATEGORY_ORDER:
        section_items = grouped_items.get(category, [])
        enriched[category] = []

        for idx, item in enumerate(section_items):
            enriched_item = dict(item)
            enriched_item["article_bullets"] = []

            if idx == 0:
                enriched_item["article_bullets"] = extract_article_bullets(item.get("url", ""))

            enriched[category].append(enriched_item)

    return enriched


def format_markdown_link(headline, url, source):
    headline = (headline or "No headline").strip()
    source = (source or "Unknown source").strip()
    if url:
        return f"- [{headline}]({url}) ({source})"
    return f"- {headline} ({source})"


def build_markdown(items):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tone = classify_tone(items)
    grouped = grouped_headlines(items)
    enriched = enrich_grouped_headlines(grouped)

    body = [
        "# Daily Macro Briefing",
        "",
        f"Generated: {now}",
        f"Market tone: **{tone}**",
        "",
        "## Top headlines by theme",
        ""
    ]

    for category in CATEGORY_ORDER:
        section_items = enriched.get(category, [])
        if section_items:
            body.append(f"### {category}")
            for item in section_items:
                body.append(
                    format_markdown_link(
                        item.get("headline", ""),
                        item.get("url", ""),
                        item.get("source", "")
                    )
                )

                for bullet in item.get("article_bullets", []):
                    body.append(f"  - {bullet}")

            body.append("")

    body.extend([
        "## Notes",
        "- This is a rules-based starter version using Finnhub market news.",
        "- Headlines are grouped into macro, geopolitics, energy, and markets sections for faster morning scanning.",
        "- Top article in each section may include 1-3 extracted summary bullets when article parsing works.",
        "- Next step: add indices, oil, FX and UK gilts for a richer signal.",
    ])

    return "\n".join(body)


def build_html_email(items):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tone = classify_tone(items)
    grouped = grouped_headlines(items)
    enriched = enrich_grouped_headlines(grouped)

    sections_html = []
    for category in CATEGORY_ORDER:
        section_items = enriched.get(category, [])
        if not section_items:
            continue

        bullets_html = []
        for item in section_items:
            headline = html.escape(item.get("headline", "No headline"))
            source = html.escape(item.get("source", "Unknown source"))
            url = item.get("url", "")
            article_bullets = item.get("article_bullets", [])

            if url:
                main_line = (
                    f'<li><a href="{html.escape(url)}" target="_blank">{headline}</a> '
                    f'<span style="color:#666;">({source})</span>'
                )
            else:
                main_line = f'<li>{headline} <span style="color:#666;">({source})</span>'

            if article_bullets:
                nested = "".join(
                    f"<li>{html.escape(point)}</li>" for point in article_bullets
                )
                main_line += f'<ul style="margin-top:6px;">{nested}</ul>'

            main_line += "</li>"
            bullets_html.append(main_line)

        sections_html.append(
            f"""
            <h3 style="margin:18px 0 8px 0;">{html.escape(category)}</h3>
            <ul style="margin-top:6px; padding-left:20px;">
                {''.join(bullets_html)}
            </ul>
            """
        )

    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #222;">
        <h1 style="margin-bottom: 12px;">Daily Macro Briefing</h1>
        <p><strong>Generated:</strong> {html.escape(now)}<br>
        <strong>Market tone:</strong> {html.escape(tone)}</p>

        <h2 style="margin-top: 24px;">Top headlines by theme</h2>
        {''.join(sections_html)}

        <h2 style="margin-top: 24px;">Notes</h2>
        <ul>
          <li>This is a rules-based starter version using Finnhub market news.</li>
          <li>Headlines are grouped into macro, geopolitics, energy, and markets sections for faster morning scanning.</li>
          <li>Top article in each section may include 1-3 extracted summary bullets when article parsing works.</li>
          <li>Next step: add indices, oil, FX and UK gilts for a richer signal.</li>
        </ul>
      </body>
    </html>
    """


def send_email(markdown_content, html_content):
    host = os.getenv("EMAIL_HOST")
    port = os.getenv("EMAIL_PORT")
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipients = os.getenv("EMAIL_RECIPIENTS", "")

    missing = []
    if not host:
        missing.append("EMAIL_HOST")
    if not port:
        missing.append("EMAIL_PORT")
    if not sender:
        missing.append("EMAIL_ADDRESS")
    if not password:
        missing.append("EMAIL_PASSWORD")
    if not recipients.strip():
        missing.append("EMAIL_RECIPIENTS")

    if missing:
        raise ValueError(f"Missing required email environment variables: {', '.join(missing)}")

    recipient_list = [r.strip() for r in recipients.split(",") if r.strip()]

    msg = EmailMessage()
    msg["Subject"] = "Daily Macro Briefing"
    msg["From"] = sender
    msg["To"] = ", ".join(recipient_list)

    msg.set_content(markdown_content)
    msg.add_alternative(html_content, subtype="html")

    with smtplib.SMTP_SSL(host, int(port)) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)

    print("Email sent successfully.")


def main():
    items = fetch_market_news()
    md = build_markdown(items)
    html_email = build_html_email(items)
    OUT_FILE.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_FILE}")
    send_email(md, html_email)


if __name__ == "__main__":
    main()
