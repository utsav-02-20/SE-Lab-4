# P03: Delivery Agent System
**Course:** CS311 Software Engineering Lab | **Institution:** IIIT Bhagalpur  
**Domain:** Lightweight Web / Enterprise Logistics Application | **Environment:** Windows 11 / Python 3.14, Flask, SQLite

---

## 1. Problem Overview
Online shopping platforms like Flipkart and Amazon need to get products to customers quickly and cheaply. This system automatically accepts delivery requests from an online portal, evaluates all registered couriers in the region based on locality coverage, capacity, pricing, rating, and active workload, and automatically assigns the order to the optimal courier.

---

## 2. Software Engineering Analysis (Starting Point)

### (a) Actors in the System
1. **Online Shopping Portal / Customer (Sender & Receiver):**
   - Submits shipping origin, destination, and consignment parameters to book deliveries.
   - Monitors consignment transit milestones in real-time.
   - Reschedules delivery slots or cancels bookings if needed.
2. **Courier Partner / Delivery Agent:**
   - Receives automated order allocations based on capacity and locality.
   - Updates transit milestones (*Picked Up*, *In Transit*, *Out for Delivery*, *Delivered*).
   - Earns base payouts plus reward bonuses for on-time SLAs; incurs penalties for SLA breaches or unfulfilled cancellations.
3. **Logistics Dispatcher / System Admin:**
   - Monitors active fleet load and locality coverage across the operating hubs.
   - Reviews transparent audit trails of rewards and penalties.
   - Archives completed and cancelled orders.

---

### (b) Use Cases per Actor

| Use Case ID | Actor | Description | System Output Produced |
|---|---|---|---|
| **UC01** | Customer / Portal | Book a Delivery | **Output 1: Booking Confirmation** |
| **UC02** | Customer / Dispatcher | Check Status & Milestones | **Output 2: Delivery Status Report** |
| **UC03** | Customer / Dispatcher | Cancel a Booking | **Output 3: Cancellation Confirmation** |
| **UC04** | Customer / Dispatcher | Reschedule a Delivery | **Output 4: Updated Record after Rescheduling** |
| **UC05** | Courier / System | Settle SLA & Rewards/Penalties | **Output 5: Notice of Reward / Penalty** |
| **UC06** | Courier / Dispatcher | Query Past Services | **Output 6: List of Past Services for a Given Courier** |
| **UC07** | Dispatcher | Archive Past Deliveries | Delivery Archive Ledger & Audit Trail |

---

### (c) Data Model & Entities

The prototype uses a unified, interconnected SQLite database (`delivery_system.db`) with foreign key constraints:

1. **`couriers`**:
   - `id`, `name`, `phone`, `email`, `vehicle_type`, `max_capacity_kg`, `serviceable_localities`, `base_fare`, `rate_per_kg`, `rating`, `is_active`, `current_active_orders`, `total_completed_orders`, `wallet_balance`, `created_at`.
2. **`deliveries`**:
   - `id`, `tracking_id`, `sender_name`, `sender_phone`, `source_address`, `source_locality`, `receiver_name`, `receiver_phone`, `dest_address`, `dest_locality`, `package_weight_kg`, `package_type`, `service_type`, `assigned_courier_id` (*FK*), `shipping_cost`, `courier_payout`, `status`, `booked_at`, `promised_delivery_time`, `actual_delivery_time`, `rescheduled_count`, `is_archived`, `archived_at`.
3. **`delivery_logs`**:
   - `id`, `delivery_id` (*FK*), `status`, `remarks`, `timestamp`.
4. **`reschedule_logs`**:
   - `id`, `delivery_id` (*FK*), `old_delivery_time`, `new_delivery_time`, `reason`, `rescheduled_at`.
5. **`cancellation_records`**:
   - `id`, `delivery_id` (*FK*), `cancelled_by`, `reason`, `cancellation_fee`, `refund_status`, `cancelled_at`.
6. **`rewards_penalties`**:
   - `id`, `delivery_id` (*FK*), `courier_id` (*FK*), `type` (`REWARD` / `PENALTY`), `amount`, `reason`, `notice_text`, `created_at`.

---

### (d) Constraints & Business Rules Enforced & Tested

1. **Locality & Capacity Constraint:** Only active couriers servicing the given origin and destination localities and having `max_capacity_kg >= package_weight` are eligible for assignment.
2. **Sequential Transit Pipeline:** Milestones must progress in strict order: `Booked` &rarr; `Picked Up` &rarr; `In Transit` &rarr; `Out for Delivery` &rarr; `Delivered`. Out-of-order stage transitions are rejected.
3. **Status Immutability Constraint:** A package cannot be cancelled or rescheduled once marked with terminal status (`Delivered`, `Cancelled`, or `Expired`).
4. **SLA Reward / Penalty Rule:**
   - Delivered on or before promised deadline: **+₹100 Reward Bonus** credited to courier wallet.
   - Delivered after promised deadline: **-₹50 SLA Penalty** deducted from courier payout.
5. **Deadline Expiry & Breach Penalty:** Consignments that exceed the promised SLA deadline without delivery can be expired by dispatch, assessing a **-₹100 failure penalty** to the assigned courier.
6. **Archive Rule:** Only deliveries with terminal status (`Delivered`, `Cancelled`, or `Expired`) can be archived.

---

## 3. Best Available Courier Matching Algorithm

When an order request arrives:
1. Candidate couriers are filtered by active status, vehicle payload capacity, and locality coverage.
2. Shipping tariff is computed:
   $$\text{Cost} = \left(\text{Base Fare} + (\text{Weight} \times \text{Rate per kg})\right) \times \text{Service Multiplier}$$
   *(where Standard = 1.0x, Express = 1.5x, SameDay = 2.0x)*
3. Courier Ranking Score:
   $$\text{Score} = \text{Cost} + (\text{Active Orders} \times 15.0) - (\text{Rating} \times 20.0) - (\text{Locality Match Score} \times 30.0)$$
   *(The lowest ranking score is automatically assigned as the optimal courier).*

---

## 4. How to Run on Windows 11

### Option 1: One-Click Launch (Recommended)
Double-click `run.bat` in this folder:
- It checks the Python installation.
- Verifies Flask dependency.
- Initializes the SQLite database.
- Automatically launches the web application at **http://127.0.0.1:5000**.

### Option 2: Command Line
```powershell
# Navigate to this folder
cd "C:\Users\kumar\OneDrive\Desktop\SE Lab 4"

# Install requirements (if needed)
pip install -r requirements.txt

# Start the application
python app.py
```
Open your browser to: **http://127.0.0.1:5000**

---

## 5. Running Automated Test Suite
To verify all 6 functional requirements, 6 outputs, and constraints:
```powershell
python test_system.py
```
Output:
```
Ran 10 tests in 0.126s
OK
```

---

## 6. Lab Demonstration Guide

1. **Book Delivery:**
   - Specify origin and destination localities (e.g. `Zero Mile` and `Sabour`, or `Adampur` and `Barari`).
   - Observe the live quote card showing the optimal courier selected by the algorithm.
   - Click **Confirm Order & Auto-Assign Courier** to generate **Output 1: Booking Confirmation Slip**.
2. **Track & Status:**
   - Click any quick-select chip or enter `TRK-2026-003`.
   - Inspect **Output 2: Delivery Status Report** with milestone audit trail.
   - Advance milestone to *Picked Up*, *In Transit*, or *Mark Delivered*.
   - When marking *Delivered*, select On-Time (+₹100 reward) or Delayed (-₹50 penalty) to demonstrate SLA calculation.
3. **Reschedule & Cancel:**
   - Enter tracking ID, set a new future timestamp, and click reschedule to generate **Output 4: Updated Record after Rescheduling**.
   - Enter tracking ID, choose cancellation reason, and confirm to generate **Output 3: Cancellation Confirmation**.
4. **Rewards & Penalties:**
   - Review the financial ledger of notices generated across all completed orders (**Output 5**).
5. **Courier Past Services:**
   - Select any courier (e.g., *Ramesh Kumar* or *Anjali Verma*).
   - View **Output 6: List of Past Services for a Given Courier**, showing SLA on-time rate, wallet balance, and completed delivery history.
6. **Delivery Archive:**
   - Click **Archive Completed & Cancelled Orders** to archive terminal consignments.
7. **Couriers & Rates:**
   - Inspect fleet capacities and register new couriers.
8. **System Specifications:**
   - Review the formal Actor breakdown, Use Case mapping, ER Model, and Constraint Rules.
