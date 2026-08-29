#!/usr/bin/env python3
"""
RSP Accounting Board - daily email parser.

Reads yesterday's Manager Log dispatch emails and any team reply emails
from the Gmail inbox via IMAP, sends the text to Claude to extract
structured status updates, and merges them into data/board.json.

Required environment variables (set as GitHub Actions secrets):
  GMAIL_ADDRESS       - the inbox that receives the dispatches
  GMAIL_APP_PASSWORD  - a Gmail App Password (not the account password)
  ANTHROPIC_API_KEY   - Claude API key

Never commit these values. They live only in repo Settings > Secrets.
"""
import imaplib, email, json, os, ssl, sys, re
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from urllib import request as urlreq

BOARD_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "board.json")
SUBJECT_MARKERS = ["Daily Manager Log", "Accounting status", "Where are we at"]
LOOKBACK_DAYS = 2

def fetch_emails():
    addr = os.environ["GMAIL_ADDRESS"]
    pw = os.environ["GMAIL_APP_PASSWORD"]
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")
    m = imaplib.IMAP4_SSL("imap.gmail.com", ssl_context=ssl.create_default_context())
    m.login(addr, pw)
    m.select("INBOX")
    _, data = m.search(None, f'(SINCE "{since}")')
    bodies = []
    for num in data[0].split():
        _, msg_data = m.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        subj = ""
        for part, enc in decode_header(msg.get("Subject", "")):
            subj += part.decode(enc or "utf-8", "ignore") if isinstance(part, bytes) else part
        if not any(mk.lower() in subj.lower() for mk in SUBJECT_MARKERS):
            continue
        text = ""
        for part in msg.walk():
            ct = part.get_content_type()
            if ct in ("text/plain", "text/html"):
                payload = part.get_payload(decode=True)
                if payload:
                    chunk = payload.decode(part.get_content_charset() or "utf-8", "ignore")
                    if ct == "text/html":
                        chunk = re.sub(r"<[^>]+>", " ", chunk)
                    text += chunk + "\n"
        bodies.append({"subject": subj, "date": msg.get("Date", ""), "text": text[:20000]})
    m.logout()
    return bodies

def extract_updates(bodies, known_entities):
    """Ask Claude to turn freeform team notes into structured board updates."""
    if not bodies:
        return {}
    prompt = (
        "You are parsing daily accounting status notes for a restaurant bookkeeping team. "
        "Known entities (use these exact names): " + json.dumps(known_entities) + ". "
        "From the emails below, extract every status update into JSON with this exact shape: "
        '{"updates": [{"entity": "<exact entity name>", "cell": "<one of: EOD, OS, DEP, RECON, BAL, PAY, CLOSE, NOTE>", '
        '"value": <true|false|number|"YYYY-MM-DD"|string>, "answeredAt": "<ISO datetime>"}]} '
        "Cell mapping: EOD reports reviewed -> EOD (true/false). Over/short dollar amounts -> OS (number). "
        "Cash deposits reconciled -> DEP (true/false). Reconciled through a date -> RECON (date). "
        "Balance sheet in balance -> BAL (true/false). Payroll entered through a date -> PAY (date). "
        "Month or period close items -> CLOSE (true/false). Blockers or exceptions -> NOTE (string). "
        "Only include updates actually stated. Respond with ONLY the JSON, no markdown fences.\n\nEMAILS:\n"
        + "\n---\n".join(b["subject"] + "\n" + b["text"] for b in bodies)
    )
    req = urlreq.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": prompt}],
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
    )
    with urlreq.urlopen(req, timeout=120) as resp:
        out = json.load(resp)
    text = "".join(c.get("text", "") for c in out.get("content", []))
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)

CELL_TO_QUESTION = {
    "EOD": "EOD reports reviewed for the full week",
    "OS": "Largest single-day over/short this week in dollars",
    "DEP": "Cash deposits reconciled, after EOD review",
    "RECON": "All accounts reconciled through date",
    "BAL": "Balance sheet in balance",
    "PAY": "Payroll entered through pay period ending",
    "CLOSE": "Month close: balance sheet in balance at close",
    "NOTE": "Exceptions or blockers",
}

def main():
    with open(BOARD_PATH) as f:
        board = json.load(f)
    entities = board.get("entities", [])
    bodies = fetch_emails()
    print(f"fetched {len(bodies)} relevant emails")
    parsed = extract_updates(bodies, entities)
    updates = parsed.get("updates", [])
    print(f"extracted {len(updates)} updates")
    answers = board.setdefault("answers", {})
    for u in updates:
        ent, cell = u.get("entity"), u.get("cell")
        if not ent or cell not in CELL_TO_QUESTION:
            continue
        key = f"{ent}-{CELL_TO_QUESTION[cell]}"
        answers[key] = {"value": u.get("value"), "answeredAt": u.get("answeredAt") or datetime.now(timezone.utc).isoformat()}
    board["generatedAt"] = datetime.now(timezone.utc).isoformat()
    with open(BOARD_PATH, "w") as f:
        json.dump(board, f, indent=1)
    print("board.json written")

if __name__ == "__main__":
    sys.exit(main())
