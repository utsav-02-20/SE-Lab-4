from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from datetime import datetime
from database import init_db, get_db_connection
import business_logic as bl

app = Flask(__name__)

# Ensure DB is created and seeded on startup
init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/overview', methods=['GET'])
def api_overview():
    try:
        data = bl.get_system_overview()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/localities', methods=['GET'])
def api_localities():
    try:
        localities = bl.get_all_localities()
        return jsonify({'success': True, 'localities': localities})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/couriers', methods=['GET'])
def api_get_couriers():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM couriers ORDER BY id ASC")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'couriers': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/couriers', methods=['POST'])
def api_add_courier():
    try:
        data = request.json or {}
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        vehicle = data.get('vehicle_type', 'Motorbike').strip()
        capacity = float(data.get('max_capacity_kg', 15.0))
        localities = data.get('serviceable_localities', '').strip()
        base_fare = float(data.get('base_fare', 50.0))
        rate_per_kg = float(data.get('rate_per_kg', 12.0))
        rating = float(data.get('rating', 4.5))

        if not name or not phone or not localities:
            return jsonify({'success': False, 'error': 'Name, phone and serviceable localities are required.'}), 400

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO couriers (
                name, phone, email, vehicle_type, max_capacity_kg, serviceable_localities,
                base_fare, rate_per_kg, rating, is_active, current_active_orders,
                total_completed_orders, wallet_balance, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, 0.0, ?)
        ''', (name, phone, email, vehicle, capacity, localities, base_fare, rate_per_kg, rating, now_str))
        courier_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'courier_id': courier_id, 'message': f'Courier {name} added successfully.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/quote', methods=['POST'])
def api_quote():
    try:
        data = request.json or {}
        source = data.get('source_locality', '')
        dest = data.get('dest_locality', '')
        weight = float(data.get('package_weight_kg', 1.0))
        service_type = data.get('service_type', 'Standard')

        candidates = bl.find_best_couriers(source, dest, weight, service_type)
        return jsonify({
            'success': True,
            'count': len(candidates),
            'recommended': candidates[0] if candidates else None,
            'all_candidates': candidates
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deliveries/book', methods=['POST'])
def api_book_delivery():
    try:
        data = request.json or {}
        res = bl.book_delivery(data)
        if res.get('success'):
            return jsonify(res), 201
        return jsonify(res), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deliveries', methods=['GET'])
def api_get_deliveries():
    try:
        status_filter = request.args.get('status')
        conn = get_db_connection()
        cursor = conn.cursor()
        if status_filter:
            cursor.execute('''
                SELECT d.*, c.name as courier_name 
                FROM deliveries d 
                JOIN couriers c ON d.assigned_courier_id = c.id 
                WHERE d.status = ?
                ORDER BY d.id DESC LIMIT 50
            ''', (status_filter,))
        else:
            cursor.execute('''
                SELECT d.*, c.name as courier_name 
                FROM deliveries d 
                JOIN couriers c ON d.assigned_courier_id = c.id 
                ORDER BY d.id DESC LIMIT 50
            ''')
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'deliveries': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deliveries/<tracking_id>', methods=['GET'])
def api_get_delivery_status(tracking_id):
    try:
        res = bl.get_delivery_status(tracking_id)
        if res.get('success'):
            return jsonify(res)
        return jsonify(res), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deliveries/<tracking_id>/status', methods=['POST'])
def api_update_delivery_status(tracking_id):
    try:
        data = request.json or {}
        new_status = data.get('status')
        remarks = data.get('remarks')
        actual_time = data.get('actual_delivery_time')

        res = bl.update_delivery_milestone(tracking_id, new_status, remarks, actual_time)
        if res.get('success'):
            return jsonify(res)
        return jsonify(res), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deliveries/<tracking_id>/cancel', methods=['POST'])
def api_cancel_delivery(tracking_id):
    try:
        data = request.json or {}
        reason = data.get('reason', 'Customer requested cancellation')
        cancelled_by = data.get('cancelled_by', 'Customer')

        res = bl.cancel_delivery(tracking_id, reason, cancelled_by)
        if res.get('success'):
            return jsonify(res)
        return jsonify(res), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deliveries/<tracking_id>/expire', methods=['POST'])
def api_expire_delivery(tracking_id):
    try:
        data = request.json or {}
        reason = data.get('reason', 'SLA deadline expired without delivery fulfillment')
        penalty = float(data.get('penalty_amount', 100.0))

        res = bl.expire_delivery(tracking_id, reason, penalty)
        if res.get('success'):
            return jsonify(res)
        return jsonify(res), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deliveries/<tracking_id>/simulate-deadline-breach', methods=['POST'])
def api_simulate_deadline_breach(tracking_id):
    try:
        from datetime import datetime, timedelta
        conn = get_db_connection()
        cursor = conn.cursor()
        past_time = (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("UPDATE deliveries SET promised_delivery_time = ? WHERE tracking_id = ?", (past_time, tracking_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'Deadline simulated to 2 hours ago ({past_time}).'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deliveries/<tracking_id>/reschedule', methods=['POST'])
def api_reschedule_delivery(tracking_id):
    try:
        data = request.json or {}
        new_time = data.get('new_delivery_time')
        reason = data.get('reason', 'Customer requested rescheduling')

        if not new_time:
            return jsonify({'success': False, 'error': 'New delivery time is required.'}), 400

        res = bl.reschedule_delivery(tracking_id, new_time, reason)
        if res.get('success'):
            return jsonify(res)
        return jsonify(res), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/couriers/<int:courier_id>/services', methods=['GET'])
def api_courier_past_services(courier_id):
    try:
        res = bl.get_courier_past_services(courier_id)
        if res.get('success'):
            return jsonify(res)
        return jsonify(res), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rewards-penalties', methods=['GET'])
def api_rewards_penalties():
    try:
        data = bl.get_all_rewards_and_penalties()
        return jsonify({'success': True, 'records': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deliveries/archive', methods=['GET', 'POST'])
def api_deliveries_archive():
    try:
        if request.method == 'POST':
            data = request.json or {}
            status_filter = data.get('status')
            res = bl.archive_past_deliveries(status_filter)
            return jsonify(res)
        else:
            archived = bl.get_archived_deliveries()
            return jsonify({'success': True, 'archived': archived})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Running on local port 5000
    print("Starting Delivery Agent System (P03) on http://127.0.0.1:5000 ...")
    app.run(host='127.0.0.1', port=5000, debug=False)
