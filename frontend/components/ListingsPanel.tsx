"use client";
import { useMemo, useState } from "react";
import { api } from "../lib/api";
import { TIER_COLORS, TIER_LABELS, type Profile, type ScoredListing } from "../lib/types";

export default function ListingsPanel({
  profile, scored, reload,
}: {
  profile: Profile;
  scored: ScoredListing[];
  reload: () => void;
}) {
  const pid = profile.id;
  const [sortKey, setSortKey] = useState<string>("combined_fit");
  const [asc, setAsc] = useState(false);
  const [onlyFavorites, setOnlyFavorites] = useState(false);
  const [hideIneligible, setHideIneligible] = useState(false);
  const [compare, setCompare] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [matchMsg, setMatchMsg] = useState("");

  // add-forms state
  const [address, setAddress] = useState("");
  const [url, setUrl] = useState("");
  const [manual, setManual] = useState<any>({ address: "", rent: "", bedrooms: "", lat: "", lon: "" });
  const [importText, setImportText] = useState("");
  const [importFmt, setImportFmt] = useState<"csv" | "json">("csv");

  const rows = useMemo(() => {
    let r = [...scored];
    if (onlyFavorites) r = r.filter((s) => s.listing.favorite);
    if (hideIneligible) r = r.filter((s) => s.combined_tier !== "ineligible");
    r.sort((a, b) => {
      const get = (s: ScoredListing): number | string =>
        sortKey === "combined_fit" ? s.combined_fit
        : sortKey === "rent" ? (s.listing.rent ?? 0)
        : sortKey === "bedrooms" ? (s.listing.bedrooms ?? 0)
        : sortKey === "area" ? s.area.fit_score
        : sortKey === "listing" ? s.listing_score.fit_score
        : s.listing.address ?? "";
      const av = get(a), bv = get(b);
      const cmp = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
      return asc ? cmp : -cmp;
    });
    return r;
  }, [scored, sortKey, asc, onlyFavorites, hideIneligible]);

  const sort = (k: string) => { if (k === sortKey) setAsc(!asc); else { setSortKey(k); setAsc(false); } };
  const wrap = async (fn: () => Promise<any>) => { setBusy(true); try { await fn(); reload(); } finally { setBusy(false); } };

  const compared = scored.filter((s) => compare.includes(s.listing.id));

  return (
    <div style={{ padding: 16, overflowY: "auto", width: "100%" }}>
      <div className="grid2" style={{ gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div className="card">
          <div className="section-title">Add by address</div>
          <div className="row">
            <input placeholder="e.g. Green Lake, Seattle" value={address}
              onChange={(e) => setAddress(e.target.value)} />
            <button className="primary" style={{ flex: "0 0 auto" }} disabled={busy || !address}
              onClick={() => wrap(async () => { await api.addAddress(pid, address); setAddress(""); })}>Add</button>
          </div>
          <small className="hint">Geocoded via the configured provider (Nominatim / fixture gazetteer).</small>
        </div>

        <div className="card">
          <div className="section-title">Add by listing URL</div>
          <div className="row">
            <input placeholder="https://www.zillow.com/..." value={url}
              onChange={(e) => setUrl(e.target.value)} />
            <button style={{ flex: "0 0 auto" }} disabled={busy || !url}
              onClick={() => wrap(async () => { await api.addUrl(pid, url); setUrl(""); })}>Save</button>
          </div>
          <small className="hint">No server-side scraping. Add visible fields via the form or the browser extension.</small>
        </div>

        <div className="card">
          <div className="section-title">Manual entry</div>
          <div className="grid2">
            <input placeholder="Address" value={manual.address} onChange={(e) => setManual({ ...manual, address: e.target.value })} />
            <input placeholder="Rent $/mo" value={manual.rent} onChange={(e) => setManual({ ...manual, rent: e.target.value })} />
            <input placeholder="Bedrooms" value={manual.bedrooms} onChange={(e) => setManual({ ...manual, bedrooms: e.target.value })} />
            <input placeholder="lat (optional)" value={manual.lat} onChange={(e) => setManual({ ...manual, lat: e.target.value })} />
            <input placeholder="lon (optional)" value={manual.lon} onChange={(e) => setManual({ ...manual, lon: e.target.value })} />
          </div>
          <button className="primary" style={{ marginTop: 6 }} disabled={busy}
            onClick={() => wrap(async () => {
              const body: any = { ...manual };
              ["rent", "bedrooms", "lat", "lon"].forEach((k) => { if (body[k] === "") delete body[k]; });
              await api.addManual(pid, body); setManual({ address: "", rent: "", bedrooms: "", lat: "", lon: "" });
            })}>Add listing</button>
        </div>

        <div className="card">
          <div className="section-title">Bulk import (CSV / JSON)</div>
          <div className="row">
            <select style={{ flex: "0 0 90px" }} value={importFmt} onChange={(e) => setImportFmt(e.target.value as any)}>
              <option value="csv">CSV</option><option value="json">JSON</option>
            </select>
            <button className="primary" style={{ flex: "0 0 auto" }} disabled={busy || !importText}
              onClick={() => wrap(async () => { await api.importListings(pid, importFmt, importText); setImportText(""); })}>Import</button>
          </div>
          <textarea rows={3} style={{ marginTop: 6 }} placeholder="address,lat,lon,rent,bedrooms&#10;Fremont,47.651,-122.35,1950,1"
            value={importText} onChange={(e) => setImportText(e.target.value)} />
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ marginBottom: 8 }}>
          <div className="section-title" style={{ margin: 0 }}>Listings ({rows.length})</div>
          <label style={{ flex: "0 0 auto", margin: 0 }}>
            <input type="checkbox" style={{ width: "auto", marginRight: 4 }} checked={onlyFavorites} onChange={(e) => setOnlyFavorites(e.target.checked)} />
            favorites
          </label>
          <label style={{ flex: "0 0 auto", margin: 0 }}>
            <input type="checkbox" style={{ width: "auto", marginRight: 4 }} checked={hideIneligible} onChange={(e) => setHideIneligible(e.target.checked)} />
            hide ineligible
          </label>
          <button className="small" style={{ flex: "0 0 auto" }}
            onClick={async () => { const r = await api.matches(pid); setMatchMsg(`${r.match_count} listing(s) match all hard requirements${r.matches.length ? ": " + r.matches.map((m) => m.address || m.listing_id).join(", ") : ""}`); }}>
            Saved-search matches
          </button>
          <a style={{ flex: "0 0 auto" }} href={api.listingsCsvUrl(pid)}><button className="small">Export CSV</button></a>
        </div>
        {matchMsg && <div className="explain pass" style={{ marginBottom: 8 }}>🔔 {matchMsg}</div>}
        <table>
          <thead>
            <tr>
              <th></th>
              <th onClick={() => sort("address")}>Address</th>
              <th onClick={() => sort("rent")}>Rent</th>
              <th onClick={() => sort("bedrooms")}>Beds</th>
              <th onClick={() => sort("area")}>Area</th>
              <th onClick={() => sort("listing")}>Apt</th>
              <th onClick={() => sort("combined_fit")}>Combined</th>
              <th title="confidence">conf</th>
              <th>★</th><th>cmp</th><th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.listing.id}>
                <td><span className="tierdot" style={{ background: TIER_COLORS[s.combined_tier] }} title={TIER_LABELS[s.combined_tier]} /></td>
                <td>{s.listing.address || s.listing.source_url || s.listing.id}</td>
                <td>{s.listing.rent ?? "—"}</td>
                <td>{s.listing.bedrooms ?? "—"}</td>
                <td>{s.area.hard_passed ? s.area.fit_score : "✗"}</td>
                <td>{s.listing_score.hard_passed ? s.listing_score.fit_score : "✗"}</td>
                <td><strong>{s.combined_fit}</strong></td>
                <td className="muted">{s.confidence != null ? s.confidence.toFixed(2) : "—"}</td>
                <td style={{ cursor: "pointer" }} onClick={() => wrap(() => api.updateListing(pid, s.listing.id, { favorite: !s.listing.favorite }))}>
                  {s.listing.favorite ? "★" : "☆"}
                </td>
                <td>
                  <input type="checkbox" style={{ width: "auto" }} checked={compare.includes(s.listing.id)}
                    onChange={(e) => setCompare(e.target.checked ? [...compare, s.listing.id] : compare.filter((x) => x !== s.listing.id))} />
                </td>
                <td style={{ cursor: "pointer", color: "var(--bad)" }} onClick={() => wrap(() => api.deleteListing(pid, s.listing.id))}>✕</td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={11} className="muted">No listings yet — add some above.</td></tr>}
          </tbody>
        </table>
      </div>

      {compared.length >= 2 && (
        <div className="card">
          <div className="section-title">Side-by-side comparison</div>
          <table>
            <thead><tr><th>Criterion</th>{compared.map((s) => <th key={s.listing.id}>{s.listing.address || s.listing.id}</th>)}</tr></thead>
            <tbody>
              {compared[0].area.results.concat(compared[0].listing_score.results).map((r, i) => (
                <tr key={r.criterion_id}>
                  <td>{r.label}</td>
                  {compared.map((s) => {
                    const all = [...s.area.results, ...s.listing_score.results];
                    const rr = all.find((x) => x.label === r.label);
                    return <td key={s.listing.id} className={rr ? (rr.missing ? "muted" : rr.passed ? "" : "") : "muted"}>
                      {rr ? (rr.raw_value != null ? `${rr.raw_value} ${rr.units}` : rr.passed ? "✓" : "✗") : "—"}
                    </td>;
                  })}
                </tr>
              ))}
              <tr><td><strong>Combined fit</strong></td>{compared.map((s) => <td key={s.listing.id}><strong>{s.combined_fit}</strong></td>)}</tr>
            </tbody>
          </table>
        </div>
      )}

      {compare.length === 1 && (
        <div className="card"><NotesEditor pid={pid} listing={scored.find((s) => s.listing.id === compare[0])!.listing} reload={reload} /></div>
      )}
    </div>
  );
}

function NotesEditor({ pid, listing, reload }: { pid: string; listing: any; reload: () => void }) {
  const [notes, setNotes] = useState(listing.notes || "");
  return (
    <div>
      <div className="section-title">Notes — {listing.address || listing.id}</div>
      <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
      <button className="primary" style={{ marginTop: 6 }}
        onClick={async () => { await api.updateListing(pid, listing.id, { notes }); reload(); }}>Save notes</button>
    </div>
  );
}
