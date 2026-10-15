"""
HarvestLink 2.0 - Direct Farmer-to-Buyer Marketplace Service
Handles products, inventory, shopping cart, direct order fulfillment,
B2B wholesale quotations, and verified customer reviews.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.database import db_session

def create_product_listing(farmer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new produce listing with inventory, bulk discounts, and quality grades."""
    product_id = f"prd_{uuid.uuid4().hex[:12]}"
    now_str = datetime.now().isoformat()

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (
                id, farmer_id, commodity_id, variety, grade, title, description,
                price_per_unit, unit, available_quantity, minimum_order_qty,
                bulk_discount_percentage, bulk_threshold_qty, harvest_date,
                organic_certified, location_state, location_district, image_url, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """, (
            product_id, farmer_id, data["commodity_id"], data["variety"],
            data.get("grade", "Grade A"), data["title"], data.get("description", ""),
            data["price_per_unit"], data.get("unit", "kg"), data["available_quantity"],
            data.get("minimum_order_qty", 1.0), data.get("bulk_discount_percentage", 0.0),
            data.get("bulk_threshold_qty", 0.0), data.get("harvest_date"),
            1 if data.get("organic_certified") else 0,
            data["location_state"], data["location_district"],
            data.get("image_url", "https://images.unsplash.com/photo-1592924357228-91a4daadcfea?w=600")
        ))

    return get_product_by_id(product_id)

def get_product_by_id(product_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full product details including farmer metadata and live mandi reference."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, u.full_name as farmer_name, u.phone as farmer_phone,
                   c.canonical_name as commodity_name, c.category as commodity_category
            FROM products p
            JOIN users u ON p.farmer_id = u.id
            JOIN commodities c ON p.commodity_id = c.id
            WHERE p.id = ?
        """, (product_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        prod = dict(row)
        
        # Look up latest mandi modal reference price for this commodity and district
        cursor.execute("""
            SELECT modal_price, arrival_date, market_name
            FROM government_market_price_records
            WHERE LOWER(commodity_name) LIKE ? AND state = ?
            ORDER BY arrival_date DESC LIMIT 1
        """, (f"%{prod['commodity_name'].lower()}%", prod["location_state"]))
        mandi_ref = cursor.fetchone()
        if mandi_ref:
            prod["mandi_reference_price_per_kg"] = round(mandi_ref["modal_price"] / 100.0, 2)
            prod["mandi_reference_market"] = mandi_ref["market_name"]
            prod["mandi_reference_date"] = mandi_ref["arrival_date"]
        else:
            prod["mandi_reference_price_per_kg"] = None

        return prod

def query_products(
    category: str = None,
    state: str = None,
    district: str = None,
    search: str = None,
    organic_only: bool = False,
    sort_by: str = "newest",
    farmer_id: str = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Search and filter farm listings with search-alias support."""
    conditions = ["p.status = 'active'"]
    params = []

    if farmer_id:
        conditions.append("p.farmer_id = ?")
        params.append(farmer_id)
    if category and category != "all":
        conditions.append("c.category = ?")
        params.append(category)
    if state:
        conditions.append("p.location_state = ?")
        params.append(state)
    if district:
        conditions.append("p.location_district = ?")
        params.append(district)
    if organic_only:
        conditions.append("p.organic_certified = 1")
    if search:
        search_term = f"%{search.lower().strip()}%"
        conditions.append("""
            (LOWER(p.title) LIKE ? OR LOWER(c.canonical_name) LIKE ? OR LOWER(p.variety) LIKE ?
             OR EXISTS (
                 SELECT 1 FROM commodity_aliases ca
                 WHERE ca.commodity_id = p.commodity_id AND LOWER(ca.alias_term) LIKE ?
             ))
        """)
        params.extend([search_term, search_term, search_term, search_term])

    order_clause = "ORDER BY p.created_at DESC"
    if sort_by == "price_low":
        order_clause = "ORDER BY p.price_per_unit ASC"
    elif sort_by == "price_high":
        order_clause = "ORDER BY p.price_per_unit DESC"

    where_sql = " WHERE " + " AND ".join(conditions)

    with db_session() as conn:
        cursor = conn.cursor()
        query = f"""
            SELECT p.*, u.full_name as farmer_name, c.canonical_name as commodity_name,
                   c.category as commodity_category
            FROM products p
            JOIN users u ON p.farmer_id = u.id
            JOIN commodities c ON p.commodity_id = c.id
            {where_sql}
            {order_clause}
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [limit, offset])
        rows = cursor.fetchall()
        
        products = []
        for r in rows:
            prod = dict(r)
            # Find closest mandi benchmark
            cursor.execute("""
                SELECT modal_price FROM government_market_price_records
                WHERE LOWER(commodity_name) LIKE ? AND state = ?
                ORDER BY arrival_date DESC LIMIT 1
            """, (f"%{prod['commodity_name'].lower()}%", prod["location_state"]))
            mandi_row = cursor.fetchone()
            prod["mandi_reference_price_per_kg"] = round(mandi_row[0] / 100.0, 2) if mandi_row else None
            products.append(prod)

        return products

def get_farmer_dashboard_stats(farmer_id: str) -> Dict[str, Any]:
    """Retrieve key performance indicators for farmer portal."""
    with db_session() as conn:
        cursor = conn.cursor()
        
        # Active listings count
        cursor.execute("SELECT COUNT(*) FROM products WHERE farmer_id = ? AND status = 'active'", (farmer_id,))
        active_listings = cursor.fetchone()[0]

        # Total revenue from delivered orders
        cursor.execute("""
            SELECT COALESCE(SUM(oi.total_price), 0.0)
            FROM order_items oi
            WHERE oi.farmer_id = ? AND oi.item_status IN ('delivered', 'accepted', 'dispatched')
        """, (farmer_id,))
        total_sales = cursor.fetchone()[0]

        # Pending orders count
        cursor.execute("""
            SELECT COUNT(DISTINCT o.id)
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            WHERE oi.farmer_id = ? AND o.order_status = 'pending'
        """, (farmer_id,))
        pending_orders = cursor.fetchone()[0]

        # Pending wholesale quotes
        cursor.execute("SELECT COUNT(*) FROM quotations WHERE farmer_id = ? AND status = 'pending'", (farmer_id,))
        pending_quotes = cursor.fetchone()[0]

        return {
            "active_listings": active_listings,
            "total_sales": round(total_sales, 2),
            "pending_orders": pending_orders,
            "pending_quotes": pending_quotes
        }

def create_order(buyer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Place direct farm-to-buyer order across multiple items with stock deduction."""
    order_id = f"ord_{uuid.uuid4().hex[:12]}"
    order_number = f"HL-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    
    total_amount = 0.0
    items_to_insert = []

    with db_session() as conn:
        cursor = conn.cursor()

        for it in data["items"]:
            prod_id = it["product_id"]
            qty = float(it["quantity"])
            
            cursor.execute("SELECT * FROM products WHERE id = ? AND status = 'active'", (prod_id,))
            prod = cursor.fetchone()
            if not prod:
                raise ValueError(f"Product {prod_id} is unavailable or sold out.")
            
            if qty > prod["available_quantity"]:
                raise ValueError(f"Insufficient stock for {prod['title']}. Available: {prod['available_quantity']}")
            if qty < prod["minimum_order_qty"]:
                raise ValueError(f"Order quantity {qty} below minimum requirement of {prod['minimum_order_qty']}")

            # Calculate price with bulk discount if eligible
            unit_price = prod["price_per_unit"]
            if prod["bulk_discount_percentage"] > 0 and qty >= prod["bulk_threshold_qty"] > 0:
                discount = (prod["bulk_discount_percentage"] / 100.0) * unit_price
                unit_price -= discount

            line_total = round(unit_price * qty, 2)
            total_amount += line_total

            items_to_insert.append({
                "product_id": prod_id,
                "farmer_id": prod["farmer_id"],
                "quantity": qty,
                "unit": prod["unit"],
                "unit_price": round(unit_price, 2),
                "total_price": line_total
            })

            # Deduct stock
            new_stock = prod["available_quantity"] - qty
            new_status = 'sold_out' if new_stock <= 0 else 'active'
            cursor.execute("UPDATE products SET available_quantity = ?, status = ? WHERE id = ?", (new_stock, new_status, prod_id))

        # Insert order
        cursor.execute("""
            INSERT INTO orders (
                id, order_number, buyer_id, total_amount, currency, order_status,
                delivery_address, delivery_pincode, delivery_state, delivery_district,
                contact_phone, payment_method, payment_status
            ) VALUES (?, ?, ?, ?, 'INR', 'pending', ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            order_id, order_number, buyer_id, total_amount,
            data["delivery_address"], data["delivery_pincode"],
            data["delivery_state"], data["delivery_district"],
            data["contact_phone"], data.get("payment_method", "cash_on_delivery")
        ))

        for item in items_to_insert:
            cursor.execute("""
                INSERT INTO order_items (
                    order_id, product_id, farmer_id, quantity, unit, unit_price, total_price, item_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                order_id, item["product_id"], item["farmer_id"], item["quantity"],
                item["unit"], item["unit_price"], item["total_price"]
            ))

    return get_order_by_id(order_id)

def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full order details and order lines."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.*, u.full_name as buyer_name, u.phone as buyer_phone
            FROM orders o
            JOIN users u ON o.buyer_id = u.id
            WHERE o.id = ?
        """, (order_id,))
        order_row = cursor.fetchone()
        if not order_row:
            return None

        order = dict(order_row)
        cursor.execute("""
            SELECT oi.*, p.title as product_title, u.full_name as farmer_name
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            JOIN users u ON oi.farmer_id = u.id
            WHERE oi.order_id = ?
        """, (order_id,))
        order["items"] = [dict(r) for r in cursor.fetchall()]
        return order

def update_order_status(order_id: str, new_status: str, actor_id: str = None) -> bool:
    """Transition order status through fulfillment lifecycle."""
    valid_statuses = ('pending', 'confirmed', 'packed', 'dispatched', 'out_for_delivery', 'delivered', 'cancelled')
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid order status: {new_status}")

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET order_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, order_id))
        cursor.execute("UPDATE order_items SET item_status = ? WHERE order_id = ?", (new_status, order_id))
        return True

def create_quotation(buyer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Submit B2B wholesale price quotation enquiry."""
    quote_id = f"qte_{uuid.uuid4().hex[:12]}"
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO quotations (
                id, buyer_id, farmer_id, commodity_id, requested_quantity,
                unit, target_price_per_unit, buyer_notes, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            quote_id, buyer_id, data["farmer_id"], data["commodity_id"],
            data["requested_quantity"], data.get("unit", "kg"),
            data.get("target_price_per_unit"), data.get("buyer_notes")
        ))
    return {"id": quote_id, "status": "pending"}

def create_review(buyer_id: str, data: Dict[str, Any]) -> int:
    """Add verified purchase review and rating."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT farmer_id FROM products WHERE id = ?", (data["product_id"],))
        p_row = cursor.fetchone()
        farmer_id = p_row[0] if p_row else "unknown"

        cursor.execute("""
            INSERT INTO reviews (order_id, product_id, buyer_id, farmer_id, rating, comment, verified_purchase)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (data["order_id"], data["product_id"], buyer_id, farmer_id, data["rating"], data.get("comment", "")))
        return cursor.lastrowid
