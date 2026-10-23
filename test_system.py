import unittest
import os
import sqlite3
from datetime import datetime, timedelta
import business_logic as bl
from database import init_db, get_db_connection

class TestDeliveryAgentSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_database_and_couriers_seeded(self):
        """Verify courier entities exist and have valid pricing & capacity."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM couriers WHERE is_active = 1")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertGreaterEqual(count, 5, "Should have at least 5 active couriers")

    def test_02_find_best_courier_and_booking(self):
        """Verify booking automatic courier matching and Output 1: Booking Confirmation."""
        order_data = {
            'sender_name': 'Flipkart Hub Adampur',
            'sender_phone': '+91-9988112233',
            'source_address': 'Shop 14, Commercial Complex',
            'source_locality': 'Adampur',
            'receiver_name': 'Aman Verma',
            'receiver_phone': '+91-9876112233',
            'dest_address': 'House 42, River View Lane',
            'dest_locality': 'Barari',
            'package_weight_kg': 2.0,
            'package_type': 'Electronics',
            'service_type': 'Standard'
        }
        res = bl.book_delivery(order_data)
        self.assertTrue(res['success'], f"Booking failed: {res.get('error')}")
        self.assertEqual(res['output_type'], 'BOOKING_CONFIRMATION')
        self.assertTrue(res['tracking_id'].startswith('TRK-'))
        self.assertIn('assigned_courier', res)
        self.assertGreater(res['shipping_cost'], 0)

        # Store tracking_id for subsequent tests
        TestDeliveryAgentSystem.test_tracking_id = res['tracking_id']

    def test_03_check_delivery_status(self):
        """Verify Output 2: Delivery Status Report with milestones and next sequential step."""
        res = bl.get_delivery_status(self.test_tracking_id)
        self.assertTrue(res['success'])
        self.assertEqual(res['output_type'], 'DELIVERY_STATUS_REPORT')
        self.assertEqual(res['delivery']['status'], 'Booked')
        self.assertEqual(res['delivery']['next_allowed_status'], 'Picked Up')
        self.assertGreaterEqual(len(res['milestones']), 1)

    def test_04_reschedule_delivery(self):
        """Verify Output 4: Updated record after rescheduling."""
        new_time = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
        res = bl.reschedule_delivery(self.test_tracking_id, new_time, reason="Customer not available today")
        self.assertTrue(res['success'])
        self.assertEqual(res['output_type'], 'RESCHEDULE_CONFIRMATION')
        self.assertEqual(res['new_delivery_time'], new_time)

        # Verify milestone updated
        status_res = bl.get_delivery_status(self.test_tracking_id)
        self.assertEqual(len(status_res['reschedule_history']), 1)

    def test_05_sequential_milestones_and_on_time_reward(self):
        """Verify strict sequential transition and on-time SLA reward."""
        trk = self.test_tracking_id

        # 1. Attempt out-of-order jump (Booked -> In Transit) should fail
        bad_jump = bl.update_delivery_milestone(trk, 'In Transit', 'Skipping pickup')
        self.assertFalse(bad_jump['success'])
        self.assertIn('Sequence Error', bad_jump['error'])

        # 2. Advance to Picked Up (Valid)
        p1 = bl.update_delivery_milestone(trk, 'Picked Up', 'Package picked up from merchant')
        self.assertTrue(p1['success'])
        self.assertEqual(p1['new_status'], 'Picked Up')

        # 3. Advance to In Transit (Valid)
        p2 = bl.update_delivery_milestone(trk, 'In Transit', 'In transit to destination hub')
        self.assertTrue(p2['success'])
        self.assertEqual(p2['new_status'], 'In Transit')

        # 4. Advance to Out for Delivery (Valid)
        p3 = bl.update_delivery_milestone(trk, 'Out for Delivery', 'Agent out for delivery')
        self.assertTrue(p3['success'])
        self.assertEqual(p3['new_status'], 'Out for Delivery')

        # 5. Deliver ahead of schedule (On-Time Reward)
        actual_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        p4 = bl.update_delivery_milestone(trk, 'Delivered', 'Handed over to customer', actual_delivery_time=actual_time)
        self.assertTrue(p4['success'])
        self.assertEqual(p4['new_status'], 'Delivered')
        self.assertIsNotNone(p4['reward_penalty'])
        self.assertEqual(p4['reward_penalty']['type'], 'REWARD')
        self.assertEqual(p4['reward_penalty']['amount'], 100.0)

    def test_06_cannot_reschedule_or_cancel_delivered_order(self):
        """Verify constraints: Cannot cancel or reschedule delivered orders."""
        res_cancel = bl.cancel_delivery(self.test_tracking_id, reason="Try cancel delivered")
        self.assertFalse(res_cancel['success'])
        self.assertIn('Constraint violation', res_cancel['error'])

        future_time = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        res_resched = bl.reschedule_delivery(self.test_tracking_id, future_time)
        self.assertFalse(res_resched['success'])
        self.assertIn('Constraint violation', res_resched['error'])

    def test_07_penalty_calculation_on_delayed_delivery(self):
        """Verify delayed delivery incurs SLA penalty notice in strict sequence."""
        order = {
            'sender_name': 'Myntra Express',
            'sender_phone': '+91-9988334455',
            'source_address': 'Sector 1 Hub',
            'source_locality': 'Zero Mile',
            'receiver_name': 'Rahul Verma',
            'receiver_phone': '+91-9876554433',
            'dest_address': 'Flat 201, Green Heights',
            'dest_locality': 'Mirjanhat',
            'package_weight_kg': 1.5,
            'package_type': 'Apparel',
            'service_type': 'Standard'
        }
        res_book = bl.book_delivery(order)
        trk = res_book['tracking_id']

        # Sequential progress
        bl.update_delivery_milestone(trk, 'Picked Up')
        bl.update_delivery_milestone(trk, 'In Transit')
        bl.update_delivery_milestone(trk, 'Out for Delivery')

        # Deliver 30 hours later (Past promised deadline)
        delayed_time = (datetime.now() + timedelta(hours=35)).strftime('%Y-%m-%d %H:%M:%S')
        res_del = bl.update_delivery_milestone(trk, 'Delivered', 'Delivered late', actual_delivery_time=delayed_time)
        self.assertTrue(res_del['success'])
        self.assertEqual(res_del['reward_penalty']['type'], 'PENALTY')
        self.assertEqual(res_del['reward_penalty']['amount'], 50.0)

    def test_08_cancellation_confirmation(self):
        """Verify Output 3: Cancellation confirmation."""
        order = {
            'sender_name': 'BookStore Online',
            'sender_phone': '+91-9988221100',
            'source_address': 'Market Complex',
            'source_locality': 'Adampur',
            'receiver_name': 'Neha Kumari',
            'receiver_phone': '+91-9123445566',
            'dest_address': 'Hostel 3, IIIT Bhagalpur',
            'dest_locality': 'Sabour',
            'package_weight_kg': 0.8,
            'package_type': 'Books',
            'service_type': 'Standard'
        }
        res_book = bl.book_delivery(order)
        trk = res_book['tracking_id']

        res_cancel = bl.cancel_delivery(trk, reason="Customer cancelled item", cancelled_by="Customer")
        self.assertTrue(res_cancel['success'])
        self.assertEqual(res_cancel['output_type'], 'CANCELLATION_CONFIRMATION')
        self.assertEqual(res_cancel['status'], 'Cancelled')

    def test_09_courier_past_services_query(self):
        """Verify Output 6: List of past services for a given courier, on query."""
        res = bl.get_courier_past_services(1)
        self.assertTrue(res['success'])
        self.assertEqual(res['output_type'], 'COURIER_PAST_SERVICES_REPORT')
        self.assertIn('metrics', res)
        self.assertGreaterEqual(res['metrics']['total_assigned'], 1)
        self.assertIsInstance(res['services'], list)

    def test_10_archive_records(self):
        """Verify archiving completed/cancelled/expired past deliveries."""
        res_archive = bl.archive_past_deliveries()
        self.assertTrue(res_archive['success'])
        archived_list = bl.get_archived_deliveries()
        self.assertGreaterEqual(len(archived_list), 1)

    def test_11_expire_delivery_and_penalty_after_deadline(self):
        """Verify consignments that exceed SLA deadline can be expired and penalized."""
        order = {
            'sender_name': 'Daily Needs Grocery',
            'sender_phone': '+91-9988443322',
            'source_address': 'Store 5, Main Road',
            'source_locality': 'Station Road',
            'receiver_name': 'Manoj Bajpayee',
            'receiver_phone': '+91-9876001122',
            'dest_address': 'House 18, Colony Rd',
            'dest_locality': 'Adampur',
            'package_weight_kg': 3.0,
            'package_type': 'Groceries',
            'service_type': 'Standard'
        }
        res_book = bl.book_delivery(order)
        trk = res_book['tracking_id']

        res_exp = bl.expire_delivery(trk, reason="Delivery deadline exceeded without fulfillment", penalty_amount=100.0)
        self.assertTrue(res_exp['success'])
        self.assertEqual(res_exp['status'], 'Expired (SLA Breach)')
        self.assertEqual(res_exp['penalty_amount'], 100.0)

        # Status check
        status_res = bl.get_delivery_status(trk)
        self.assertEqual(status_res['delivery']['status'], 'Expired (SLA Breach)')

if __name__ == '__main__':
    unittest.main()
