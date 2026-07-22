# Prebuilt OSRM image: bakes a prepared routing graph into the image so the
# service starts instantly with no volume mounting or runtime data prep.
#
# Build it with a region + profile already prepared by scripts/build-osrm.sh:
#   scripts/build-osrm.sh washington bicycle
#   docker build -f docker/osrm/Dockerfile \
#     --build-arg REGION=washington --build-arg PROFILE=bicycle \
#     -t apartment-fit/osrm-bicycle ./osm-data
#
# Then point OSRM_URL_BIKE at a container running this image.
FROM osrm/osrm-backend:v5.27.1

ARG REGION=washington
ARG PROFILE=bicycle

# Expects ./osm-data/<REGION>.osrm* (built by scripts/build-osrm.sh) as context.
COPY ${REGION}.osrm* /data/
ENV OSRM_FILE=/data/${REGION}.osrm

EXPOSE 5000
CMD ["sh", "-c", "osrm-routed --algorithm mld ${OSRM_FILE}"]
