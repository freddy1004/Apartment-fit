import type { StyleSpecification } from "maplibre-gl";

// A minimal raster basemap using OpenStreetMap tiles (loaded by the user's
// browser at runtime). If tiles fail to load (offline), the vector overlays
// still render on the dark background.
export const osmRasterStyle: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#0f1720" } },
    { id: "osm", type: "raster", source: "osm", paint: { "raster-opacity": 0.55 } },
  ],
};
