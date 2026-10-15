"""
Automated Test Suite: Direct Farmer Marketplace, Listings, Orders, and RBAC
"""

import pytest
from backend.services.marketplace_service import (
    create_product_listing, query_products, create_order,
    get_order_by_id, update_order_status
)
from backend.services.auth_service import authenticate_user, create_user
from backend.database import init_db
from backend.seed_data import seed_all

@pytest.fixture(scope="module", autouse=True)
def setup_seed():
    init_db()
    seed_all()

def test_farmer_listing_creation_and_query():
    """Verify farmers can create produce listings with stock, grade, and MOQ."""
    product_data = {
        "commodity_id": "tomato",
        "variety": "Avinash-2 Hybrid",
        "grade": "Grade A",
        "title": "Chittoor Special Red Tomatoes",
        "description": "Crisp salad-grade firm tomatoes.",
        "price_per_unit": 26.0,
        "unit": "kg",
        "available_quantity": 3000.0,
        "minimum_order_qty": 20.0,
        "bulk_discount_percentage": 5.0,
        "bulk_threshold_qty": 200.0,
        "harvest_date": "2026-10-14",
        "organic_certified": True,
        "location_state": "Andhra Pradesh",
        "location_district": "Chittoor",
        "image_url": "https://example.com/tomato.jpg"
    }

    prod = create_product_listing("demo_farmer_ramesh", product_data)
    assert prod["id"].startswith("prd_")
    assert prod["price_per_unit"] == 26.0
    assert prod["available_quantity"] == 3000.0
    assert prod["organic_certified"] == 1

    # Verify query finds the new product
    listed = query_products(district="Chittoor", search="Special Red")
    assert any(p["id"] == prod["id"] for p in listed)

def test_direct_order_placement_and_stock_deduction():
    """Verify buyers can place orders, stock is decremented, and order milestones tracked."""
    # Find an active product
    prods = query_products(district="Chittoor")
    assert len(prods) > 0
    target_prod = prods[0]
    initial_stock = target_prod["available_quantity"]

    order_qty = target_prod["minimum_order_qty"] + 5.0
    order_payload = {
        "items": [{"product_id": target_prod["id"], "quantity": order_qty}],
        "delivery_address": "42 MG Road, Tirupati",
        "delivery_district": "Chittoor",
        "delivery_state": "Andhra Pradesh",
        "delivery_pincode": "517501",
        "contact_phone": "9876543212",
        "payment_method": "cash_on_delivery"
    }

    order = create_order("demo_restaurant_anita", order_payload)
    assert order["id"].startswith("ord_")
    assert order["order_status"] == "pending"
    assert len(order["items"]) == 1
    assert order["total_amount"] > 0

    # Verify stock decremented
    refreshed_prods = query_products(district="Chittoor")
    refreshed = next(p for p in refreshed_prods if p["id"] == target_prod["id"])
    assert refreshed["available_quantity"] == initial_stock - order_qty

    # Verify status transition
    update_order_status(order["id"], "dispatched")
    updated_order = get_order_by_id(order["id"])
    assert updated_order["order_status"] == "dispatched"

def test_user_authentication_and_roles():
    """Verify credential hashing and role authentication."""
    user = authenticate_user("9876543210", "DemoPass@2026")
    assert user is not None
    assert user["role"] == "farmer"
    assert user["full_name"] == "Ramesh Patel"

    # Invalid password check
    bad_user = authenticate_user("9876543210", "WrongPassword")
    assert bad_user is None
