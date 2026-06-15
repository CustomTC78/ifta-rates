#!/usr/bin/env python3
# Trucker Core — IFTA rate auto-updater (runs in GitHub Actions).
# Fetches the official IFTA tax matrix (iftach.org) for the current + next
# quarter, parses Special Diesel rates + surcharges, validates, and upserts
# them into ifta-rates.json (served to the app via GitHub Pages).
# Deterministic parsing — no guessing. Always writes last-checked.txt so the
# weekly schedule never gets paused for inactivity.
import urllib.request, re, html, json, os
from datetime import datetime, timezone

BASE = "https://www.iftach.org/taxmatrix4/Taxmatrix.php?QY="
OUT = "ifta-rates.json"
STAMP = "last-checked.txt"

def fetch(qy):
    req = urllib.request.Request(BASE + qy, headers={"User-Agent": "TruckerCore-IFTA/1.0 (+trucker-core.com)"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "ignore")

def parse_matrix(raw):
    """{code: {'rate': float|None, 'surcharge': float|None}} from IFTA matrix HTML."""
    def cell_text(td):
        t = re.sub(r"<[^>]+>", " ", td)
        return re.sub(r"\s+", " ", html.unescape(t)).strip()
    out = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", raw, re.S | re.I):
        tds = [cell_text(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]
        if len(tds) < 4:
            continue
        m = re.search(r"\(([A-Z]{2})\)", tds[0])
        if not m or "U.S" not in tds[1]:
            continue
        code = m.group(1)
        nums = re.findall(r"[\d]+\.[\d]+", tds[3])  # Special Diesel column; first = U.S.
        val = float(nums[0]) if nums else 0.0
        d = out.setdefault(code, {"rate": None, "surcharge": None})
        if "(Surcharge)" in tds[0]:
            d["surcharge"] = val
        else:
            d["rate"] = val
    return out

def quarters():
    now = datetime.now(timezone.utc)
    q, y = (now.month - 1) // 3 + 1, now.year
    nq, ny = (q + 1, y) if q < 4 else (1, y + 1)
    return [(q, y), (nq, ny)]

def entry(code, qkey, v):
    e = {"jurisdictionCode": code, "fuelType": "diesel", "quarterKey": qkey, "ratePerGallon": round(v["rate"], 4)}
    if v.get("surcharge"):
        e["surchargeRate"] = round(v["surcharge"], 4)
    return e

def main():
    data = json.load(open(OUT)) if os.path.exists(OUT) else []
    changed, notes = [], []
    for (q, y) in quarters():
        qy, qkey = f"{q}Q{y}", f"{y}-Q{q}"
        try:
            parsed = parse_matrix(fetch(qy))
        except Exception as e:
            notes.append(f"{qy}: fetch/parse failed ({e})")
            continue
        if len(parsed) < 50:
            notes.append(f"{qy}: only {len(parsed)} jurisdictions — skipped (kept old)")
            continue
        bad = [(c, v["rate"]) for c, v in parsed.items() if v["rate"] is None or v["rate"] < 0 or v["rate"] > 1.5]
        if bad:
            notes.append(f"{qy}: bad rates {bad[:5]} — skipped (kept old)")
            continue
        existing = {r["jurisdictionCode"]: r for r in data if r["fuelType"] == "diesel" and r["quarterKey"] == qkey}
        for code, v in parsed.items():
            new = entry(code, qkey, v)
            if existing.get(code) != new:
                old = existing.get(code)
                changed.append(f"{qkey} {code}: {old.get('ratePerGallon') if old else 'NEW'} -> {new['ratePerGallon']}")
        data = [r for r in data if not (r["fuelType"] == "diesel" and r["quarterKey"] == qkey)]
        for code in sorted(parsed):
            data.append(entry(code, qkey, parsed[code]))

    with open(OUT + ".tmp", "w") as f:
        f.write("[\n" + ",\n".join("  " + json.dumps(r) for r in data) + "\n]\n")
    os.replace(OUT + ".tmp", OUT)

    stamp = f"last checked (UTC): {datetime.now(timezone.utc).isoformat()}\n"
    stamp += ("CHANGED:\n  " + "\n  ".join(changed) + "\n") if changed else "no rate changes\n"
    if notes:
        stamp += "NOTES:\n  " + "\n  ".join(notes) + "\n"
    with open(STAMP, "w") as f:
        f.write(stamp)
    print(stamp)

if __name__ == "__main__":
    main()
