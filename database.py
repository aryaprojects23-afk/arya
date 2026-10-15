"""
HarvestLink 2.0 - Database Module
SQLite connection, schema initialization, migrations, and transactional helpers.
"""

import sqlite3
import logging
from contextlib import contextmanager
from backend.config import DATABASE_PATH

logger = logging.getLogger("harvestlink.database")

def get_db_connection():
    """Create and return a configured sqlite3 connection with dict-like row access."""
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

@contextmanager
def db_session():
    """Context manager for atomic database operations with automatic commit/rollback."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error during transaction: {e}")
        raise
    finally:
        conn.close()

def init_db():
    """Initialize full database schema with required tables, indexes, and constraints."""
    with db_session() as conn:
        cursor = conn.cursor()

        # 1. Users and Profiles
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('farmer', 'consumer', 'restaurant', 'retailer', 'wholesaler', 'admin')),
            is_active INTEGER DEFAULT 1,
            is_verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            organization_name TEXT,
            gstin TEXT,
            state TEXT NOT NULL,
            district TEXT NOT NULL,
            village_or_mandal TEXT,
            pincode TEXT,
            address TEXT,
            latitude REAL,
            longitude REAL,
            avatar_url TEXT,
            bio TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_language_preferences (
            user_id TEXT PRIMARY KEY,
            preferred_language TEXT NOT NULL DEFAULT 'en',
            auto_translate INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)

        # 2. Canonical Commodities, Translations, Aliases & Varieties
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS commodities (
            id TEXT PRIMARY KEY, -- e.g. 'tomato', 'potato'
            canonical_name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL CHECK(category IN ('vegetables', 'fruits', 'cereals', 'pulses', 'spices', 'oilseeds', 'commercial')),
            scientific_name TEXT,
            standard_unit TEXT NOT NULL DEFAULT 'kg', -- 'kg', 'quintal'
            image_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS commodity_translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commodity_id TEXT NOT NULL,
            language_code TEXT NOT NULL,
            localized_name TEXT NOT NULL,
            script TEXT,
            FOREIGN KEY (commodity_id) REFERENCES commodities(id) ON DELETE CASCADE,
            UNIQUE(commodity_id, language_code)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS commodity_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commodity_id TEXT NOT NULL,
            alias_term TEXT NOT NULL,
            language_code TEXT, -- optional: specific language or general
            is_regional_dialect INTEGER DEFAULT 0,
            FOREIGN KEY (commodity_id) REFERENCES commodities(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS commodity_varieties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commodity_id TEXT NOT NULL,
            variety_name TEXT NOT NULL,
            grade_standards TEXT, -- 'Grade A', 'Grade B', 'FAQ' (Fair Average Quality)
            FOREIGN KEY (commodity_id) REFERENCES commodities(id) ON DELETE CASCADE,
            UNIQUE(commodity_id, variety_name)
        );
        """)

        # 3. Mandi Markets & Official Government Price Records
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id TEXT PRIMARY KEY, -- slug e.g. 'ap-chittoor-chittoor'
            name TEXT NOT NULL,
            state TEXT NOT NULL,
            district TEXT NOT NULL,
            apmc_code TEXT,
            latitude REAL,
            longitude REAL,
            is_active INTEGER DEFAULT 1
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS government_market_price_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_record_id TEXT, -- original OGD / Agmarknet record ID
            state TEXT NOT NULL,
            district TEXT NOT NULL,
            market_name TEXT NOT NULL,
            commodity_name TEXT NOT NULL,
            variety TEXT NOT NULL DEFAULT 'Other',
            grade TEXT NOT NULL DEFAULT 'FAQ',
            arrival_date DATE NOT NULL,
            min_price REAL NOT NULL, -- in INR per Quintal
            max_price REAL NOT NULL, -- in INR per Quintal
            modal_price REAL NOT NULL, -- in INR per Quintal
            price_unit TEXT NOT NULL DEFAULT 'Rs/Quintal',
            arrivals_in_tonnes REAL DEFAULT 0.0,
            retrieval_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_live_synced INTEGER DEFAULT 0,
            raw_source_json TEXT,
            UNIQUE(state, district, market_name, commodity_name, variety, grade, arrival_date)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS government_data_sync_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_name TEXT NOT NULL, -- 'OGD_API' or 'FALLBACK_SEED'
            records_fetched INTEGER DEFAULT 0,
            records_inserted INTEGER DEFAULT 0,
            records_updated INTEGER DEFAULT 0,
            status TEXT NOT NULL, -- 'SUCCESS', 'PARTIAL', 'FAILED'
            error_message TEXT,
            response_time_ms INTEGER
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS provider_health_status (
            provider_id TEXT PRIMARY KEY,
            provider_name TEXT NOT NULL,
            is_healthy INTEGER DEFAULT 1,
            consecutive_failures INTEGER DEFAULT 0,
            last_checked_at TIMESTAMP,
            last_success_at TIMESTAMP,
            last_status_code INTEGER,
            latency_ms INTEGER,
            message TEXT
        );
        """)

        # 4. Direct Marketplace: Farmer Products, Inventory & Bulk Pricing
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            farmer_id TEXT NOT NULL,
            commodity_id TEXT NOT NULL,
            variety TEXT NOT NULL,
            grade TEXT NOT NULL DEFAULT 'Grade A',
            title TEXT NOT NULL,
            description TEXT,
            price_per_unit REAL NOT NULL, -- INR per standard unit (e.g. per kg)
            unit TEXT NOT NULL DEFAULT 'kg', -- 'kg', 'quintal', 'crate'
            available_quantity REAL NOT NULL,
            minimum_order_qty REAL NOT NULL DEFAULT 1.0,
            bulk_discount_percentage REAL DEFAULT 0.0,
            bulk_threshold_qty REAL DEFAULT 0.0,
            harvest_date DATE,
            organic_certified INTEGER DEFAULT 0,
            location_state TEXT NOT NULL,
            location_district TEXT NOT NULL,
            image_url TEXT,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'paused', 'sold_out', 'deleted')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (commodity_id) REFERENCES commodities(id)
        );
        """)

        # 5. Orders, Line Items, Shipments & Payments
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            order_number TEXT UNIQUE NOT NULL,
            buyer_id TEXT NOT NULL,
            total_amount REAL NOT NULL,
            currency TEXT DEFAULT 'INR',
            order_status TEXT NOT NULL DEFAULT 'pending' 
                CHECK(order_status IN ('pending', 'confirmed', 'packed', 'dispatched', 'out_for_delivery', 'delivered', 'cancelled', 'rejected')),
            delivery_address TEXT NOT NULL,
            delivery_pincode TEXT NOT NULL,
            delivery_state TEXT NOT NULL,
            delivery_district TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'pending' CHECK(payment_status IN ('pending', 'escrow_held', 'released_to_farmer', 'refunded')),
            payment_method TEXT NOT NULL DEFAULT 'cash_on_delivery' CHECK(payment_method IN ('upi', 'bank_transfer', 'cash_on_delivery', 'card')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (buyer_id) REFERENCES users(id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            farmer_id TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            item_status TEXT NOT NULL DEFAULT 'pending' CHECK(item_status IN ('pending', 'accepted', 'rejected', 'dispatched', 'delivered')),
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (farmer_id) REFERENCES users(id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS quotations (
            id TEXT PRIMARY KEY,
            buyer_id TEXT NOT NULL,
            farmer_id TEXT NOT NULL,
            commodity_id TEXT NOT NULL,
            requested_quantity REAL NOT NULL,
            unit TEXT NOT NULL DEFAULT 'kg',
            target_price_per_unit REAL,
            offered_price_per_unit REAL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'countered', 'accepted', 'rejected', 'expired')),
            buyer_notes TEXT,
            farmer_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            valid_until TIMESTAMP,
            FOREIGN KEY (buyer_id) REFERENCES users(id),
            FOREIGN KEY (farmer_id) REFERENCES users(id),
            FOREIGN KEY (commodity_id) REFERENCES commodities(id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            buyer_id TEXT NOT NULL,
            farmer_id TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment TEXT,
            verified_purchase INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (buyer_id) REFERENCES users(id),
            FOREIGN KEY (farmer_id) REFERENCES users(id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS translation_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            language_code TEXT NOT NULL,
            translation_key TEXT NOT NULL,
            current_text TEXT NOT NULL,
            suggested_correction TEXT,
            user_notes TEXT,
            reporter_user_id TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'reviewed', 'applied', 'rejected')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id TEXT,
            action_type TEXT NOT NULL,
            target_entity TEXT NOT NULL,
            target_id TEXT,
            details_json TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Indexes for fast querying
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mandi_state_dist ON government_market_price_records(state, district);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mandi_commodity ON government_market_price_records(commodity_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mandi_date ON government_market_price_records(arrival_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_commodity ON products(commodity_id, status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_location ON products(location_state, location_district);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_aliases_term ON commodity_aliases(alias_term);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_buyer ON orders(buyer_id);")

        logger.info("HarvestLink database tables and indexes initialized successfully.")

if __name__ == "__main__":
    init_db()
    print("HarvestLink 2.0 Database successfully initialized at:", DATABASE_PATH)
