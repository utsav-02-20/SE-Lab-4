import sys
import os
from database import init_db, get_db_connection
from mongo_db import get_mongo_client, init_mongo_collections, sync_sqlite_to_mongo, is_mongo_connected

def main():
    print("==================================================================")
    print("   DELIVERY AGENT SYSTEM - MONGODB SYNCHRONIZER / MIGRATOR")
    print("==================================================================")
    
    uri = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('MONGO_URI', 'mongodb://localhost:27017/delivery_system')
    print(f"Connecting to MongoDB at: {uri} ...")

    client, db = get_mongo_client(uri, timeout_ms=3000)
    if client is None or db is None:
        print("[ERROR] Could not connect to MongoDB server.")
        print("Please verify that MongoDB daemon is running locally (e.g. 'mongod')")
        print("OR supply a valid MongoDB Atlas connection URI:")
        print("  python sync_to_mongo.py \"mongodb+srv://<user>:<password>@cluster0.mongodb.net/delivery_system\"")
        sys.exit(1)

    print("[SUCCESS] Connected to MongoDB database successfully!")
    print("Ensuring collections & indexes...")
    init_mongo_collections(db)

    print("Reading records from SQLite database...")
    init_db()
    sqlite_conn = get_db_connection()

    success, msg = sync_sqlite_to_mongo(sqlite_conn, db)
    sqlite_conn.close()

    if success:
        print(f"[COMPLETED] {msg}")
        print("\nMongoDB Collections Summary:")
        print(f" - couriers count: {db.couriers.count_documents({})}")
        print(f" - deliveries count: {db.deliveries.count_documents({})}")
        print(f" - rewards_penalties count: {db.rewards_penalties.count_documents({})}")
    else:
        print(f"[FAILED] {msg}")

if __name__ == '__main__':
    main()
