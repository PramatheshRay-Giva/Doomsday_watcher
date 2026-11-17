"""One-off: dump BookMyShow page structure into the Actions log."""
import re
from playwright.sync_api import sync_playwright

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
VENUE = "https://in.bookmyshow.com/cinemas/BANG/amb-cinemas-kapali-bengaluru/buytickets/ACKB/20261217"

def lines(page, n):
    return [l.strip() for l in page.inner_text("body").splitlines() if l.strip()][:n]

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(user_agent=UA, locale="en-IN", timezone_id="Asia/Kolkata", viewport={"width": 1366, "height": 900})
    page = ctx.new_page()
    resp = []
    def on_resp(r):
        ct = r.headers.get("content-type", "")
        if "json" in ct:
            try: body = r.text()
            except Exception: body = ""
            resp.append((r.status, r.url, body))
    page.on("response", on_resp)

    page.goto(VENUE, wait_until="domcontentloaded", timeout=60000); page.wait_for_timeout(9000)
    print("=== VENUE text")
    for l in lines(page, 90): print("T|", l[:110])
    print("=== VENUE json responses")
    for s, u, body in resp:
        ets = sorted(set(re.findall(r"ET\d{8}", body)))
        print("X|", s, len(body), u[:180], "ETs:", ets[:8], "doomsday" if "doomsday" in body.lower() else "")
    for s, u, body in resp:
        i = body.lower().find("doomsday")
        if i >= 0:
            print("SNIP|", u[:120]); print("SNIP|", body[max(0, i-600): i+600].replace("\n", " "))
            break
    print("=== VENUE elements mentioning doomsday")
    els = page.eval_on_selector_all("*", """els => els.filter(e => e.children.length < 3 && /doomsday/i.test(e.innerText||''))
        .slice(0,8).map(e => [e.tagName, e.className.toString().slice(0,80), (e.getAttribute('href')||''), e.outerHTML.slice(0,300)])""")
    for e in els: print("E|", e)

    resp.clear()
    page.goto("https://in.bookmyshow.com/explore/movies-bengaluru", wait_until="domcontentloaded", timeout=60000); page.wait_for_timeout(8000)
    print("=== EXPLORE", page.url)
    for t, h in page.eval_on_selector_all("a", "els => els.map(e => [e.innerText.trim().slice(0,50), e.href])"):
        if "doomsday" in (t + h).lower(): print("L|", repr(t), h)
    b.close()
