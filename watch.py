#!/usr/bin/env python3
"""
BookMyShow ticket watcher.

Opens the AMB Cinemas (Bengaluru) BookMyShow page for a given date every few
minutes in a real headless browser. When the page for that date is live AND
lists the movie, it sends you a phone push (ntfy.sh) and/or an email.

Usage:
    python watch.py --test-notify      # check that notifications reach you
    python watch.py --once             # check once and print what was seen
    python watch.py                    # keep watching until tickets are live
"""

import argparse
import os
import random
import re
import smtplib
import sys
import time
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# --------------------------------------------------------------------------
# Settings. Edit these, or pass them as flags or environment variables.
# --------------------------------------------------------------------------
# Open BookMyShow -> Bengaluru -> Cinemas -> AMB Cinemas, pick any date and
# copy the URL. It looks like:
#   https://in.bookmyshow.com/cinemas/BANG/amb-cinemas-kapali-bengaluru/buytickets/ACKB/20261117
# The date at the end gets replaced with TARGET_DATE automatically.
VENUE_URL = (os.getenv("BMS_VENUE_URL") or
             "https://in.bookmyshow.com/cinemas/BANG/amb-cinemas-kapali-bengaluru/buytickets/ACKB/20261117")
TARGET_DATE = (os.getenv("BMS_DATE") or "20261217")        # YYYYMMDD
MOVIE_KEYWORD = (os.getenv("BMS_MOVIE") or "doomsday")     # matched case-insensitively
INTERVAL_SEC = int(os.getenv("BMS_INTERVAL") or 180)   # time between checks

# Phone push via https://ntfy.sh (free, no account). Install the ntfy app and
# subscribe to this topic. Pick something long and random; anyone who knows
# the topic name can read it.
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")

# Email via Gmail. Needs a Gmail "App password", not your normal password:
# Google Account -> Security -> 2-Step Verification -> App passwords.
SMTP_USER = os.getenv("SMTP_USER", "")        # you@gmail.com
SMTP_PASS = os.getenv("SMTP_PASS", "")        # 16-char app password
EMAIL_TO = os.getenv("EMAIL_TO") or SMTP_USER
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

# Tell you if the watcher itself breaks (blocked, page errors) this many times
# in a row, so it can't fail silently.
FAIL_ALERT_AFTER = 10
# --------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
SHOT = HERE / "last_check.png"
BLOCK_MARKERS = ("access denied", "verify you are human", "just a moment",
                 "unusual traffic", "are you a robot", "request blocked")


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def target_url(venue_url, date):
    url = venue_url.strip().split("?")[0].rstrip("/")
    if re.search(r"/\d{8}$", url):
        return re.sub(r"/\d{8}$", f"/{date}", url)
    return f"{url}/{date}"


def check(page, url, date, keyword):
    """Return (status, detail). status: LIVE, NOT_YET, BLOCKED, ERROR."""
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except PWTimeout:
            pass  # the page keeps polling; what's loaded is enough
        page.wait_for_timeout(2_000)
        page.screenshot(path=str(SHOT), full_page=True)

        final_url = page.url
        text = page.inner_text("body").lower()
        code = resp.status if resp else 0

        if code in (403, 429) or any(m in text for m in BLOCK_MARKERS):
            return "BLOCKED", f"HTTP {code}, page looks like a bot check"

        # If the date isn't open yet, BookMyShow sends you to the nearest
        # date that is, so the URL no longer ends in the date we asked for.
        date_ok = date in final_url
        movie_ok = keyword.lower() in text
        detail = (f"HTTP {code} | final URL: {final_url} | "
                  f"date in URL: {date_ok} | '{keyword}' on page: {movie_ok}")
        if date_ok and movie_ok:
            return "LIVE", detail
        return "NOT_YET", detail
    except Exception as e:  # noqa: BLE001
        return "ERROR", f"{type(e).__name__}: {e}"


def notify(title, body, url=None, attach=None):
    sent = []
    if NTFY_TOPIC:
        try:
            headers = {"Title": title, "Priority": "urgent", "Tags": "rotating_light"}
            if url:
                headers["Click"] = url
            req = urllib.request.Request(f"https://ntfy.sh/{NTFY_TOPIC}",
                                         data=body.encode(), headers=headers)
            urllib.request.urlopen(req, timeout=20).read()
            sent.append("ntfy")
        except Exception as e:  # noqa: BLE001
            log(f"ntfy failed: {e}")
    if SMTP_USER and SMTP_PASS and EMAIL_TO:
        try:
            msg = EmailMessage()
            msg["Subject"], msg["From"], msg["To"] = title, SMTP_USER, EMAIL_TO
            msg.set_content(body + (f"\n\n{url}" if url else ""))
            if attach and Path(attach).exists():
                msg.add_attachment(Path(attach).read_bytes(), maintype="image",
                                   subtype="png", filename="bookmyshow.png")
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as s:
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
            sent.append("email")
        except Exception as e:  # noqa: BLE001
            log(f"email failed: {e}")
    if not sent:
        log("WARNING: no notification was sent (set NTFY_TOPIC and/or SMTP_* settings)")
    else:
        log(f"notified via {', '.join(sent)}")
    return bool(sent)


def main():
    global VENUE_URL, TARGET_DATE, MOVIE_KEYWORD, INTERVAL_SEC
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="AMB venue URL on BookMyShow (overrides BMS_VENUE_URL)")
    ap.add_argument("--date", help="YYYYMMDD (default 20261217)")
    ap.add_argument("--movie", help="keyword to look for (default 'doomsday')")
    ap.add_argument("--interval", type=int, help="seconds between checks (default 180)")
    ap.add_argument("--once", action="store_true", help="check once, print result, exit")
    ap.add_argument("--test-notify", action="store_true", help="send a test notification")
    ap.add_argument("--show", action="store_true", help="show the browser window")
    ap.add_argument("--max-minutes", type=float, default=0,
                    help="stop after this many minutes (used on GitHub Actions)")
    a = ap.parse_args()

    VENUE_URL = a.url or VENUE_URL
    TARGET_DATE = a.date or TARGET_DATE
    MOVIE_KEYWORD = a.movie or MOVIE_KEYWORD
    INTERVAL_SEC = a.interval or INTERVAL_SEC

    if a.test_notify:
        ok = notify("BMS watcher test", "If you can read this, alerts work.",
                    url="https://in.bookmyshow.com")
        sys.exit(0 if ok else 1)

    if not VENUE_URL:
        sys.exit("Set the AMB venue URL: --url '<link>' or BMS_VENUE_URL (see README).")

    url = target_url(VENUE_URL, TARGET_DATE)
    log(f"Watching {url} for '{MOVIE_KEYWORD}' every ~{INTERVAL_SEC}s")

    fails = 0
    deadline = time.time() + a.max_minutes * 60 if a.max_minutes else None
    with sync_playwright() as p:
        launch = {"headless": not a.show}
        if os.getenv("CHROMIUM_PATH"):
            launch["executable_path"] = os.environ["CHROMIUM_PATH"]
        browser = p.chromium.launch(**launch)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
            locale="en-IN", timezone_id="Asia/Kolkata",
            viewport={"width": 1366, "height": 900})
        page = ctx.new_page()

        while True:
            status, detail = check(page, url, TARGET_DATE, MOVIE_KEYWORD)
            log(f"{status}: {detail}")

            if status == "LIVE":
                notify("🎟️ Avengers: Doomsday tickets are LIVE at AMB!",
                       f"Bookings for {TARGET_DATE} at AMB Cinemas Bengaluru look open. "
                       f"Go book now. (Screenshot attached to the email.)\n\n{detail}",
                       url=url, attach=SHOT)
                if os.getenv("GITHUB_OUTPUT"):  # tell the workflow to switch itself off
                    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                        f.write("live=true\n")
                break

            fails = fails + 1 if status in ("BLOCKED", "ERROR") else 0
            if fails == FAIL_ALERT_AFTER:
                notify("BMS watcher is having trouble",
                       f"{fails} checks in a row failed. Last: {status} {detail}. "
                       "Check the terminal; you may need to run it with --show or "
                       "from another network.")

            if a.once:
                log(f"Screenshot of what was seen: {SHOT}")
                break
            if deadline and time.time() + INTERVAL_SEC > deadline:
                log("Reached --max-minutes; exiting (the next scheduled run takes over)")
                break
            # small jitter so requests don't look perfectly robotic
            time.sleep(INTERVAL_SEC + random.randint(0, 45))

        browser.close()


if __name__ == "__main__":
    main()
