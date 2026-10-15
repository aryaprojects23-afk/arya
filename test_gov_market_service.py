"""
Automated Test Suite: Official Government Mandi Price Adapter & Services
"""

import pytest
from datetime import datetime
from backend.services.gov_market_service import (
    GovMarketPriceAdapter, query_market_prices, get_mandi_trends,
    get_nearby_mandi_comparisons, get_distinct_locations_and_commodities
)
from backend.database import init_db
from backend.seed_data import seed_all

@pytest.fixture(scope="module", autouse=True)
def setup_seed():
    init_db()
    seed_all()

def test_adapter_record_normalization_and_idempotency():
    """Verify that government records with varying key names are normalized and stored idempotently."""
    adapter = GovMarketPriceAdapter()
    
    mock_raw_records = [
        {
            "State": "Andhra Pradesh",
            "District": "Chittoor",
            "Market": "Chittoor APMC",
            "Commodity": "Tomato",
            "Variety": "Hybrid",
            "Grade": "FAQ",
            "Arrival_Date": "2026-10-15",
            "Min_Price": "1800",
            "Max_Price": "2600",
            "Modal_Price": "2200",
            "Arrivals_Tonnes": "50.5"
        },
        {
            "state": "Maharashtra",
            "district": "Pune",
            "market_name": "Pune APMC",
            "commodity_name": "Onion",
            "variety": "Red",
            "grade": "FAQ",
            "arrival_date": "15/10/2026",
            "min_price": 2000,
            "max_price": 2800,
            "modal_price": 2400,
            "arrivals_in_qtl": 80.0
        }
    ]

    # First pass: insertion
    res1 = adapter.normalize_and_store_records(mock_raw_records, is_live=True)
    assert res1["inserted"] + res1["updated"] == 2

    # Second pass: duplicate prevention & idempotent update
    res2 = adapter.normalize_and_store_records(mock_raw_records, is_live=True)
    assert res2["updated"] == 2
    assert res2["inserted"] == 0

def test_query_market_prices_with_filters():
    """Verify that market prices can be filtered by state, district, commodity and freshness."""
    res = query_market_prices(state="Andhra Pradesh", district="Chittoor", commodity="Tomato")
    assert res["total"] > 0
    assert len(res["data"]) > 0
    
    first = res["data"][0]
    assert first["state"] == "Andhra Pradesh"
    assert first["district"] == "Chittoor"
    assert "Tomato" in first["commodity_name"]
    assert first["modal_price"] > 0
    assert first["freshness_status"] in ("Live", "Fresh", "Stale (Cached)")
    assert "Agmarknet" in res["source_attribution"]

def test_mandi_trends_calculation():
    """Verify historical price trends projection (average, min, max, chronology)."""
    trends_res = get_mandi_trends(commodity="Tomato", market_name="Chittoor APMC", days=30)
    assert trends_res["records_count"] > 0
    assert "trends" in trends_res
    assert trends_res["summary"]["average_modal_price"] > 0
    
    # Chronological order check
    dates = [t["date"] for t in trends_res["trends"]]
    assert dates == sorted(dates), "Trend points must be in chronological order."

def test_nearby_mandi_comparisons():
    """Verify nearby market comparison within district (e.g. Chittoor vs Madanapalle)."""
    nearby = get_nearby_mandi_comparisons("Andhra Pradesh", "Chittoor", "Tomato")
    assert len(nearby) > 0
    market_names = [m["market_name"] for m in nearby]
    assert any("Chittoor" in m for m in market_names)

def test_provider_health_monitoring():
    """Verify health status endpoint returns provider info and cached records metrics."""
    adapter = GovMarketPriceAdapter()
    health = adapter.get_provider_health()
    assert health["provider_id"] == "ogd_agmarknet_in"
    assert health["total_records_cached"] > 0
    assert "Agmarknet" in health["source_attribution"]
