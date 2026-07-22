// Injected into the active tab on demand. Extracts ONLY user-visible structured
// data already present on the page the user is looking at:
//   1. schema.org JSON-LD blocks the page publishes,
//   2. Open Graph / meta tags,
//   3. visible text patterns (price, beds, baths, sqft).
// It performs no navigation, no pagination, no hidden/private API calls, and no
// anti-bot circumvention. If nothing usable is found, fields are left blank for
// manual confirmation.
(function extractListing() {
  const out = { source: "extension", source_url: location.href };

  const num = (s) => {
    if (s == null) return null;
    const m = String(s).replace(/,/g, "").match(/-?\d+(\.\d+)?/);
    return m ? parseFloat(m[0]) : null;
  };

  // 1) JSON-LD
  document.querySelectorAll('script[type="application/ld+json"]').forEach((el) => {
    try {
      const data = JSON.parse(el.textContent);
      const nodes = Array.isArray(data) ? data : [data];
      for (const n of nodes) {
        const addr = n.address;
        if (addr && typeof addr === "object") {
          out.address = [addr.streetAddress, addr.addressLocality, addr.addressRegion, addr.postalCode]
            .filter(Boolean).join(", ");
        } else if (typeof addr === "string" && !out.address) {
          out.address = addr;
        }
        const offer = n.offers || (n.mainEntity && n.mainEntity.offers);
        if (offer && offer.price && out.rent == null) out.rent = num(offer.price);
        if (n.numberOfRooms && out.bedrooms == null) out.bedrooms = num(n.numberOfRooms);
        if (n.numberOfBedrooms && out.bedrooms == null) out.bedrooms = num(n.numberOfBedrooms);
        if (n.numberOfBathroomsTotal && out.bathrooms == null) out.bathrooms = num(n.numberOfBathroomsTotal);
        if (n.floorSize && out.size == null) out.size = num(n.floorSize.value || n.floorSize);
        if (n.geo) { out.lat = num(n.geo.latitude); out.lon = num(n.geo.longitude); }
        if (n.name && !out.title) out.title = n.name;
      }
    } catch (_) { /* ignore malformed */ }
  });

  // 2) meta tags
  const meta = (p) => document.querySelector(`meta[property="${p}"],meta[name="${p}"]`)?.content;
  if (!out.title) out.title = meta("og:title") || document.title;
  if (!out.address && meta("og:street-address")) out.address = meta("og:street-address");

  // 3) visible text fallback (bounded to the visible body text)
  const text = (document.body?.innerText || "").slice(0, 20000);
  if (out.rent == null) { const m = text.match(/\$\s?([\d,]{3,7})\s*(?:\/mo|per month|month)?/i); if (m) out.rent = num(m[1]); }
  if (out.bedrooms == null) { const m = text.match(/(\d+(?:\.\d+)?)\s*(?:bd|beds?|bedrooms?)\b/i); if (m) out.bedrooms = num(m[1]); }
  if (out.bathrooms == null) { const m = text.match(/(\d+(?:\.\d+)?)\s*(?:ba|baths?|bathrooms?)\b/i); if (m) out.bathrooms = num(m[1]); }
  if (out.size == null) { const m = text.match(/([\d,]{3,6})\s*(?:sq\s?ft|sqft|square feet)/i); if (m) out.size = num(m[1]); }
  out.pets = /pet friendly|pets allowed|dogs? ok|cats? ok/i.test(text) ? true : undefined;
  out.parking = /parking (included|available|garage)|garage parking/i.test(text) ? true : undefined;
  out.laundry = /in[- ]unit laundry|washer\/dryer in unit|in unit washer/i.test(text) ? true : undefined;

  return out;
})();
