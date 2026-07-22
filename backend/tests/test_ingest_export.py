from app.analysis.demo import seattle_demo_profile
from app.analysis.engine import run_city_analysis, score_listing
from app.analysis.exporters import (
    area_results_to_csv,
    area_results_to_geojson,
    listing_scores_to_csv,
)
from app.listings import ingest
from app.providers.registry import Providers

PROV = Providers("fixture")


def test_normalize_coerces_types():
    li = ingest.normalize_listing({
        "address": "123 Main", "rent": "$1,800/mo", "bedrooms": "2",
        "pets": "allowed", "parking": "no",
    })
    assert li["rent"] == 1800.0
    assert li["bedrooms"] == 2.0
    assert li["pets"] is True
    assert li["parking"] is False
    assert li["id"]


def test_detect_listing_site():
    assert ingest.detect_listing_site("https://www.zillow.com/homedetails/x") == "zillow"
    assert ingest.detect_listing_site("https://redfin.com/x") == "redfin"


def test_from_url_stub_no_scraping():
    stub = ingest.from_url_stub("https://www.zillow.com/b/123")
    assert stub["needs_manual_confirmation"] is True
    assert stub["source"] == "zillow"
    assert "lat" not in stub  # nothing scraped


def test_from_csv_and_json():
    csv_text = "address,rent,bedrooms\nGreen Lake,1800,2\nBallard,2200,3\n"
    rows = ingest.from_csv(csv_text)
    assert len(rows) == 2
    assert rows[0]["rent"] == 1800.0

    json_text = '{"listings": [{"address": "Fremont", "rent": 1900, "bedrooms": 1}]}'
    jrows = ingest.from_json(json_text)
    assert jrows[0]["rent"] == 1900.0


def test_area_exports():
    profile = seattle_demo_profile()
    result = run_city_analysis(profile, PROV)
    gj = area_results_to_geojson(result)
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == len(result.cells)
    assert gj["features"][0]["properties"]["tier"]

    csv_text = area_results_to_csv(result)
    assert "cell_id" in csv_text.splitlines()[0]
    assert len(csv_text.splitlines()) == len(result.cells) + 1


def test_listing_export_csv():
    profile = seattle_demo_profile()
    analysis = run_city_analysis(profile, PROV)
    listings = [
        {"id": "L1", "address": "Green Lake", "lat": 47.6806, "lon": -122.3286,
         "rent": 1800, "bedrooms": 2},
    ]
    scores = [score_listing(profile, li, PROV, analysis) for li in listings]
    by_id = {li["id"]: li for li in listings}
    csv_text = listing_scores_to_csv(scores, by_id)
    assert "combined_fit" in csv_text
    assert "L1" in csv_text
