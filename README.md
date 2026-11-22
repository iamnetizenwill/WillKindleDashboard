# WillKindleDashboard
Weather and Bible Verses

# Kindle Daily Dashboard

Black-and-white e-ink dashboard for a Kindle 10th gen (600×800): date, current temperature,
5-day North Hollywood, CA forecast, and a Bible verse that you type in yourself.

```
render.py        draws dashboard.png (weather from Open-Meteo, no API key)
verse.json       YOUR verse: just the reference (text is looked up)
config.json      location / units
fonts/           bundled Liberation fonts (SIL Open Font License)
kindle/dashboard the KUAL extension that goes on the Kindle
.github/         optional: free auto-refresh using GitHub Actions
```

## 1. Try it on your computer (2 minutes)

```
pip install pillow
python3 render.py --demo      # fake weather, no internet needed
python3 render.py             # real weather -> dashboard.png
```

## 2. Set your verse (just type the reference)

Edit `verse.json`. The text is looked up for you from a public-domain Bible:

```json
{ "reference": "Philippians 4:6-7", "translation": "kjv" }
```

- `translation` can be `kjv` (default), `web` or `asv`, which are all public domain.
- The lookup uses bible-api.com and is saved in `verse_cache.json`, so each verse is only fetched once.
- Want your own wording instead? Add a `"text"` line and nothing is looked up:
  `{ "reference": "John 3:16", "text": "..." }`
- Want a different verse each day? Use a list. It rotates one per day:

```json
{ "verses": [
  { "reference": "Psalm 118:24" },
  { "reference": "Psalm 23:1-3", "translation": "web" },
  { "reference": "Romans 8:28", "text": "your own text here" }
] }
```

Long verses shrink automatically to fit (about 60 words fits comfortably). If the lookup fails
(typo in the reference, no internet), the dashboard says so instead of showing a blank.
Other translations (NIV, ESV, ...) have their own permissions, so stick to the public-domain ones.

## 3. Put the extension on the Kindle

1. Plug the Kindle into your computer over USB.
2. Copy the folder `kindle/dashboard` to the Kindle's `extensions/` folder
   so you end up with `extensions/dashboard/menu.json`.
3. Eject. Open KUAL, and you'll see **Daily Dashboard**:
   - **Show dashboard (once)**: draws it and keeps the screensaver off for ~10 minutes
   - **Show dashboard (keep refreshing)**: redraws every 30 min for up to 12 hours
   - **Stop dashboard**: stops the loop and returns to the Home screen

To get out of the dashboard screen, press the power button twice (sleep, then wake). KUAL comes
back; tap **Stop dashboard**.

## 4. Getting the picture onto the Kindle: pick one

**A. Manual (works right away, no server).** Run `render.py` on your computer and copy
`dashboard.png` into `extensions/dashboard/` on the Kindle. Leave `DASH_URL` empty in `settings.conf`.
Good for a quick test, but the weather only updates when you copy a new file.

**B. Automatic with GitHub (free, phone-friendly).**
1. Make a new **public** GitHub repo and upload everything in this folder
   (except `kindle/`, if you like). Public is needed so the Kindle can download without logging in;
   the repo would only contain your verse and the neighborhood coordinates.
2. Repo → Settings → Actions → General → Workflow permissions → **Read and write**.
3. Actions tab → "Render Kindle dashboard" → **Run workflow**. It also re-runs every 3 hours and
   whenever you edit `verse.json` (you can do that from the GitHub phone app or website).
4. On the Kindle, edit `extensions/dashboard/settings.conf`:
   `DASH_URL="https://raw.githubusercontent.com/YOURNAME/YOURREPO/main/dashboard.png"`

**C. Automatic from a home computer / Raspberry Pi.**
```
*/30 * * * *  python3 /home/me/kindle-dashboard/render.py --out /srv/kindle/dashboard.png
python3 -m http.server 8080 --directory /srv/kindle
```
Then `DASH_URL="http://<that machine's IP>:8080/dashboard.png"`.

## Troubleshooting (use kterm)

```
sh /mnt/us/extensions/dashboard/bin/dashboard.sh once
cat /mnt/us/extensions/dashboard/dashboard.log
```
- *"Download failed"* with an HTTPS/certificate message: set `INSECURE_TLS="1"` in `settings.conf`,
  or use the plain-http option C.
- Screen shows the image, then KUAL redraws over it: use the "keep refreshing" mode; it redraws on a timer.
- Ghosting: the script already does a full-screen flash before drawing.
- Nothing draws: confirm the Kindle can run `eips -g /mnt/us/extensions/dashboard/dashboard.png` by hand.

## Notes

- Weather data: Open-Meteo (free for non-commercial use). If a fetch fails, the last good data is used (marked "cached").
- Change city/units in `config.json` (`"units": "celsius"` works too).
- Screen is 600×800 portrait. If you want landscape later, that's a small change to `W, H` in `render.py` plus rotating the image.
