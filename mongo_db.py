import os
from datetime import datetime, timedelta
import random

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

DEFAULT_MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/delivery_system')

_mongo_client = None
_mongo_db = None
_is_connected = False
_current_uri = DEFAULT_MONGO_URI

def get_mongo_client(uri=None, timeout_ms=2000):
    global _mongo_client, _mongo_db, _is_connected, _current_uri
    if not PYMONGO_AVAILABLE:
        _is_connected = False
        return None, None

    target_uri = uri or _current_uri
    try:
        client = MongoClient(target_uri, serverSelectionTimeoutMS=timeout_ms)
        # Test connection with ping
        client.admin.command('ping')
        
        # Extract db name or default
        db_name = 'delivery_system'
        if '/' in target_uri.split('?')[0]:
            parts = target_uri.split('?')[0].split('/')
            if parts[-1] and not parts[-1].startswith('mongodb'):
                db_name = parts[-1]
                
        db = client[db_name]
        _mongo_client = client
        _mongo_db = db
        _is_connected = True
        _current_uri = target_uri
        return client, db
    except Exception as e:
        _is_connected = False
        return None, None

def is_mongo_connected():
    global _is_connected
    if not _is_connected or _mongo_client is None:
        client, db = get_mongo_client(timeout_ms=1000)
        return _is_connected
    try:
        _mongo_client.admin.command('ping')
        return True
    except Exception:
        _is_connected = False
        return False

def get_db_status():
    connected = is_mongo_connected()
    return {
        'pymongo_installed': PYMONGO_AVAILABLE,
        'mongo_connected': connected,
        'current_engine': 'MongoDB' if connected else 'SQLite',
        'mongo_uri': _current_uri if connected else 'Not connected (using local SQLite)',
        'sqlite_fallback': True
    }

def init_mongo_collections(db):
    """Ensure indexes and initial seed documents exist in MongoDB."""
    if db is None:
        return

    # Create indexes
    db.couriers.create_index('id', unique=True)
    db.deliveries.create_index('tracking_id', unique=True)
    db.rewards_penalties.create_index('id', unique=True)

    # Seed if empty
    if db.couriers.count_documents({}) == 0:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        seed_couriers = [
            {
                "id": 1,
                "name": "SwiftExpress Logistics (Ramesh Kumar)",
                "phone": "+91-9876543210",
                "email": "ramesh.swift@example.com",
                "vehicle_type": "Motorbike",
                "max_capacity_kg": 15.0,
                "serviceable_localities": "Adampur, Barari, Station Road, Zero Mile, Tilkamanjhi",
                "base_fare": 45.0,
                "rate_per_kg": 12.0,
                "rating": 4.8,
                "is_active": 1,
                "current_active_orders": 0,
                "total_completed_orders": 3,
                "wallet_balance": 720.0,
                "created_at": now_str
            },
            {
                "id": 2,
                "name": "BlueDart Regional (Anjali Verma)",
                "phone": "+91-9876543211",
                "email": "anjali.bluedart@example.com",
                "vehicle_type": "Delivery Van",
                "max_capacity_kg": 120.0,
                "serviceable_localities": "Zero Mile, Mirjanhat, Nathnagar, Barari, Sabour, Adampur",
                "base_fare": 75.0,
                "rate_per_kg": 10.0,
                "rating": 4.9,
                "is_active": 1,
                "current_active_orders": 1,
                "total_completed_orders": 2,
                "wallet_balance": 550.0,
                "created_at": now_str
            },
            {
                "id": 3,
                "name": "EcoRide City Couriers (Vikram Singh)",
                "phone": "+91-9876543212",
                "email": "vikram.ecoride@example.com",
                "vehicle_type": "EV Cargo Scooter",
                "max_capacity_kg": 25.0,
                "serviceable_localities": "Station Road, Adampur, Tilkamanjhi, Mirjanhat",
                "base_fare": 40.0,
                "rate_per_kg": 14.0,
                "rating": 4.6,
                "is_active": 1,
                "current_active_orders": 0,
                "total_completed_orders": 1,
                "wallet_balance": 290.0,
                "created_at": now_str
            },
            {
                "id": 4,
                "name": "SpeedyFreight Cargo (Pooja Sharma)",
                "phone": "+91-9876543213",
                "email": "pooja.speedy@example.com",
                "vehicle_type": "Mini Truck",
                "max_capacity_kg": 300.0,
                "serviceable_localities": "Zero Mile, Sabour, Barari, Industrial Area, Station Road",
                "base_fare": 120.0,
                "rate_per_kg": 8.0,
                "rating": 4.7,
                "is_active": 1,
                "current_active_orders": 0,
                "total_completed_orders": 1,
                "wallet_balance": 410.0,
                "created_at": now_str
            },
            {
                "id": 5,
                "name": "QuickDrop Hyperlocal (Mohit Raj)",
                "phone": "+91-9876543214",
                "email": "mohit.quick@example.com",
                "vehicle_type": "Motorbike",
                "max_capacity_kg": 12.0,
                "serviceable_localities": "Tilkamanjhi, Adampur, Nathnagar, Mirjanhat",
                "base_fare": 50.0,
                "rate_per_kg": 15.0,
                "rating": 4.3,
                "is_active": 1,
                "current_active_orders": 0,
                "total_completed_orders": 0,
                "wallet_balance": 0.0,
                "created_at": now_str
            }
        ]
        db.couriers.insert_many(seed_couriers)

def sync_sqlite_to_mongo(conn, db):
    """One-way sync from SQLite tables to MongoDB collections."""
    if db is None:
        return False, "MongoDB not connected"

    cursor = conn.cursor()
    
    # Sync couriers
    cursor.execute("SELECT * FROM couriers")
    for row in cursor.fetchall():
        doc = dict(row)
        db.couriers.update_one({'id': doc['id']}, {'$set': doc}, upsert=True)

    # Sync deliveries
    cursor.execute("SELECT * FROM deliveries")
    for row in cursor.fetchall():
        doc = dict(row)
        # Fetch related milestones
        cursor.execute("SELECT * FROM delivery_logs WHERE delivery_id = ? ORDER BY id ASC", (doc['id'],))
        doc['milestones'] = [dict(m) for m in cursor.fetchall()]

        # Fetch reschedules
        cursor.execute("SELECT * FROM reschedule_logs WHERE delivery_id = ? ORDER BY id DESC", (doc['id'],))
        doc['reschedule_history'] = [dict(r) for r in cursor.fetchall()]

        # Fetch cancellation
        cursor.execute("SELECT * FROM cancellation_records WHERE delivery_id = ?", (doc['id'],))
        cancel_row = cursor.fetchone()
        doc['cancellation_details'] = dict(cancel_row) if cancel_row else None

        # Fetch reward penalty
        cursor.execute("SELECT * FROM rewards_penalties WHERE delivery_id = ?", (doc['id'],))
        rp_row = cursor.fetchone()
        doc['reward_penalty_details'] = dict(rp_row) if rp_row else None

        db.deliveries.update_one({'tracking_id': doc['tracking_id']}, {'$set': doc}, upsert=True)

    # Sync rewards_penalties collection
    cursor.execute("SELECT * FROM rewards_penalties")
    for row in cursor.fetchall():
        doc = dict(row)
        db.rewards_penalties.update_one({'id': doc['id']}, {'$set': doc}, upsert=True)

    return True, "Synchronized SQLite data to MongoDB collections successfully."

# Live Sync Helpers
def mongo_sync_new_delivery(delivery_dict, courier_dict=None):
    if not is_mongo_connected():
        return
    try:
        doc = dict(delivery_dict)
        doc['milestones'] = [{
            'status': 'Booked',
            'remarks': f"Order accepted. Assigned to {courier_dict.get('name') if courier_dict else 'Courier'}",
            'timestamp': doc.get('booked_at')
        }]
        doc['reschedule_history'] = []
        doc['cancellation_details'] = None
        doc['reward_penalty_details'] = None
        _mongo_db.deliveries.insert_one(doc)

        # Update courier active load
        if courier_dict:
            _mongo_db.couriers.update_one(
                {'id': courier_dict['id']},
                {'$inc': {'current_active_orders': 1}}
            )
    except Exception as e:
        print("[MongoDB Sync Notice] Could not write new delivery:", e)

def mongo_sync_status_update(tracking_id, new_status, remarks, timestamp, actual_delivery_time=None, rp_doc=None, courier_id=None, wallet_delta=0):
    if not is_mongo_connected():
        return
    try:
        update_fields = {'status': new_status}
        if actual_delivery_time:
            update_fields['actual_delivery_time'] = actual_delivery_time
        if rp_doc:
            update_fields['reward_penalty_details'] = rp_doc

        _mongo_db.deliveries.update_one(
            {'tracking_id': tracking_id},
            {
                '$set': update_fields,
                '$push': {'milestones': {'status': new_status, 'remarks': remarks, 'timestamp': timestamp}}
            }
        )

        if courier_id and (wallet_delta != 0 or new_status == 'Delivered'):
            courier_update = {}
            if wallet_delta != 0:
                courier_update['wallet_balance'] = wallet_delta
            if new_status == 'Delivered':
                courier_update['total_completed_orders'] = 1
                courier_update['current_active_orders'] = -1
            
            _mongo_db.couriers.update_one(
                {'id': courier_id},
                {'$inc': courier_update}
            )

        if rp_doc:
            rp_doc['created_at'] = timestamp
            _mongo_db.rewards_penalties.insert_one(dict(rp_doc))
    except Exception as e:
        print("[MongoDB Sync Notice] Status update sync error:", e)

def mongo_sync_reschedule(tracking_id, old_time, new_time, reason, rescheduled_at):
    if not is_mongo_connected():
        return
    try:
        _mongo_db.deliveries.update_one(
            {'tracking_id': tracking_id},
            {
                '$set': {'promised_delivery_time': new_time},
                '$inc': {'rescheduled_count': 1},
                '$push': {
                    'reschedule_history': {
                        'old_delivery_time': old_time,
                        'new_delivery_time': new_time,
                        'reason': reason,
                        'rescheduled_at': rescheduled_at
                    },
                    'milestones': {
                        'status': 'Rescheduled',
                        'remarks': f"Slot adjusted to {new_time}. Reason: {reason}",
                        'timestamp': rescheduled_at
                    }
                }
            }
        )
    except Exception as e:
        print("[MongoDB Sync Notice] Reschedule sync error:", e)

def mongo_sync_cancellation(tracking_id, cancelled_by, reason, fee, refund_status, cancelled_at, courier_id=None, courier_penalty=None):
    if not is_mongo_connected():
        return
    try:
        cancel_info = {
            'cancelled_by': cancelled_by,
            'reason': reason,
            'cancellation_fee': fee,
            'refund_status': refund_status,
            'cancelled_at': cancelled_at
        }
        _mongo_db.deliveries.update_one(
            {'tracking_id': tracking_id},
            {
                '$set': {'status': 'Cancelled', 'cancellation_details': cancel_info},
                '$push': {
                    'milestones': {
                        'status': 'Cancelled',
                        'remarks': f"Cancelled by {cancelled_by}. Reason: {reason}",
                        'timestamp': cancelled_at
                    }
                }
            }
        )
        if courier_id:
            courier_dec = {'current_active_orders': -1}
            if courier_penalty:
                courier_dec['wallet_balance'] = -courier_penalty
            _mongo_db.couriers.update_one(
                {'id': courier_id},
                {'$inc': courier_dec}
            )
    except Exception as e:
        print("[MongoDB Sync Notice] Cancel sync error:", e)

