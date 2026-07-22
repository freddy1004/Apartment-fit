"use client";
import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
import { osmRasterStyle } from "../lib/mapStyle";
import { TIER_COLORS, type Profile, type Zone } from "../lib/types";

interface Props {
  profile: Profile;
  geojson: any | null;
  pois: Record<string, any[]>;
  zones: Zone[];
  activeLayers: Record<string, boolean>;
  onCellClick: (cellId: string) => void;
}

const POI_COLORS: Record<string, string> = {
  supermarket: "#48bb78",
  freeway_ramp: "#ed8936",
  transit_stop: "#4299e1",
  park: "#38a169",
  destinations: "#f56565",
};

export default function MapView({ profile, geojson, pois, zones, activeLayers, onCellClick }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  // init map once
  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: ref.current,
      style: osmRasterStyle,
      center: [profile.center_lon, profile.center_lat],
      zoom: 11.5,
    });
    map.addControl(new maplibregl.NavigationControl(), "bottom-right");
    map.on("load", () => {
      map.addSource("cells", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "cells-fill",
        type: "fill",
        source: "cells",
        paint: {
          "fill-color": [
            "match", ["get", "tier"],
            "strong_fit", TIER_COLORS.strong_fit,
            "qualifying", TIER_COLORS.qualifying,
            "borderline", TIER_COLORS.borderline,
            "ineligible", TIER_COLORS.ineligible,
            "insufficient_data", TIER_COLORS.insufficient_data,
            "#888",
          ],
          "fill-opacity": 0.5,
        },
      });
      map.addLayer({
        id: "cells-outline",
        type: "line",
        source: "cells",
        paint: { "line-color": "#0b1017", "line-width": 0.3 },
      });
      map.addSource("zones", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "zones-outline",
        type: "line",
        source: "zones",
        paint: { "line-color": "#4da3ff", "line-width": 2, "line-dasharray": [2, 1] },
      });
      map.on("click", "cells-fill", (e) => {
        const f = e.features?.[0];
        if (f) onCellClick(f.properties?.cell_id);
      });
      map.on("mouseenter", "cells-fill", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "cells-fill", () => (map.getCanvas().style.cursor = ""));
      mapRef.current = map;
      // force initial data paint
      map.fire("af:ready");
    });
    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // update cells + fit bounds
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !geojson) return;
    const apply = () => {
      const src = map.getSource("cells") as maplibregl.GeoJSONSource | undefined;
      if (!src) return;
      const visible = {
        ...geojson,
        features: geojson.features.filter((f: any) =>
          activeLayers[f.properties.tier] !== false,
        ),
      };
      src.setData(visible);
      if (profile.bbox?.length === 4) {
        map.fitBounds(
          [[profile.bbox[0], profile.bbox[1]], [profile.bbox[2], profile.bbox[3]]],
          { padding: 30, duration: 0 },
        );
      }
    };
    if (map.isStyleLoaded()) apply();
    else map.once("af:ready", apply);
  }, [geojson, activeLayers, profile.bbox]);

  // zones
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const src = map.getSource("zones") as maplibregl.GeoJSONSource | undefined;
      if (!src) return;
      src.setData({
        type: "FeatureCollection",
        features: (activeLayers["zones"] === false ? [] : zones).map((z) => ({
          type: "Feature",
          properties: { zone_id: z.zone_id },
          geometry: {
            type: "Polygon",
            coordinates: [[
              [z.min_lon, z.min_lat], [z.max_lon, z.min_lat],
              [z.max_lon, z.max_lat], [z.min_lon, z.max_lat], [z.min_lon, z.min_lat],
            ]],
          },
        })),
      });
    };
    if (map.isStyleLoaded()) apply();
    else map.once("af:ready", apply);
  }, [zones, activeLayers]);

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
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([p.lon, p.lat])
          .setPopup(new maplibregl.Popup({ offset: 10 }).setText(`${cat}: ${p.name}`))
          .addTo(map);
        markersRef.current.push(marker);
      });
    });
  }, [pois, activeLayers]);

  return <div id="map" ref={ref} />;
}
