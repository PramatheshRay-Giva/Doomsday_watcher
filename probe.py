"""One-off: dump BookMyShow page structure into the Actions log so the
multi-cinema watcher can be written against the real page."""
import json, re
from playwright.sync_api import sync_playwright

VENUE = "https://in.bookmyshow.com/cinemas/BANG/amb-cinemas-kapali-bengaluru/buytickets/ACKB/20261217"

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                        locale="en-IN", timezone_id="Asia/Kolkata", viewport={"width": 1366, "height": 900})
    page = ctx.new_page()
    xhr = []
    page.on("response", lambda r: xhr.append((r.status, r.url, r.headers.get("content-type", ""))) if "json" in r.headers.get("content-type", "") else None)

    page.goto(VENUE, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    links = page.eval_on_selector_all("a", "els => els.map(e => [e.innerText.trim().slice(0,60), e.href])")
    print("=== VENUE PAGE doomsday links")
    for t, h in links:
        if "doomsday" in (t + h).lower(): print("LINK", repr(t), h)
    html = page.content()
    print("ET codes in venue html:", sorted(set(re.findall(r"ET\d{8}", html)))[:20])
    m = re.search(r'(https://in\.bookmyshow\.com)?/movies/[^"\s]*doomsday[^"\s]*', html)
    print("movie path in html:", m.group(0) if m else None)

    codes = [c for c in sorted(set(re.findall(r"ET\d{8}", html)))]
    for code in codes[:6]:
        url = f"https://in.bookmyshow.com/movies/bengaluru/avengers-doomsday/buytickets/{code}/20261217"
        xhr.clear()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        for _ in range(6):
            page.mouse.wheel(0, 3000); page.wait_for_timeout(800)
        txt = page.inner_text("body")
        print(f"\n=== MOVIE PAGE {code} -> {page.url}  title={page.title()!r}  len={len(txt)}")
        if "doomsday" not in txt.lower():
            print("(no doomsday on page)"); continue
        print("--- first 120 text lines")
        for line in [l.strip() for l in txt.splitlines() if l.strip()][:120]: print("T|", line[:100])
        print("--- anchors with cinemas/venue in href")
        hs = page.eval_on_selector_all("a", "els => els.map(e => [e.innerText.trim().slice(0,60), e.href])")
        for t, h in hs:
            if re.search(r"cinemas|venue|seat", h, re.I): print("A|", repr(t), h)
        print("--- json responses")
        for s, u, ct in xhr: print("X|", s, u[:200])
        break
    b.close()
