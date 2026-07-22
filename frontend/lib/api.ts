import type {
  CellDetail,
  Listing,
  Profile,
  RunResult,
  ScoredListing,
  Zone,
} from "./types";

// The browser calls the backend directly. Default targets the backend published
// on the host at :8000 (works for both `docker compose up` and local dev, since
// the backend is published on localhost:8000 in both). Override at build time
// with NEXT_PUBLIC_API_BASE (e.g. a Codespaces/remote URL), or set it to "" to
// use same-origin relative paths behind a reverse proxy.
const BASE =
  process.env.NEXT_PUBLIC_API_BASE !== undefined
    ? process.env.NEXT_PUBLIC_API_BASE
    : "http://localhost:8000";

const u = (path: string) => `${BASE}${path}`;
const f = (path: string, init?: RequestInit) => fetch(u(path), init);

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

const H = { "Content-Type": "application/json" };

export const api = {
  health: () => f("/api/health").then(
    j<{ status: string; provider_mode: string; sources?: { routing: string; geocoding: string; pois: string } }>,
  ),

  listProfiles: () => f("/api/profiles").then(j<Profile[]>),
  seedDemo: () => f("/api/profiles/seed-demo", { method: "POST" }).then(j<Profile>),
  getProfile: (id: string) => f(`/api/profiles/${id}`).then(j<Profile>),
  saveProfile: (p: Profile) =>
    f(`/api/profiles/${p.id}`, { method: "PUT", headers: H, body: JSON.stringify(p) }).then(
      j<Profile>,
    ),
  duplicate: (id: string, body: any) =>
    f(`/api/profiles/${id}/duplicate`, { method: "POST", headers: H, body: JSON.stringify(body) }).then(
      j<Profile>,
    ),

  runAnalysis: (id: string) => f(`/api/analysis/${id}/run`, { method: "POST" }).then(j<RunResult>),
  geojson: (id: string) => f(`/api/analysis/${id}/geojson`).then(j<any>),
  cellDetail: (id: string, cell: string) =>
    f(`/api/analysis/${id}/cells/${cell}`).then(j<CellDetail>),
  zones: (id: string) => f(`/api/analysis/${id}/zones`).then(j<Zone[]>),
  snapshots: (id: string) =>
    f(`/api/analysis/${id}/snapshots`).then(
      j<{ id: number; signature: string; created_at: string; tier_counts: Record<string, number>; zone_count: number; cell_count: number }[]>,
    ),
  pois: (id: string) => f(`/api/analysis/${id}/pois`).then(j<Record<string, any[]>>),
  layers: (id: string) =>
    f(`/api/analysis/${id}/layers`).then(
      j<{ id: string; name: string; value_property: string | null; geojson: any }[]>,
    ),
  isochrones: (id: string) =>
    f(`/api/analysis/${id}/isochrones`).then(
      j<{ bands: number[]; surfaces: { criterion_id: string; label: string; geojson: any }[] }>,
    ),

  addBoundary: (pid: string, geometry: number[][], mode: "inclusion" | "exclusion", hard: boolean) =>
    f(`/api/profiles/${pid}/criteria/boundary`, { method: "POST", headers: H, body: JSON.stringify({ geometry: [geometry], mode, hard }) }).then(
      j<any>,
    ),
  importLayer: (pid: string, body: { name: string; value_property?: string; units?: string; default_value?: number; geojson: any }) =>
    f(`/api/profiles/${pid}/layers/import`, { method: "POST", headers: H, body: JSON.stringify(body) }).then(
      j<{ layer_id: string; feature_count: number }>,
    ),
  addLayerCriterion: (pid: string, body: any) =>
    f(`/api/profiles/${pid}/criteria/layer`, { method: "POST", headers: H, body: JSON.stringify(body) }).then(
      j<any>,
    ),
  addCriterion: (pid: string, spec: any) =>
    f(`/api/profiles/${pid}/criteria`, { method: "POST", headers: H, body: JSON.stringify(spec) }).then(
      j<any>,
    ),
  deleteCriterion: (pid: string, cid: string) =>
    f(`/api/profiles/${pid}/criteria/${cid}`, { method: "DELETE" }).then(j<any>),

  flagAmbiguities: (text: string) =>
    f("/api/criteria/flag-ambiguities", { method: "POST", headers: H, body: JSON.stringify({ text }) }).then(
      j<{ flags: { term: string; reason: string; suggestions: any[] }[] }>,
    ),

  listListings: (pid: string) => f(`/api/profiles/${pid}/listings`).then(j<Listing[]>),
  addManual: (pid: string, body: any) =>
    f(`/api/profiles/${pid}/listings/manual`, { method: "POST", headers: H, body: JSON.stringify(body) }).then(
      j<Listing>,
    ),
  addAddress: (pid: string, address: string) =>
    f(`/api/profiles/${pid}/listings/address`, { method: "POST", headers: H, body: JSON.stringify({ address }) }).then(
      j<Listing>,
    ),
  addUrl: (pid: string, url: string) =>
    f(`/api/profiles/${pid}/listings/url`, { method: "POST", headers: H, body: JSON.stringify({ url }) }).then(
      j<any>,
    ),
  importListings: (pid: string, format: "csv" | "json", content: string) =>
    f(`/api/profiles/${pid}/listings/import`, { method: "POST", headers: H, body: JSON.stringify({ format, content }) }).then(
      j<{ imported: number; listings: Listing[] }>,
    ),
  updateListing: (pid: string, lid: string, body: any) =>
    f(`/api/profiles/${pid}/listings/${lid}`, { method: "PATCH", headers: H, body: JSON.stringify(body) }).then(
      j<Listing>,
    ),
  deleteListing: (pid: string, lid: string) =>
    f(`/api/profiles/${pid}/listings/${lid}`, { method: "DELETE" }).then(j<any>),
  scoredListings: (pid: string) => f(`/api/profiles/${pid}/listings/scored`).then(j<ScoredListing[]>),
  matches: (pid: string) =>
    f(`/api/profiles/${pid}/listings/matches`).then(
      j<{ match_count: number; matches: { listing_id: string; address: string; combined_fit: number; combined_tier: string }[] }>,
    ),
  runAlerts: (pid: string) =>
    f(`/api/profiles/${pid}/listings/alerts/run`, { method: "POST" }).then(
      j<{ total_matches: number; notified: number; new_matches: { address: string }[] }>,
    ),

  areaCsvUrl: (id: string) => u(`/api/analysis/${id}/export.csv`),
  areaGeojsonUrl: (id: string) => u(`/api/analysis/${id}/export.geojson`),
  listingsCsvUrl: (pid: string) => u(`/api/profiles/${pid}/listings/export.csv`),
};
