"use client";
import {
  TIER_COLORS,
  TIER_LABELS,
  type CellDetail,
  type EliminationRow,
  type RunResult,
  type Zone,
} from "../lib/types";

export function Legend({
  activeLayers, toggle, pois,
}: {
  activeLayers: Record<string, boolean>;
  toggle: (k: string) => void;
  pois: Record<string, any[]>;
}) {
  return (
    <div className="card">
      <div className="section-title">Map layers</div>
      <div className="legend">
        {Object.keys(TIER_LABELS).map((t) => (
          <label className="item" key={t} style={{ cursor: "pointer" }}>
            <input type="checkbox" style={{ width: "auto" }}
              checked={activeLayers[t] !== false} onChange={() => toggle(t)} />
            <span className="swatch" style={{ background: TIER_COLORS[t] }} />
            {TIER_LABELS[t]}
          </label>
        ))}
        {Object.keys(pois).map((cat) => (
          <label className="item" key={cat} style={{ cursor: "pointer" }}>
            <input type="checkbox" style={{ width: "auto" }}
              checked={activeLayers[`poi:${cat}`] !== false} onChange={() => toggle(`poi:${cat}`)} />
            <span className="swatch" style={{ background: "#888" }} />
            {cat} markers
          </label>
        ))}
      </div>
    </div>
  );
}

export function EliminationPanel({ run }: { run: RunResult | null }) {
  if (!run) return null;
  const max = Math.max(1, ...run.elimination.map((e) => e.eliminated));
  return (
    <div className="card">
      <div className="section-title">Which criteria eliminate the most areas</div>
      {run.elimination.map((e: EliminationRow) => (
        <div key={e.criterion_id} style={{ marginBottom: 6 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
            <span>{e.label}</span>
            <span className="muted">{e.eliminated} ({e.pct_of_cells}%)</span>
          </div>
          <div style={{ background: "#0b1017", borderRadius: 4, height: 8, overflow: "hidden" }}>
            <div style={{ width: `${(e.eliminated / max) * 100}%`, height: "100%", background: "#d73027" }} />
          </div>
          {e.eliminated_solely_by_this > 0 && (
            <small className="hint">{e.eliminated_solely_by_this} cells fail this criterion alone</small>
          )}
        </div>
      ))}
    </div>
  );
}

export function TierSummary({ run }: { run: RunResult | null }) {
  if (!run) return null;
  return (
    <div className="card">
      <div className="section-title">Analysis summary</div>
      <div style={{ fontSize: 12 }} className="muted">
        {run.cell_count} cells · {run.zone_count} search zones
      </div>
      <div style={{ marginTop: 6 }}>
        {Object.entries(TIER_LABELS).map(([t, label]) => (
          <div key={t} className="item" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <span className="tierdot" style={{ background: TIER_COLORS[t] }} />
            {label}: <strong>{run.tier_counts[t] || 0}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SnapshotHistory({ snapshots }: {
  snapshots: { id: number; signature: string; created_at: string; zone_count: number }[];
}) {
  if (!snapshots?.length) return null;
  return (
    <div className="card">
      <div className="section-title">Run history ({snapshots.length})</div>
      {snapshots.slice(0, 6).map((s) => (
        <div key={s.id} style={{ fontSize: 11, display: "flex", justifyContent: "space-between" }} className="muted">
          <span>{new Date(s.created_at).toLocaleString()}</span>
          <span>sig {s.signature.slice(0, 6)} · {s.zone_count}z</span>
        </div>
      ))}
    </div>
  );
}

export function ZoneList({ zones }: { zones: Zone[] }) {
  if (!zones.length) return null;
  return (
    <div className="card">
      <div className="section-title">Apartment-search zones</div>
      {zones.slice(0, 8).map((z) => (
        <div key={z.zone_id} style={{ fontSize: 12, marginBottom: 6 }}>
          <strong>{z.zone_id}</strong> · fit {z.avg_fit_score} · {z.cell_count} cells
          <div className="muted">near {z.nearby_neighborhoods.join(", ")}</div>
        </div>
      ))}
    </div>
  );
}

export function CellDetailPanel({ detail, onClose }: { detail: CellDetail | null; onClose: () => void }) {
  if (!detail) return null;
  return (
    <div className="overlay-panel">
      <div className="row">
        <strong>
          <span className="tierdot" style={{ background: TIER_COLORS[detail.tier] }} />
          {TIER_LABELS[detail.tier]} — fit {detail.fit_score}
        </strong>
        <button className="small" style={{ flex: "0 0 auto" }} onClick={onClose}>✕</button>
      </div>
      <div className="muted" style={{ fontSize: 11, margin: "4px 0 8px" }}>
        cell {detail.cell_id} · {detail.center.lat.toFixed(4)}, {detail.center.lon.toFixed(4)} ·
        confidence {detail.confidence}
      </div>
      {detail.criteria.map((r) => (
        <div key={r.criterion_id} className={`explain ${r.missing ? "miss" : r.passed ? "pass" : "fail"}`}>
          <div>
            {r.kind === "hard" ? (r.passed ? "✓" : "✗") : "•"} <strong>{r.label}</strong>
            {r.is_fallback && <span className="muted"> (est.)</span>}
          </div>
          <div className="muted" style={{ fontSize: 11 }}>{r.explanation}</div>
        </div>
      ))}
    </div>
  );
}
