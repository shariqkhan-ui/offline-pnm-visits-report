#!/usr/bin/env python3
"""Daily PNM visits report — fetches form responses, renders an HTML table,
screenshots it via headless Chrome, and posts the PNG + commentary to Slack.

Runs in GitHub Actions on a daily cron at 04:30 UTC (10:00 AM IST).

Required env vars:
- SLACK_BOT_TOKEN   xoxb- token with chat:write and files:write scopes
- SLACK_CHANNEL_ID  Target channel ID (Cxxxxx)
- HARMEET_USER_ID   (optional) User ID to cc — defaults to U077923R68H
- WHATSAPPER_USER_ID (optional) User ID to cc — defaults to U040Y7SEUSU
"""
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

CSV_URL = "https://docs.google.com/spreadsheets/d/1wTCNVePUf3jIPYgWH6lRREZevaVuGCZnd578AJmlmIY/export?format=csv&gid=415112236"
HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.html")
PNG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.png")

EMAIL_TO_NAME = {
    "fahad.ahmad@wiom.in": "Fahad",
    "ajinkya.bhasagare@wiom.in": "Ajinkya",
}
DISPLAY_ORDER = ["Fahad", "Ajinkya", "Anurag", "Gaurav"]
NORMAL_LED = {"all on", "only power led glowing"}
UNKNOWN_BUG_NEEDLE = "internet led not glowing"


def classify(led):
    s = led.strip().lower()
    if s in NORMAL_LED:
        return "normal"
    if UNKNOWN_BUG_NEEDLE in s:
        return "unknown_bug"
    return "csp"


def fetch_rows():
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return list(csv.DictReader(io.StringIO(resp.read().decode("utf-8"))))


def parse_date(ts):
    return datetime.strptime(ts.strip(), "%m/%d/%Y %H:%M:%S").date()


def compute(today_ist):
    rows = fetch_rows()
    yesterday = today_ist - timedelta(days=1)
    d2 = today_ist - timedelta(days=2)
    d3 = today_ist - timedelta(days=3)
    daily = defaultdict(lambda: defaultdict(lambda: {"v": 0, "c": 0, "u": 0}))
    ttd = defaultdict(lambda: {"v": 0, "c": 0, "u": 0})
    for r in rows:
        email = (r.get("Email Address") or "").strip().lower()
        name = EMAIL_TO_NAME.get(email)
        if not name:
            continue
        try:
            d = parse_date(r["Timestamp"])
        except (KeyError, ValueError):
            continue
        if d >= today_ist:
            continue
        kind = classify(r.get("Device LED Status", ""))
        daily[name][d]["v"] += 1
        ttd[name]["v"] += 1
        if kind == "csp":
            daily[name][d]["c"] += 1
            ttd[name]["c"] += 1
        elif kind == "unknown_bug":
            daily[name][d]["u"] += 1
            ttd[name]["u"] += 1
    return daily, ttd, yesterday, d2, d3


def pct(v, c):
    if v == 0:
        return f"{c} <span class='muted'>(-)</span>"
    return f"{c} <span class='muted'>({round(c * 100 / v)}%)</span>"


def ttd_cell(t):
    v, c = t["v"], t["c"]
    if v == 0:
        return f"{v} <span class='muted'>(-)</span>"
    return f"{v} <span class='muted'>({round(c * 100 / v)}%)</span>"


def render_html(daily, ttd, yesterday, d2, d3):
    rows_html = []
    for name in DISPLAY_ORDER:
        y = daily[name][yesterday]
        d2v = daily[name][d2]["v"]
        d3v = daily[name][d3]["v"]
        t = ttd[name]
        rows_html.append(
            f"<tr>"
            f"<td class='name'>{name}</td>"
            f"<td>{y['v']}</td>"
            f"<td>{pct(y['v'], y['c'])}</td>"
            f"<td>{pct(y['v'], y['u'])}</td>"
            f"<td>{y['v']}</td>"
            f"<td>{d2v}</td>"
            f"<td>{d3v}</td>"
            f"<td>{ttd_cell(t)}</td>"
            f"</tr>"
        )
    body_rows = "\n".join(rows_html)
    title_date = yesterday.strftime("%d %b %Y")
    d1_label = yesterday.strftime("%d %b")
    d2_label = d2.strftime("%d %b")
    d3_label = d3.strftime("%d %b")
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><style>
  body {{ margin:0; padding:32px; background:#f5f6f8; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#1d1c1d; }}
  .card {{ background:#fff; border-radius:12px; box-shadow:0 1px 3px rgba(0,0,0,0.08); padding:24px; max-width:1020px; }}
  h1 {{ margin:0 0 4px; font-size:18px; color:#1d1c1d; }}
  .sub {{ color:#616061; font-size:13px; margin-bottom:18px; }}
  table {{ border-collapse:collapse; width:100%; font-size:14px; }}
  th {{ background:#E5178F; color:#fff; text-align:center; padding:10px 12px; font-weight:600; }}
  th:first-child {{ text-align:left; border-top-left-radius:8px; }}
  th:last-child {{ border-top-right-radius:8px; }}
  td {{ padding:10px 12px; text-align:center; border-bottom:1px solid #e8e8e8; }}
  td.name {{ text-align:left; font-weight:600; }}
  tr:last-child td {{ border-bottom:none; }}
  tr:nth-child(even) td {{ background:#fafbfc; }}
  .muted {{ color:#888; font-weight:400; }}
  .day {{ font-size:11px; color:#cfd2d8; font-weight:400; display:block; margin-top:2px; }}
  .note {{ margin-top:14px; font-size:12px; color:#616061; font-style:italic; line-height:1.5; }}
</style></head>
<body>
  <div class='card'>
    <h1>Surprise physical visit at CSP &mdash; Daily Report</h1>
    <div class='sub'>As of {title_date} (cutoff: end of yesterday IST)</div>
    <table>
      <thead><tr>
        <th>Name</th>
        <th># Visits</th>
        <th>CSP Issue</th>
        <th>Unknown Bug<span class='day'>Net led is not glowing</span></th>
        <th>D-1<span class='day'>{d1_label}</span></th>
        <th>D-2<span class='day'>{d2_label}</span></th>
        <th>D-3<span class='day'>{d3_label}</span></th>
        <th>TTD</th>
      </tr></thead>
      <tbody>
{body_rows}
      </tbody>
    </table>
    <div class='note'>Note: Unknown Bug is the issue where CSP and Wiom both are attributable till the final RCA and fix &mdash; hence not attributed to anyone.</div>
  </div>
</body></html>"""


def find_chrome():
    for env in ("CHROME_PATH",):
        v = os.environ.get(env)
        if v and os.path.exists(v):
            return v
    for name in ("google-chrome", "chromium-browser", "chromium", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise RuntimeError("No Chrome/Chromium found")


def screenshot(html_path, png_path):
    chrome = find_chrome()
    args = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--default-background-color=00000000",
        "--window-size=1080,560",
        f"--screenshot={png_path}",
        f"file://{html_path}" if os.sep == "/" else f"file:///{html_path.replace(os.sep, '/')}",
    ]
    subprocess.run(args, check=True, timeout=120)


def slack_api(method, token, **fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def slack_api_json(method, token, payload):
    req = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def post_message(token, channel_id, text):
    r = slack_api_json(
        "chat.postMessage",
        token,
        {"channel": channel_id, "text": text, "unfurl_links": True, "unfurl_media": True},
    )
    if not r.get("ok"):
        raise RuntimeError(f"chat.postMessage failed: {r}")
    return r


def main():
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL_ID")
    if not token or not channel:
        print("ERROR: SLACK_BOT_TOKEN and SLACK_CHANNEL_ID env vars required", file=sys.stderr)
        sys.exit(1)
    harmeet = os.environ.get("HARMEET_USER_ID", "U077923R68H")
    whats = os.environ.get("WHATSAPPER_USER_ID", "U040Y7SEUSU")
    image_url = os.environ.get("IMAGE_URL", "")

    now_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    today = now_ist.date()
    daily, ttd, yesterday, d2, d3 = compute(today)
    html = render_html(daily, ttd, yesterday, d2, d3)
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    screenshot(HTML_PATH, PNG_PATH)

    text_parts = [
        '<!channel>- Please find the report of "Surprise physical visit at CSP" as of yesterday.',
        f"cc <@{harmeet}> <@{whats}>",
    ]
    if image_url:
        text_parts.append("")
        text_parts.append(image_url)
    text_parts.append("")
    text_parts.append(
        "_Note: Unknown Bug is the issue where CSP and Wiom both are attributable till the final RCA and fix — hence not attributed to anyone._"
    )
    post_message(token, channel, "\n".join(text_parts))
    print(f"Posted report to channel {channel}")


if __name__ == "__main__":
    main()
