import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'delivery_system.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Couriers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS couriers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            vehicle_type TEXT NOT NULL,
            max_capacity_kg REAL NOT NULL,
            serviceable_localities TEXT NOT NULL,
            base_fare REAL NOT NULL DEFAULT 50.0,
            rate_per_kg REAL NOT NULL DEFAULT 15.0,
            rating REAL NOT NULL DEFAULT 4.5,
            is_active INTEGER NOT NULL DEFAULT 1,
            current_active_orders INTEGER NOT NULL DEFAULT 0,
            total_completed_orders INTEGER NOT NULL DEFAULT 0,
            wallet_balance REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL
        )
    ''')

    # 2. Deliveries table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id TEXT UNIQUE NOT NULL,
            sender_name TEXT NOT NULL,
            sender_phone TEXT NOT NULL,
            source_address TEXT NOT NULL,
            source_locality TEXT NOT NULL,
            receiver_name TEXT NOT NULL,
            receiver_phone TEXT NOT NULL,
            dest_address TEXT NOT NULL,
            dest_locality TEXT NOT NULL,
            package_weight_kg REAL NOT NULL,
            package_type TEXT NOT NULL,
            service_type TEXT NOT NULL,
            assigned_courier_id INTEGER NOT NULL,
            shipping_cost REAL NOT NULL,
            courier_payout REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Booked',
            booked_at TEXT NOT NULL,
            promised_delivery_time TEXT NOT NULL,
            actual_delivery_time TEXT,
            rescheduled_count INTEGER NOT NULL DEFAULT 0,
            is_archived INTEGER NOT NULL DEFAULT 0,
            archived_at TEXT,
            FOREIGN KEY (assigned_courier_id) REFERENCES couriers (id)
        )
    ''')

    # 3. Delivery Tracking Logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS delivery_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            remarks TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (delivery_id) REFERENCES deliveries (id)
        )
    ''')

    # 4. Reschedule Logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reschedule_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_id INTEGER NOT NULL,
            old_delivery_time TEXT NOT NULL,
            new_delivery_time TEXT NOT NULL,
            reason TEXT NOT NULL,
            rescheduled_at TEXT NOT NULL,
            FOREIGN KEY (delivery_id) REFERENCES deliveries (id)
        )
    ''')

    # 5. Cancellation Records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cancellation_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_id INTEGER NOT NULL,
            cancelled_by TEXT NOT NULL,
            reason TEXT NOT NULL,
            cancellation_fee REAL NOT NULL DEFAULT 0.0,
            refund_status TEXT NOT NULL DEFAULT 'Processed',
            cancelled_at TEXT NOT NULL,
            FOREIGN KEY (delivery_id) REFERENCES deliveries (id)
        )
    ''')

    # 6. Rewards and Penalties table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rewards_penalties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_id INTEGER NOT NULL,
            courier_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            reason TEXT NOT NULL,
            notice_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (delivery_id) REFERENCES deliveries (id),
            FOREIGN KEY (courier_id) REFERENCES couriers (id)
        )
    ''')

    conn.commit()
    seed_interconnected_data(conn)
    conn.close()

def seed_interconnected_data(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM couriers")
    count = cursor.fetchone()[0]

    if count == 0:
        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')

        # Real initial couriers with distinct localities, vehicles and pricing models
        couriers_data = [
            (
                "SwiftExpress Logistics (Ramesh Kumar)",
                "+91-9876543210",
                "ramesh.swift@example.com",
                "Motorbike",
                15.0,
                "Adampur, Barari, Station Road, Zero Mile, Tilkamanjhi",
                45.0,
                12.0,
                4.8,
                1,
                0,
                3,
                720.0,
                now_str
            ),
            (
                "BlueDart Regional (Anjali Verma)",
                "+91-9876543211",
                "anjali.bluedart@example.com",
                "Delivery Van",
                120.0,
                "Zero Mile, Mirjanhat, Nathnagar, Barari, Sabour, Adampur",
                75.0,
                10.0,
                4.9,
                1,
                0,
                2,
                550.0,
                now_str
            ),
            (
                "EcoRide City Couriers (Vikram Singh)",
                "+91-9876543212",
                "vikram.ecoride@example.com",
                "EV Cargo Scooter",
                25.0,
                "Station Road, Adampur, Tilkamanjhi, Mirjanhat",
                40.0,
                14.0,
                4.6,
                1,
                0,
                1,
                290.0,
                now_str
            ),
            (
                "SpeedyFreight Cargo (Pooja Sharma)",
                "+91-9876543213",
                "pooja.speedy@example.com",
                "Mini Truck",
                300.0,
                "Zero Mile, Sabour, Barari, Industrial Area, Station Road",
                120.0,
                8.0,
                4.7,
                1,
                0,
                1,
                410.0,
                now_str
            ),
            (
                "QuickDrop Hyperlocal (Mohit Raj)",
                "+91-9876543214",
                "mohit.quick@example.com",
                "Motorbike",
                12.0,
                "Tilkamanjhi, Adampur, Nathnagar, Mirjanhat",
                50.0,
                15.0,
                4.3,
                1,
                0,
                0,
                0.0,
                now_str
            )
        ]

        cursor.executemany('''
            INSERT INTO couriers (
                name, phone, email, vehicle_type, max_capacity_kg, serviceable_localities,
                base_fare, rate_per_kg, rating, is_active, current_active_orders,
                total_completed_orders, wallet_balance, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', couriers_data)

        conn.commit()

        # Seed interconnected delivered orders with reward & penalty notices so service queries have real historical records
        # 1. On-time delivery for Ramesh (Earned Reward)
        d1_time = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
        d1_promised = (now - timedelta(days=2, hours=-4)).strftime('%Y-%m-%d %H:%M:%S')
        d1_actual = (now - timedelta(days=2, hours=-3)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO deliveries (
                tracking_id, sender_name, sender_phone, source_address, source_locality,
                receiver_name, receiver_phone, dest_address, dest_locality,
                package_weight_kg, package_type, service_type, assigned_courier_id,
                shipping_cost, courier_payout, status, booked_at, promised_delivery_time,
                actual_delivery_time, rescheduled_count, is_archived, archived_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            "TRK-2026-001", "Amazon Hub Bhagalpur", "+91-9988776655", "Warehouse Rd 4", "Zero Mile",
            "Dr. Alok Sen", "+91-9123456780", "House 12, Main St", "Adampur",
            2.5, "Electronics", "Standard", 1,
            95.0, 75.0, "Delivered", d1_time, d1_promised, d1_actual, 0, 0, None
        ))
        d1_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
            VALUES (?, 'Booked', 'Delivery requested via portal and assigned to Ramesh Kumar', ?)
        ''', (d1_id, d1_time))
        cursor.execute('''
            INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
            VALUES (?, 'Delivered', 'Package safely handed over 1 hour ahead of schedule', ?)
        ''', (d1_id, d1_actual))

        cursor.execute('''
            INSERT INTO rewards_penalties (delivery_id, courier_id, type, amount, reason, notice_text, created_at)
            VALUES (?, 1, 'REWARD', 100.0, 'On-Time Delivery Bonus',
            'REWARD NOTICE: Excellent work! Order TRK-2026-001 was delivered 1.0 hr ahead of promised time. Bonus +₹100 credited.', ?)
        ''', (d1_id, d1_actual))

        # 2. Delayed delivery for Ramesh (Incurred Penalty)
        d2_time = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        d2_promised = (now - timedelta(days=1, hours=-2)).strftime('%Y-%m-%d %H:%M:%S')
        d2_actual = (now - timedelta(days=1, hours=-5)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO deliveries (
                tracking_id, sender_name, sender_phone, source_address, source_locality,
                receiver_name, receiver_phone, dest_address, dest_locality,
                package_weight_kg, package_type, service_type, assigned_courier_id,
                shipping_cost, courier_payout, status, booked_at, promised_delivery_time,
                actual_delivery_time, rescheduled_count, is_archived, archived_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            "TRK-2026-002", "Flipkart Fulfillment Center", "+91-9988776656", "Industrial Hub Lot 2", "Station Road",
            "Priya Rani", "+91-9123456781", "Flat 4B, Shivalik Apts", "Barari",
            3.0, "Apparel", "Standard", 1,
            110.0, 85.0, "Delivered", d2_time, d2_promised, d2_actual, 0, 0, None
        ))
        d2_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
            VALUES (?, 'Booked', 'Delivery accepted and allocated to Ramesh Kumar', ?)
        ''', (d2_id, d2_time))
        cursor.execute('''
            INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
            VALUES (?, 'Delivered', 'Delivered with 3 hours delay due to traffic', ?)
        ''', (d2_id, d2_actual))

        cursor.execute('''
            INSERT INTO rewards_penalties (delivery_id, courier_id, type, amount, reason, notice_text, created_at)
            VALUES (?, 1, 'PENALTY', 50.0, 'Late Delivery SLA Breach',
            'PENALTY NOTICE: Order TRK-2026-002 was delivered 3.0 hrs after promised deadline. Penalty -₹50 deducted from payout.', ?)
        ''', (d2_id, d2_actual))

        # 3. Active in-transit delivery for BlueDart (Anjali Verma)
        d3_time = (now - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
        d3_promised = (now + timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO deliveries (
                tracking_id, sender_name, sender_phone, source_address, source_locality,
                receiver_name, receiver_phone, dest_address, dest_locality,
                package_weight_kg, package_type, service_type, assigned_courier_id,
                shipping_cost, courier_payout, status, booked_at, promised_delivery_time,
                actual_delivery_time, rescheduled_count, is_archived, archived_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            "TRK-2026-003", "Tata 1mg Pharmacy", "+91-9988776657", "Medical Road 10", "Mirjanhat",
            "Prof. S. K. Sinha", "+91-9123456782", "Dept of CSE, IIIT Bhagalpur", "Sabour",
            1.2, "Medicines", "Express", 2,
            150.0, 110.0, "In Transit", d3_time, d3_promised, None, 0, 0, None
        ))
        d3_id = cursor.lastrowid

        # Update Anjali's active count
        cursor.execute("UPDATE couriers SET current_active_orders = 1 WHERE id = 2")

        cursor.execute('''
            INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
            VALUES (?, 'Booked', 'Express medicine order confirmed and assigned to Anjali Verma', ?)
        ''', (d3_id, d3_time))
        cursor.execute('''
            INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
            VALUES (?, 'Picked Up', 'Package picked up from Tata 1mg pharmacy counter', ?)
        ''', (d3_id, (now - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')))
        cursor.execute('''
            INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
            VALUES (?, 'In Transit', 'Transit via Sabour Bypass road', ?)
        ''', (d3_id, (now - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized and verified.")
