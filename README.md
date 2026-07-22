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
- **Browser extension:** compliant MV3 capture tool (Chrome/Edge) with per-site adapters.

### v0.2 additions (roadmap items now implemented)

- **Geospatial layers & drawn zones** — import GeoJSON choropleth layers and draw
  inclusion/exclusion polygons on the map; both feed real point-in-polygon
  criteria. Generated **crime** and **noise** fixture layers back the "safe" and
  "quiet" proxies, plus a **terrain (slope)** provider.
- **Persisted analysis snapshots** keyed by a criteria signature, with run
  history and confidence-aware tie-breaking of zones and listings.
- **Routing precompute** endpoint that warms the cache so threshold/weight edits
  re-run incrementally; **prebuilt-OSRM** image + `scripts/build-osrm.sh`.
- **Opt-in auth** (bearer tokens, per-user ownership) and **saved-search
  matching** with a pluggable alert notifier.

---

## Quick start (no API keys)

The default `auto` provider mode uses each **live** OpenStreetMap service that is
reachable and falls back to bundled offline data otherwise. With a plain
`docker compose up` that means **live points-of-interest from the public Overpass
API** (complete, current grocery/park/transit data) while routing and geocoding
use offline estimates — because OSRM/Nominatim only run if you start the `osm`
profile. No keys required. `/api/health` reports which source each capability is
using; the UI badge shows "live POIs (Overpass)" when live data is active. Set
`PROVIDER_MODE=fixture` to force fully-offline/deterministic behavior.

```bash
cp .env.example .env
docker compose up --build
# Frontend:  http://localhost:3000
# API docs:  http://localhost:8000/docs
```

> Offline? No internet, or Overpass unreachable? The health probe fails fast and
> everything transparently falls back to the bundled Seattle data — the app never
> hard-fails.

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
| Backend unit + integration + API E2E | `pytest -q` | **73 passed** |
| Frontend unit | `npm test` (vitest) | **5 passed** |
| Extension parser unit | `node --test extension/` | **6 passed** |
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
                                          ├─ analysis/   geo, spatial, scoring, engine, layers,
                                          │              precompute, exporters, demo
                                          ├─ providers/  base interfaces + osm adapters + fixtures
                                          │              (routing/geocoding/POI/terrain) + registry
                                          ├─ listings/   multi-source ingestion + matcher
                                          ├─ auth.py     opt-in bearer-token auth + ownership
                                          └─ routers/    auth, profiles, analysis, listings, criteria
db/  PostgreSQL + PostGIS       extension/  MV3 capture tool (parse.js adapters)
docker/osrm/  prebuilt graph    scripts/  build-osrm.sh, package-extension.sh
```

Geometry/scoring math runs in Python (haversine + grid) so correctness doesn't
depend on a live database; PostGIS backs storage/serving in the stack. All
external capabilities go through **provider interfaces** (`providers/base.py`),
selected by `PROVIDER_MODE` in `providers/registry.py`, with routing/geocoding
results cached.

---

## Enabling real OSM providers (optional)

`PROVIDER_MODE=auto` (default) already uses the live public **Overpass** API for
POIs and needs nothing. `PROVIDER_MODE=fixture` forces fully-offline data. To add
real self-hosted OSM **routing/geocoding**
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

**None are required.** In the default `auto` mode POIs come from the public
Overpass API (no key); everything else runs offline, and it all falls back to
bundled data when offline.

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
  are fully implemented (draw on the map, import GeoJSON, point-in-polygon
  criteria). The backing crime/noise/terrain layers are **synthetic fixtures**
  for demonstration — swap in licensed open data for production.
- The browser extension reads only **user-visible** structured data on demand; it
  won't fill fields a site renders purely as images or hides behind interaction.
  Site adapters use best-effort selectors that listing sites change over time.
- Opt-in auth uses simple bearer tokens (no password hashing/OAuth) and adds an
  `owner_id` column; existing databases predating it need a migration.

---

## Compliance note (listing sites)

Apartment Fit does **not** perform unauthorized bulk scraping, use private/
undocumented APIs, bypass CAPTCHAs, or circumvent anti-bot measures. Listing URLs
are saved as shells for **manual confirmation**; the browser extension captures
only the user-visible structured data on the page the user is actively viewing
and always falls back to manual entry.

---

## Roadmap status

The original next-steps are now implemented (see **v0.2 additions** above):

1. ✅ Prebuilt regional OSRM image (`docker/osrm/Dockerfile`, `scripts/build-osrm.sh`)
   + routing precompute (`POST /api/analysis/{id}/precompute`).
2. ✅ Freehand inclusion/exclusion polygon drawing + GeoJSON layer import on the
   map, feeding `boundary`/`geospatial` point-in-polygon criteria.
3. ✅ Persisted analysis snapshots keyed by criteria signature, run history, and
   confidence-aware tie-breaking; provider-level route/geocode caches make
   threshold/weight edits re-run incrementally.
4. ✅ Crime/noise fixture layers + terrain (slope) provider backing the
   "safe"/"quiet"/terrain proxies the ambiguity flagger suggests.
5. ✅ Opt-in bearer-token auth with per-user ownership + saved-search matching
   (`GET /api/profiles/{id}/listings/matches`) and a pluggable alert notifier.
6. ✅ Extension per-site adapters (Zillow/Apartments.com/Redfin/Trulia/generic),
   unit-tested pure parser, and a store-packaging script.

### Further work — implemented (Seattle)

- ✅ **Real Seattle data** for crime/noise/terrain: the synthetic sine-surface is
  replaced by SPD-grounded crime (inverse-distance over real neighborhood
  patterns), an FHWA line-source noise model over real freeway/arterial geometry
  (I-5, SR-99, Lake City Way, …), and terrain from real Seattle hill elevations.
  Live loaders (`data/open_data.py`) pull SPD Socrata / USGS elevation / OSM when
  the network allows, cached under `data/cache/`; `scripts/fetch_seattle_data.py`
  refreshes them and degrades gracefully offline.
- ✅ **Isochrone precompute** (`POST/GET /api/analysis/{id}/isochrones`) —
  per-destination banded travel-time surfaces — plus **per-cell measurement
  caching keyed by a measurement signature**, so threshold/weight edits re-grade
  cached measurements without recomputing routes (verified by tests).
- ✅ **Notifiers** (`console` / `webhook` / `email`) behind the `Notifier`
  interface, selectable by env; **scheduled alert runs** (`ALERT_INTERVAL_SECONDS`)
  and on-demand `POST …/listings/alerts/run` that detect and notify only **new**
  matches (persisted seen-set).
- ✅ **Store-ready extension review UI** — per-field auto-vs-manual badges, a
  confidence meter, and matched-adapter display — plus adapters for HotPads,
  Craigslist (Seattle), Zumper, PadMapper, and Realtor.com on top of
  Zillow/Apartments.com/Redfin/Trulia.

### Remaining beyond this scope

- Extend the real-data pipeline beyond Seattle (per-city Socrata/DOT/DEM sources).
- Cache isochrone tiles for very large metros; push-notification transport.
