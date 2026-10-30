// OmniLead 24/7 Autonomous Agent Controller
let currentLeads = [];
let currentDeals = [];
let activeSimulatorLeadId = null;
let ws = null;

// Sound synthesizer using Web Audio API for celebrations
function playNotificationSound(type = 'deal') {
    const soundEnabled = document.getElementById('soundToggle')?.checked;
    if (!soundEnabled) return;

    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();

        osc.connect(gain);
        gain.connect(audioCtx.destination);

        if (type === 'deal') {
            // High triumph chord
            osc.frequency.setValueAtTime(523.25, audioCtx.currentTime); // C5
            osc.frequency.setValueAtTime(659.25, audioCtx.currentTime + 0.1); // E5
            osc.frequency.setValueAtTime(783.99, audioCtx.currentTime + 0.2); // G5
            osc.frequency.setValueAtTime(1046.50, audioCtx.currentTime + 0.3); // C6
            gain.gain.setValueAtTime(0.25, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.8);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.8);
        } else {
            // Subtle lead ping
            osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.3);
        }
    } catch (e) {
        console.warn('Audio synthesis note:', e);
    }
}

// WebSocket connection
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        document.getElementById('wsStatusBadge').textContent = 'Live Connected';
        document.getElementById('wsStatusBadge').style.borderColor = 'rgba(16, 185, 129, 0.4)';
        document.getElementById('wsStatusBadge').style.color = '#34d399';
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWsMessage(data);
        } catch (e) {
            console.error('WS parse error:', e);
        }
    };

    ws.onclose = () => {
        document.getElementById('wsStatusBadge').textContent = 'Reconnecting...';
        document.getElementById('wsStatusBadge').style.borderColor = 'rgba(245, 158, 11, 0.4)';
        document.getElementById('wsStatusBadge').style.color = '#fbbf24';
        setTimeout(initWebSocket, 3000);
    };
}

function handleWsMessage(payload) {
    if (payload.type === 'log') {
        appendLogEntry(payload.data);
    } else if (payload.type === 'lead_discovered') {
        appendLogEntry({
            level: 'INFO',
            category: 'HUNTER',
            message: `Discovered new lead: ${payload.data.business_name} (${payload.data.niche})`
        });
        playNotificationSound('lead');
        loadStats();
        loadLeads();
    } else if (payload.type === 'lead_updated') {
        loadStats();
        loadLeads();
        loadDeals();
    }
}

// Terminal Log Management
function appendLogEntry(log) {
    const terminal = document.getElementById('terminalLogs');
    if (!terminal) return;

    const timeStr = log.created_at ? new Date(log.created_at).toLocaleTimeString() : new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry ${(log.level || 'info').toLowerCase()}`;
    
    entry.innerHTML = `
        <span class="log-time">[${timeStr}]</span>
        <span class="log-tag ${(log.category || 'system').toLowerCase()}">${log.category || 'SYSTEM'}</span>
        <span class="log-msg">${escapeHtml(log.message || '')}</span>
    `;

    terminal.appendChild(entry);
    terminal.scrollTop = terminal.scrollHeight;
}

// API Data Fetching
async function loadStats() {
    try {
        const res = await fetch('/api/stats');
        if (!res.ok) return;
        const data = await res.json();
        
        document.getElementById('kpiTotalLeads').textContent = data.total_leads;
        document.getElementById('kpiContacted').textContent = data.total_contacted;
        document.getElementById('kpiNegotiating').textContent = data.total_negotiating;
        document.getElementById('kpiDeals').textContent = data.total_deals;
        document.getElementById('kpiRevenue').textContent = `$${Math.round(data.total_revenue).toLocaleString()}`;
        document.getElementById('kpiConversionRate').textContent = `${data.conversion_rate}% Close Rate`;
    } catch (e) {
        console.error('Stats error:', e);
    }
}

async function loadLeads() {
    try {
        const status = document.getElementById('filterStatus').value;
        const source = document.getElementById('filterSource').value;
        const search = document.getElementById('searchInput').value.toLowerCase();

        let url = `/api/leads?status=${status}&source=${source}`;
        const res = await fetch(url);
        if (!res.ok) return;
        currentLeads = await res.json();

        renderLeads(currentLeads, search);
        updateSimulatorDropdown(currentLeads);
    } catch (e) {
        console.error('Leads error:', e);
    }
}

function renderLeads(leads, search = '') {
    const container = document.getElementById('leadsContainer');
    if (!container) return;

    const filtered = leads.filter(l => {
        if (!search) return true;
        const text = `${l.business_name} ${l.contact_name} ${l.niche} ${l.audit_summary}`.toLowerCase();
        return text.includes(search);
    });

    if (filtered.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 3rem; color: var(--text-muted);">
                <p style="font-size: 1.1rem; margin-bottom: 0.5rem;">No leads found in this view.</p>
                <button class="btn btn-primary" onclick="triggerScan()">⚡ Run Lead Scan Now</button>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map(l => {
        const scoreBadgeClass = l.score >= 80 ? 'badge-score' : 'badge-source';
        const statusBadgeClass = l.status === 'deal_won' || l.status === 'paid' ? 'badge-won' : 'badge-status';

        return `
            <div class="lead-card" onclick="openLeadModal(${l.id})">
                <div class="lead-card-header">
                    <div class="lead-title-area">
                        <h3>${escapeHtml(l.business_name || l.title || 'Prospective Lead')}</h3>
                        <div class="lead-meta">
                            <span>👤 ${escapeHtml(l.contact_name || 'Contact')}</span>
                            <span>•</span>
                            <span>🏷️ ${escapeHtml(l.niche || 'General')}</span>
                            <span>•</span>
                            <span>📧 ${escapeHtml(l.contact_email || 'No email')}</span>
                        </div>
                    </div>
                    <div class="lead-badges">
                        <span class="badge ${scoreBadgeClass}">Score: ${l.score}/100</span>
                        <span class="badge badge-source">${l.source.replace('_', ' ')}</span>
                        <span class="badge ${statusBadgeClass}">${l.status.replace('_', ' ')}</span>
                    </div>
                </div>

                <div class="lead-audit">
                    <strong>Opportunity Audit:</strong> ${escapeHtml(l.audit_summary || 'Targeted for website creation & automated client capture.')}
                </div>

                <div class="lead-card-footer">
                    <div>Recommended: <strong>${(l.recommended_package || 'starter_landing_page').replace(/_/g, ' ').toUpperCase()}</strong></div>
                    <div class="quote-highlight">Target Price: $${Math.round(l.target_price)} USD</div>
                </div>
            </div>
        `;
    }).join('');
}

async function loadDeals() {
    try {
        const res = await fetch('/api/deals');
        if (!res.ok) return;
        currentDeals = await res.json();
        renderDeals(currentDeals);
    } catch (e) {
        console.error('Deals error:', e);
    }
}

function renderDeals(deals) {
    const container = document.getElementById('dealsContainer');
    if (!container) return;

    if (deals.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-muted);">
                <p style="font-size: 1.1rem; margin-bottom: 0.5rem;">No closed deals yet.</p>
                <p style="font-size: 0.85rem;">As the agent negotiates and closes agreements, orders appear here with client requirements.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = deals.map(d => {
        const lead = d.lead || {};
        const isPaid = d.payment_status === 'paid';
        return `
            <div class="deal-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <h3 style="font-size: 1.1rem; font-weight: 700;">${escapeHtml(lead.business_name || 'Client Project')}</h3>
                        <p style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(lead.contact_name || '')} (${escapeHtml(lead.contact_email || '')})</p>
                    </div>
                    <span class="badge ${isPaid ? 'badge-won' : 'badge-score'}">${d.payment_status.toUpperCase()}</span>
                </div>

                <div class="deal-amount">$${Math.round(d.agreed_price).toLocaleString()} USD</div>
                <div style="font-size: 0.85rem; font-weight: 600; color: var(--accent-cyan);">${escapeHtml(d.package_name)}</div>

                <div class="deal-reqs">
                    <strong>Client Scope & Requirements:</strong><br>
                    ${escapeHtml(d.client_requirements || 'Standard production package kickoff.')}
                </div>

                <div style="font-size: 0.75rem; color: var(--text-muted); word-break: break-all;">
                    <strong>Payment Link:</strong> <a href="${escapeHtml(d.payment_link || '#')}" target="_blank" style="color: var(--accent-blue);">${escapeHtml(d.payment_link || 'Direct Invoice')}</a>
                </div>

                <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
                    ${!isPaid ? `
                        <button class="btn btn-primary" style="flex: 1; justify-content: center;" onclick="markDealPaid(${d.id})">
                            ✅ Mark Payment Received
                        </button>
                    ` : `
                        <div style="color: var(--accent-emerald); font-weight: 700; font-size: 0.85rem; display: flex; align-items: center; gap: 0.35rem;">
                            <span>✨ Order Secured & Ready for Production</span>
                        </div>
                    `}
                </div>
            </div>
        `;
    }).join('');
}

async function markDealPaid(dealId) {
    try {
        const res = await fetch(`/api/deals/${dealId}/mark_paid`, { method: 'POST' });
        if (res.ok) {
            playNotificationSound('deal');
            loadStats();
            loadDeals();
            loadLeads();
        }
    } catch (e) {
        console.error('Mark paid error:', e);
    }
}

// LEAD MODAL & CONVERSATION
async function openLeadModal(leadId) {
    try {
        const res = await fetch(`/api/leads/${leadId}`);
        if (!res.ok) return;
        const lead = await res.json();

        document.getElementById('modalLeadTitle').textContent = lead.business_name || lead.title;
        document.getElementById('modalLeadBadge').textContent = `${lead.status.toUpperCase()} (${lead.score}/100)`;

        const modalBody = document.getElementById('modalLeadBody');
        const interactions = lead.interactions || [];

        modalBody.innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; background: rgba(0,0,0,0.25); padding: 1rem; border-radius: 12px;">
                <div><strong>Contact:</strong> ${escapeHtml(lead.contact_name || 'N/A')}</div>
                <div><strong>Email:</strong> ${escapeHtml(lead.contact_email || 'N/A')}</div>
                <div><strong>Niche:</strong> ${escapeHtml(lead.niche || 'N/A')}</div>
                <div><strong>Channel:</strong> ${escapeHtml(lead.source || 'N/A')}</div>
                <div><strong>Target Package:</strong> ${escapeHtml((lead.recommended_package || '').replace(/_/g, ' '))}</div>
                <div><strong>Target Price:</strong> $${Math.round(lead.target_price)} USD</div>
            </div>

            <div>
                <strong>Opportunity Audit:</strong>
                <p style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.25rem;">${escapeHtml(lead.audit_summary || '')}</p>
                ${lead.original_url ? `<p style="font-size: 0.78rem; margin-top: 0.25rem;"><a href="${escapeHtml(lead.original_url)}" target="_blank" style="color: var(--accent-blue);">🔗 View Original Posting / Listing</a></p>` : ''}
            </div>

            <div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <strong>Conversation & Negotiation History (${interactions.length} messages):</strong>
                    ${lead.status === 'discovered' || lead.status === 'scored' ? `
                        <button class="btn btn-primary" style="padding: 0.35rem 0.8rem; font-size: 0.75rem;" onclick="manualContactLead(${lead.id})">
                            ✉️ Send Personalized Pitch
                        </button>
                    ` : ''}
                </div>

                <div class="conversation-thread">
                    ${interactions.length === 0 ? '<div style="color: var(--text-muted); font-size: 0.8rem;">No messages exchanged yet. Click Send Pitch to initiate.</div>' : ''}
                    ${interactions.map(item => `
                        <div class="thread-msg ${item.direction}">
                            <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-secondary); margin-bottom: 0.3rem;">
                                <span>${item.direction === 'outbound' ? '🤖 OmniLead Agent' : '👤 Client'}</span>
                                <span>${item.created_at ? new Date(item.created_at).toLocaleString() : ''}</span>
                            </div>
                            <div style="white-space: pre-wrap;">${escapeHtml(item.message_body)}</div>
                            ${item.ai_strategy ? `
                                <div class="ai-reasoning-card" style="margin-top: 0.5rem;">
                                    <strong>AI Negotiation Strategy:</strong> ${escapeHtml(item.ai_strategy)}
                                </div>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>

            <div style="border-top: 1px solid var(--border-color); padding-top: 1rem;">
                <label style="font-size: 0.8rem; font-weight: 700; color: var(--text-secondary);">Simulate / Send Client Message for this Lead:</label>
                <div style="display: flex; gap: 0.5rem; margin-top: 0.4rem;">
                    <input type="text" id="modalSimInput" class="text-input" style="flex: 1;" placeholder="e.g. Can you do $400? or Send me the invoice link">
                    <button class="btn btn-primary" onclick="sendModalSimReply(${lead.id})">Send</button>
                </div>
            </div>
        `;

        document.getElementById('leadModal').classList.add('active');
    } catch (e) {
        console.error('Open lead error:', e);
    }
}

async function manualContactLead(leadId) {
    try {
        const res = await fetch(`/api/leads/${leadId}/contact`, { method: 'POST' });
        if (res.ok) {
            openLeadModal(leadId);
            loadStats();
            loadLeads();
        }
    } catch (e) {
        console.error('Contact error:', e);
    }
}

async function sendModalSimReply(leadId) {
    const input = document.getElementById('modalSimInput');
    const msg = input.value.trim();
    if (!msg) return;

    input.value = '';
    try {
        const res = await fetch(`/api/leads/${leadId}/simulate_reply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_message: msg })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.is_deal_closed) {
                playNotificationSound('deal');
            }
            openLeadModal(leadId);
            loadStats();
            loadLeads();
            loadDeals();
        }
    } catch (e) {
        console.error('Sim reply error:', e);
    }
}

// SIMULATOR PLAYGROUND
function updateSimulatorDropdown(leads) {
    const select = document.getElementById('simLeadSelect');
    if (!select) return;

    const currentVal = select.value;
    select.innerHTML = '<option value="">Select a target lead...</option>' + 
        leads.map(l => `<option value="${l.id}">${escapeHtml(l.business_name || l.title)} ($${Math.round(l.target_price)})</option>`).join('');

    if (currentVal) select.value = currentVal;
    else if (leads.length > 0 && !activeSimulatorLeadId) {
        select.value = leads[0].id;
        selectSimulatorLead(leads[0].id);
    }
}

function selectSimulatorLead(leadId) {
    activeSimulatorLeadId = leadId;
    const lead = currentLeads.find(l => l.id == leadId);
    if (!lead) return;

    document.getElementById('simLeadTitle').textContent = lead.business_name || lead.title;
    document.getElementById('simLeadPackage').textContent = `Package: ${(lead.recommended_package || 'starter_landing_page').replace(/_/g, ' ').toUpperCase()} (Standard: $${Math.round(lead.target_price)})`;
    document.getElementById('simLeadFloor').textContent = `Price Floor: None ($0 - Accept Any Client Budget)`;

    const chatContainer = document.getElementById('simChatMessages');
    chatContainer.innerHTML = `
        <div class="chat-bubble ai">
            <div class="bubble-header">🤖 OmniLead Closer Brain</div>
            <div class="bubble-text">
                Targeting <strong>${escapeHtml(lead.business_name)}</strong>.<br>
                Service: <em>${escapeHtml((lead.recommended_package || '').replace(/_/g, ' '))}</em>. Initial Quote: $${Math.round(lead.target_price)}.<br>
                Try asking a timeline question, requesting past work, or offering a lower price to test negotiation!
            </div>
        </div>
    `;
}

async function sendSimulatorMessage(text) {
    if (!activeSimulatorLeadId) {
        alert('Please select a lead first.');
        return;
    }

    const chatContainer = document.getElementById('simChatMessages');

    // Add Client Bubble
    const clientBubble = document.createElement('div');
    clientBubble.className = 'chat-bubble client';
    clientBubble.innerHTML = `
        <div class="bubble-header">👤 Client Prospect</div>
        <div class="bubble-text">${escapeHtml(text)}</div>
    `;
    chatContainer.appendChild(clientBubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    try {
        const res = await fetch(`/api/leads/${activeSimulatorLeadId}/simulate_reply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_message: text })
        });
        if (res.ok) {
            const data = await res.json();
            
            const aiBubble = document.createElement('div');
            aiBubble.className = 'chat-bubble ai';
            aiBubble.innerHTML = `
                <div class="bubble-header">🤖 OmniLead Closer Brain</div>
                <div class="bubble-text" style="white-space: pre-wrap;">${escapeHtml(data.ai_response)}</div>
                <div class="ai-reasoning-card" style="margin-top: 0.6rem; font-size: 0.75rem;">
                    <strong>AI Strategy:</strong> ${escapeHtml(data.ai_strategy)}<br>
                    <strong>Price Offered:</strong> $${Math.round(data.proposed_price)}
                    ${data.is_deal_closed ? '<br><span style="color: #34d399; font-weight: 700;">🎉 DEAL CLOSED & WON!</span>' : ''}
                </div>
            `;
            chatContainer.appendChild(aiBubble);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            if (data.is_deal_closed) {
                playNotificationSound('deal');
            }
            loadStats();
            loadDeals();
            loadLeads();
        }
    } catch (e) {
        console.error('Sim error:', e);
    }
}

// SETTINGS & CONFIGURATION
async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById('setAutonomous').checked = data.autonomous_mode;
        document.getElementById('setMinScore').value = data.min_lead_score;
        document.getElementById('setBusinessName').value = data.business_name || '';
        document.getElementById('setBusinessEmail').value = data.business_email || '';
        document.getElementById('setBusinessWebsite').value = data.business_website || '';
        document.getElementById('setSmtpHost').value = data.smtp_host || '';
        document.getElementById('setSmtpUser').value = data.smtp_user || '';
        document.getElementById('setStripeLink').value = data.stripe_payment_link || '';
        document.getElementById('setPaypalLink').value = data.paypal_link || '';
        document.getElementById('setDiscordUrl').value = data.discord_webhook_url || '';
        document.getElementById('setTgToken').value = data.telegram_bot_token || '';
        document.getElementById('setTgChatId').value = data.telegram_chat_id || '';
    } catch (e) {
        console.error('Settings error:', e);
    }
}

async function saveSettings() {
    const payload = {
        autonomous_mode: document.getElementById('setAutonomous').checked,
        min_lead_score: parseInt(document.getElementById('setMinScore').value) || 70,
        business_name: document.getElementById('setBusinessName').value,
        business_email: document.getElementById('setBusinessEmail').value,
        business_website: document.getElementById('setBusinessWebsite').value,
        smtp_host: document.getElementById('setSmtpHost').value,
        smtp_port: parseInt(document.getElementById('setSmtpPort').value) || 587,
        smtp_user: document.getElementById('setSmtpUser').value,
        smtp_password: document.getElementById('setSmtpPassword').value || undefined,
        stripe_payment_link: document.getElementById('setStripeLink').value,
        paypal_link: document.getElementById('setPaypalLink').value,
        discord_webhook_url: document.getElementById('setDiscordUrl').value || undefined,
        telegram_bot_token: document.getElementById('setTgToken').value || undefined,
        telegram_chat_id: document.getElementById('setTgChatId').value || undefined,
        gemini_api_key: document.getElementById('setGeminiKey').value || undefined,
    };

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            document.getElementById('settingsModal').classList.remove('active');
            appendLogEntry({ level: 'SUCCESS', category: 'SYSTEM', message: 'Agent configuration successfully updated.' });
        }
    } catch (e) {
        console.error('Save settings error:', e);
    }
}

// INSTANT SCAN TRIGGER
async function triggerScan() {
    const btn = document.getElementById('btnScanNow');
    btn.disabled = true;
    btn.innerHTML = '<span>⏳ Scanning...</span>';

    try {
        await fetch('/api/scan_now', { method: 'POST' });
        appendLogEntry({ level: 'INFO', category: 'HUNTER', message: 'Instant lead hunt triggered across channels...' });
    } catch (e) {
        console.error('Scan trigger error:', e);
    } finally {
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = '<span class="btn-icon">🔍</span><span>Scan Now</span>';
            loadStats();
            loadLeads();
        }, 3000);
    }
}

// Helper: HTML Escaping
function escapeHtml(str) {
    if (!str) return '';
    return str.toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// EVENT LISTENERS INITIALIZATION
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    loadStats();
    loadLeads();
    loadDeals();
    loadSettings();

    // Scan Now
    document.getElementById('btnScanNow')?.addEventListener('click', triggerScan);

    // Filters
    document.getElementById('filterStatus')?.addEventListener('change', loadLeads);
    document.getElementById('filterSource')?.addEventListener('change', loadLeads);
    document.getElementById('searchInput')?.addEventListener('input', (e) => renderLeads(currentLeads, e.target.value.toLowerCase()));

    // Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const tabId = btn.getAttribute('data-tab');
            document.getElementById(`tab-${tabId}`)?.classList.add('active');
        });
    });

    // Modals
    document.getElementById('btnOpenSettings')?.addEventListener('click', () => {
        loadSettings();
        document.getElementById('settingsModal').classList.add('active');
    });
    document.getElementById('btnCloseSettingsModal')?.addEventListener('click', () => {
        document.getElementById('settingsModal').classList.remove('active');
    });
    document.getElementById('btnCancelSettings')?.addEventListener('click', () => {
        document.getElementById('settingsModal').classList.remove('active');
    });
    document.getElementById('btnSaveSettings')?.addEventListener('click', saveSettings);

    // Test Telegram Ping
    document.getElementById('btnTestTelegram')?.addEventListener('click', async () => {
        const btn = document.getElementById('btnTestTelegram');
        const statusEl = document.getElementById('tgTestStatus');
        const token = document.getElementById('setTgToken').value.replace(/\s+/g, '');
        const chatId = document.getElementById('setTgChatId').value.replace(/\s+/g, '');

        if (!token || !chatId) {
            statusEl.textContent = '⚠️ Enter Bot Token & Chat ID first.';
            statusEl.style.color = '#fbbf24';
            return;
        }

        btn.disabled = true;
        statusEl.textContent = 'Sending ping...';
        statusEl.style.color = '#38bdf8';

        try {
            const res = await fetch('/api/settings/test_telegram', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ telegram_bot_token: token, telegram_chat_id: chatId })
            });
            const data = await res.json();
            if (data.success) {
                statusEl.textContent = '✅ Message delivered to your Telegram!';
                statusEl.style.color = '#34d399';
                playNotificationSound('deal');
            } else {
                statusEl.textContent = `❌ ${data.error || 'Failed to send'}`;
                statusEl.style.color = '#f87171';
            }
        } catch (e) {
            statusEl.textContent = '❌ Network error';
            statusEl.style.color = '#f87171';
        } finally {
            btn.disabled = false;
        }
    });

    // Test SMTP Email Ping
    document.getElementById('btnTestSmtp')?.addEventListener('click', async () => {
        const btn = document.getElementById('btnTestSmtp');
        const statusEl = document.getElementById('smtpTestStatus');
        const host = document.getElementById('setSmtpHost').value.trim();
        const port = parseInt(document.getElementById('setSmtpPort').value) || 587;
        const user = document.getElementById('setSmtpUser').value.trim();
        const password = document.getElementById('setSmtpPassword').value.trim();

        if (!host || !user || !password) {
            statusEl.textContent = '⚠️ Enter Host, Email, and App Password.';
            statusEl.style.color = '#fbbf24';
            return;
        }

        btn.disabled = true;
        statusEl.textContent = 'Connecting to Zoho & sending test email...';
        statusEl.style.color = '#38bdf8';

        try {
            const res = await fetch('/api/settings/test_smtp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ smtp_host: host, smtp_port: port, smtp_user: user, smtp_password: password })
            });
            const data = await res.json();
            if (data.success) {
                statusEl.textContent = '✅ Email sent! Check your inbox.';
                statusEl.style.color = '#34d399';
                playNotificationSound('deal');
            } else {
                statusEl.textContent = `❌ ${data.error || 'Failed'}`;
                statusEl.style.color = '#f87171';
            }
        } catch (e) {
            statusEl.textContent = '❌ Network error';
            statusEl.style.color = '#f87171';
        } finally {
            btn.disabled = false;
        }
    });

    document.getElementById('btnCloseLeadModal')?.addEventListener('click', () => {
        document.getElementById('leadModal').classList.remove('active');
    });

    // Add Lead
    document.getElementById('btnAddLead')?.addEventListener('click', () => {
        document.getElementById('addLeadModal').classList.add('active');
    });
    document.getElementById('btnCloseAddLeadModal')?.addEventListener('click', () => {
        document.getElementById('addLeadModal').classList.remove('active');
    });
    document.getElementById('btnCancelAddLead')?.addEventListener('click', () => {
        document.getElementById('addLeadModal').classList.remove('active');
    });
    document.getElementById('btnSubmitAddLead')?.addEventListener('click', async () => {
        const payload = {
            title: document.getElementById('newLeadBusiness').value,
            business_name: document.getElementById('newLeadBusiness').value,
            contact_name: document.getElementById('newLeadContact').value,
            contact_email: document.getElementById('newLeadEmail').value,
            niche: document.getElementById('newLeadNiche').value,
            recommended_package: document.getElementById('newLeadPackage').value,
            audit_summary: document.getElementById('newLeadAudit').value,
        };
        try {
            const res = await fetch('/api/leads', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                document.getElementById('addLeadModal').classList.remove('active');
                loadStats();
                loadLeads();
            }
        } catch (e) {
            console.error('Add lead error:', e);
        }
    });

    // Simulator Dropdown
    document.getElementById('simLeadSelect')?.addEventListener('change', (e) => {
        if (e.target.value) selectSimulatorLead(e.target.value);
    });

    // Quick Prompts in Simulator
    document.querySelectorAll('.btn-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const msg = chip.getAttribute('data-msg');
            sendSimulatorMessage(msg);
        });
    });

    // Simulator Send Button & Enter Key
    const sendSim = () => {
        const input = document.getElementById('simInputMessage');
        const msg = input.value.trim();
        if (msg) {
            input.value = '';
            sendSimulatorMessage(msg);
        }
    };
    document.getElementById('btnSendSimMessage')?.addEventListener('click', sendSim);
    document.getElementById('simInputMessage')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendSim();
    });

    // Dedicated Telegram Modal
    document.getElementById('btnOpenTelegram')?.addEventListener('click', () => {
        document.getElementById('tgModalToken').value = document.getElementById('setTgToken').value;
        document.getElementById('tgModalChatId').value = document.getElementById('setTgChatId').value;
        document.getElementById('tgModalStatus').textContent = '';
        document.getElementById('telegramModal').classList.add('active');
    });

    document.getElementById('btnCloseTelegramModal')?.addEventListener('click', () => {
        document.getElementById('telegramModal').classList.remove('active');
    });

    document.getElementById('btnCancelTelegramModal')?.addEventListener('click', () => {
        document.getElementById('telegramModal').classList.remove('active');
    });

    document.getElementById('btnModalTestTelegram')?.addEventListener('click', async () => {
        const btn = document.getElementById('btnModalTestTelegram');
        const statusEl = document.getElementById('tgModalStatus');
        const token = document.getElementById('tgModalToken').value.replace(/\s+/g, '');
        const chatId = document.getElementById('tgModalChatId').value.replace(/\s+/g, '');

        if (!token || !chatId) {
            statusEl.textContent = '⚠️ Enter Bot Token & Chat ID first.';
            statusEl.style.color = '#fbbf24';
            return;
        }

        btn.disabled = true;
        statusEl.textContent = 'Sending ping to your Telegram...';
        statusEl.style.color = '#38bdf8';

        try {
            const res = await fetch('/api/settings/test_telegram', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ telegram_bot_token: token, telegram_chat_id: chatId })
            });
            const data = await res.json();
            if (data.success) {
                statusEl.textContent = '✅ Message delivered to your Telegram!';
                statusEl.style.color = '#34d399';
                playNotificationSound('deal');
            } else {
                statusEl.textContent = `❌ ${data.error || 'Failed to send'}`;
                statusEl.style.color = '#f87171';
            }
        } catch (e) {
            statusEl.textContent = '❌ Network error';
            statusEl.style.color = '#f87171';
        } finally {
            btn.disabled = false;
        }
    });

    document.getElementById('btnSaveTelegramModal')?.addEventListener('click', async () => {
        const token = document.getElementById('tgModalToken').value.trim();
        const chatId = document.getElementById('tgModalChatId').value.trim();

        document.getElementById('setTgToken').value = token;
        document.getElementById('setTgChatId').value = chatId;

        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ telegram_bot_token: token, telegram_chat_id: chatId })
            });
            if (res.ok) {
                document.getElementById('telegramModal').classList.remove('active');
                appendLogEntry({ level: 'SUCCESS', category: 'SYSTEM', message: 'Telegram bot settings saved and active.' });
            }
        } catch (e) {
            console.error('Save error:', e);
        }
    });

    // Dedicated Zoho Email Modal
    document.getElementById('btnOpenEmail')?.addEventListener('click', () => {
        document.getElementById('emailModalHost').value = document.getElementById('setSmtpHost').value || 'smtp.zoho.com';
        document.getElementById('emailModalPort').value = document.getElementById('setSmtpPort').value || 587;
        document.getElementById('emailModalUser').value = document.getElementById('setSmtpUser').value || '';
        document.getElementById('emailModalPassword').value = document.getElementById('setSmtpPassword').value || '';
        document.getElementById('emailModalStatus').textContent = '';
        document.getElementById('emailModal').classList.add('active');
    });

    document.getElementById('btnCloseEmailModal')?.addEventListener('click', () => {
        document.getElementById('emailModal').classList.remove('active');
    });

    document.getElementById('btnCancelEmailModal')?.addEventListener('click', () => {
        document.getElementById('emailModal').classList.remove('active');
    });

    document.getElementById('btnModalTestEmail')?.addEventListener('click', async () => {
        const btn = document.getElementById('btnModalTestEmail');
        const statusEl = document.getElementById('emailModalStatus');
        const host = document.getElementById('emailModalHost').value.trim();
        const port = parseInt(document.getElementById('emailModalPort').value) || 587;
        const user = document.getElementById('emailModalUser').value.trim();
        const password = document.getElementById('emailModalPassword').value.trim();

        if (!host || !user || !password) {
            statusEl.textContent = '⚠️ Enter Host, Zoho Email, and App Password.';
            statusEl.style.color = '#fbbf24';
            return;
        }

        btn.disabled = true;
        statusEl.textContent = 'Connecting to Zoho & sending test email to your inbox...';
        statusEl.style.color = '#38bdf8';

        try {
            const res = await fetch('/api/settings/test_smtp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ smtp_host: host, smtp_port: port, smtp_user: user, smtp_password: password })
            });
            const data = await res.json();
            if (data.success) {
                statusEl.textContent = '✅ ' + data.message;
                statusEl.style.color = '#34d399';
                playNotificationSound('deal');
            } else {
                statusEl.textContent = `❌ ${data.error || 'Connection failed'}`;
                statusEl.style.color = '#f87171';
            }
        } catch (e) {
            statusEl.textContent = '❌ Network error';
            statusEl.style.color = '#f87171';
        } finally {
            btn.disabled = false;
        }
    });

    document.getElementById('btnSaveEmailModal')?.addEventListener('click', async () => {
        const host = document.getElementById('emailModalHost').value.trim();
        const port = parseInt(document.getElementById('emailModalPort').value) || 587;
        const user = document.getElementById('emailModalUser').value.trim();
        const password = document.getElementById('emailModalPassword').value.trim();

        document.getElementById('setSmtpHost').value = host;
        document.getElementById('setSmtpPort').value = port;
        document.getElementById('setSmtpUser').value = user;
        document.getElementById('setSmtpPassword').value = password;

        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    smtp_host: host,
                    smtp_port: port,
                    smtp_user: user,
                    smtp_password: password,
                    business_email: user
                })
            });
            if (res.ok) {
                document.getElementById('emailModal').classList.remove('active');
                appendLogEntry({ level: 'SUCCESS', category: 'SYSTEM', message: `Zoho Email (${user}) saved and live outreach authorized.` });
            }
        } catch (e) {
            console.error('Save error:', e);
        }
    });

    // Dedicated PayPal Modal
    document.getElementById('btnOpenPaypal')?.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/settings');
            const data = await res.json();
            if (data.paypal_link) {
                document.getElementById('paypalModalInput').value = data.paypal_link;
                document.getElementById('setPaypalLink').value = data.paypal_link;
            }
        } catch (e) {
            console.error('Error fetching settings for PayPal modal:', e);
        }
        if (!document.getElementById('paypalModalInput').value) {
            document.getElementById('paypalModalInput').value = document.getElementById('setPaypalLink').value || '';
        }
        document.getElementById('paypalModalStatus').textContent = '';
        document.getElementById('paypalModal').classList.add('active');
    });

    document.getElementById('btnClosePaypalModal')?.addEventListener('click', () => {
        document.getElementById('paypalModal').classList.remove('active');
    });

    document.getElementById('btnCancelPaypalModal')?.addEventListener('click', () => {
        document.getElementById('paypalModal').classList.remove('active');
    });

    document.getElementById('btnTestOpenPaypal')?.addEventListener('click', () => {
        const rawLink = document.getElementById('paypalModalInput').value.trim();
        const amount = document.getElementById('paypalTestAmount').value.trim() || '150';
        const statusEl = document.getElementById('paypalModalStatus');

        if (!rawLink) {
            statusEl.textContent = '⚠️ Please enter your PayPal.me link or username first.';
            statusEl.style.color = '#fbbf24';
            return;
        }

        let cleanLink = rawLink.replace(/\s+/g, '').replace('@', '');
        if (!cleanLink.startsWith('http')) {
            cleanLink = `https://paypal.me/${cleanLink}`;
        }
        cleanLink = cleanLink.replace(/\/+$/, '');
        const testPayUrl = `${cleanLink}/${amount}USD`;

        statusEl.innerHTML = `🚀 Opening PayPal Checkout: <a href="${testPayUrl}" target="_blank" style="color: #38bdf8; font-weight: 700;">${testPayUrl}</a>`;
        statusEl.style.color = '#34d399';
        playNotificationSound('deal');

        // Open in new tab
        window.open(testPayUrl, '_blank');
    });

    document.getElementById('btnSavePaypalModal')?.addEventListener('click', async () => {
        const rawLink = document.getElementById('paypalModalInput').value.trim();
        let cleanLink = rawLink.replace(/\s+/g, '').replace('@', '');
        if (cleanLink && !cleanLink.startsWith('http')) {
            cleanLink = `https://paypal.me/${cleanLink}`;
        }

        document.getElementById('setPaypalLink').value = cleanLink;

        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ paypal_link: cleanLink })
            });
            if (res.ok) {
                document.getElementById('paypalModal').classList.remove('active');
                appendLogEntry({ level: 'SUCCESS', category: 'SYSTEM', message: `PayPal payment link (${cleanLink}) saved as primary checkout.` });
            }
        } catch (e) {
            console.error('Save error:', e);
        }
    });

    // Clear Terminal Logs
    document.getElementById('btnClearLogs')?.addEventListener('click', () => {
        const terminal = document.getElementById('terminalLogs');
        if (terminal) terminal.innerHTML = '';
    });
});
