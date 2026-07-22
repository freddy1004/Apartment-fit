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
  pois: (id: string) => fetch(`/api/analysis/${id}/pois`).then(j<Record<string, any[]>>),

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

  areaCsvUrl: (id: string) => `/api/analysis/${id}/export.csv`,
  areaGeojsonUrl: (id: string) => `/api/analysis/${id}/export.geojson`,
  listingsCsvUrl: (pid: string) => `/api/profiles/${pid}/listings/export.csv`,
};
