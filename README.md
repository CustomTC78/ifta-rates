# Trucker Core — IFTA tax rates (auto-updated)

Public IFTA diesel tax rates + surcharges, used by the Trucker Core app.

- **`ifta-rates.json`** — the live rate table (served to the app via GitHub Pages).
- **`ifta_rates_update.py`** — parser that reads the official IFTA matrix
  (https://www.iftach.org/taxmatrix4/Taxmatrix.php) for the current + next
  quarter and updates `ifta-rates.json`.
- **`.github/workflows/update-ifta-rates.yml`** — runs the parser weekly
  (and on manual trigger), commits any changes.
- **`last-checked.txt`** — timestamp + change log of the last run.

Only public tax data lives here — no app code, no secrets, no customer data.

The app fetches `ifta-rates.json` at launch (read-only) and falls back to its
bundled copy if offline.
