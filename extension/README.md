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
