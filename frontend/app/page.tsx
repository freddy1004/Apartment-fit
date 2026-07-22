"use client";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import AmbiguityHelper from "../components/AmbiguityHelper";
import CriteriaEditor from "../components/CriteriaEditor";
import ListingsPanel from "../components/ListingsPanel";
import {
  CellDetailPanel, EliminationPanel, Legend, TierSummary, ZoneList,
} from "../components/Panels";
import { api } from "../lib/api";
import type { CellDetail, Profile, RunResult, ScoredListing, Zone } from "../lib/types";

const MapView = dynamic(() => import("../components/MapView"), { ssr: false });

type Tab = "analysis" | "listings" | "builder";

export default function Home() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [saved, setSaved] = useState<Profile | null>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [run, setRun] = useState<RunResult | null>(null);
  const [geojson, setGeojson] = useState<any | null>(null);
  const [pois, setPois] = useState<Record<string, any[]>>({});
  const [zones, setZones] = useState<Zone[]>([]);
  const [detail, setDetail] = useState<CellDetail | null>(null);
  const [scored, setScored] = useState<ScoredListing[]>([]);
  const [activeLayers, setActiveLayers] = useState<Record<string, boolean>>({});
  const [tab, setTab] = useState<Tab>("analysis");
  const [busy, setBusy] = useState(false);
  const [providerMode, setProviderMode] = useState<string>("");

  const dirty = !!profile && !!saved && JSON.stringify(profile) !== JSON.stringify(saved);

  useEffect(() => {
    api.health().then((h) => setProviderMode(h.provider_mode)).catch(() => {});
    refreshProfiles();
  }, []);

  const refreshProfiles = async () => {
    const list = await api.listProfiles();
    setProfiles(list);
    if (list.length && !profile) selectProfile(list[0]);
  };

  const selectProfile = async (p: Profile) => {
    setProfile(p); setSaved(JSON.parse(JSON.stringify(p)));
    setDetail(null);
    await analyze(p.id);
  };

  const analyze = useCallback(async (pid: string) => {
    setBusy(true);
    try {
      const r = await api.runAnalysis(pid);
      setRun(r);
      const [gj, po, zn, sc] = await Promise.all([
        api.geojson(pid), api.pois(pid), api.zones(pid), api.scoredListings(pid).catch(() => []),
      ]);
      setGeojson(gj); setPois(po); setZones(zn); setScored(sc);
    } finally { setBusy(false); }
  }, []);

  const seed = async () => {
    const p = await api.seedDemo();
    await refreshProfiles();
    selectProfile(p);
  };

  const saveAndRerun = async () => {
    if (!profile) return;
    const p = await api.saveProfile(profile);
    setSaved(JSON.parse(JSON.stringify(p)));
    await analyze(p.id);
  };

  const onCellClick = async (cellId: string) => {
    if (!profile) return;
    setDetail(await api.cellDetail(profile.id, cellId));
  };

  const toggleLayer = (k: string) =>
    setActiveLayers((s) => ({ ...s, [k]: s[k] === false }));

  const duplicate = async () => {
    if (!profile) return;
    const name = prompt("New profile name?", `${profile.city} copy`);
    if (!name) return;
    const city = prompt("City?", profile.city) || profile.city;
    const lat = parseFloat(prompt("Center latitude?", String(profile.center_lat)) || "");
    const lon = parseFloat(prompt("Center longitude?", String(profile.center_lon)) || "");
    if (isNaN(lat) || isNaN(lon)) return;
    const d = 0.055;
    const p = await api.duplicate(profile.id, {
      name, city, center_lat: lat, center_lon: lon,
      bbox: [lon - d, lat - d * 0.7, lon + d, lat + d * 0.7],
    });
    await refreshProfiles();
    selectProfile(p);
  };

  const reloadListings = async () => {
    if (profile) setScored(await api.scoredListings(profile.id).catch(() => []));
  };

  return (
    <div className="app">
      <header className="topbar">
        <h1>🏙️ Apartment Fit</h1>
        <div className="tabs">
          {(["analysis", "listings", "builder"] as Tab[]).map((t) => (
            <div key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
              {t === "analysis" ? "Area analysis" : t === "listings" ? "Listings" : "Criteria builder"}
            </div>
          ))}
        </div>
        <div className="spacer" />
        {profiles.length > 0 && (
          <select style={{ width: 220 }} value={profile?.id || ""}
            onChange={(e) => { const p = profiles.find((x) => x.id === e.target.value); if (p) selectProfile(p); }}>
            {profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        )}
        <button onClick={seed}>+ Seed Seattle demo</button>
        {profile && <button onClick={duplicate}>Duplicate…</button>}
        <span className="badge">{busy ? "analyzing…" : `provider: ${providerMode || "?"}`}</span>
      </header>

      {!profile ? (
        <div style={{ padding: 40 }}>
          <h2>Welcome</h2>
          <p className="muted">Seed the Seattle demo profile to begin, then explore qualifying areas on the map,
            adjust thresholds, and score listings.</p>
          <button className="primary" onClick={seed}>Seed Seattle demo profile</button>
        </div>
      ) : tab === "listings" ? (
        <div className="layout"><ListingsPanel profile={profile} scored={scored} reload={reloadListings} /></div>
      ) : tab === "builder" ? (
        <div className="layout"><div style={{ padding: 20, maxWidth: 720 }}>
          <AmbiguityHelper />
          <div className="card">
            <div className="section-title">About</div>
            <p className="muted" style={{ fontSize: 13 }}>
              The criteria builder flags vague concepts and suggests measurable alternatives. Configure the
              actual thresholds and weights in the Area analysis tab’s criteria editor. Each criterion is a
              hard requirement (pass/fail gate) or a weighted preference — preferences never rescue a failed
              hard requirement.
            </p>
          </div>
        </div></div>
      ) : (
        <div className="layout">
          <div className="sidebar">
            <TierSummary run={run} />
            <Legend activeLayers={activeLayers} toggle={toggleLayer} pois={pois} />
            <EliminationPanel run={run} />
            <ZoneList zones={zones} />
            <div className="card">
              <div className="section-title">Export</div>
              <div className="row">
                <a href={api.areaCsvUrl(profile.id)}><button className="small">Areas CSV</button></a>
                <a href={api.areaGeojsonUrl(profile.id)}><button className="small">Areas GeoJSON</button></a>
              </div>
            </div>
            <CriteriaEditor profile={profile} onChange={setProfile} onSave={saveAndRerun} dirty={dirty} />
          </div>
          <div className="main">
            <MapView profile={profile} geojson={geojson} pois={pois} zones={zones}
              activeLayers={activeLayers} onCellClick={onCellClick} />
            <CellDetailPanel detail={detail} onClose={() => setDetail(null)} />
          </div>
        </div>
      )}
    </div>
  );
}
