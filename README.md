# 🏙️ Apartment Fit

Turn vague apartment-search preferences into **measurable criteria**, find the
**specific areas** of a city that satisfy them at a block/grid-cell level, and
**score individual listings** (including Zillow listings you're viewing) against
both area-level and apartment-level criteria — with an explanation for every
score and every failure.

- **Frontend:** Next.js + TypeScript + MapLibre GL
- **Backend:** FastAPI (Python 3.11)
- **Database:** PostgreSQL + PostGIS (SQLite for zero-setup/tests)
- **Providers:** pluggable interfaces for geocoding / routing / POIs, with real
  self-hosted **OpenStreetMap** adapters (OSRM, Nominatim, Overpass) **and**
  bundled open-data **fixtures** so everything runs offline with no keys.
- **Browser extension:** compliant MV3 capture tool (Chrome/Edge).

---

## Quick start (offline, no API keys)

The default `fixture` provider mode uses bundled open-data fixtures and network-
approximated (straight-line, clearly labeled) travel times, so the whole product
runs with `docker compose up` and no external services.

```bash
cp .env.example .env
docker compose up --build
# Frontend:  http://localhost:3000
# API docs:  http://localhost:8000/docs
```

In the UI: **Seed Seattle demo** → the map fills with fit-scored grid cells →
adjust thresholds/weights → open **Listings** to add & score apartments.

### Run locally without Docker

Backend:
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000      # uses SQLite by default
```

Frontend (in another terminal):
```bash
cd frontend
npm install
npm run dev                                     # http://localhost:3000
```
The frontend proxies `/api/*` to `http://localhost:8000` (configurable via
`BACKEND_URL`).

---

## Tests

```bash
# Backend: unit + integration + API end-to-end (35 tests)
cd backend && source .venv/bin/activate
PROVIDER_MODE=fixture pytest -q

# Frontend: unit tests (sorting/filtering logic)
cd frontend && npm test

# Optional browser E2E (requires the stack running):
cd frontend && npx playwright install chromium && npx playwright test
```

**Latest results**

| Suite | Command | Result |
|-------|---------|--------|
| Backend unit + integration + API E2E | `pytest -q` | **35 passed** |
| Frontend unit | `npm test` (vitest) | **4 passed** |
| Frontend build/typecheck | `npm run build` | **compiled, types valid** |

Backend coverage includes: geospatial math & grid generation, criteria builder &
ambiguity flagging, the scoring engine (hard-gate-over-preferences, preference
normalization, all four missing-data behaviors, insufficient-data detection),
the full city analysis (tiers, zones, elimination ranking), listing ingestion
(CSV/JSON/URL/manual, type coercion), exporters, profile duplication, and a
14-step API end-to-end journey through real HTTP routes.

---

## Implemented features

**1. Criteria builder**
- Vague phrase → measurable criterion templates (commute, groceries, freeway,
  transit, parks, direction boundary, rent, bedrooms, booleans…).
- Every criterion carries: hard-vs-preference, threshold + units, weight,
  transport mode, destination/amenity type, calculation method, and
  missing-data behavior (`fail` / `pass` / `neutral` / `penalize`).
- **Ambiguity flagging:** "safe", "quiet", "walkable", "convenient", "nice" are
  flagged with measurable alternatives.

**2. City-area analysis**
- Block/small-grid-cell decomposition (configurable cell size) over a bbox.
- Per cell: every criterion computed, raw measurements recorded, hard filters
  applied, weighted preference score, **0–100 fit score**, tier, and provenance
  (source, fallback flag, confidence).
- **Hard requirements gate; strong preferences never rescue a failed hard.**
- Tiers: **strong-fit / qualifying / borderline / ineligible / insufficient-data**.
- Interactive MapLibre map: tier fills, per-tier + POI layer toggles,
  destination/amenity markers, search-zone outlines. Click a cell for a full
  pass/fail explanation with raw travel times & distances.
- Contiguous qualifying cells grouped into **search zones** with approximate
  bounds and nearby neighborhood names.
- **"Which criteria eliminate the most areas"** ranking.

**3. Listing ingestion & scoring**
- Add via **address, manual form, listing URL, CSV/JSON import, or the browser
  extension**.
- Each listing is geocoded, tied to the area analysis, evaluated at its exact
  location, and given **separate area / apartment / combined** scores, each with
  explanations.
- Comparison view: sort, filter (favorites / hide-ineligible), favorites, notes,
  and side-by-side criterion comparison.

**Exports:** area results as **CSV** and **GeoJSON**; listing scores as **CSV**.
**Profiles:** create, save, edit thresholds/weights (auto re-run), and
**duplicate for another city** — no city-specific logic is hard-coded.

**Seattle demo profile** (all editable) encodes the required hard requirements as
data: north of a downtown reference; ≤30 min regular-bike to a downtown
destination; ≤0.75 mi walk to a full-service grocery; ≤10 min drive to an I-5
entrance — plus transit/parks/rent/bedroom preferences.

---

## Architecture

```
frontend/  Next.js UI ── /api proxy ──▶ backend/  FastAPI
                                          ├─ criteria/   schema + builder + ambiguity
                                          ├─ analysis/   geo, scoring engine, engine, exporters, demo
                                          ├─ providers/  base interfaces + osm adapters + fixtures + registry
                                          ├─ listings/   multi-source ingestion
                                          └─ routers/    profiles, analysis, listings, criteria
db/  PostgreSQL + PostGIS       extension/  MV3 capture tool
```

Geometry/scoring math runs in Python (haversine + grid) so correctness doesn't
depend on a live database; PostGIS backs storage/serving in the stack. All
external capabilities go through **provider interfaces** (`providers/base.py`),
selected by `PROVIDER_MODE` in `providers/registry.py`, with routing/geocoding
results cached.

---

## Enabling real OSM providers (optional)

`PROVIDER_MODE=fixture` (default) needs nothing. To use real self-hosted OSM
routing/geocoding:

1. **OSRM** — download a region extract and prepare a graph into `./osm-data`:
   ```bash
   mkdir -p osm-data && cd osm-data
   curl -O https://download.geofabrik.de/north-america/us/washington-latest.osm.pbf
   docker run -t -v "$PWD:/data" osrm/osrm-backend:v5.27.1 osrm-extract -p /opt/bicycle.lua /data/washington-latest.osm.pbf
   docker run -t -v "$PWD:/data" osrm/osrm-backend:v5.27.1 osrm-partition /data/washington-latest.osrm
   docker run -t -v "$PWD:/data" osrm/osrm-backend:v5.27.1 osrm-customize /data/washington-latest.osrm
   mv washington-latest.osrm region.osrm   # (and matching sidecar files)
   ```
   Run separate instances per profile (`bicycle.lua`, `foot.lua`, `car.lua`) and
   point `OSRM_URL_BIKE/WALK/DRIVE` at them for mode-accurate routing.
2. **Nominatim** — the compose `nominatim` service imports
   `NOMINATIM_PBF_URL` on first boot (multi-GB, takes a while).
3. Start with the OSM profile:
   ```bash
   PROVIDER_MODE=osm docker compose --profile osm up --build
   ```

The registry **falls back to fixtures per-call** if a service is unhealthy, so
the app never hard-fails; fixture/straight-line results are labeled in the UI.

---

## Optional external credentials

**None are required.** Everything runs offline on bundled fixtures.

| Capability | Default (no key) | Optional upgrade |
|-----------|------------------|------------------|
| Routing | fixture straight-line estimate | self-hosted **OSRM** (no key) |
| Geocoding | fixture gazetteer | self-hosted **Nominatim** (no key) |
| POIs | bundled Seattle fixtures | **Overpass API** (public, no key) or self-host |
| Basemap tiles | OSM raster tiles (browser-side) | any MapLibre style / MapTiler key |

Swapping in a commercial provider (Mapbox/Google/Graphhopper) is just a new class
implementing `providers/base.py`.

---

## Known limitations

- **Offline mode uses straight-line + detour-factor travel estimates**, labeled
  as fallbacks (`is_fallback`, confidence 0.6, "(est.)" in the UI). Enable OSM
  providers for true network routes. Transit is approximated as a speed model in
  fixture mode.
- **Seattle fixtures are approximate**, demonstration-grade coordinates for
  groceries, I-5 ramps, transit, and parks — not a complete or navigation-grade
  dataset.
- Grid analysis evaluates at **cell centroids**; very large cities with tiny
  cells will produce many cells (analysis is cached per profile; OSM mode adds
  per-route HTTP latency mitigated by the route cache).
- Terrain, user-drawn inclusion/exclusion zones, and imported geospatial layers
  are modeled in the criteria schema (`terrain`, `boundary`, `geospatial`) with
  the direction-boundary case fully implemented; freehand polygon drawing and
  arbitrary GeoJSON import are not yet wired into the map UI.
- The browser extension reads only **user-visible** structured data on demand; it
  won't fill fields a site renders purely as images or hides behind interaction.

---

## Compliance note (listing sites)

Apartment Fit does **not** perform unauthorized bulk scraping, use private/
undocumented APIs, bypass CAPTCHAs, or circumvent anti-bot measures. Listing URLs
are saved as shells for **manual confirmation**; the browser extension captures
only the user-visible structured data on the page the user is actively viewing
and always falls back to manual entry.

---

## Recommended next steps

1. Ship OSM providers by default with a prebuilt regional OSRM graph baked into
   an image; add isochrone precompute for faster large-city analysis.
2. Add freehand inclusion/exclusion polygon drawing and GeoJSON layer import to
   the map, feeding the existing `boundary`/`geospatial` criteria.
3. Persist scored snapshots and add confidence-aware tie-breaking; add per-cell
   caching keyed by criteria hash for incremental re-runs.
4. Real crime/noise/terrain layers to back the "safe"/"quiet"/terrain proxies the
   ambiguity flagger suggests.
5. Auth + multi-user saved searches; alerting when new listings match a profile.
6. Package the extension for the Chrome/Edge stores with site-specific
   visible-DOM adapters and a shared review UI.
