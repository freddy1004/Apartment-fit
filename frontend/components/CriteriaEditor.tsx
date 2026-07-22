"use client";
import type { Criterion, Profile } from "../lib/types";

interface Props {
  profile: Profile;
  onChange: (p: Profile) => void;
  onSave: () => void;
  dirty: boolean;
}

export default function CriteriaEditor({ profile, onChange, onSave, dirty }: Props) {
  const update = (id: string, patch: Partial<Criterion>) => {
    onChange({
      ...profile,
      criteria: profile.criteria.map((c) => (c.id === id ? { ...c, ...patch } : c)),
    });
  };

  const area = profile.criteria.filter((c) => c.scope === "area");
  const listing = profile.criteria.filter((c) => c.scope === "listing");

  const renderCrit = (c: Criterion) => (
    <div className="crit" key={c.id}>
      <div className="hd">
        <strong style={{ fontSize: 13 }}>{c.label}</strong>
        <span className={`pill ${c.kind === "hard" ? "hard" : "pref"}`}>{c.kind}</span>
      </div>
      <div className="grid2" style={{ marginTop: 6 }}>
        {c.threshold != null && c.method !== "direction" && (
          <div>
            <label>Threshold ({c.units})</label>
            <input
              type="number"
              value={c.threshold ?? 0}
              step="any"
              onChange={(e) => update(c.id, { threshold: parseFloat(e.target.value) })}
            />
          </div>
        )}
        <div>
          <label>Weight ({c.weight.toFixed(1)})</label>
          <input
            type="range" min={0} max={5} step={0.1} value={c.weight}
            onChange={(e) => update(c.id, { weight: parseFloat(e.target.value) })}
          />
        </div>
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        <label style={{ margin: 0, flex: "0 0 auto" }}>
          <input
            type="checkbox" style={{ width: "auto", marginRight: 6 }}
            checked={c.kind === "hard"}
            onChange={(e) => update(c.id, { kind: e.target.checked ? "hard" : "preference" })}
          />
          Hard requirement
        </label>
        <label style={{ margin: 0, flex: "0 0 auto" }}>
          <input
            type="checkbox" style={{ width: "auto", marginRight: 6 }}
            checked={c.enabled}
            onChange={(e) => update(c.id, { enabled: e.target.checked })}
          />
          Enabled
        </label>
      </div>
    </div>
  );

  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <div className="section-title" style={{ margin: 0 }}>Criteria</div>
        <button className={dirty ? "primary" : ""} onClick={onSave} disabled={!dirty}
          style={{ flex: "0 0 auto" }}>
          {dirty ? "Save & re-run" : "Saved"}
        </button>
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>Area criteria</div>
      {area.map(renderCrit)}
      {listing.length > 0 && (
        <>
          <div className="muted" style={{ fontSize: 12, margin: "10px 0 6px" }}>Listing criteria</div>
          {listing.map(renderCrit)}
        </>
      )}
    </div>
  );
}
