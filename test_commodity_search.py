"""
Automated Test Suite: Localized Commodity Search & Aliases
"""

import pytest
from backend.services.commodity_service import (
    search_commodities, get_autocomplete_suggestions, get_all_commodities
)
from backend.database import init_db
from backend.seed_data import seed_all

@pytest.fixture(scope="module", autouse=True)
def setup_seed():
    init_db()
    seed_all()

def test_multilingual_search_aliases():
    """Verify searching vernacular aliases resolves to canonical commodity."""
    # Searching Hindi/Urdu alias 'tamatar'
    res_hi = search_commodities("tamatar")
    assert any(c["id"] == "tomato" for c in res_hi), "Searching 'tamatar' must match Tomato."

    # Searching Tamil/Malayalam alias 'thakkali'
    res_ta = search_commodities("thakkali")
    assert any(c["id"] == "tomato" for c in res_ta), "Searching 'thakkali' must match Tomato."

    # Searching Marathi/Konkani alias 'batata'
    res_mr = search_commodities("batata")
    assert any(c["id"] == "potato" for c in res_mr), "Searching 'batata' must match Potato."

    # Searching Telugu alias 'ullipayalu'
    res_te = search_commodities("ullipayalu")
    assert any(c["id"] == "onion" for c in res_te), "Searching 'ullipayalu' must match Onion."

def test_autocomplete_suggestions():
    """Verify prefix suggestions for search inputs."""
    sugg = get_autocomplete_suggestions("tam")
    assert len(sugg) > 0
    assert any("tamatar" in s["term"] or "tamata" in s["term"] for s in sugg)

def test_catalog_retrieval_with_varieties():
    """Verify catalog commodities include varieties and units."""
    catalog = get_all_commodities(lang="en")
    assert len(catalog) >= 10
    
    tomato = next((c for c in catalog if c["id"] == "tomato"), None)
    assert tomato is not None
    assert len(tomato["varieties"]) > 0
    assert tomato["standard_unit"] == "kg"
