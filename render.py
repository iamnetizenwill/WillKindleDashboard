#!/usr/bin/env python3
"""Kindle Daily Dashboard renderer.

Draws a clean black-and-white 600x800 PNG (Kindle 10th gen, 167 ppi) with a
5-day weather forecast (Open-Meteo, no API key) and a Bible verse you control
in verse.json.

Usage:
    python3 render.py                      # fetch weather, write dashboard.png
    python3 render.py --demo               # fake weather, no network
    python3 render.py --out /path/to.png

Needs: Python 3.8+ and Pillow (pip install pillow).
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
W, H = 600, 800          # Kindle 10th gen screen
S = 2                    # draw at 2x, then downsample for smooth edges

INK, MID, LIGHT, PAPER = 0, 95, 200, 255

FONT_DIR = HERE / "fonts"
SYSTEM_FONT_DIRS = [
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/truetype/dejavu",
    "/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "C:/Windows/Fonts",
]
FALLBACKS = {
    "LiberationSerif-Regular.ttf": ["DejaVuSerif.ttf", "Times New Roman.ttf", "times.ttf"],
    "LiberationSerif-Italic.ttf": ["DejaVuSerif-Italic.ttf", "Times New Roman Italic.ttf", "timesi.ttf"],
    "LiberationSerif-Bold.ttf": ["DejaVuSerif-Bold.ttf", "Times New Roman Bold.ttf", "timesbd.ttf"],
    "LiberationSans-Regular.ttf": ["DejaVuSans.ttf", "Arial.ttf", "arial.ttf"],
    "LiberationSans-Bold.ttf": ["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"],
}


def font(name, size):
    """Load a font at logical `size` (scaled by S)."""
    candidates = [FONT_DIR / name]
    for d in SYSTEM_FONT_DIRS:
        for n in [name] + FALLBACKS.get(name, []):
            candidates.append(Path(d) / n)
    for c in candidates:
        if c.exists():
            return ImageFont.truetype(str(c), int(round(size * S)))
    sys.exit(f"Font not found: {name}. Keep the fonts/ folder next to render.py.")


SERIF, SERIF_I, SERIF_B = "LiberationSerif-Regular.ttf", "LiberationSerif-Italic.ttf", "LiberationSerif-Bold.ttf"
SANS, SANS_B = "LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"


# ---------------------------------------------------------------- drawing helpers
def text(d, xy, s, f, fill=INK, anchor="la", tracking=0.0):
    """Draw text at logical coords. `tracking` adds letter-spacing (logical px)."""
    x, y = xy
    if not tracking:
        d.text((x * S, y * S), s, font=f, fill=fill, anchor=anchor)
        return
    ha, va = anchor[0], anchor[1]
    widths = [f.getlength(c) for c in s]
    total = sum(widths) + tracking * S * (len(s) - 1)
    cx = x * S - (0 if ha == "l" else total / 2 if ha == "m" else total)
    for c, w in zip(s, widths):
        d.text((cx, y * S), c, font=f, fill=fill, anchor="l" + va)
        cx += w + tracking * S


def hline(d, x1, x2, y, fill=INK, w=1):
    d.rectangle([x1 * S, y * S, x2 * S - 1, (y + w) * S - 1], fill=fill)


def vline(d, x, y1, y2, fill=LIGHT, w=1):
    d.rectangle([x * S, y1 * S, (x + w) * S - 1, y2 * S - 1], fill=fill)


def circle(d, cx, cy, r, fill=None, outline=None, width=0):
    d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S],
              fill=fill, outline=outline, width=int(round(width * S)))


def line(d, x1, y1, x2, y2, w=3, fill=INK):
    d.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=fill, width=int(round(w * S)))
    r = w / 2  # round caps
    circle(d, x1, y1, r, fill=fill)
    circle(d, x2, y2, r, fill=fill)


# ---------------------------------------------------------------- weather icons
import math


def sun(d, cx, cy, u, lw=3):
    circle(d, cx, cy, 0.42 * u, outline=INK, width=lw)
    for i in range(8):
        a = math.radians(i * 45)
        line(d, cx + math.cos(a) * 0.66 * u, cy + math.sin(a) * 0.66 * u,
             cx + math.cos(a) * 0.95 * u, cy + math.sin(a) * 0.95 * u, w=lw)


def cloud(d, cx, cy, u, lw=3):
    """Outlined cloud, white-filled so it can sit in front of a sun."""
    parts = [
        ("rr", cx - 1.0 * u, cy - 0.05 * u, cx + 1.0 * u, cy + 0.5 * u, 0.275 * u),
        ("c", cx - 0.42 * u, cy - 0.10 * u, 0.44 * u),
        ("c", cx + 0.24 * u, cy - 0.28 * u, 0.62 * u),
    ]

    def paint(expand, fill):
        for p in parts:
            if p[0] == "rr":
                _, x1, y1, x2, y2, r = p
                d.rounded_rectangle([(x1 - expand) * S, (y1 - expand) * S,
                                     (x2 + expand) * S, (y2 + expand) * S],
                                    radius=(r + expand) * S, fill=fill)
            else:
                _, x, y, r = p
                circle(d, x, y, r + expand, fill=fill)

    paint(lw / 2, INK)
    paint(-lw / 2, PAPER)


def partly(d, cx, cy, u, lw=3):
    sun(d, cx - 0.38 * u, cy - 0.34 * u, 0.78 * u, lw)
    cloud(d, cx + 0.14 * u, cy + 0.14 * u, 0.82 * u, lw)


def rain(d, cx, cy, u, lw=3):
    cloud(d, cx, cy - 0.3 * u, u, lw)
    for dx in (-0.5, 0.0, 0.5):
        line(d, cx + dx * u + 0.12 * u, cy + 0.38 * u, cx + dx * u - 0.08 * u, cy + 0.78 * u, w=lw)


def snow(d, cx, cy, u, lw=3):
    cloud(d, cx, cy - 0.3 * u, u, lw)
    for dx, dy in ((-0.5, 0.42), (0.0, 0.42), (0.5, 0.42), (-0.25, 0.74), (0.25, 0.74)):
        circle(d, cx + dx * u, cy + dy * u, 0.075 * u + 0.6, fill=INK)


def storm(d, cx, cy, u, lw=3):
    cloud(d, cx, cy - 0.3 * u, u, lw)
    pts = [(0.14, 0.30), (-0.22, 0.74), (-0.03, 0.74), (-0.14, 1.08),
           (0.26, 0.58), (0.06, 0.58), (0.26, 0.30)]
    d.polygon([((cx + x * u) * S, (cy + y * u) * S) for x, y in pts], fill=INK)


def fog(d, cx, cy, u, lw=3):
    rows = [(-0.42, 1.5, -0.1), (-0.14, 1.9, 0.0), (0.14, 1.5, 0.1), (0.42, 1.0, -0.2)]
    for dy, length, off in rows:
        line(d, cx + (off - length / 2) * u, cy + dy * u, cx + (off + length / 2) * u, cy + dy * u, w=lw)


def plain_cloud(d, cx, cy, u, lw=3):
    cloud(d, cx, cy, u, lw)


ICONS = {"sun": sun, "partly": partly, "cloud": plain_cloud, "fog": fog,
         "rain": rain, "snow": snow, "storm": storm}


def classify(code):
    """WMO weather code -> (icon, short label)."""
    if code == 0:
        return "sun", "Clear"
    if code == 1:
        return "sun", "Mostly clear"
    if code == 2:
        return "partly", "Partly cloudy"
    if code == 3:
        return "cloud", "Overcast"
    if code in (45, 48):
        return "fog", "Fog"
    if code in (51, 53, 55, 56, 57):
        return "rain", "Drizzle"
    if code in (61, 63, 65, 66, 67):
        return "rain", "Rain"
    if code in (80, 81, 82):
        return "rain", "Showers"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow", "Snow"
    if code in (95, 96, 99):
        return "storm", "Storms"
    return "cloud", "Cloudy"


# ---------------------------------------------------------------- data
def now_in(tz):
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz))
    except Exception:
        return datetime.now()


def fetch_weather(cfg, cache_path):
    loc = cfg["location"]
    params = {
        "latitude": loc["latitude"],
        "longitude": loc["longitude"],
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "current": "temperature_2m,weather_code",
        "temperature_unit": cfg.get("units", "fahrenheit"),
        "timezone": loc["timezone"],
        "forecast_days": 5,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "kindle-dashboard/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        data["_fetched_at"] = now_in(loc["timezone"]).isoformat()
        cache_path.write_text(json.dumps(data))
        return data, False
    except Exception as e:  # network down, API hiccup...
        print(f"Weather fetch failed ({e}); trying cache.", file=sys.stderr)
        if cache_path.exists():
            return json.loads(cache_path.read_text()), True
        return None, True


def demo_weather():
    return {
        "current": {"temperature_2m": 61.4, "weather_code": 2},
        "daily": {
            "time": ["2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25"],
            "weather_code": [2, 0, 61, 3, 95],
            "temperature_2m_max": [72.1, 75.0, 66.3, 64.9, 62.2],
            "temperature_2m_min": [52.4, 54.0, 51.8, 50.1, 49.7],
            "precipitation_probability_max": [3, 0, 70, 25, 85],
        },
        "_fetched_at": datetime.now().isoformat(),
    }


VERSE_CACHE = HERE / "verse_cache.json"


def fetch_verse_text(reference, translation):
    """Look up public-domain verse text (bible-api.com, no key). Cached in verse_cache.json."""
    key = f"{translation}|{reference.lower()}"
    cache = {}
    if VERSE_CACHE.exists():
        try:
            cache = json.loads(VERSE_CACHE.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}
    if key in cache:
        return cache[key]
    url = ("https://bible-api.com/" + urllib.parse.quote(reference, safe=":,-;")
           + "?" + urllib.parse.urlencode({"translation": translation}))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "kindle-dashboard/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        txt = data.get("text") or " ".join(v.get("text", "") for v in data.get("verses", []))
        txt = " ".join(txt.split())  # one clean paragraph
        if not txt:
            raise ValueError("empty response")
        cache[key] = txt
        VERSE_CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
        return txt
    except Exception as e:
        print(f"Verse lookup failed for '{reference}' ({e}).", file=sys.stderr)
        return None


def load_verse(path, today):
    """verse.json: {"reference": "John 3:16"} fetches the text; add "text" to use your own."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "verses" in data:
        data = data["verses"]
    if isinstance(data, list):  # a list rotates through the verses, one per day
        data = data[today.toordinal() % len(data)]
    reference = str(data["reference"]).strip()
    text = str(data.get("text") or "").strip()
    if not text:
        text = fetch_verse_text(reference, str(data.get("translation", "kjv")).strip().lower())
    if not text:
        text = "Verse text could not be loaded. Check the reference, or add a \"text\" line to verse.json."
    return reference, text


# ---------------------------------------------------------------- layout
MARGIN = 36


def wrap(s, f, max_w):
    lines = []
    for para in s.split("\n"):
        cur = ""
        for word in para.split():
            trial = (cur + " " + word).strip()
            if f.getlength(trial) <= max_w * S or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def fit_verse(s, max_w, max_h):
    for size in range(38, 17, -1):
        f = font(SERIF_I, size)
        lines = wrap(s, f, max_w)
        lh = size * 1.34
        if len(lines) * lh <= max_h:
            return f, lines, lh
    n = max(1, int(max_h // lh))  # still too long at the smallest size: trim
    lines = lines[:n]
    lines[-1] = lines[-1].rstrip(" ,;:.") + "…"
    print("Warning: verse is very long; it was trimmed to fit.", file=sys.stderr)
    return f, lines, lh


def render(cfg, weather, from_cache, reference, verse, today, out_path):
    img = Image.new("L", (W * S, H * S), PAPER)
    d = ImageDraw.Draw(img)
    loc = cfg["location"]
    deg = "°"

    # ---- header
    text(d, (MARGIN, 52), today.strftime("%A").upper(), font(SANS_B, 15), anchor="ls", tracking=3)
    text(d, (MARGIN, 100), f"{today.strftime('%B')} {today.day}, {today.year}", font(SERIF, 38), anchor="ls")
    if weather:
        cur = weather["current"]
        _, cur_label = classify(cur["weather_code"])
        text(d, (W - MARGIN, 52), f"NOW · {cur_label.upper()}", font(SANS_B, 13), anchor="rs", tracking=2)
        text(d, (W - MARGIN, 100), f"{round(cur['temperature_2m'])}{deg}", font(SERIF, 60), anchor="rs")
    hline(d, MARGIN, W - MARGIN, 122, INK, 2)
    hline(d, MARGIN, W - MARGIN, 127, INK, 1)

    # ---- forecast
    text(d, (MARGIN, 156), loc["name"].upper(), font(SANS_B, 13), fill=MID, anchor="ls", tracking=2)
    text(d, (W - MARGIN, 156), "5-DAY FORECAST", font(SANS_B, 13), fill=MID, anchor="rs", tracking=2)

    x0, x1 = MARGIN, W - MARGIN
    colw = (x1 - x0) / 5
    if weather:
        daily = weather["daily"]
        for i in range(5):
            cx = x0 + colw * (i + 0.5)
            code = daily["weather_code"][i]
            icon, label = classify(code)
            day = datetime.strptime(daily["time"][i], "%Y-%m-%d")
            name = "TODAY" if i == 0 else day.strftime("%a").upper()
            hi = round(daily["temperature_2m_max"][i])
            lo = round(daily["temperature_2m_min"][i])
            pop = daily["precipitation_probability_max"][i]

            text(d, (cx, 206), name, font(SANS_B, 15), anchor="ms", tracking=2)
            ICONS[icon](d, cx, 262, 30)
            text(d, (cx, 322), label, font(SANS, 13), fill=MID, anchor="ms")
            text(d, (cx, 374), f"{hi}{deg}", font(SERIF_B, 36), anchor="ms")
            text(d, (cx, 406), f"{lo}{deg}", font(SERIF, 25), fill=MID, anchor="ms")
            ptxt = f"{pop}% rain" if pop is not None and pop >= 10 else "dry"
            text(d, (cx, 438), ptxt, font(SANS, 13), fill=MID, anchor="ms")
            if i:
                vline(d, round(x0 + colw * i), 184, 446)
    else:
        text(d, (W / 2, 300), "Weather unavailable", font(SERIF_I, 28), fill=MID, anchor="mm")
        text(d, (W / 2, 336), "Check the Kindle's Wi-Fi connection", font(SANS, 14), fill=MID, anchor="mm")
    hline(d, MARGIN, W - MARGIN, 462, INK, 1)

    # ---- verse
    label_y = 496
    text(d, (W / 2, label_y), "VERSE OF THE DAY", font(SANS_B, 13), fill=MID, anchor="mm", tracking=3)
    lw_ = font(SANS_B, 13).getlength("VERSE OF THE DAY") / S + 3 * 15 + 20
    hline(d, MARGIN, round(W / 2 - lw_ / 2), label_y, LIGHT)
    hline(d, round(W / 2 + lw_ / 2), W - MARGIN, label_y, LIGHT)

    area_top, area_bottom = 520, 742
    ref_font = font(SANS_B, 15)
    ref_h, gap = 18, 16
    f, lines, lh = fit_verse(verse, W - 2 * MARGIN - 24, (area_bottom - area_top) - ref_h - gap)
    block_h = len(lines) * lh + gap + ref_h
    y = area_top + ((area_bottom - area_top) - block_h) / 2
    for ln in lines:
        text(d, (W / 2, y + lh * 0.78), ln, f, anchor="ms")
        y += lh
    y += gap
    text(d, (W / 2, y + ref_h * 0.8), "— " + reference.upper(), ref_font, anchor="ms", tracking=2)

    # ---- footer
    hline(d, MARGIN, W - MARGIN, 758, INK, 1)
    stamp = today.strftime("%a %-I:%M %p") if sys.platform != "win32" else today.strftime("%a %I:%M %p").replace(" 0", " ")
    text(d, (MARGIN, 782), f"Updated {stamp}", font(SANS, 12), fill=MID, anchor="ls")
    src = "Weather: Open-Meteo" + (" (cached)" if from_cache and weather else "")
    text(d, (W - MARGIN, 782), src, font(SANS, 12), fill=MID, anchor="rs")

    out = img.resize((W, H), Image.LANCZOS).convert("L")  # 8-bit grayscale, no alpha
    out.save(out_path, "PNG", optimize=True)
    print(f"Wrote {out_path} ({W}x{H})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--verse", default=str(HERE / "verse.json"))
    ap.add_argument("--out", default=str(HERE / "dashboard.png"))
    ap.add_argument("--demo", action="store_true", help="use fake weather (no network)")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    today = now_in(cfg["location"]["timezone"])
    if args.demo:
        weather, cached = demo_weather(), False
    else:
        weather, cached = fetch_weather(cfg, HERE / "weather_cache.json")
    reference, verse = load_verse(args.verse, today)
    render(cfg, weather, cached, reference, verse, today, args.out)


if __name__ == "__main__":
    main()
