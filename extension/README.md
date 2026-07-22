# Apartment Fit — browser capture extension (MV3)

Captures **only user-visible structured data** from the listing page you are
currently viewing (schema.org JSON-LD the page publishes, Open Graph/meta tags,
and visible price/beds/baths/sqft text), lets you review and edit it, and sends
it to your Apartment Fit backend.

It does **not** perform bulk scraping, use private/undocumented APIs, bypass
CAPTCHAs, or circumvent anti-bot measures. It only reads the page already open
in your active tab, on demand, when you click **Extract**.

## Load it (Chrome or Edge)

1. Start the backend (`docker compose up` or the local backend) so
   `http://localhost:8000` is reachable.
2. Open `chrome://extensions` (or `edge://extensions`).
3. Enable **Developer mode**.
4. **Load unpacked** → select this `extension/` folder.
5. Open a listing page, click the toolbar icon, set the **API base URL**
   (`http://localhost:8000`) and **Profile ID** (`demo-seattle`), then
   **Extract** → review → **Send to Apartment Fit**.

If extraction finds nothing, fill the fields manually and send — the popup
always falls back to manual confirmation.

The extension posts to `POST /api/profiles/{profileId}/listings/extension`.

## Site adapters

Extraction is adapter-driven (`parse.js` + `extract.js`). `pickAdapter(hostname)`
selects a per-site adapter whose declarative selector lists say which
**user-visible** elements to read; results are merged with generic JSON-LD,
Open Graph, and visible-text passes. Built-in adapters:

| Site | Host match |
|------|-----------|
| Zillow | `zillow.com` |
| Apartments.com | `apartments.com` |
| Redfin | `redfin.com` |
| Trulia | `trulia.com` |
| HotPads | `hotpads.com` |
| Craigslist (Seattle) | `craigslist.org` |
| Zumper | `zumper.com` |
| PadMapper | `padmapper.com` |
| Realtor.com | `realtor.com` |
| _fallback_ | `generic` (JSON-LD + meta + visible text) |

## Review UI

The popup is a review surface: after **Extract** it shows each field with a
🟢 **auto** badge (extracted from the page) or 🟡 **manual** badge (you typed or
edited it), a per-capture **confidence** meter (how many fields were
auto-filled), and which **adapter** matched. Editing an auto field flips it to
manual so you always know what came from the page vs. what you changed before
sending.

Add a new site by appending a selector config to `ADAPTERS` in `parse.js` — no
DOM code needed. Selectors only ever read visible fields on the page the user
has open.

## Tests

The pure parser has unit tests (no DOM needed):

```bash
node --test extension/          # 4 tests: num, parseBedBathSqft, parseRent, pickAdapter
```

## Packaging for the Chrome/Edge stores

```bash
scripts/package-extension.sh    # -> dist/apartment-fit-extension.zip
```

Upload the zip in the Chrome Web Store / Edge Add-ons developer dashboard, or
distribute it for "Load unpacked". `activeTab` + on-click injection means the
extension needs no broad host permissions — it only touches a page when you
click **Extract** on it. `host_permissions` is limited to `localhost` for the
API call; change it to your deployed API origin before publishing.
