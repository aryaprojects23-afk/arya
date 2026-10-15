"""
HarvestLink 2.0 - Price Comparison Engine ("Know Your Mandi Price")
Handles unit normalization (quintal, kg, tonne, crate), variance math, gross revenue estimations,
and official disclaimer disclosures.
"""

from typing import Dict, Any, Optional
import math
from backend.config import GOV_ATTRIBUTION

# Supported standard agricultural units and their conversion factor to 1 kilogram (kg)
UNIT_TO_KG_FACTORS = {
    "kg": 1.0,
    "kilogram": 1.0,
    "quintal": 100.0,
    "q": 100.0,
    "tonne": 1000.0,
    "ton": 1000.0,
    "metric_tonne": 1000.0,
    "crate": 25.0, # Standard Indian tomato/vegetable crate is approx 25 kg
    "bag_50kg": 50.0,
}

def normalize_unit_to_kg(quantity: float, unit: str) -> float:
    """Convert any supported agricultural quantity to kilograms."""
    unit_key = unit.lower().strip()
    factor = UNIT_TO_KG_FACTORS.get(unit_key)
    if factor is None:
        raise ValueError(f"Unsupported unit: '{unit}'. Supported units: {list(UNIT_TO_KG_FACTORS.keys())}")
    return quantity * factor

def normalize_price_to_per_kg(price_per_unit: float, unit: str) -> float:
    """Convert price per specified unit to price per kilogram (₹/kg)."""
    unit_key = unit.lower().strip()
    factor = UNIT_TO_KG_FACTORS.get(unit_key)
    if factor is None:
        raise ValueError(f"Unsupported unit: '{unit}'. Supported units: {list(UNIT_TO_KG_FACTORS.keys())}")
    return price_per_unit / factor

def compare_farmer_price_with_mandi(
    proposed_price: float,
    quantity: float,
    unit: str,
    mandi_modal_price_per_quintal: float,
    mandi_min_price_per_quintal: float,
    mandi_max_price_per_quintal: float,
    commodity_name: str,
    market_name: str,
    reporting_date: str,
    data_freshness: str = "Fresh"
) -> Dict[str, Any]:
    """
    Perform decimal-safe mathematical comparison between a farmer's proposed selling price
    and official government Agmarknet APMC mandi prices.
    
    All prices are normalized to INR/kg for rigorous apples-to-apples comparison.
    """
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    if proposed_price < 0:
        raise ValueError("Proposed price cannot be negative.")
    if mandi_modal_price_per_quintal <= 0:
        raise ValueError("Mandi modal price must be greater than zero.")

    # 1. Normalize units
    qty_in_kg = normalize_unit_to_kg(quantity, unit)
    proposed_price_per_kg = normalize_price_to_per_kg(proposed_price, unit)

    # 2. Normalize Agmarknet prices (recorded in Rs/Quintal -> 100 kg)
    mandi_modal_per_kg = mandi_modal_price_per_quintal / 100.0
    mandi_min_per_kg = mandi_min_price_per_quintal / 100.0
    mandi_max_per_kg = mandi_max_price_per_quintal / 100.0

    # 3. Compute price differences
    diff_per_kg = round(proposed_price_per_kg - mandi_modal_per_kg, 2)
    percent_diff = round(((proposed_price_per_kg - mandi_modal_per_kg) / mandi_modal_per_kg) * 100, 2)

    # 4. Compute Gross Sales Values
    farmer_gross = round(proposed_price_per_kg * qty_in_kg, 2)
    mandi_gross = round(mandi_modal_per_kg * qty_in_kg, 2)
    gross_variance = round(farmer_gross - mandi_gross, 2)

    # 5. Determine sentiment and user guidance
    if diff_per_kg > 0.05:
        sentiment = "above_modal"
        status_label = f"₹{abs(diff_per_kg):.2f}/kg above Mandi Modal (+{percent_diff:.1f}%)"
    elif diff_per_kg < -0.05:
        sentiment = "below_modal"
        status_label = f"₹{abs(diff_per_kg):.2f}/kg below Mandi Modal ({percent_diff:.1f}%)"
    else:
        sentiment = "at_modal"
        status_label = "Identical to Mandi Modal Rate (0.0%)"

    formula_explanation = (
        f"Farmer Price: ₹{proposed_price_per_kg:.2f}/kg ({proposed_price}/{unit}) | "
        f"Govt Agmarknet Modal: ₹{mandi_modal_per_kg:.2f}/kg (₹{mandi_modal_price_per_quintal:.0f}/Quintal) | "
        f"Volume: {qty_in_kg:.1f} kg ({quantity} {unit})"
    )

    is_msp_warning = (
        "Note: Agmarknet APMC modal rates represent wholesale auction prices reported by market yards, "
        "not official Government Minimum Support Price (MSP) announcements."
    )

    return {
        "commodity_name": commodity_name,
        "input_unit": unit,
        "normalized_quantity_kg": qty_in_kg,
        "farmer_proposed_price_per_input_unit": proposed_price,
        "farmer_proposed_price_per_kg": round(proposed_price_per_kg, 2),
        "government_mandi_name": market_name,
        "government_reporting_date": reporting_date,
        "mandi_modal_price_per_quintal": round(mandi_modal_price_per_quintal, 2),
        "mandi_modal_price_per_kg": round(mandi_modal_per_kg, 2),
        "mandi_min_price_per_kg": round(mandi_min_per_kg, 2),
        "mandi_max_price_per_kg": round(mandi_max_per_kg, 2),
        "price_difference_per_kg": diff_per_kg,
        "percentage_difference": percent_diff,
        "farmer_gross_sale_value": farmer_gross,
        "mandi_equivalent_gross_value": mandi_gross,
        "gross_variance_value": gross_variance,
        "comparison_sentiment": sentiment,
        "status_label": status_label,
        "formula_explanation": formula_explanation,
        "is_msp_warning": is_msp_warning,
        "source_attribution": GOV_ATTRIBUTION,
        "data_freshness": data_freshness
    }
