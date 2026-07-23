"use client";
import { useState } from "react";
import { api } from "../lib/api";
import type { Criterion, Profile } from "../lib/types";

interface Props {
  profile: Profile;
  reload: () => void;   // refresh profile + re-run analysis
}

const AMENITIES = [
  { value: "supermarket", label: "Grocery store" },
  { value: "park", label: "Park" },
  { value: "transit_stop", label: "Major transit station (light rail / hub)" },
  { value: "transit_any", label: "Any transit stop (incl. bus)" },
  { value: "freeway_ramp", label: "Freeway entrance" },
];
const LISTING_NUMERIC = [
  { value: "rent", label: "Rent ($/mo, max)" },
  { value: "fees", label: "Fees ($, max)" },
  { value: "bedrooms", label: "Bedrooms (min)" },
  { value: "bathrooms", label: "Bathrooms (min)" },
  { value: "size", label: "Size (sqft, min)" },
  { value: "lease_length", label: "Lease length (months, min)" },
];
const LISTING_BOOL = [
  { value: "parking", label: "Parking" },
  { value: "laundry", label: "In-unit laundry" },
  { value: "pets", label: "Pets allowed" },
];

type Kind = "area-amenity" | "area-place" | "listing";

export default function CriteriaBuilder({ profile, reload }: Props) {
  const pid = profile.id;
  const [kind, setKind] = useState<Kind>("area-amenity");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  // shared
  const [hard, setHard] = useState(false);
  const [weight, setWeight] = useState(1);
  const [label, setLabel] = useState("");
  // area
  const [amenity, setAmenity] = useState("supermarket");
  const [place, setPlace] = useState("");
  const [mode, setMode] = useState("walk");
  const [measure, setMeasure] = useState<"time" | "distance">("time");
  const [threshold, setThreshold] = useState<string>("15");
  // listing
  const [listingKind, setListingKind] = useState<"numeric" | "bool">("numeric");
  const [numField, setNumField] = useState("rent");
  const [boolField, setBoolField] = useState("parking");
  const [listingThreshold, setListingThreshold] = useState("2500");

  const submit = async () => {
    setBusy(true); setMsg("");
    try {
      let spec: any = { kind: hard ? "hard" : "preference", weight, label: label || undefined };
      if (kind === "area-amenity") {
        spec = { ...spec, scope: "area", source: "amenity", amenity_type: amenity,
                 mode, measure, threshold: parseFloat(threshold) };
      } else if (kind === "area-place") {
        if (!place.trim()) { setMsg("Enter an address or place name."); setBusy(false); return; }
        spec = { ...spec, scope: "area", source: "place", dest_address: place,
                 mode, measure, threshold: parseFloat(threshold) };
      } else {
        if (listingKind === "bool") {
          spec = { ...spec, scope: "listing", field: boolField };
        } else {
          spec = { ...spec, scope: "listing", field: numField, threshold: parseFloat(listingThreshold) };
        }
      }
      const res = await api.addCriterion(pid, spec);
      const resolved = res.resolved_destination
        ? ` → resolved to ${res.resolved_destination.display_name} (confidence ${(res.resolved_destination.confidence * 100).toFixed(0)}%)`
        : "";
      setMsg(`Added: ${res.label}${resolved}`);
      setLabel(""); setPlace("");
      reload();
    } catch (e: any) {
      setMsg("Failed: " + e.message);
    } finally { setBusy(false); }
  };

  const del = async (c: Criterion) => {
    setBusy(true);
    try { await api.deleteCriterion(pid, c.id); reload(); } finally { setBusy(false); }
  };

  const unit = measure === "time" ? "minutes" : "miles";

  return (
    <div>
      <div className="card">
        <div className="section-title">Define a new criterion</div>

        {/* what kind */}
        <label>What do you want to measure?</label>
        <select value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
          <option value="area-amenity">Distance/time to a type of place (grocery, park, transit, freeway)</option>
          <option value="area-place">Distance/time to a specific address or place</option>
          <option value="listing">An apartment attribute (rent, beds, parking…)</option>
        </select>

        {kind === "area-amenity" && (
          <>
            <label>Nearest…</label>
            <select value={amenity} onChange={(e) => setAmenity(e.target.value)}>
              {AMENITIES.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
            </select>
          </>
        )}
        {kind === "area-place" && (
          <>
            <label>Address or place (geocoded when you save)</label>
            <input placeholder="e.g. Green Lake Park, or 400 Broad St Seattle"
              value={place} onChange={(e) => setPlace(e.target.value)} />
          </>
        )}

        {(kind === "area-amenity" || kind === "area-place") && (
          <>
            <div className="grid2">
              <div>
                <label>Travel mode</label>
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="walk">Walk</option><option value="bike">Bike</option>
                  <option value="drive">Drive</option><option value="transit">Transit</option>
                </select>
              </div>
              <div>
                <label>Measure by</label>
                <select value={measure} onChange={(e) => setMeasure(e.target.value as any)}>
                  <option value="time">Time (minutes)</option>
                  <option value="distance">Distance (miles)</option>
                </select>
              </div>
            </div>
            <label>Threshold — at most this many {unit}</label>
            <input type="number" step="any" value={threshold}
              onChange={(e) => setThreshold(e.target.value)} />
          </>
        )}

        {kind === "listing" && (
          <>
            <label>Attribute type</label>
            <select value={listingKind} onChange={(e) => setListingKind(e.target.value as any)}>
              <option value="numeric">Numeric (rent, beds, size…)</option>
              <option value="bool">Yes/no feature (parking, laundry, pets)</option>
            </select>
            {listingKind === "numeric" ? (
              <>
                <label>Field</label>
                <select value={numField} onChange={(e) => setNumField(e.target.value)}>
                  {LISTING_NUMERIC.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
                </select>
                <label>Threshold</label>
                <input type="number" step="any" value={listingThreshold}
                  onChange={(e) => setListingThreshold(e.target.value)} />
              </>
            ) : (
              <>
                <label>Feature</label>
                <select value={boolField} onChange={(e) => setBoolField(e.target.value)}>
                  {LISTING_BOOL.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
                </select>
              </>
            )}
          </>
        )}

        <label style={{ marginTop: 8 }}>Custom label (optional)</label>
        <input placeholder="auto-generated if blank" value={label}
          onChange={(e) => setLabel(e.target.value)} />

        <div className="row" style={{ marginTop: 8 }}>
          <label style={{ margin: 0, flex: "0 0 auto" }}>
            <input type="checkbox" style={{ width: "auto", marginRight: 6 }}
              checked={hard} onChange={(e) => setHard(e.target.checked)} />
            Hard requirement (pass/fail gate)
          </label>
          <div>
            <label style={{ margin: 0 }}>Weight ({weight.toFixed(1)})</label>
            <input type="range" min={0} max={5} step={0.1} value={weight}
              onChange={(e) => setWeight(parseFloat(e.target.value))} />
          </div>
        </div>

        <button className="primary" style={{ marginTop: 8 }} disabled={busy} onClick={submit}>
          Add criterion
        </button>
        {msg && <div className={`explain ${msg.startsWith("Failed") ? "fail" : "pass"}`} style={{ marginTop: 6 }}>{msg}</div>}
      </div>

      {/* existing criteria */}
      <div className="card">
        <div className="section-title">Your criteria ({profile.criteria.length})</div>
        {profile.criteria.map((c) => (
          <div className="crit" key={c.id}>
            <div className="hd">
              <span style={{ fontSize: 13 }}>{c.label}</span>
              <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span className={`pill ${c.kind === "hard" ? "hard" : "pref"}`}>{c.kind}</span>
                <button className="small" style={{ color: "var(--bad)" }} onClick={() => del(c)}>✕</button>
              </span>
            </div>
            <small className="hint">
              {c.scope} · {c.method}{c.threshold != null ? ` · ≤/≥ ${c.threshold} ${c.units}` : ""} · weight {c.weight}
            </small>
          </div>
        ))}
        {!profile.criteria.length && <div className="muted">No criteria yet — add one above.</div>}
      </div>
    </div>
  );
}
