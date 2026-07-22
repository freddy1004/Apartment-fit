import type {
  CellDetail,
  Listing,
  Profile,
  RunResult,
  ScoredListing,
  Zone,
} from "./types";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

const H = { "Content-Type": "application/json" };

export const api = {
  health: () => fetch("/api/health").then(j<{ status: string; provider_mode: string }>),

  listProfiles: () => fetch("/api/profiles").then(j<Profile[]>),
  seedDemo: () => fetch("/api/profiles/seed-demo", { method: "POST" }).then(j<Profile>),
  getProfile: (id: string) => fetch(`/api/profiles/${id}`).then(j<Profile>),
  saveProfile: (p: Profile) =>
    fetch(`/api/profiles/${p.id}`, { method: "PUT", headers: H, body: JSON.stringify(p) }).then(
      j<Profile>,
    ),
  duplicate: (id: string, body: any) =>
    fetch(`/api/profiles/${id}/duplicate`, { method: "POST", headers: H, body: JSON.stringify(body) }).then(
      j<Profile>,
    ),

  runAnalysis: (id: string) => fetch(`/api/analysis/${id}/run`, { method: "POST" }).then(j<RunResult>),
  geojson: (id: string) => fetch(`/api/analysis/${id}/geojson`).then(j<any>),
  cellDetail: (id: string, cell: string) =>
    fetch(`/api/analysis/${id}/cells/${cell}`).then(j<CellDetail>),
  zones: (id: string) => fetch(`/api/analysis/${id}/zones`).then(j<Zone[]>),
  snapshots: (id: string) =>
    fetch(`/api/analysis/${id}/snapshots`).then(
      j<{ id: number; signature: string; created_at: string; tier_counts: Record<string, number>; zone_count: number; cell_count: number }[]>,
    ),
  pois: (id: string) => fetch(`/api/analysis/${id}/pois`).then(j<Record<string, any[]>>),
  layers: (id: string) =>
    fetch(`/api/analysis/${id}/layers`).then(
      j<{ id: string; name: string; value_property: string | null; geojson: any }[]>,
    ),
  isochrones: (id: string) =>
    fetch(`/api/analysis/${id}/isochrones`).then(
      j<{ bands: number[]; surfaces: { criterion_id: string; label: string; geojson: any }[] }>,
    ),

  addBoundary: (pid: string, geometry: number[][], mode: "inclusion" | "exclusion", hard: boolean) =>
    fetch(`/api/profiles/${pid}/criteria/boundary`, { method: "POST", headers: H, body: JSON.stringify({ geometry: [geometry], mode, hard }) }).then(
      j<any>,
    ),
  importLayer: (pid: string, body: { name: string; value_property?: string; units?: string; default_value?: number; geojson: any }) =>
    fetch(`/api/profiles/${pid}/layers/import`, { method: "POST", headers: H, body: JSON.stringify(body) }).then(
      j<{ layer_id: string; feature_count: number }>,
    ),
  addLayerCriterion: (pid: string, body: any) =>
    fetch(`/api/profiles/${pid}/criteria/layer`, { method: "POST", headers: H, body: JSON.stringify(body) }).then(
      j<any>,
    ),
  deleteCriterion: (pid: string, cid: string) =>
    fetch(`/api/profiles/${pid}/criteria/${cid}`, { method: "DELETE" }).then(j<any>),

  flagAmbiguities: (text: string) =>
    fetch("/api/criteria/flag-ambiguities", { method: "POST", headers: H, body: JSON.stringify({ text }) }).then(
      j<{ flags: { term: string; reason: string; suggestions: any[] }[] }>,
    ),

  listListings: (pid: string) => fetch(`/api/profiles/${pid}/listings`).then(j<Listing[]>),
  addManual: (pid: string, body: any) =>
    fetch(`/api/profiles/${pid}/listings/manual`, { method: "POST", headers: H, body: JSON.stringify(body) }).then(
      j<Listing>,
    ),
  addAddress: (pid: string, address: string) =>
    fetch(`/api/profiles/${pid}/listings/address`, { method: "POST", headers: H, body: JSON.stringify({ address }) }).then(
      j<Listing>,
    ),
  addUrl: (pid: string, url: string) =>
    fetch(`/api/profiles/${pid}/listings/url`, { method: "POST", headers: H, body: JSON.stringify({ url }) }).then(
      j<any>,
    ),
  importListings: (pid: string, format: "csv" | "json", content: string) =>
    fetch(`/api/profiles/${pid}/listings/import`, { method: "POST", headers: H, body: JSON.stringify({ format, content }) }).then(
      j<{ imported: number; listings: Listing[] }>,
    ),
  updateListing: (pid: string, lid: string, body: any) =>
    fetch(`/api/profiles/${pid}/listings/${lid}`, { method: "PATCH", headers: H, body: JSON.stringify(body) }).then(
      j<Listing>,
    ),
  deleteListing: (pid: string, lid: string) =>
    fetch(`/api/profiles/${pid}/listings/${lid}`, { method: "DELETE" }).then(j<any>),
  scoredListings: (pid: string) => fetch(`/api/profiles/${pid}/listings/scored`).then(j<ScoredListing[]>),
  matches: (pid: string) =>
    fetch(`/api/profiles/${pid}/listings/matches`).then(
      j<{ match_count: number; matches: { listing_id: string; address: string; combined_fit: number; combined_tier: string }[] }>,
    ),
  runAlerts: (pid: string) =>
    fetch(`/api/profiles/${pid}/listings/alerts/run`, { method: "POST" }).then(
      j<{ total_matches: number; notified: number; new_matches: { address: string }[] }>,
    ),

  areaCsvUrl: (id: string) => `/api/analysis/${id}/export.csv`,
  areaGeojsonUrl: (id: string) => `/api/analysis/${id}/export.geojson`,
  listingsCsvUrl: (pid: string) => `/api/profiles/${pid}/listings/export.csv`,
};
