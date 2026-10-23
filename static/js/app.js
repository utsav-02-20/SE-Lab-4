// Delivery Agent System - Frontend Application Logic

let currentTrackingId = null;

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    loadOverview();
    loadLocalities();
    loadCouriersList();
    loadRecentDeliveries();
    setupQuoteListener();
});

// Tab navigation
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-tab');
            tabButtons.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetPane = document.getElementById(targetId);
            if (targetPane) targetPane.classList.add('active');

            // Lazy tab refresh
            if (targetId === 'tab-rewards') loadRewardsPenalties();
            if (targetId === 'tab-courier-services') loadCourierSelectOptions();
            if (targetId === 'tab-archive') loadArchivedDeliveries();
            if (targetId === 'tab-couriers') loadCouriersManagement();
            if (targetId === 'tab-track') loadRecentDeliveriesForTrack();
        });
    });
}

// Fetch header metrics
async function loadOverview() {
    try {
        const res = await fetch('/api/overview');
        const json = await res.json();
        if (json.success) {
            const d = json.data;
            document.getElementById('stat-total').innerText = d.total_deliveries;
            document.getElementById('stat-active').innerText = d.active_deliveries;
            document.getElementById('stat-delivered').innerText = d.delivered_count;
            document.getElementById('stat-cancelled').innerText = d.cancelled_count;
            document.getElementById('stat-rewards').innerText = `+₹${d.total_rewards}`;
            document.getElementById('stat-penalties').innerText = `-₹${d.total_penalties}`;
        }
    } catch (err) {
        console.error('Error fetching overview:', err);
    }
}

// Load localities into datalists
async function loadLocalities() {
    try {
        const res = await fetch('/api/localities');
        const json = await res.json();
        if (json.success) {
            const list = document.getElementById('locality-list');
            list.innerHTML = '';
            json.localities.forEach(loc => {
                const opt = document.createElement('option');
                opt.value = loc;
                list.appendChild(opt);
            });
        }
    } catch (err) {
        console.error('Error fetching localities:', err);
    }
}

// Auto-quote listener
function setupQuoteListener() {
    const inputs = ['book-source-loc', 'book-dest-loc', 'book-weight', 'book-service-type'];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', fetchQuoteRecommendation);
            el.addEventListener('keyup', debounce(fetchQuoteRecommendation, 400));
        }
    });
}

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

async function fetchQuoteRecommendation() {
    const source = document.getElementById('book-source-loc').value.trim();
    const dest = document.getElementById('book-dest-loc').value.trim();
    const weight = parseFloat(document.getElementById('book-weight').value) || 1.0;
    const serviceType = document.getElementById('book-service-type').value;

    const quoteBox = document.getElementById('auto-quote-container');

    if (!source || !dest) {
        quoteBox.innerHTML = `
            <div style="color: var(--gray-600); font-size: 0.83rem; text-align: center; padding: 0.85rem; border: 1px dashed var(--gray-300); border-radius: var(--radius-sm); margin-top: 0.75rem;">
                Specify origin and destination localities above to execute algorithmic courier evaluation.
            </div>`;
        return;
    }

    try {
        const res = await fetch('/api/quote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source_locality: source, dest_locality: dest, package_weight_kg: weight, service_type: serviceType })
        });
        const json = await res.json();

        if (json.success && json.count > 0) {
            const best = json.recommended;
            quoteBox.innerHTML = `
                <div class="recommend-box">
                    <div class="recommend-header">
                        <div>
                            <span class="badge badge-delivered">OPTIMAL ALLOCATION</span>
                            <div class="recommend-title" style="margin-top: 0.35rem;">${best.name}</div>
                            <div style="font-size: 0.8rem; color: var(--gray-600); margin-top: 0.2rem;">
                                Fleet Vehicle: <strong>${best.vehicle_type}</strong> | Driver Score: <strong>${best.rating} / 5.0</strong> | Active Load: <strong>${best.current_active_orders}</strong>
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div class="recommend-cost">₹${best.total_cost}</div>
                            <div style="font-size: 0.72rem; color: var(--gray-600);">Courier Payout: ₹${best.courier_payout}</div>
                        </div>
                    </div>
                    <div style="font-size: 0.78rem; color: var(--gray-700); background: #ffffff; padding: 0.5rem 0.65rem; border-radius: 4px; border: 1px solid var(--gray-200); margin-top: 0.4rem;">
                        <strong>Dispatch Optimization:</strong> Evaluated ${json.count} eligible courier service(s) covering '${source}' and '${dest}'. Selected based on tariff minimization, driver performance rating, and workload balancing.
                    </div>
                </div>
            `;
        } else {
            quoteBox.innerHTML = `
                <div class="alert alert-danger" style="margin-top: 0.75rem;">
                    No active courier partners currently service route '${source}' to '${dest}' with ${weight} kg payload capacity.
                </div>
            `;
        }
    } catch (err) {
        console.error('Error fetching quote:', err);
    }
}

// Handle Book Delivery Form
async function handleBookDelivery(e) {
    e.preventDefault();
    const btn = document.getElementById('btn-book-submit');
    btn.disabled = true;
    btn.innerText = 'Evaluating and Assigning Courier...';

    const data = {
        sender_name: document.getElementById('book-sender-name').value,
        sender_phone: document.getElementById('book-sender-phone').value,
        source_address: document.getElementById('book-source-addr').value,
        source_locality: document.getElementById('book-source-loc').value,
        receiver_name: document.getElementById('book-recv-name').value,
        receiver_phone: document.getElementById('book-recv-phone').value,
        dest_address: document.getElementById('book-dest-addr').value,
        dest_locality: document.getElementById('book-dest-loc').value,
        package_weight_kg: parseFloat(document.getElementById('book-weight').value) || 1.0,
        package_type: document.getElementById('book-pkg-type').value,
        service_type: document.getElementById('book-service-type').value
    };

    try {
        const res = await fetch('/api/deliveries/book', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const json = await res.json();

        if (json.success) {
            renderBookingConfirmation(json);
            loadOverview();
            loadRecentDeliveries();
            // Reset form
            document.getElementById('booking-form').reset();
            document.getElementById('auto-quote-container').innerHTML = '';
        } else {
            alert('Booking Dispatch Error: ' + (json.error || 'Unknown error'));
        }
    } catch (err) {
        alert('Server communication error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerText = 'Confirm Order & Auto-Assign Courier';
    }
}

// Render Output 1: Booking confirmation
function renderBookingConfirmation(data) {
    const container = document.getElementById('booking-confirmation-container');
    container.innerHTML = `
        <div class="receipt-slip" id="booking-slip">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
                <h3 style="color: var(--gray-900); font-size: 1.05rem;">Booking Confirmation (Output 1)</h3>
                <span class="badge badge-booked">${data.status}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--gray-600); margin-bottom: 0.85rem; font-family: var(--font-mono);">
                Tracking ID: <strong style="color: var(--primary); font-size: 0.95rem;">${data.tracking_id}</strong> | Reference: ${data.booking_reference}
            </div>

            <div class="receipt-row">
                <span class="receipt-label">Allocated Courier</span>
                <span class="receipt-val">${data.assigned_courier.name} (${data.assigned_courier.vehicle_type})</span>
            </div>
            <div class="receipt-row">
                <span class="receipt-label">Driver Contact & Rating</span>
                <span class="receipt-val">${data.assigned_courier.phone} | Score ${data.assigned_courier.rating} / 5.0</span>
            </div>
            <div class="receipt-row">
                <span class="receipt-label">Consignment Transit Route</span>
                <span class="receipt-val">${data.route.source} &rarr; ${data.route.destination}</span>
            </div>
            <div class="receipt-row">
                <span class="receipt-label">Consignment Specifications</span>
                <span class="receipt-val">${data.route.package_type} (${data.route.weight_kg} kg) [${data.route.service_type}]</span>
            </div>
            <div class="receipt-row">
                <span class="receipt-label">Target Delivery SLA</span>
                <span class="receipt-val mono" style="color: var(--primary);">${data.promised_delivery_time}</span>
            </div>
            <div class="receipt-row" style="background: var(--gray-50); padding: 0.6rem 0.5rem; margin-top: 0.5rem; border-radius: var(--radius-sm);">
                <span class="receipt-label" style="font-weight: 700; color: var(--gray-800);">Net Shipping Tariff</span>
                <span class="receipt-val mono" style="color: var(--primary); font-size: 1.05rem; font-weight: 700;">₹${data.shipping_cost}</span>
            </div>

            <div style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                <button class="btn btn-primary btn-sm" onclick="trackFromBooking('${data.tracking_id}')">
                    Inspect Real-Time Status
                </button>
                <button class="btn btn-secondary btn-sm" onclick="window.print()">
                    Print Official Slip
                </button>
            </div>
        </div>
    `;
    container.scrollIntoView({ behavior: 'smooth' });
}

function trackFromBooking(trackingId) {
    document.querySelector('[data-tab="tab-track"]').click();
    document.getElementById('track-search-input').value = trackingId;
    searchTracking();
}

// Load recent deliveries table
async function loadRecentDeliveries() {
    try {
        const res = await fetch('/api/deliveries');
        const json = await res.json();
        if (json.success) {
            const tbody = document.getElementById('recent-deliveries-body');
            if (!tbody) return;
            tbody.innerHTML = '';

            json.deliveries.slice(0, 8).forEach(d => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-family: var(--font-mono); font-weight: 600;">${d.tracking_id}</td>
                    <td>${d.sender_name} <br><small style="color: var(--gray-600);">${d.source_locality}</small></td>
                    <td>${d.receiver_name} <br><small style="color: var(--gray-600);">${d.dest_locality}</small></td>
                    <td>${d.courier_name}</td>
                    <td style="font-family: var(--font-mono); font-weight: 600;">₹${d.shipping_cost}</td>
                    <td><span class="badge badge-${d.status.toLowerCase().replace(/\s+/g, '-')}">${d.status}</span></td>
                    <td>
                        <button class="btn btn-secondary btn-sm" onclick="trackFromBooking('${d.tracking_id}')">Track</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error('Error loading recent deliveries:', err);
    }
}

// Quick chip loader for Track tab
async function loadRecentDeliveriesForTrack() {
    try {
        const res = await fetch('/api/deliveries');
        const json = await res.json();
        if (json.success) {
            const container = document.getElementById('track-quick-chips');
            container.innerHTML = '<span style="font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--gray-600); margin-right: 0.4rem; font-weight: 600;">Quick Select:</span>';
            json.deliveries.slice(0, 6).forEach(d => {
                const chip = document.createElement('span');
                chip.className = 'chip';
                chip.innerText = `${d.tracking_id} [${d.status}]`;
                chip.onclick = () => {
                    document.getElementById('track-search-input').value = d.tracking_id;
                    searchTracking();
                };
                container.appendChild(chip);
            });
        }
    } catch (err) {
        console.error('Error loading quick chips:', err);
    }
}

// Search tracking ID
async function searchTracking() {
    const input = document.getElementById('track-search-input');
    const trackingId = input.value.trim();
    if (!trackingId) {
        alert('Please enter a valid Tracking ID (e.g. TRK-2026-001)');
        return;
    }

    currentTrackingId = trackingId;
    const reportBox = document.getElementById('track-report-container');
    reportBox.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--gray-600);">Querying dispatch records...</div>';

    try {
        const res = await fetch(`/api/deliveries/${encodeURIComponent(trackingId)}`);
        const json = await res.json();

        if (json.success) {
            renderDeliveryStatusReport(json);
        } else {
            reportBox.innerHTML = `
                <div class="alert alert-danger">
                    ${json.error || 'Tracking record not found.'}
                </div>
            `;
        }
    } catch (err) {
        reportBox.innerHTML = `<div class="alert alert-danger">Error: ${err.message}</div>`;
    }
}

// Render Output 2: Delivery status report
function renderDeliveryStatusReport(data) {
    const d = data.delivery;
    const reportBox = document.getElementById('track-report-container');

    let milestonesHtml = '';
    data.milestones.forEach(m => {
        milestonesHtml += `
            <div class="timeline-item active">
                <div class="timeline-date">${m.timestamp}</div>
                <div class="timeline-title">${m.status}</div>
                <div class="timeline-desc">${m.remarks || ''}</div>
            </div>
        `;
    });

    let rescheduleHtml = '';
    if (data.reschedule_history && data.reschedule_history.length > 0) {
        rescheduleHtml = `
            <div style="margin-top: 1rem; background: var(--gray-50); border: 1px solid var(--gray-300); border-radius: var(--radius-sm); padding: 0.75rem;">
                <h4 style="color: var(--gray-800); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.4rem;">Schedule Modification Audit:</h4>
                ${data.reschedule_history.map(r => `
                    <div style="font-size: 0.8rem; color: var(--gray-700); margin-bottom: 0.25rem;">
                        <strong>${r.rescheduled_at}:</strong> Slot adjusted from <span style="font-family: var(--font-mono);">${r.old_delivery_time}</span> to <strong style="font-family: var(--font-mono);">${r.new_delivery_time}</strong>. Reason: ${r.reason}
                    </div>
                `).join('')}
            </div>
        `;
    }

    let cancelHtml = '';
    if (data.cancellation_details) {
        const c = data.cancellation_details;
        cancelHtml = `
            <div class="alert alert-danger" style="margin-top: 1rem;">
                <div>
                    <strong>Cancellation Record:</strong> Processed by ${c.cancelled_by} at ${c.cancelled_at}.<br>
                    <strong>Reason:</strong> ${c.reason} | <strong>Fee:</strong> ₹${c.cancellation_fee} | <strong>Refund Status:</strong> ${c.refund_status}
                </div>
            </div>
        `;
    }

    let rewardPenaltyHtml = '';
    if (data.reward_penalty_details) {
        const rp = data.reward_penalty_details;
        const isReward = rp.type === 'REWARD';
        rewardPenaltyHtml = `
            <div class="alert ${isReward ? 'alert-success' : 'alert-danger'}" style="margin-top: 1rem;">
                <div>
                    <strong>${isReward ? 'SLA Compliance Reward Notice' : 'SLA Breach Penalty Notice'}:</strong><br>
                    ${rp.notice_text}
                </div>
            </div>
        `;
    }

    // Stepper definition
    const allSteps = ['Booked', 'Picked Up', 'In Transit', 'Out for Delivery', 'Delivered'];
    const currentStepIdx = allSteps.indexOf(d.status);
    const isTerminal = ['Delivered', 'Cancelled', 'Expired (SLA Breach)'].includes(d.status);

    let stepperHtml = '<div class="stepper-container">';
    allSteps.forEach((stepName, idx) => {
        let nodeClass = '';
        let circleContent = (idx + 1);

        if (d.status === 'Cancelled' || d.status === 'Expired (SLA Breach)') {
            nodeClass = '';
        } else if (idx < currentStepIdx) {
            nodeClass = 'completed';
            circleContent = '&#10003;';
        } else if (idx === currentStepIdx) {
            nodeClass = 'active';
            circleContent = (idx + 1);
        }

        stepperHtml += `
            <div class="step-node ${nodeClass}">
                <div class="step-circle">${circleContent}</div>
                <div class="step-label">${stepName}</div>
            </div>
        `;

        if (idx < allSteps.length - 1) {
            const connectorClass = (idx < currentStepIdx) ? 'completed' : ((idx === currentStepIdx - 1) ? 'active' : '');
            stepperHtml += `<div class="step-connector ${connectorClass}"></div>`;
        }
    });
    stepperHtml += '</div>';

    // SLA Deadline Monitor Card
    let slaMonitorHtml = '';
    if (!isTerminal) {
        if (d.is_overdue) {
            slaMonitorHtml = `
                <div class="sla-monitor-card overdue">
                    <div>
                        <div class="sla-title" style="color: var(--danger);">SLA STATUS: DEADLINE EXPIRED / OVERDUE</div>
                        <div class="sla-time" style="color: var(--danger);">Promised Deadline: ${d.promised_delivery_time} (Breached by ${d.hours_overdue} hrs)</div>
                        <div style="font-size: 0.78rem; color: var(--gray-700); margin-top: 0.2rem;">
                            The delivery window has lapsed. Penalty will be enforced upon delivery, or order can be forfeited.
                        </div>
                    </div>
                    <div style="display: flex; gap: 0.4rem; align-items: center;">
                        <button class="btn btn-danger btn-sm" onclick="expireConsignment('${d.tracking_id}', 'Consignment expired past SLA deadline (${d.hours_overdue}h late)')">
                            Expire & Penalize Courier (-₹100)
                        </button>
                    </div>
                </div>
            `;
        } else {
            slaMonitorHtml = `
                <div class="sla-monitor-card on-schedule">
                    <div>
                        <div class="sla-title" style="color: var(--success);">SLA STATUS: ACTIVE & ON SCHEDULE</div>
                        <div class="sla-time" style="color: var(--success);">Target Delivery: ${d.promised_delivery_time} (${d.hours_remaining} hrs remaining)</div>
                    </div>
                    <button class="btn btn-secondary btn-sm" onclick="simulateBreach('${d.tracking_id}')">
                        Simulate Deadline Expiry (+2h Breach)
                    </button>
                </div>
            `;
        }
    }

    reportBox.innerHTML = `
        <div class="card" style="margin-top: 1rem;">
            <div class="card-header">
                <div>
                    <h3 style="font-size: 1.05rem;">Delivery Status Report (Output 2)</h3>
                    <div style="font-size: 0.78rem; color: var(--gray-600); margin-top: 0.2rem; font-family: var(--font-mono);">
                        Tracking ID: <strong>${d.tracking_id}</strong> | Timestamp: ${d.booked_at}
                    </div>
                </div>
                <div>
                    <span class="badge badge-${d.status.toLowerCase().replace(/[^a-z0-9]+/g, '-')}">${d.status}</span>
                </div>
            </div>
            <div class="card-body">
                <!-- Visual Sequential Stepper -->
                ${stepperHtml}

                <!-- SLA Monitor Bar -->
                ${slaMonitorHtml}

                <div class="grid-2">
                    <div>
                        <h4 style="font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--gray-600); margin-bottom: 0.5rem;">Origin, Destination & Payload</h4>
                        <table class="data-table">
                            <tr><td style="width: 32%; font-weight: 600;">Sender</td><td>${d.sender_name} (${d.sender_phone})<br><small style="color: var(--gray-600);">${d.source_address}, ${d.source_locality}</small></td></tr>
                            <tr><td style="font-weight: 600;">Recipient</td><td>${d.receiver_name} (${d.receiver_phone})<br><small style="color: var(--gray-600);">${d.dest_address}, ${d.dest_locality}</small></td></tr>
                            <tr><td style="font-weight: 600;">Consignment</td><td>${d.package_type} (${d.package_weight_kg} kg) - ${d.service_type}</td></tr>
                            <tr><td style="font-weight: 600;">Promised SLA</td><td><strong style="color: var(--primary); font-family: var(--font-mono);">${d.promised_delivery_time}</strong></td></tr>
                            ${d.actual_delivery_time ? `<tr><td style="font-weight: 600;">Completion</td><td><strong style="color: var(--success); font-family: var(--font-mono);">${d.actual_delivery_time}</strong></td></tr>` : ''}
                        </table>
                    </div>
                    <div>
                        <h4 style="font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--gray-600); margin-bottom: 0.5rem;">Allocated Courier Logistics</h4>
                        <table class="data-table">
                            <tr><td style="width: 35%; font-weight: 600;">Partner</td><td><strong>${d.courier_name}</strong></td></tr>
                            <tr><td style="font-weight: 600;">Contact</td><td>${d.courier_phone}</td></tr>
                            <tr><td style="font-weight: 600;">Vehicle</td><td>${d.vehicle_type}</td></tr>
                            <tr><td style="font-weight: 600;">Driver Score</td><td>${d.courier_rating} / 5.0</td></tr>
                            <tr><td style="font-weight: 600;">Tariff Breakdown</td><td>Total: ₹${d.shipping_cost} | Payout: ₹${d.courier_payout}</td></tr>
                        </table>
                    </div>
                </div>

                ${rescheduleHtml}
                ${cancelHtml}
                ${rewardPenaltyHtml}

                <!-- Milestones Timeline -->
                <div style="margin-top: 1.5rem;">
                    <h4 style="font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--gray-600); margin-bottom: 0.75rem;">Transit Milestone Log</h4>
                    <div class="timeline">
                        ${milestonesHtml}
                    </div>
                </div>

                <!-- Sequential Milestone Controller -->
                ${!isTerminal ? `
                <div class="milestone-controller-box">
                    <div class="header-action">
                        <div>
                            <div style="font-size: 0.84rem; font-weight: 700; text-transform: uppercase; color: var(--gray-900);">Sequential Milestone Controller</div>
                            <div style="font-size: 0.78rem; color: var(--gray-600); margin-top: 0.15rem;">
                                Current stage: <strong>${d.status}</strong> &bull; Next required sequential step: <strong style="color: var(--primary);">${d.next_allowed_status}</strong>
                            </div>
                        </div>
                        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                            ${d.next_allowed_status !== 'Delivered' ? `
                                <button class="btn btn-primary" onclick="advanceSequentialMilestone('${d.tracking_id}', '${d.next_allowed_status}')">
                                    Advance Milestone: ${d.next_allowed_status} &rarr;
                                </button>
                            ` : `
                                <button class="btn btn-success" onclick="executeDeliveryCompletion('${d.tracking_id}', '${d.promised_delivery_time}', ${d.is_overdue})">
                                    Complete Final Delivery (Execute SLA Settlement)
                                </button>
                            `}
                        </div>
                    </div>
                </div>
                ` : `
                <div style="background: var(--gray-100); border: 1px solid var(--gray-300); border-radius: var(--radius-sm); padding: 0.8rem; margin-top: 1.25rem; font-size: 0.84rem; color: var(--gray-700);">
                    Consignment has concluded with terminal status: <strong>${d.status}</strong>. Transit operations are finalized.
                </div>
                `}
            </div>
        </div>
    `;
}

// Advance milestone in strict sequence
async function advanceSequentialMilestone(trackingId, nextStatus) {
    try {
        const res = await fetch(`/api/deliveries/${encodeURIComponent(trackingId)}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: nextStatus, remarks: `Stage advanced sequentially to ${nextStatus}` })
        });
        const json = await res.json();
        if (json.success) {
            searchTracking();
            loadOverview();
            loadRecentDeliveries();
        } else {
            alert('Sequence Error: ' + json.error);
        }
    } catch (err) {
        alert('Communication Error: ' + err.message);
    }
}

// Complete final delivery with automatic SLA verification
async function executeDeliveryCompletion(trackingId, promisedTime, isAlreadyOverdue) {
    let actualTimeStr;
    const now = new Date();

    if (isAlreadyOverdue) {
        // Automatically enforce penalty due to overdue deadline
        actualTimeStr = formatDateTime(now);
    } else {
        const promptChoice = confirm(
            `Execute Final Delivery for ${trackingId}?\n\n` +
            `Target SLA Deadline: ${promisedTime}\n\n` +
            `Click [OK] to deliver ON-TIME (Awards +₹100 Courier Reward Bonus)\n` +
            `Click [Cancel] to simulate DELAYED Delivery (Applies -₹50 SLA Penalty Notice)`
        );

        if (promptChoice) {
            actualTimeStr = formatDateTime(now);
        } else {
            const lateDate = new Date(new Date(promisedTime).getTime() + (3 * 3600 * 1000));
            actualTimeStr = formatDateTime(lateDate);
        }
    }

    try {
        const res = await fetch(`/api/deliveries/${encodeURIComponent(trackingId)}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: 'Delivered',
                remarks: 'Delivered to recipient with digital proof of delivery',
                actual_delivery_time: actualTimeStr
            })
        });
        const json = await res.json();
        if (json.success) {
            let msg = `Delivery confirmed for ${trackingId}.`;
            if (json.reward_penalty) {
                msg += `\n\n${json.reward_penalty.notice_text}`;
            }
            alert(msg);
            searchTracking();
            loadOverview();
            loadRecentDeliveries();
        } else {
            alert('Delivery completion failed: ' + json.error);
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// Expire consignment after deadline breach
async function expireConsignment(trackingId, reason) {
    if (!confirm(`Are you sure you want to expire ${trackingId} due to SLA deadline breach?\n\nThis will forfeit the consignment and penalize the assigned courier -₹100.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/deliveries/${encodeURIComponent(trackingId)}/expire`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: reason, penalty_amount: 100.0 })
        });
        const json = await res.json();
        if (json.success) {
            alert(json.notice_text || json.message);
            searchTracking();
            loadOverview();
            loadRecentDeliveries();
        } else {
            alert('Expiry failed: ' + json.error);
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// Simulate deadline breach for testing in lab
async function simulateBreach(trackingId) {
    try {
        const res = await fetch(`/api/deliveries/${encodeURIComponent(trackingId)}/simulate-deadline-breach`, {
            method: 'POST'
        });
        const json = await res.json();
        if (json.success) {
            alert(json.message + ' Consignment is now overdue. Notice the red alert and expiry/penalty triggers.');
            searchTracking();
        } else {
            alert('Simulation failed: ' + json.error);
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// Reschedule submission
async function handleRescheduleSubmit(e) {
    e.preventDefault();
    const trackingId = document.getElementById('resched-tracking-id').value.trim();
    const newDate = document.getElementById('resched-new-date').value;
    const reason = document.getElementById('resched-reason').value.trim();

    if (!trackingId || !newDate) {
        alert('Please fill in tracking ID and new delivery date.');
        return;
    }

    try {
        const res = await fetch(`/api/deliveries/${encodeURIComponent(trackingId)}/reschedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_delivery_time: newDate, reason: reason })
        });
        const json = await res.json();

        const resultBox = document.getElementById('resched-result-container');
        if (json.success) {
            resultBox.innerHTML = `
                <div class="receipt-slip">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
                        <h3 style="color: var(--gray-900); font-size: 1rem;">Updated Record after Rescheduling (Output 4)</h3>
                        <span class="badge badge-rescheduled">Rescheduled</span>
                    </div>
                    <div class="receipt-row"><span class="receipt-label">Tracking ID</span><span class="receipt-val mono">${json.tracking_id}</span></div>
                    <div class="receipt-row"><span class="receipt-label">Original SLA Window</span><span class="receipt-val mono" style="text-decoration: line-through; color: var(--gray-600);">${json.old_delivery_time}</span></div>
                    <div class="receipt-row"><span class="receipt-label">New Promised SLA Window</span><span class="receipt-val mono" style="color: var(--primary); font-weight: 700;">${json.new_delivery_time}</span></div>
                    <div class="receipt-row"><span class="receipt-label">Assigned Courier</span><span class="receipt-val">${json.assigned_courier}</span></div>
                    <div class="receipt-row"><span class="receipt-label">Revision Sequence</span><span class="receipt-val">Revision #${json.rescheduled_count}</span></div>
                    <div class="receipt-row"><span class="receipt-label">Justification</span><span class="receipt-val">${json.reason}</span></div>
                    <div class="receipt-row"><span class="receipt-label">Modification Timestamp</span><span class="receipt-val mono">${json.rescheduled_at}</span></div>
                </div>
            `;
            loadOverview();
        } else {
            resultBox.innerHTML = `<div class="alert alert-danger">${json.error}</div>`;
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// Cancel submission
async function handleCancelSubmit(e) {
    e.preventDefault();
    const trackingId = document.getElementById('cancel-tracking-id').value.trim();
    const reason = document.getElementById('cancel-reason').value.trim();
    const cancelledBy = document.getElementById('cancel-by').value;

    if (!trackingId || !reason) {
        alert('Please fill in tracking ID and cancellation reason.');
        return;
    }

    try {
        const res = await fetch(`/api/deliveries/${encodeURIComponent(trackingId)}/cancel`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: reason, cancelled_by: cancelledBy })
        });
        const json = await res.json();

        const resultBox = document.getElementById('cancel-result-container');
        if (json.success) {
            resultBox.innerHTML = `
                <div class="receipt-slip">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
                        <h3 style="color: var(--danger); font-size: 1rem;">Cancellation Confirmation (Output 3)</h3>
                        <span class="badge badge-cancelled">Cancelled</span>
                    </div>
                    <div class="receipt-row"><span class="receipt-label">Cancellation Reference</span><span class="receipt-val mono">${json.cancellation_id}</span></div>
                    <div class="receipt-row"><span class="receipt-label">Tracking ID</span><span class="receipt-val mono">${json.tracking_id}</span></div>
                    <div class="receipt-row"><span class="receipt-label">Initiated By</span><span class="receipt-val">${json.cancelled_by}</span></div>
                    <div class="receipt-row"><span class="receipt-label">Stated Reason</span><span class="receipt-val">${json.reason}</span></div>
                    <div class="receipt-row"><span class="receipt-label">Processing Fee</span><span class="receipt-val mono">₹${json.cancellation_fee}</span></div>
                    <div class="receipt-row"><span class="receipt-label">Refund Settlement</span><span class="receipt-val" style="color: var(--success);">${json.refund_status}</span></div>
                    <div class="receipt-row"><span class="receipt-label">Timestamp</span><span class="receipt-val mono">${json.cancelled_at}</span></div>
                    ${json.courier_penalty_notice ? `<div class="alert alert-danger" style="margin-top: 0.75rem;">${json.courier_penalty_notice}</div>` : ''}
                </div>
            `;
            loadOverview();
            loadRecentDeliveries();
        } else {
            resultBox.innerHTML = `<div class="alert alert-danger">${json.error}</div>`;
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// Rewards and Penalties Tab
async function loadRewardsPenalties() {
    try {
        const res = await fetch('/api/rewards-penalties');
        const json = await res.json();
        if (json.success) {
            const tbody = document.getElementById('rewards-penalties-body');
            tbody.innerHTML = '';
            if (json.records.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--gray-600); padding: 1.5rem;">No reward or penalty notices issued yet.</td></tr>';
                return;
            }
            json.records.forEach(r => {
                const isReward = r.type === 'REWARD';
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-family: var(--font-mono); font-weight: 600;">#${r.id}</td>
                    <td style="font-family: var(--font-mono); font-weight: 600;">${r.tracking_id}</td>
                    <td>${r.courier_name} <br><small style="color: var(--gray-600);">${r.courier_phone}</small></td>
                    <td><span class="badge ${isReward ? 'badge-reward' : 'badge-penalty'}">${r.type}</span></td>
                    <td style="font-family: var(--font-mono); font-weight: 700; color: ${isReward ? 'var(--success)' : 'var(--danger)'};">
                        ${isReward ? '+' : '-'}₹${r.amount}
                    </td>
                    <td><small style="color: var(--gray-800);">${r.notice_text}</small></td>
                    <td style="font-family: var(--font-mono);"><small>${r.created_at}</small></td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error('Error loading rewards:', err);
    }
}

// Load Couriers for Service Query Tab
async function loadCourierSelectOptions() {
    try {
        const res = await fetch('/api/couriers');
        const json = await res.json();
        if (json.success) {
            const select = document.getElementById('courier-query-select');
            select.innerHTML = '<option value="">-- Select Courier Partner for Service Query --</option>';
            json.couriers.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id;
                opt.innerText = `${c.name} [${c.vehicle_type} - Active: ${c.current_active_orders}, Balance: ₹${c.wallet_balance}]`;
                select.appendChild(opt);
            });
        }
    } catch (err) {
        console.error('Error loading couriers:', err);
    }
}

// Fetch and display Output 6: Courier Past Services Report
async function queryCourierPastServices() {
    const courierId = document.getElementById('courier-query-select').value;
    if (!courierId) {
        alert('Please choose a courier to query.');
        return;
    }

    const container = document.getElementById('courier-service-report-container');
    container.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--gray-600);">Querying courier service ledger...</div>';

    try {
        const res = await fetch(`/api/couriers/${courierId}/services`);
        const json = await res.json();

        if (json.success) {
            renderCourierServiceReport(json);
        } else {
            container.innerHTML = `<div class="alert alert-danger">${json.error}</div>`;
        }
    } catch (err) {
        container.innerHTML = `<div class="alert alert-danger">Error: ${err.message}</div>`;
    }
}

function renderCourierServiceReport(data) {
    const c = data.courier;
    const m = data.metrics;
    const container = document.getElementById('courier-service-report-container');

    let servicesRows = '';
    if (data.services.length === 0) {
        servicesRows = '<tr><td colspan="8" style="text-align: center; color: var(--gray-600); padding: 1.5rem;">No historical service records found for this courier partner.</td></tr>';
    } else {
        data.services.forEach(s => {
            const rpBadge = s.rp_type ? `<span class="badge ${s.rp_type === 'REWARD' ? 'badge-reward' : 'badge-penalty'}">${s.rp_type}: ₹${s.rp_amount}</span>` : '<span style="color: var(--gray-400);">-</span>';
            servicesRows += `
                <tr>
                    <td style="font-family: var(--font-mono); font-weight: 600;">${s.tracking_id}</td>
                    <td>${s.source_locality} &rarr; ${s.dest_locality}</td>
                    <td>${s.package_type} (${s.package_weight_kg} kg)</td>
                    <td style="font-family: var(--font-mono); font-size: 0.78rem;">${s.booked_at}</td>
                    <td><span class="badge badge-${s.status.toLowerCase().replace(/\s+/g, '-')}">${s.status}</span></td>
                    <td style="font-family: var(--font-mono);">₹${s.shipping_cost}</td>
                    <td style="font-family: var(--font-mono);">₹${s.courier_payout}</td>
                    <td>${rpBadge}</td>
                </tr>
            `;
        });
    }

    container.innerHTML = `
        <div class="card" style="margin-top: 1rem;">
            <div class="card-header">
                <div>
                    <h3>List of Past Services for ${c.name} (Output 6)</h3>
                    <div style="font-size: 0.78rem; color: var(--gray-600); margin-top: 0.2rem;">
                        Contact: ${c.phone} | Vehicle: ${c.vehicle_type} (Max Capacity: ${c.max_capacity_kg} kg) | Quality Rating: ${c.rating} / 5.0
                    </div>
                </div>
                <div>
                    <span class="badge badge-delivered" style="font-size: 0.82rem; padding: 0.35rem 0.7rem; font-family: var(--font-mono);">
                        Net Balance: ₹${c.wallet_balance}
                    </span>
                </div>
            </div>
            <div class="card-body">
                <!-- Metrics Bar -->
                <div class="grid-4" style="margin-bottom: 1.25rem;">
                    <div class="stat-pill" style="background: var(--gray-50); border: 1px solid var(--gray-200);">
                        <span class="label" style="color: var(--gray-600);">Total Assigned</span>
                        <span class="value" style="color: var(--gray-900);">${m.total_assigned}</span>
                    </div>
                    <div class="stat-pill" style="background: #f0fdf4; border: 1px solid #bbf7d0;">
                        <span class="label" style="color: #166534;">Delivered Orders</span>
                        <span class="value" style="color: #15803d;">${m.delivered_count}</span>
                    </div>
                    <div class="stat-pill" style="background: #f0f9ff; border: 1px solid #bae6fd;">
                        <span class="label" style="color: #0369a1;">SLA On-Time Rate</span>
                        <span class="value" style="color: #0284c7;">${m.on_time_rate}%</span>
                    </div>
                    <div class="stat-pill" style="background: #fffbeb; border: 1px solid #fde68a;">
                        <span class="label" style="color: #92400e;">Reward / Penalty</span>
                        <span class="value" style="color: #b45309; font-size: 0.95rem;">+₹${m.total_rewards_val} / -₹${m.total_penalties_val}</span>
                    </div>
                </div>

                <div class="section-label">Historical Consignment Operations:</div>
                <div class="table-responsive">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Tracking ID</th>
                                <th>Route</th>
                                <th>Payload</th>
                                <th>Booked Time</th>
                                <th>Status</th>
                                <th>Tariff</th>
                                <th>Payout</th>
                                <th>SLA Adjustment</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${servicesRows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
}

// Archive Management
async function loadArchivedDeliveries() {
    try {
        const res = await fetch('/api/deliveries/archive');
        const json = await res.json();
        if (json.success) {
            const tbody = document.getElementById('archive-table-body');
            tbody.innerHTML = '';
            if (json.archived.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--gray-600); padding: 1.5rem;">No archived deliveries catalogued yet. Use the archive trigger above to archive terminal consignments.</td></tr>';
                return;
            }
            json.archived.forEach(d => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-family: var(--font-mono); font-weight: 600;">${d.tracking_id}</td>
                    <td>${d.sender_name} &rarr; ${d.receiver_name}</td>
                    <td>${d.source_locality} &rarr; ${d.dest_locality}</td>
                    <td>${d.courier_name}</td>
                    <td><span class="badge badge-${d.status.toLowerCase().replace(/\s+/g, '-')}">${d.status}</span></td>
                    <td style="font-family: var(--font-mono);">₹${d.shipping_cost}</td>
                    <td style="font-family: var(--font-mono);"><small>${d.archived_at}</small></td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error('Error loading archive:', err);
    }
}

async function triggerArchive() {
    if (!confirm('Archive all Delivered and Cancelled deliveries to long-term storage?')) return;
    try {
        const res = await fetch('/api/deliveries/archive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const json = await res.json();
        if (json.success) {
            alert(json.message);
            loadArchivedDeliveries();
            loadOverview();
        } else {
            alert('Archive operation failed: ' + json.error);
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// Couriers List & Management
async function loadCouriersList() {
    try {
        const res = await fetch('/api/couriers');
        const json = await res.json();
        if (json.success) {
            // Pre-loaded
        }
    } catch (err) {
        console.error('Error fetching couriers:', err);
    }
}

async function loadCouriersManagement() {
    try {
        const res = await fetch('/api/couriers');
        const json = await res.json();
        if (json.success) {
            const tbody = document.getElementById('couriers-mgmt-body');
            tbody.innerHTML = '';
            json.couriers.forEach(c => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-family: var(--font-mono); font-weight: 600;">#${c.id}</td>
                    <td><strong>${c.name}</strong><br><small style="color: var(--gray-600);">${c.phone} | ${c.email || 'N/A'}</small></td>
                    <td>${c.vehicle_type} (${c.max_capacity_kg} kg)</td>
                    <td><small>${c.serviceable_localities}</small></td>
                    <td style="font-family: var(--font-mono); font-size: 0.8rem;">Base ₹${c.base_fare} + ₹${c.rate_per_kg}/kg</td>
                    <td style="font-weight: 600;">${c.rating} / 5.0</td>
                    <td><span class="badge ${c.current_active_orders > 0 ? 'badge-in-transit' : 'badge-delivered'}">${c.current_active_orders} orders</span></td>
                    <td style="font-family: var(--font-mono); font-weight: 700;">₹${c.wallet_balance}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error('Error loading couriers mgmt:', err);
    }
}

// Add new courier
async function handleAddCourier(e) {
    e.preventDefault();
    const data = {
        name: document.getElementById('courier-name').value.trim(),
        phone: document.getElementById('courier-phone').value.trim(),
        email: document.getElementById('courier-email').value.trim(),
        vehicle_type: document.getElementById('courier-vehicle').value,
        max_capacity_kg: parseFloat(document.getElementById('courier-capacity').value) || 20.0,
        serviceable_localities: document.getElementById('courier-localities').value.trim(),
        base_fare: parseFloat(document.getElementById('courier-base-fare').value) || 50.0,
        rate_per_kg: parseFloat(document.getElementById('courier-rate-kg').value) || 12.0,
        rating: parseFloat(document.getElementById('courier-rating').value) || 4.5
    };

    try {
        const res = await fetch('/api/couriers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const json = await res.json();

        if (json.success) {
            alert(json.message);
            document.getElementById('add-courier-form').reset();
            loadCouriersManagement();
            loadLocalities();
            loadOverview();
        } else {
            alert('Failed to register courier: ' + json.error);
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}
