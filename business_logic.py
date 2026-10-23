import sqlite3
from datetime import datetime, timedelta
import random
from database import get_db_connection

def get_all_localities():
    """Retrieve distinct serviceable localities from active couriers."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT serviceable_localities FROM couriers WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()

    localities = set()
    for row in rows:
        locs = [l.strip() for l in row['serviceable_localities'].split(',') if l.strip()]
        localities.update(locs)
    
    # Return sorted list
    return sorted(list(localities))

def find_best_couriers(source_loc, dest_loc, weight_kg, service_type='Standard'):
    """
    Finds and ranks available couriers based on:
    - Serviceable locality match
    - Vehicle capacity >= package weight
    - Active status and active orders capacity (< 5)
    - Calculated cost and rating
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # Re-sync actual active workload from non-terminal deliveries
    cursor.execute('''
        UPDATE couriers 
        SET current_active_orders = (
            SELECT COUNT(*) FROM deliveries 
            WHERE deliveries.assigned_courier_id = couriers.id 
            AND deliveries.status IN ('Booked', 'Picked Up', 'In Transit', 'Out for Delivery')
        )
    ''')
    conn.commit()

    cursor.execute('''
        SELECT * FROM couriers 
        WHERE is_active = 1 AND max_capacity_kg >= ? AND current_active_orders < 10
    ''', (weight_kg,))
    couriers = cursor.fetchall()
    conn.close()

    candidates = []
    service_multiplier = 1.0
    if service_type.lower() == 'express':
        service_multiplier = 1.5
    elif service_type.lower() == 'sameday':
        service_multiplier = 2.0

    for c in couriers:
        serv_locs = [l.strip().lower() for l in c['serviceable_localities'].split(',')]
        
        # Check if courier serves source and/or destination
        source_matched = source_loc.strip().lower() in serv_locs
        dest_matched = dest_loc.strip().lower() in serv_locs

        # Eligibility: at least one locality covered, or courier covers broad area
        if not (source_matched and dest_matched):
            # If not covering both, give priority to couriers covering at least one, or skip if strict
            coverage_score = (1 if source_matched else 0) + (1 if dest_matched else 0)
            if coverage_score == 0:
                continue
        else:
            coverage_score = 2

        # Pricing formula
        # Base fare + (weight * rate_per_kg) * service_multiplier
        base_cost = c['base_fare'] + (weight_kg * c['rate_per_kg'])
        total_cost = round(base_cost * service_multiplier, 2)
        courier_payout = round(total_cost * 0.80, 2) # Courier gets 80%

        # Best courier ranking algorithm
        # Lower score = better recommendation
        # Cost factor + Workload penalty - Rating bonus - Full locality coverage bonus
        rank_score = total_cost + (c['current_active_orders'] * 15.0) - (c['rating'] * 20.0) - (coverage_score * 30.0)

        candidates.append({
            'courier_id': c['id'],
            'name': c['name'],
            'phone': c['phone'],
            'vehicle_type': c['vehicle_type'],
            'max_capacity_kg': c['max_capacity_kg'],
            'rating': c['rating'],
            'current_active_orders': c['current_active_orders'],
            'base_fare': c['base_fare'],
            'rate_per_kg': c['rate_per_kg'],
            'total_cost': total_cost,
            'courier_payout': courier_payout,
            'coverage_score': coverage_score,
            'rank_score': round(rank_score, 2)
        })

    # Sort by rank_score ascending (best first)
    candidates.sort(key=lambda x: x['rank_score'])
    return candidates

def book_delivery(data):
    """
    Accepts delivery request from online portal, evaluates best courier,
    and produces Booking Confirmation Output.
    """
    sender_name = data.get('sender_name', '').strip()
    sender_phone = data.get('sender_phone', '').strip()
    source_address = data.get('source_address', '').strip()
    source_locality = data.get('source_locality', '').strip()

    receiver_name = data.get('receiver_name', '').strip()
    receiver_phone = data.get('receiver_phone', '').strip()
    dest_address = data.get('dest_address', '').strip()
    dest_locality = data.get('dest_locality', '').strip()

    weight_kg = float(data.get('package_weight_kg', 1.0))
    package_type = data.get('package_type', 'Standard')
    service_type = data.get('service_type', 'Standard')
    manual_courier_id = data.get('courier_id')

    if not sender_name or not receiver_name or not source_locality or not dest_locality:
        return {'success': False, 'error': 'Missing required sender, receiver, or locality details.'}

    # Find best courier
    candidates = find_best_couriers(source_locality, dest_locality, weight_kg, service_type)
    if not candidates:
        return {'success': False, 'error': 'No available couriers servicing these localities with required capacity.'}

    selected = None
    if manual_courier_id:
        for c in candidates:
            if c['courier_id'] == int(manual_courier_id):
                selected = c
                break
    
    if not selected:
        selected = candidates[0] # Best automated match

    # Calculate promised delivery time
    now = datetime.now()
    if service_type.lower() == 'express':
        promised_time = now + timedelta(hours=4)
    elif service_type.lower() == 'sameday':
        promised_time = now + timedelta(hours=8)
    else: # Standard
        promised_time = now + timedelta(hours=24)

    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    promised_str = promised_time.strftime('%Y-%m-%d %H:%M:%S')

    # Generate unique tracking ID: TRK-YEAR-RANDOM
    tracking_id = f"TRK-{now.year}-{random.randint(1000, 9999)}"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO deliveries (
            tracking_id, sender_name, sender_phone, source_address, source_locality,
            receiver_name, receiver_phone, dest_address, dest_locality,
            package_weight_kg, package_type, service_type, assigned_courier_id,
            shipping_cost, courier_payout, status, booked_at, promised_delivery_time,
            rescheduled_count, is_archived
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Booked', ?, ?, 0, 0)
    ''', (
        tracking_id, sender_name, sender_phone, source_address, source_locality,
        receiver_name, receiver_phone, dest_address, dest_locality,
        weight_kg, package_type, service_type, selected['courier_id'],
        selected['total_cost'], selected['courier_payout'], now_str, promised_str
    ))
    delivery_id = cursor.lastrowid

    # Add initial tracking milestone log
    cursor.execute('''
        INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
        VALUES (?, 'Booked', ?, ?)
    ''', (delivery_id, f"Order accepted from portal. Assigned to best courier: {selected['name']}", now_str))

    # Update courier active load
    cursor.execute('''
        UPDATE couriers SET current_active_orders = current_active_orders + 1
        WHERE id = ?
    ''', (selected['courier_id'],))

    conn.commit()
    conn.close()

    # Output 1: Booking confirmation
    return {
        'success': True,
        'output_type': 'BOOKING_CONFIRMATION',
        'tracking_id': tracking_id,
        'booking_reference': f"BKG-{delivery_id:05d}",
        'delivery_id': delivery_id,
        'status': 'Booked',
        'booked_at': now_str,
        'promised_delivery_time': promised_str,
        'shipping_cost': selected['total_cost'],
        'assigned_courier': {
            'id': selected['courier_id'],
            'name': selected['name'],
            'phone': selected['phone'],
            'vehicle_type': selected['vehicle_type'],
            'rating': selected['rating']
        },
        'route': {
            'source': f"{source_address}, {source_locality}",
            'destination': f"{dest_address}, {dest_locality}",
            'package_type': package_type,
            'weight_kg': weight_kg,
            'service_type': service_type
        },
        'candidates_considered': len(candidates),
        'message': f"Booking successfully confirmed! Tracking ID: {tracking_id}. Assigned to {selected['name']}."
    }

def get_delivery_status(tracking_id):
    """
    Check status of a delivery and produce Delivery Status Report (Output 2).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT d.*, c.name as courier_name, c.phone as courier_phone, c.vehicle_type, c.rating as courier_rating
        FROM deliveries d
        JOIN couriers c ON d.assigned_courier_id = c.id
        WHERE d.tracking_id = ?
    ''', (tracking_id.strip(),))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {'success': False, 'error': f"Delivery with Tracking ID '{tracking_id}' not found."}

    delivery = dict(row)

    # Get tracking logs (milestones)
    cursor.execute('''
        SELECT * FROM delivery_logs WHERE delivery_id = ? ORDER BY id ASC
    ''', (delivery['id'],))
    logs = [dict(log) for log in cursor.fetchall()]

    # Get reschedule logs if any
    cursor.execute('''
        SELECT * FROM reschedule_logs WHERE delivery_id = ? ORDER BY id DESC
    ''', (delivery['id'],))
    reschedules = [dict(r) for r in cursor.fetchall()]

    # Get cancellation if cancelled
    cursor.execute('''
        SELECT * FROM cancellation_records WHERE delivery_id = ?
    ''', (delivery['id'],))
    cancel_row = cursor.fetchone()
    cancellation = dict(cancel_row) if cancel_row else None

    # Get reward/penalty if settled
    cursor.execute('''
        SELECT * FROM rewards_penalties WHERE delivery_id = ?
    ''', (delivery['id'],))
    rp_row = cursor.fetchone()
    reward_penalty = dict(rp_row) if rp_row else None

    # Calculate SLA status and sequential next step
    now = datetime.now()
    try:
        promised_dt = datetime.strptime(delivery['promised_delivery_time'], '%Y-%m-%d %H:%M:%S')
        is_terminal = delivery['status'] in ['Delivered', 'Cancelled', 'Expired (SLA Breach)']
        is_overdue = (now > promised_dt) and not is_terminal
        hours_overdue = round((now - promised_dt).total_seconds() / 3600.0, 1) if is_overdue else 0
        hours_remaining = max(0.0, round((promised_dt - now).total_seconds() / 3600.0, 1)) if not is_overdue else 0
    except Exception:
        is_overdue = False
        hours_overdue = 0
        hours_remaining = 0

    status_sequence = {
        'Booked': 'Picked Up',
        'Picked Up': 'In Transit',
        'In Transit': 'Out for Delivery',
        'Out for Delivery': 'Delivered'
    }
    next_step = status_sequence.get(delivery['status'], None)

    delivery['is_overdue'] = is_overdue
    delivery['hours_overdue'] = hours_overdue
    delivery['hours_remaining'] = hours_remaining
    delivery['next_allowed_status'] = next_step

    conn.close()

    # Output 2: Delivery status report
    return {
        'success': True,
        'output_type': 'DELIVERY_STATUS_REPORT',
        'delivery': delivery,
        'milestones': logs,
        'reschedule_history': reschedules,
        'cancellation_details': cancellation,
        'reward_penalty_details': reward_penalty
    }

STATUS_SEQUENCE = {
    'Booked': 'Picked Up',
    'Picked Up': 'In Transit',
    'In Transit': 'Out for Delivery',
    'Out for Delivery': 'Delivered'
}

def update_delivery_milestone(tracking_id, new_status, remarks=None, actual_delivery_time=None):
    """
    Updates the transit milestone of an active delivery in strict sequence.
    If transitioning to 'Delivered', triggers reward/penalty calculation.
    """
    valid_statuses = ['Booked', 'Picked Up', 'In Transit', 'Out for Delivery', 'Delivered']
    if new_status not in valid_statuses:
        return {'success': False, 'error': f"Invalid status: {new_status}"}

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deliveries WHERE tracking_id = ?", (tracking_id.strip(),))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {'success': False, 'error': f"Delivery '{tracking_id}' not found."}

    delivery = dict(row)

    if delivery['status'] == 'Delivered':
        conn.close()
        return {'success': False, 'error': 'Delivery has already been marked Delivered. Cannot change status.'}

    if delivery['status'] in ['Cancelled', 'Expired (SLA Breach)']:
        conn.close()
        return {'success': False, 'error': f"Cannot update milestone for a {delivery['status']} consignment."}

    # Strict Sequential Check
    expected_next = STATUS_SEQUENCE.get(delivery['status'])
    if expected_next != new_status:
        conn.close()
        return {
            'success': False,
            'error': f"Sequence Error: Consignment is currently '{delivery['status']}'. The next required sequential milestone must be '{expected_next}', not '{new_status}'."
        }

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    reward_notice = None

    if new_status == 'Delivered':
        # Use provided actual delivery time or current timestamp
        delivery_time_str = actual_delivery_time if actual_delivery_time else now_str
        try:
            actual_dt = datetime.strptime(delivery_time_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            actual_dt = now
            delivery_time_str = now_str

        promised_dt = datetime.strptime(delivery['promised_delivery_time'], '%Y-%m-%d %H:%M:%S')

        # Compare actual vs promised delivery time
        time_diff_hours = round((actual_dt - promised_dt).total_seconds() / 3600.0, 1)

        is_on_time = actual_dt <= promised_dt

        cursor.execute('''
            UPDATE deliveries 
            SET status = 'Delivered', actual_delivery_time = ?
            WHERE id = ?
        ''', (delivery_time_str, delivery['id']))

        # Free active load and increment completed orders
        cursor.execute('''
            UPDATE couriers 
            SET current_active_orders = MAX(0, current_active_orders - 1),
                total_completed_orders = total_completed_orders + 1
            WHERE id = ?
        ''', (delivery['assigned_courier_id'],))

        # Reward / Penalty calculation rule engine
        if is_on_time:
            reward_amt = 100.0
            hours_early = abs(time_diff_hours)
            reason = f"On-Time SLA Delivery ({hours_early}h margin)"
            notice = f"REWARD NOTICE: Excellent performance! Order {tracking_id} was successfully delivered on-time. Bonus of +₹{reward_amt:.2f} credited to courier wallet."
            rp_type = 'REWARD'

            cursor.execute('''
                INSERT INTO rewards_penalties (delivery_id, courier_id, type, amount, reason, notice_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (delivery['id'], delivery['assigned_courier_id'], rp_type, reward_amt, reason, notice, delivery_time_str))

            # Update courier wallet with payout + reward bonus
            net_gain = delivery['courier_payout'] + reward_amt
            cursor.execute('''
                UPDATE couriers SET wallet_balance = wallet_balance + ? WHERE id = ?
            ''', (net_gain, delivery['assigned_courier_id']))

        else:
            penalty_amt = 50.0
            reason = f"Delayed Delivery SLA Breach ({time_diff_hours}h late)"
            notice = f"PENALTY NOTICE: Order {tracking_id} was delivered {time_diff_hours} hours past the promised deadline. SLA penalty of -₹{penalty_amt:.2f} deducted from payout."
            rp_type = 'PENALTY'

            cursor.execute('''
                INSERT INTO rewards_penalties (delivery_id, courier_id, type, amount, reason, notice_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (delivery['id'], delivery['assigned_courier_id'], rp_type, penalty_amt, reason, notice, delivery_time_str))

            # Update courier wallet with payout - penalty
            net_gain = max(0.0, delivery['courier_payout'] - penalty_amt)
            cursor.execute('''
                UPDATE couriers SET wallet_balance = wallet_balance + ? WHERE id = ?
            ''', (net_gain, delivery['assigned_courier_id']))

        reward_notice = {
            'type': rp_type,
            'amount': reward_amt if is_on_time else penalty_amt,
            'reason': reason,
            'notice_text': notice,
            'time_diff_hours': time_diff_hours,
            'is_on_time': is_on_time
        }

        default_remarks = f"Package successfully delivered. SLA verification: {'ON TIME' if is_on_time else 'DELAYED (PENALTY ENFORCED)'}."
    else:
        cursor.execute("UPDATE deliveries SET status = ? WHERE id = ?", (new_status, delivery['id']))
        default_remarks = f"Status sequentially updated to {new_status}"

    log_remarks = remarks.strip() if remarks else default_remarks
    cursor.execute('''
        INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (delivery['id'], new_status, log_remarks, now_str))

    conn.commit()
    conn.close()

    return {
        'success': True,
        'tracking_id': tracking_id,
        'new_status': new_status,
        'remarks': log_remarks,
        'updated_at': now_str,
        'reward_penalty': reward_notice
    }

def expire_delivery(tracking_id, reason="SLA deadline expired without delivery", penalty_amount=100.0):
    """
    Expires an active delivery that has breached its SLA deadline and charges the courier a breach penalty.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deliveries WHERE tracking_id = ?", (tracking_id.strip(),))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {'success': False, 'error': f"Delivery '{tracking_id}' not found."}

    delivery = dict(row)

    if delivery['status'] in ['Delivered', 'Cancelled', 'Expired (SLA Breach)']:
        conn.close()
        return {'success': False, 'error': f"Consignment is already in terminal status '{delivery['status']}'."}

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    # Update delivery status to Expired (SLA Breach)
    cursor.execute("UPDATE deliveries SET status = 'Expired (SLA Breach)' WHERE id = ?", (delivery['id'],))

    # Free assigned courier active slot
    cursor.execute('''
        UPDATE couriers SET current_active_orders = MAX(0, current_active_orders - 1)
        WHERE id = ?
    ''', (delivery['assigned_courier_id'],))

    # Charge breach penalty
    notice = f"PENALTY NOTICE: Consignment {tracking_id} breached the promised delivery deadline ({delivery['promised_delivery_time']}). Consignment expired with SLA Breach. Penalty of -₹{penalty_amount:.2f} deducted from courier wallet."
    cursor.execute('''
        INSERT INTO rewards_penalties (delivery_id, courier_id, type, amount, reason, notice_text, created_at)
        VALUES (?, ?, 'PENALTY', ?, 'SLA Deadline Expiration Breach', ?, ?)
    ''', (delivery['id'], delivery['assigned_courier_id'], penalty_amount, notice, now_str))

    cursor.execute('''
        UPDATE couriers SET wallet_balance = wallet_balance - ? WHERE id = ?
    ''', (penalty_amount, delivery['assigned_courier_id']))

    # Log milestone
    log_text = f"Consignment expired past SLA deadline ({delivery['promised_delivery_time']}). Reason: {reason}. Courier penalized ₹{penalty_amount}."
    cursor.execute('''
        INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
        VALUES (?, 'Expired (SLA Breach)', ?, ?)
    ''', (delivery['id'], log_text, now_str))

    conn.commit()
    conn.close()

    return {
        'success': True,
        'tracking_id': tracking_id,
        'status': 'Expired (SLA Breach)',
        'penalty_amount': penalty_amount,
        'notice_text': notice,
        'expired_at': now_str,
        'message': f"Consignment {tracking_id} expired and penalized for SLA deadline breach."
    }

def cancel_delivery(tracking_id, reason="Customer requested cancellation", cancelled_by="Customer"):
    """
    Cancel an existing booking and produce Cancellation Confirmation (Output 3).
    Enforces constraint: Cannot cancel if already Delivered or already Cancelled.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deliveries WHERE tracking_id = ?", (tracking_id.strip(),))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {'success': False, 'error': f"Delivery with Tracking ID '{tracking_id}' not found."}

    delivery = dict(row)

    # Constraint check
    if delivery['status'] == 'Delivered':
        conn.close()
        return {'success': False, 'error': 'Constraint violation: Cannot cancel a package that has already been delivered.'}

    if delivery['status'] == 'Cancelled':
        conn.close()
        return {'success': False, 'error': 'Delivery is already cancelled.'}

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    cancellation_fee = 0.0
    refund_status = "100% Refund Approved"
    
    # If cancelled after Pickup, small logistics cancellation fee applies
    if delivery['status'] in ['Picked Up', 'In Transit', 'Out for Delivery']:
        cancellation_fee = 30.0
        refund_status = f"Partial Refund (₹{delivery['shipping_cost'] - cancellation_fee:.2f} refunded, ₹30 fee applied)"

    # Update delivery status
    cursor.execute("UPDATE deliveries SET status = 'Cancelled' WHERE id = ?", (delivery['id'],))

    # Free assigned courier's active delivery slot
    cursor.execute('''
        UPDATE couriers SET current_active_orders = MAX(0, current_active_orders - 1)
        WHERE id = ?
    ''', (delivery['assigned_courier_id'],))

    # Add cancellation record
    cursor.execute('''
        INSERT INTO cancellation_records (delivery_id, cancelled_by, reason, cancellation_fee, refund_status, cancelled_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (delivery['id'], cancelled_by, reason, cancellation_fee, refund_status, now_str))
    cancel_id = cursor.lastrowid

    # Add tracking milestone log
    cursor.execute('''
        INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
        VALUES (?, 'Cancelled', ?, ?)
    ''', (delivery['id'], f"Booking cancelled by {cancelled_by}. Reason: {reason}", now_str))

    # If courier cancelled after taking order, apply courier penalty
    courier_penalty_notice = None
    if cancelled_by.lower() == 'courier':
        penalty_amount = 80.0
        p_notice = f"PENALTY NOTICE: Order {tracking_id} was cancelled by courier. Unfulfilled assignment penalty of -₹{penalty_amount:.2f} charged."
        cursor.execute('''
            INSERT INTO rewards_penalties (delivery_id, courier_id, type, amount, reason, notice_text, created_at)
            VALUES (?, ?, 'PENALTY', ?, 'Courier Initiated Cancellation', ?, ?)
        ''', (delivery['id'], delivery['assigned_courier_id'], penalty_amount, p_notice, now_str))
        cursor.execute('''
            UPDATE couriers SET wallet_balance = wallet_balance - ? WHERE id = ?
        ''', (penalty_amount, delivery['assigned_courier_id']))
        courier_penalty_notice = p_notice

    conn.commit()
    conn.close()

    # Output 3: Cancellation confirmation
    return {
        'success': True,
        'output_type': 'CANCELLATION_CONFIRMATION',
        'cancellation_id': f"CAN-{cancel_id:05d}",
        'tracking_id': tracking_id,
        'status': 'Cancelled',
        'cancelled_by': cancelled_by,
        'reason': reason,
        'cancellation_fee': cancellation_fee,
        'refund_status': refund_status,
        'cancelled_at': now_str,
        'courier_penalty_notice': courier_penalty_notice,
        'message': f"Cancellation confirmed for {tracking_id}. Slot released."
    }

def reschedule_delivery(tracking_id, new_delivery_time, reason="Customer requested new time slot"):
    """
    Reschedule delivery and produce Updated Record after Rescheduling (Output 4).
    Enforces constraint: Cannot reschedule if already Delivered or Cancelled.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT d.*, c.name as courier_name 
        FROM deliveries d 
        JOIN couriers c ON d.assigned_courier_id = c.id 
        WHERE d.tracking_id = ?
    ''', (tracking_id.strip(),))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {'success': False, 'error': f"Delivery '{tracking_id}' not found."}

    delivery = dict(row)

    if delivery['status'] == 'Delivered':
        conn.close()
        return {'success': False, 'error': 'Constraint violation: Cannot reschedule a package that has already been delivered.'}

    if delivery['status'] == 'Cancelled':
        conn.close()
        return {'success': False, 'error': 'Constraint violation: Cannot reschedule a cancelled order.'}

    # Validate new delivery time format
    try:
        new_dt = datetime.strptime(new_delivery_time, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            # Handle standard datetime-local format (YYYY-MM-DDTHH:MM)
            new_dt = datetime.strptime(new_delivery_time, '%Y-%m-%dT%H:%M')
            new_delivery_time = new_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            conn.close()
            return {'success': False, 'error': 'Invalid datetime format. Expected YYYY-MM-DD HH:MM:SS or YYYY-MM-DDTHH:MM.'}

    now = datetime.now()
    if new_dt <= now:
        conn.close()
        return {'success': False, 'error': 'New scheduled delivery time must be in the future.'}

    old_delivery_time = delivery['promised_delivery_time']
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    # Update delivery record
    cursor.execute('''
        UPDATE deliveries 
        SET promised_delivery_time = ?, rescheduled_count = rescheduled_count + 1
        WHERE id = ?
    ''', (new_delivery_time, delivery['id']))

    # Insert into reschedule logs
    cursor.execute('''
        INSERT INTO reschedule_logs (delivery_id, old_delivery_time, new_delivery_time, reason, rescheduled_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (delivery['id'], old_delivery_time, new_delivery_time, reason, now_str))

    # Add milestone log
    cursor.execute('''
        INSERT INTO delivery_logs (delivery_id, status, remarks, timestamp)
        VALUES (?, 'Rescheduled', ?, ?)
    ''', (delivery['id'], f"Delivery slot rescheduled from {old_delivery_time} to {new_delivery_time}. Reason: {reason}", now_str))

    conn.commit()
    conn.close()

    # Output 4: Updated record after rescheduling
    return {
        'success': True,
        'output_type': 'RESCHEDULE_CONFIRMATION',
        'tracking_id': tracking_id,
        'old_delivery_time': old_delivery_time,
        'new_delivery_time': new_delivery_time,
        'reason': reason,
        'rescheduled_at': now_str,
        'rescheduled_count': delivery['rescheduled_count'] + 1,
        'assigned_courier': delivery['courier_name'],
        'message': f"Order {tracking_id} successfully rescheduled to {new_delivery_time}."
    }

def get_courier_past_services(courier_id):
    """
    List of past services for a given courier, on query (Output 6).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM couriers WHERE id = ?", (courier_id,))
    courier_row = cursor.fetchone()
    if not courier_row:
        conn.close()
        return {'success': False, 'error': f"Courier with ID {courier_id} not found."}

    courier = dict(courier_row)

    # Fetch deliveries assigned to this courier
    cursor.execute('''
        SELECT d.*, 
               rp.type as rp_type, rp.amount as rp_amount, rp.reason as rp_reason, rp.notice_text
        FROM deliveries d
        LEFT JOIN rewards_penalties rp ON d.id = rp.delivery_id AND rp.courier_id = d.assigned_courier_id
        WHERE d.assigned_courier_id = ?
        ORDER BY d.id DESC
    ''', (courier_id,))
    deliveries = [dict(r) for r in cursor.fetchall()]

    # Performance calculations
    total_assigned = len(deliveries)
    delivered_count = sum(1 for d in deliveries if d['status'] == 'Delivered')
    cancelled_count = sum(1 for d in deliveries if d['status'] == 'Cancelled')
    active_count = sum(1 for d in deliveries if d['status'] in ['Booked', 'Picked Up', 'In Transit', 'Out for Delivery'])

    rewards_count = sum(1 for d in deliveries if d.get('rp_type') == 'REWARD')
    penalties_count = sum(1 for d in deliveries if d.get('rp_type') == 'PENALTY')
    total_rewards_val = sum(d['rp_amount'] for d in deliveries if d.get('rp_type') == 'REWARD' and d['rp_amount'])
    total_penalties_val = sum(d['rp_amount'] for d in deliveries if d.get('rp_type') == 'PENALTY' and d['rp_amount'])

    on_time_rate = round((rewards_count / delivered_count * 100.0), 1) if delivered_count > 0 else 100.0

    conn.close()

    # Output 6: List of past services for a given courier, on query
    return {
        'success': True,
        'output_type': 'COURIER_PAST_SERVICES_REPORT',
        'courier': courier,
        'metrics': {
            'total_assigned': total_assigned,
            'delivered_count': delivered_count,
            'cancelled_count': cancelled_count,
            'active_count': active_count,
            'rewards_count': rewards_count,
            'penalties_count': penalties_count,
            'total_rewards_val': total_rewards_val,
            'total_penalties_val': total_penalties_val,
            'on_time_rate': on_time_rate
        },
        'services': deliveries
    }

def get_all_rewards_and_penalties():
    """
    Produces list of updated records and notices of reward/penalty (Output 5).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT rp.*, d.tracking_id, c.name as courier_name, c.phone as courier_phone,
               d.source_locality, d.dest_locality
        FROM rewards_penalties rp
        JOIN deliveries d ON rp.delivery_id = d.id
        JOIN couriers c ON rp.courier_id = c.id
        ORDER BY rp.id DESC
    ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def archive_past_deliveries(status_filter=None):
    """
    Archive records of past deliveries (Delivered or Cancelled).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    query = '''
        UPDATE deliveries 
        SET is_archived = 1, archived_at = ?
        WHERE is_archived = 0 AND status IN ('Delivered', 'Cancelled', 'Expired (SLA Breach)')
    '''
    params = [now_str]

    if status_filter in ['Delivered', 'Cancelled']:
        query += " AND status = ?"
        params.append(status_filter)

    cursor.execute(query, params)
    archived_count = cursor.rowcount
    conn.commit()
    conn.close()

    return {
        'success': True,
        'archived_count': archived_count,
        'archived_at': now_str,
        'message': f"Successfully archived {archived_count} completed/cancelled deliveries."
    }

def get_archived_deliveries():
    """List all archived past deliveries."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT d.*, c.name as courier_name 
        FROM deliveries d 
        JOIN couriers c ON d.assigned_courier_id = c.id 
        WHERE d.is_archived = 1
        ORDER BY d.archived_at DESC
    ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_system_overview():
    """Returns overview statistics across the interconnected system."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM couriers WHERE is_active = 1")
    total_couriers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM deliveries")
    total_deliveries = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM deliveries WHERE status IN ('Booked', 'Picked Up', 'In Transit', 'Out for Delivery')")
    active_deliveries = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM deliveries WHERE status = 'Delivered'")
    delivered_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM deliveries WHERE status = 'Cancelled'")
    cancelled_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM deliveries WHERE is_archived = 1")
    archived_count = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM rewards_penalties WHERE type = 'REWARD'")
    total_rewards = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM rewards_penalties WHERE type = 'PENALTY'")
    total_penalties = cursor.fetchone()[0]

    conn.close()

    return {
        'total_couriers': total_couriers,
        'total_deliveries': total_deliveries,
        'active_deliveries': active_deliveries,
        'delivered_count': delivered_count,
        'cancelled_count': cancelled_count,
        'archived_count': archived_count,
        'total_rewards': total_rewards,
        'total_penalties': total_penalties
    }
