"use client";
import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
import { osmRasterStyle } from "../lib/mapStyle";
import { TIER_COLORS, type Profile } from "../lib/types";

export interface LayerInfo {
  id: string;
  name: string;
  value_property: string | null;
  geojson: any;
}

interface Props {
  profile: Profile;
  geojson: any | null;
  pois: Record<string, any[]>;
  layers: LayerInfo[];
  activeLayers: Record<string, boolean>;
  drawMode: boolean;
  drawVertices: [number, number][];
  onDrawClick: (lng: number, lat: number) => void;
  onCellClick: (cellId: string) => void;
}

const POI_COLORS: Record<string, string> = {
  supermarket: "#48bb78", freeway_ramp: "#ed8936", transit_stop: "#4299e1",
  transit_any: "#63b3ed", park: "#38a169", destinations: "#f56565",
};

function colorRamp(layer: LayerInfo): any {
  const prop = layer.value_property;
  if (!prop) return "rgba(120,120,255,0.25)";
  const vals = (layer.geojson.features || [])
    .map((f: any) => f.properties?.[prop]).filter((v: any) => typeof v === "number");
  if (!vals.length) return "rgba(120,120,255,0.25)";
  const min = Math.min(...vals), max = Math.max(...vals);
  const mid = (min + max) / 2;
  return ["interpolate", ["linear"], ["get", prop],
    min, "#2c7fb8", mid, "#fdae61", max, "#d7191c"];
}

export default function MapView(props: Props) {
  const { profile, geojson, pois, layers, activeLayers, drawMode, drawVertices, onDrawClick, onCellClick } = props;
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const drawModeRef = useRef(drawMode);
  const onDrawClickRef = useRef(onDrawClick);
  const onCellClickRef = useRef(onCellClick);
  const layerIdsRef = useRef<string[]>([]);
  drawModeRef.current = drawMode;
  onDrawClickRef.current = onDrawClick;
  onCellClickRef.current = onCellClick;

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: ref.current, style: osmRasterStyle,
      center: [profile.center_lon, profile.center_lat], zoom: 11.5,
    });
    map.addControl(new maplibregl.NavigationControl(), "bottom-right");
    map.on("load", () => {
      map.addSource("cells", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "cells-fill", type: "fill", source: "cells",
        paint: {
          "fill-color": ["match", ["get", "tier"],
            "strong_fit", TIER_COLORS.strong_fit, "qualifying", TIER_COLORS.qualifying,
            "borderline", TIER_COLORS.borderline, "ineligible", TIER_COLORS.ineligible,
            "insufficient_data", TIER_COLORS.insufficient_data, "#888"],
          "fill-opacity": 0.5,
        },
      });
      map.addLayer({ id: "cells-outline", type: "line", source: "cells", paint: { "line-color": "#0b1017", "line-width": 0.3 } });
      // in-progress drawing
      map.addSource("draw", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({ id: "draw-fill", type: "fill", source: "draw", paint: { "fill-color": "#f6ad55", "fill-opacity": 0.25 } });
      map.addLayer({ id: "draw-line", type: "line", source: "draw", paint: { "line-color": "#f6ad55", "line-width": 2 } });
      map.addLayer({ id: "draw-pts", type: "circle", source: "draw", filter: ["==", "$type", "Point"], paint: { "circle-radius": 4, "circle-color": "#f6ad55" } });

      map.on("click", "cells-fill", (e) => {
        if (drawModeRef.current) return;
        const f = e.features?.[0];
        if (f) onCellClickRef.current(f.properties?.cell_id);
      });
      map.on("click", (e) => {
        if (drawModeRef.current) onDrawClickRef.current(e.lngLat.lng, e.lngLat.lat);
      });
      map.on("mouseenter", "cells-fill", () => { if (!drawModeRef.current) map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "cells-fill", () => { map.getCanvas().style.cursor = ""; });
      mapRef.current = map;
      map.fire("af:ready");
    });
    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // cursor for draw mode
  useEffect(() => {
    const map = mapRef.current;
    if (map) map.getCanvas().style.cursor = drawMode ? "crosshair" : "";
  }, [drawMode]);

  const whenReady = (map: maplibregl.Map, fn: () => void) => {
    if (map.isStyleLoaded()) fn(); else map.once("af:ready", fn);
  };

  // cells
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !geojson) return;
    whenReady(map, () => {
      const src = map.getSource("cells") as maplibregl.GeoJSONSource | undefined;
      if (!src) return;
      src.setData({ ...geojson, features: geojson.features.filter((f: any) => activeLayers[f.properties.tier] !== false) });
      if (profile.bbox?.length === 4) {
        map.fitBounds([[profile.bbox[0], profile.bbox[1]], [profile.bbox[2], profile.bbox[3]]], { padding: 30, duration: 0 });
      }
    });
  }, [geojson, activeLayers, profile.bbox]);

  // imported/generated layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    whenReady(map, () => {
      // remove stale layer/sources
      layerIdsRef.current.forEach((id) => {
        if (map.getLayer(`lyr-${id}`)) map.removeLayer(`lyr-${id}`);
        if (map.getLayer(`lyr-${id}-line`)) map.removeLayer(`lyr-${id}-line`);
        if (map.getSource(`lyr-${id}`)) map.removeSource(`lyr-${id}`);
      });
      layerIdsRef.current = layers.map((l) => l.id);
      for (const l of layers) {
        if (activeLayers[`layer:${l.id}`] !== true) continue; // off by default
        map.addSource(`lyr-${l.id}`, { type: "geojson", data: l.geojson });
        const before = map.getLayer("cells-fill") ? "cells-fill" : undefined;
        map.addLayer({ id: `lyr-${l.id}`, type: "fill", source: `lyr-${l.id}`, paint: { "fill-color": colorRamp(l), "fill-opacity": 0.45 } }, before);
        map.addLayer({ id: `lyr-${l.id}-line`, type: "line", source: `lyr-${l.id}`, paint: { "line-color": "#0b1017", "line-width": 0.2 } }, before);
      }
    });
  }, [layers, activeLayers]);

  // draw preview
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    whenReady(map, () => {
      const src = map.getSource("draw") as maplibregl.GeoJSONSource | undefined;
      if (!src) return;
      const pts = drawVertices.map((v) => ({ type: "Feature" as const, properties: {}, geometry: { type: "Point" as const, coordinates: v } }));
      const feats: any[] = [...pts];
      if (drawVertices.length >= 2) {
        const ring = drawVertices.length >= 3 ? [...drawVertices, drawVertices[0]] : drawVertices;
        feats.push({ type: "Feature", properties: {}, geometry: { type: drawVertices.length >= 3 ? "Polygon" : "LineString", coordinates: drawVertices.length >= 3 ? [ring] : ring } });
      }
      src.setData({ type: "FeatureCollection", features: feats });
    });
  }, [drawVertices]);

  // POI markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    Object.entries(pois).forEach(([cat, points]) => {
      if (activeLayers[`poi:${cat}`] === false) return;
      points.forEach((p) => {
        const el = document.createElement("div");
        el.style.cssText = `width:10px;height:10px;border-radius:50%;border:1px solid #000;background:${POI_COLORS[cat] || "#fff"}`;
        markersRef.current.push(new maplibregl.Marker({ element: el }).setLngLat([p.lon, p.lat])
          .setPopup(new maplibregl.Popup({ offset: 10 }).setText(`${cat}: ${p.name}`)).addTo(map));
      });
    });
  }, [pois, activeLayers]);

  return <div id="map" ref={ref} />;
}
