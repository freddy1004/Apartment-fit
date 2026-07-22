import type { ScoredListing, Tier } from "./types";

export const TIER_RANK: Record<Tier, number> = {
  strong_fit: 4,
  qualifying: 3,
  borderline: 2,
  insufficient_data: 1,
  ineligible: 0,
};

export function sortListings(
  rows: ScoredListing[],
  key: string,
  asc: boolean,
): ScoredListing[] {
  const get = (s: ScoredListing): number | string =>
    key === "combined_fit" ? s.combined_fit
    : key === "rent" ? (s.listing.rent ?? 0)
    : key === "bedrooms" ? (s.listing.bedrooms ?? 0)
    : key === "area" ? s.area.fit_score
    : key === "listing" ? s.listing_score.fit_score
    : key === "tier" ? TIER_RANK[s.combined_tier]
    : s.listing.address ?? "";
  return [...rows].sort((a, b) => {
    const av = get(a), bv = get(b);
    const cmp =
      typeof av === "number" && typeof bv === "number"
        ? av - bv
        : String(av).localeCompare(String(bv));
    return asc ? cmp : -cmp;
  });
}

export function filterListings(
  rows: ScoredListing[],
  opts: { onlyFavorites?: boolean; hideIneligible?: boolean },
): ScoredListing[] {
  let r = rows;
  if (opts.onlyFavorites) r = r.filter((s) => s.listing.favorite);
  if (opts.hideIneligible) r = r.filter((s) => s.combined_tier !== "ineligible");
  return r;
}
