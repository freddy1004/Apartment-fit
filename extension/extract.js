// Injected (after parse.js) into the active tab on demand. Extracts ONLY
// user-visible structured data already present on the page the user is viewing:
//   1. a site adapter's visible selectors (Zillow / Apartments.com / Redfin / …),
//   2. schema.org JSON-LD the page publishes,
//   3. Open Graph / meta tags,
//   4. visible text patterns (price, beds, baths, sqft).
// No navigation, no pagination, no hidden/private API calls, no anti-bot
// circumvention. If nothing usable is found, fields are left blank for manual
// confirmation.
(function extractListing() {
  const P = window.AFParse;
  const out = { source: "extension", source_url: location.href };
  const adapterName = P.pickAdapter(location.hostname);
  out.adapter = adapterName;

  const text = (el) => (el && (el.innerText || el.textContent) || "").trim();
  const firstText = (selectors) => {
    for (const sel of selectors || []) {
      const el = document.querySelector(sel);
      const t = text(el);
      if (t) return t;
    }
    return "";
  };

  // 1) Site adapter (visible selectors)
  const cfg = P.ADAPTERS[adapterName];
  const priceText = firstText(cfg.price);
  if (priceText) out.rent = P.parseRent(priceText);
  const summary = firstText(cfg.summary);
  Object.assign(out, P.parseBedBathSqft(summary));
  const addr = firstText(cfg.address);
  if (addr) out.address = addr;

  // 2) JSON-LD published by the page
  document.querySelectorAll('script[type="application/ld+json"]').forEach((el) => {
    try {
      const data = JSON.parse(el.textContent);
      const nodes = Array.isArray(data) ? data : [data];
      for (const n of nodes) {
        const a = n.address;
        if (a && typeof a === "object" && !out.address) {
          out.address = [a.streetAddress, a.addressLocality, a.addressRegion, a.postalCode].filter(Boolean).join(", ");
        } else if (typeof a === "string" && !out.address) out.address = a;
        const offer = n.offers || (n.mainEntity && n.mainEntity.offers);
        if (offer && offer.price && out.rent == null) out.rent = P.num(offer.price);
        if ((n.numberOfBedrooms || n.numberOfRooms) && out.bedrooms == null) out.bedrooms = P.num(n.numberOfBedrooms || n.numberOfRooms);
        if (n.numberOfBathroomsTotal && out.bathrooms == null) out.bathrooms = P.num(n.numberOfBathroomsTotal);
        if (n.floorSize && out.size == null) out.size = P.num(n.floorSize.value || n.floorSize);
        if (n.geo) { out.lat = P.num(n.geo.latitude); out.lon = P.num(n.geo.longitude); }
        if (n.name && !out.title) out.title = n.name;
      }
    } catch (_) { /* ignore malformed */ }
  });

  // 3) meta tags
  const meta = (p) => document.querySelector(`meta[property="${p}"],meta[name="${p}"]`)?.content;
  if (!out.title) out.title = meta("og:title") || document.title;
  if (!out.address && meta("og:street-address")) out.address = meta("og:street-address");

  // 4) visible body-text fallback
  const body = (document.body?.innerText || "").slice(0, 20000);
  if (out.rent == null) out.rent = P.parseRent(body);
  const bbs = P.parseBedBathSqft(body);
  ["bedrooms", "bathrooms", "size"].forEach((k) => { if (out[k] == null && bbs[k] != null) out[k] = bbs[k]; });
  if (/pet friendly|pets allowed|dogs? ok|cats? ok/i.test(body)) out.pets = true;
  if (/parking (included|available|garage)|garage parking/i.test(body)) out.parking = true;
  if (/in[- ]unit laundry|washer\/dryer in unit|in unit washer/i.test(body)) out.laundry = true;

  return out;
})();
