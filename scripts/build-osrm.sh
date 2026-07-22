#!/usr/bin/env bash
# Download an OSM extract and prepare an OSRM routing graph for one profile.
#
# Usage:   scripts/build-osrm.sh <region> <profile>
# Example: scripts/build-osrm.sh washington bicycle
#
# Profiles: car | bicycle | foot  (map to OSRM's /opt/*.lua)
# Output:   ./osm-data/<region>.osrm*  (consumed by docker/osrm/Dockerfile or a
#           volume mount in docker-compose's osrm service)
#
# Requires Docker. This downloads a multi-GB extract and can take a while.
set -euo pipefail

REGION="${1:-washington}"
PROFILE="${2:-bicycle}"
OSRM_IMG="osrm/osrm-backend:v5.27.1"
DATA_DIR="$(pwd)/osm-data"
# Geofabrik path (adjust for other regions/continents as needed).
PBF_URL="${PBF_URL:-https://download.geofabrik.de/north-america/us/${REGION}-latest.osm.pbf}"

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

if [ ! -f "${REGION}.osm.pbf" ]; then
  echo ">> Downloading ${PBF_URL}"
  curl -L -o "${REGION}.osm.pbf" "$PBF_URL"
fi

run() { docker run --rm -t -v "$DATA_DIR:/data" "$OSRM_IMG" "$@"; }

echo ">> Extracting (${PROFILE})"
run osrm-extract -p "/opt/${PROFILE}.lua" "/data/${REGION}.osm.pbf"
echo ">> Partitioning"
run osrm-partition "/data/${REGION}.osrm"
echo ">> Customizing"
run osrm-customize "/data/${REGION}.osrm"

echo ">> Done. Graph ready at ${DATA_DIR}/${REGION}.osrm"
echo "   Run:  PROVIDER_MODE=osm OSRM_URL_BIKE=http://osrm:5000 docker compose --profile osm up"
