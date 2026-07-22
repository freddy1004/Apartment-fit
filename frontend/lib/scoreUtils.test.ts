import { describe, expect, it } from "vitest";
import { filterListings, sortListings } from "./scoreUtils";
import type { ScoredListing } from "./types";

function mk(id: string, fit: number, tier: any, rent: number, fav = false, confidence = 0.5): ScoredListing {
  return {
    listing: { id, address: id, rent, favorite: fav },
    combined_fit: fit,
    combined_tier: tier,
    matched_zone: null,
    confidence,
    area: { fit_score: fit, hard_passed: tier !== "ineligible", tier, results: [] },
    listing_score: { fit_score: fit, hard_passed: true, tier, results: [] },
  };
}

const rows = [
  mk("a", 90, "strong_fit", 2000, true),
  mk("b", 60, "qualifying", 1500),
  mk("c", 0, "ineligible", 1000),
];

describe("sortListings", () => {
  it("sorts by combined fit descending", () => {
    const r = sortListings(rows, "combined_fit", false);
    expect(r.map((x) => x.listing.id)).toEqual(["a", "b", "c"]);
  });
  it("sorts by rent ascending", () => {
    const r = sortListings(rows, "rent", true);
    expect(r.map((x) => x.listing.id)).toEqual(["c", "b", "a"]);
  });
  it("breaks ties by confidence", () => {
    const tied = [
      mk("low", 70, "qualifying", 1500, false, 0.3),
      mk("high", 70, "qualifying", 1500, false, 0.9),
    ];
    const r = sortListings(tied, "combined_fit", false);
    expect(r.map((x) => x.listing.id)).toEqual(["high", "low"]);
  });
});

describe("filterListings", () => {
  it("filters favorites", () => {
    expect(filterListings(rows, { onlyFavorites: true }).map((x) => x.listing.id)).toEqual(["a"]);
  });
  it("hides ineligible", () => {
    expect(filterListings(rows, { hideIneligible: true }).map((x) => x.listing.id)).toEqual(["a", "b"]);
  });
});
