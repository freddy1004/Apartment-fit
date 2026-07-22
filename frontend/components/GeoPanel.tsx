"use client";
import { useRef, useState } from "react";
import { api } from "../lib/api";
import type { LayerInfo } from "./MapView";

interface Props {
  profileId: string;
  layers: LayerInfo[];
  activeLayers: Record<string, boolean>;
  toggleLayer: (k: string) => void;
  drawMode: "inclusion" | "exclusion" | null;
  vertexCount: number;
  onStartDraw: (mode: "inclusion" | "exclusion") => void;
  onFinishDraw: () => void;
  onCancelDraw: () => void;
  reload: () => void;
}

export default function GeoPanel(p: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [prop, setProp] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const importFile = async (file: File) => {
    setBusy(true); setMsg("");
    try {
      const gj = JSON.parse(await file.text());
      const feats = gj.features || [];
      // Guess a numeric property if the user didn't name one.
      let vp = prop;
      if (!vp && feats[0]?.properties) {
        vp = Object.keys(feats[0].properties).find(
          (k) => typeof feats[0].properties[k] === "number") || "";
      }
      const res = await api.importLayer(p.profileId, {
        name: file.name.replace(/\.[^.]+$/, ""), value_property: vp || undefined, geojson: gj,
      });
      setMsg(`Imported ${res.feature_count} features as ${res.layer_id}`);
      p.reload();
    } catch (e: any) {
      setMsg("Import failed: " + e.message);
    } finally { setBusy(false); }
  };

  return (
    <div className="card">
      <div className="section-title">Geospatial layers & zones</div>

      {/* Draw zones */}
      {!p.drawMode ? (
        <div className="row">
          <button className="small" onClick={() => p.onStartDraw("inclusion")}>Draw inclusion zone</button>
          <button className="small" onClick={() => p.onStartDraw("exclusion")}>Draw exclusion zone</button>
        </div>
      ) : (
        <div className="card" style={{ margin: "6px 0", background: "#2a2416", borderColor: "#7a5b30" }}>
          <div style={{ fontSize: 12 }}>
            Click the map to add points to your <strong>{p.drawMode}</strong> zone ({p.vertexCount} placed).
          </div>
          <div className="row" style={{ marginTop: 6 }}>
            <button className="small primary" disabled={p.vertexCount < 3} onClick={p.onFinishDraw}>Finish zone</button>
            <button className="small" onClick={p.onCancelDraw}>Cancel</button>
          </div>
        </div>
      )}

      {/* Import GeoJSON */}
      <label style={{ marginTop: 8 }}>Import GeoJSON layer (choropleth)</label>
      <input placeholder="numeric property (auto-detected if blank)" value={prop} onChange={(e) => setProp(e.target.value)} />
      <input ref={fileRef} type="file" accept=".geojson,.json,application/geo+json" style={{ marginTop: 6 }}
        onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])} disabled={busy} />
      {msg && <small className="hint">{msg}</small>}

      {/* Layer toggles */}
      {p.layers.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {p.layers.map((l) => (
            <label className="item" key={l.id} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: 12 }}>
              <input type="checkbox" style={{ width: "auto" }}
                checked={p.activeLayers[`layer:${l.id}`] === true}
                onChange={() => p.toggleLayer(`layer:${l.id}`)} />
              {l.name}{l.value_property ? ` (${l.value_property})` : ""}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
