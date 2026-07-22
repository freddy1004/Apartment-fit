export type Tier =
  | "strong_fit"
  | "qualifying"
  | "borderline"
  | "ineligible"
  | "insufficient_data";

export interface Destination {
  label: string;
  lat?: number | null;
  lon?: number | null;
  amenity_type?: string | null;
}

export interface Criterion {
  id: string;
  type: string;
  scope: "area" | "listing";
  kind: "hard" | "preference";
  label: string;
  threshold?: number | null;
  units: string;
  comparator: string;
  weight: number;
  mode: string;
  method: string;
  destination?: Destination | null;
  tolerance: number;
  missing_data: string;
  enabled: boolean;
}

export interface Profile {
  id: string;
  name: string;
  city: string;
  center_lat: number;
  center_lon: number;
  bbox: number[];
  cell_size_m: number;
  criteria: Criterion[];
}

export interface EliminationRow {
  criterion_id: string;
  label: string;
  eliminated: number;
  eliminated_solely_by_this: number;
  pct_of_cells: number;
}

export interface RunResult {
  profile_id: string;
  cell_count: number;
  tier_counts: Record<string, number>;
  zone_count: number;
  elimination: EliminationRow[];
  bbox: number[];
}

export interface CriterionResult {
  criterion_id: string;
  label: string;
  kind: string;
  passed: boolean;
  preference_score: number | null;
  raw_value: number | null;
  units: string;
  threshold: number | null;
  weight: number;
  confidence: number;
  source: string;
  is_fallback: boolean;
  missing: boolean;
  explanation: string;
  detail?: Record<string, any>;
}

export interface CellDetail {
  cell_id: string;
  center: { lat: number; lon: number };
  tier: Tier;
  fit_score: number;
  hard_passed: boolean;
  confidence: number;
  criteria: CriterionResult[];
}

export interface Listing {
  id: string;
  address: string;
  lat?: number;
  lon?: number;
  rent?: number;
  bedrooms?: number;
  bathrooms?: number;
  size?: number;
  parking?: boolean;
  laundry?: boolean;
  pets?: boolean;
  favorite?: boolean;
  notes?: string;
  source?: string;
  source_url?: string;
  [k: string]: any;
}

export interface ScoredListing {
  listing: Listing;
  combined_fit: number;
  combined_tier: Tier;
  matched_zone: string | null;
  confidence?: number;
  area: { fit_score: number; hard_passed: boolean; tier: Tier; results: CriterionResult[] };
  listing_score: { fit_score: number; hard_passed: boolean; tier: Tier; results: CriterionResult[] };
}

export interface Zone {
  zone_id: string;
  cell_count: number;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
  centroid_lat: number;
  centroid_lon: number;
  avg_fit_score: number;
  nearby_neighborhoods: string[];
  cell_ids: string[];
}

export const TIER_COLORS: Record<string, string> = {
  strong_fit: "#1a9850",
  qualifying: "#91cf60",
  borderline: "#fee08b",
  ineligible: "#d73027",
  insufficient_data: "#9e9e9e",
};

export const TIER_LABELS: Record<string, string> = {
  strong_fit: "Strong fit",
  qualifying: "Qualifying",
  borderline: "Borderline",
  ineligible: "Ineligible",
  insufficient_data: "Insufficient data",
};
