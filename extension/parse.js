// Pure, DOM-free parsing helpers + per-site adapter config.
//
// UMD wrapper so the SAME code runs in two places:
//   - injected into a page (exposes window.AFParse), used by extract.js
//   - imported in Node for unit tests (module.exports)
//
// Adapters are declarative *selector lists* (which visible elements to read on
// each site). All DOM access happens in extract.js; this file stays pure and
// testable. Adapters only ever read user-visible fields on the open page.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.AFParse = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function num(s) {
    if (s == null) return null;
    const m = String(s).replace(/,/g, "").match(/-?\d+(\.\d+)?/);
    return m ? parseFloat(m[0]) : null;
  }

  // Parse a "3 bd | 2 ba | 1,500 sqft" style summary string.
  function parseBedBathSqft(text) {
    const out = {};
    if (!text) return out;
    const bd = text.match(/(\d+(?:\.\d+)?)\s*(?:bd|beds?|bedrooms?)\b/i);
    const ba = text.match(/(\d+(?:\.\d+)?)\s*(?:ba|baths?|bathrooms?)\b/i);
    const sf = text.match(/([\d,]{3,6})\s*(?:sq\s?ft|sqft|square\s?feet)/i);
    if (bd) out.bedrooms = num(bd[1]);
    if (ba) out.bathrooms = num(ba[1]);
    if (sf) out.size = num(sf[1]);
    return out;
  }

  function parseRent(text) {
    if (!text) return null;
    const m = text.match(/\$\s?([\d,]{3,7})/);
    return m ? num(m[1]) : null;
  }

  // Declarative site adapters: ordered selector lists per field.
  const ADAPTERS = {
    zillow: {
      host: "zillow.com",
      price: ['[data-testid="price"]', "span[data-testid='price']", ".summary-container h3"],
      summary: ['[data-testid="bed-bath-sqft-fact-container"]', ".summary-container"],
      address: ["h1"],
    },
    apartments: {
      host: "apartments.com",
      price: [".priceBedRangeInfoInnerContainer .rentInfoDetail", ".priceInfo", ".rentRollup"],
      summary: [".priceBedRangeInfo", ".propertyInfoBar"],
      address: [".propertyAddressContainer h1", "h1.propertyName"],
    },
    redfin: {
      host: "redfin.com",
      price: ['[data-rf-test-id="abp-price"] .statsValue', ".price"],
      summary: [".stats", ".home-main-stats"],
      address: [".street-address", "h1"],
    },
    trulia: {
      host: "trulia.com",
      price: ['[data-testid="price"]', "h3"],
      summary: ['[data-testid="facts"]', ".facts"],
      address: ["h1"],
    },
    hotpads: {
      host: "hotpads.com",
      price: ['[data-testid="price"]', ".Listing-price", ".price"],
      summary: [".Listing-facts", ".HdpBanner-facts", ".facts"],
      address: [".Listing-address", "h1"],
    },
    craigslist: {
      // Seattle: seattle.craigslist.org
      host: "craigslist.org",
      price: [".price", ".postingtitletext .price"],
      summary: [".attrgroup", ".mapAndAttrs"],
      address: [".postingtitletext", "h1.postingtitle"],
    },
    zumper: {
      host: "zumper.com",
      price: ['[class*="price"]', ".listing-price"],
      summary: ['[class*="MediaSummary"]', ".listing-details"],
      address: ['[class*="address"]', "h1"],
    },
    padmapper: {
      host: "padmapper.com",
      price: [".Price", '[class*="price"]'],
      summary: [".Description-details", '[class*="ListingSummary"]'],
      address: [".FullDescription-address", "h1"],
    },
    realtor: {
      host: "realtor.com",
      price: ['[data-testid="list-price"]', '[data-label="pc-price"]', ".Price__Component"],
      summary: ['[data-testid="property-meta"]', ".ldp-key-facts"],
      address: ['[data-testid="address"]', "h1"],
    },
    generic: { host: "", price: [], summary: [], address: ["h1"] },
  };

  function pickAdapter(hostname) {
    const h = (hostname || "").toLowerCase();
    for (const [name, cfg] of Object.entries(ADAPTERS)) {
      if (cfg.host && h.includes(cfg.host)) return name;
    }
    return "generic";
  }

  return { num, parseBedBathSqft, parseRent, pickAdapter, ADAPTERS };
});
