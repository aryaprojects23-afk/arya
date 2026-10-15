"""
Automated Test Suite: Farmer Price-Comparison Engine ("Know Your Mandi Price")
"""

import pytest
from backend.services.price_comparison import (
    normalize_unit_to_kg,
    normalize_price_to_per_kg,
    compare_farmer_price_with_mandi
)

def test_unit_normalization():
    """Verify agricultural unit conversions to standard kilograms."""
    assert normalize_unit_to_kg(1, "kg") == 1.0
    assert normalize_unit_to_kg(1, "quintal") == 100.0
    assert normalize_unit_to_kg(2.5, "tonne") == 2500.0
    assert normalize_unit_to_kg(10, "crate") == 250.0

    # Unsupported unit test
    with pytest.raises(ValueError):
        normalize_unit_to_kg(10, "unknown_unit")

def test_price_per_kg_normalization():
    """Verify price conversions to standard INR/kg."""
    assert normalize_price_to_per_kg(25.0, "kg") == 25.0
    # ₹2500 per quintal = ₹25 per kg
    assert normalize_price_to_per_kg(2500.0, "quintal") == 25.0
    # ₹500 per 25kg crate = ₹20 per kg
    assert normalize_price_to_per_kg(500.0, "crate") == 20.0

def test_price_comparison_above_modal():
    """Test farmer proposing price higher than government modal rate."""
    # Farmer: ₹28/kg, Mandi modal: ₹2200/Q (₹22/kg)
    comp = compare_farmer_price_with_mandi(
        proposed_price=28.0,
        quantity=1000.0,
        unit="kg",
        mandi_modal_price_per_quintal=2200.0,
        mandi_min_price_per_quintal=1800.0,
        mandi_max_price_per_quintal=2600.0,
        commodity_name="Tomato",
        market_name="Chittoor APMC",
        reporting_date="2026-10-15"
    )

    assert comp["comparison_sentiment"] == "above_modal"
    assert comp["farmer_proposed_price_per_kg"] == 28.0
    assert comp["mandi_modal_price_per_kg"] == 22.0
    assert comp["price_difference_per_kg"] == 6.0
    assert comp["percentage_difference"] == round((6.0 / 22.0) * 100, 2)
    assert comp["farmer_gross_sale_value"] == 28000.0
    assert comp["mandi_equivalent_gross_value"] == 22000.0
    assert comp["gross_variance_value"] == 6000.0
    assert "Agmarknet" in comp["source_attribution"]
    assert "MSP" in comp["is_msp_warning"]

def test_price_comparison_below_modal():
    """Test farmer proposing price lower than government modal rate."""
    # Farmer: ₹1800/Q (₹18/kg), Mandi modal: ₹2000/Q (₹20/kg)
    comp = compare_farmer_price_with_mandi(
        proposed_price=1800.0,
        quantity=5.0,
        unit="quintal",
        mandi_modal_price_per_quintal=2000.0,
        mandi_min_price_per_quintal=1600.0,
        mandi_max_price_per_quintal=2400.0,
        commodity_name="Tomato",
        market_name="Madanapalle APMC",
        reporting_date="2026-10-15"
    )

    assert comp["comparison_sentiment"] == "below_modal"
    assert comp["farmer_proposed_price_per_kg"] == 18.0
    assert comp["mandi_modal_price_per_kg"] == 20.0
    assert comp["price_difference_per_kg"] == -2.0
    assert comp["percentage_difference"] == -10.0
    assert comp["normalized_quantity_kg"] == 500.0
    assert comp["farmer_gross_sale_value"] == 9000.0
    assert comp["mandi_equivalent_gross_value"] == 10000.0
    assert comp["gross_variance_value"] == -1000.0

def test_price_comparison_validation_errors():
    """Test invalid input parameters (negative price, zero quantity)."""
    with pytest.raises(ValueError):
        compare_farmer_price_with_mandi(
            proposed_price=25.0, quantity=0, unit="kg",
            mandi_modal_price_per_quintal=2000.0, mandi_min_price_per_quintal=1500.0,
            mandi_max_price_per_quintal=2500.0, commodity_name="Tomato",
            market_name="Test", reporting_date="2026-10-15"
        )
