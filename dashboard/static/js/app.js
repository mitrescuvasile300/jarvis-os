/* ═══════════════════════════════════════════════════════════
   Jarvis OS — Mission Control JavaScript
   ═══════════════════════════════════════════════════════════ */

const API_BASE = window.location.origin;

// ── State ──────────────────────────────────────────────────

const state = {
  agents: [],
  settings: {
    apiKeys: {},
    defaultModel: 'gpt-4o',
  },
  currentPage: 'dashboard',
  chatAgent: null,
  chatHistories: {},
  logs: [],
};

// Load from localStorage
function loadState() {
  try {
    const saved = localStorage.getItem('jarvis_state');
    if (saved) {
      const parsed = JSON.parse(saved);
      Object.assign(state, parsed);
    }
  } catch (e) { console.warn('Failed to load state:', e); }
}

function saveState() {
  try {
    localStorage.setItem('jarvis_state', JSON.stringify(state));
  } catch (e) { console.warn('Failed to save state:', e); }
}

// ── Navigation ──────────────────────────────────────────────

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    const page = item.dataset.page;
    navigateTo(page);
  });
});

function navigateTo(page) {
  // Hide all pages
  document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
  // Show target
  const target = document.getElementById(`page-${page}`);
  if (target) {
    target.classList.remove('hidden');
    target.querySelector('.page-content')?.classList.add('fade-in');
  }

  // Update nav
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelector(`.nav-item[data-page="${page}"]`)?.classList.add('active');

  state.currentPage = page;

  // Refresh page data
  if (page === 'dashboard') refreshDashboard();
  if (page === 'agents') refreshAgentsGrid();
  if (page === 'chat') refreshChatSelector();
  if (page === 'logs') refreshLogs();
}

// ── Tabs ────────────────────────────────────────────────────

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const tabId = tab.dataset.tab;
    const parent = tab.closest('.page-content') || tab.parentElement.parentElement;

    // Update tab buttons
    tab.parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');

    // Show/hide tab content
    parent.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    const content = parent.querySelector(`#tab-${tabId}`);
    if (content) content.classList.remove('hidden');
  });
});

// ── Dashboard ──────────────────────────────────────────────

function refreshDashboard() {
  const activeCount = state.agents.filter(a => a.status === 'running').length;
  document.getElementById('stat-active').textContent = activeCount;
  document.getElementById('stat-active-note').textContent =
    activeCount > 0 ? `${state.agents.length} total agents` : 'No agents yet';

  // Count memory entries
  let memoryCount = 0;
  Object.values(state.chatHistories).forEach(h => memoryCount += h.length);
  document.getElementById('stat-memory').textContent = memoryCount;

  // Provider status
  const providers = Object.keys(state.settings.apiKeys).filter(k => state.settings.apiKeys[k]);
  if (providers.length > 0) {
    document.getElementById('stat-provider').textContent = providers[0];
    document.getElementById('stat-model-note').textContent = `${providers.length} provider(s) configured`;
  }

  // Agent count badge
  document.getElementById('agent-count-badge').textContent = state.agents.length;

  // Agent list
  const container = document.getElementById('dashboard-agents-list');
  if (state.agents.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🤖</div>
        <h3>No agents yet</h3>
        <p>Create your first AI agent to get started.</p>
        <button class="btn btn-primary" onclick="openNewAgentModal()">➕ Create Agent</button>
      </div>`;
    return;
  }

  container.innerHTML = '<div class="grid grid-3">' + state.agents.map(a => agentCardHTML(a)).join('') + '</div>';
}

function agentCardHTML(agent) {
  const icons = {
    trading: '💹', research: '🔬', content: '✍️', 'social-media': '📱',
    support: '🎧', devops: '🛠️', 'personal-assistant': '🧑‍💼', custom: '⚡',
  };
  const icon = icons[agent.template] || '🤖';
  const avatarClass = ['trading', 'research', 'content', 'devops', 'support'].includes(agent.template) ? agent.template : 'default';

  return `
    <div class="agent-card" onclick="openAgentChat('${agent.id}')">
      <div class="agent-card-header">
        <div>
          <div class="agent-name">${agent.name}</div>
          <div class="agent-template">${agent.template} • ${agent.model}</div>
        </div>
        <div class="agent-avatar ${avatarClass}">${icon}</div>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center">
        <span class="status status-${agent.status}">
          <span class="status-dot"></span>
          ${agent.status}
        </span>
        <div style="display:flex; gap:6px">
          <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); toggleAgent('${agent.id}')" title="${agent.status === 'running' ? 'Stop' : 'Start'}">
            ${agent.status === 'running' ? '⏸' : '▶️'}
          </button>
          <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); deleteAgent('${agent.id}')" title="Delete">🗑</button>
        </div>
      </div>
      <div class="agent-meta">
        <span>🔧 ${agent.tools?.length || 0} tools</span>
        <span>🧠 ${(state.chatHistories[agent.id] || []).length} msgs</span>
        <span>⏱ ${timeSince(agent.createdAt)}</span>
      </div>
    </div>`;
}

// ── Agents Grid ─────────────────────────────────────────────

function refreshAgentsGrid() {
  const grid = document.getElementById('agents-grid');

  if (state.agents.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-icon">🤖</div>
        <h3>No agents yet</h3>
        <p>Create your first AI agent to get started.</p>
        <button class="btn btn-primary" onclick="openNewAgentModal()">➕ Create Agent</button>
      </div>`;
    return;
  }

  grid.innerHTML = state.agents.map(a => agentCardHTML(a)).join('');
}

// ── New Agent Modal ─────────────────────────────────────────

let selectedTemplate = 'trading';

document.querySelectorAll('.template-option').forEach(opt => {
  opt.addEventListener('click', () => {
    document.querySelectorAll('.template-option').forEach(o => o.classList.remove('selected'));
    opt.classList.add('selected');
    selectedTemplate = opt.dataset.template;

    // Auto-fill personality
    const personalities = {
      trading: 'Disciplined quantitative trader. Data-driven, risk-aware, never emotional.',
      research: 'Thorough researcher. Verifies facts from multiple sources. Clear and concise.',
      content: 'Creative content strategist. Engaging, authentic, adapts tone per platform.',
      'social-media': 'Social media expert. Grows followers organically. Never spammy.',
      support: 'Patient, empathetic support agent. Always helpful, escalates complex issues.',
      devops: 'Calm under pressure SRE. Follows runbooks precisely. Documents everything.',
      'personal-assistant': 'Proactive personal assistant. Anticipates needs, stays organized.',
      custom: '',
    };
    document.getElementById('new-agent-personality').placeholder = personalities[selectedTemplate] || 'Describe personality...';
  });
});

function openNewAgentModal() {
  document.getElementById('new-agent-modal').classList.add('active');
  document.getElementById('new-agent-name').focus();
}

function closeNewAgentModal() {
  document.getElementById('new-agent-modal').classList.remove('active');
}

function createAgent() {
  const name = document.getElementById('new-agent-name').value.trim();
  if (!name) {
    showToast('Please enter an agent name', 'error');
    return;
  }

  // Check for duplicate name
  if (state.agents.find(a => a.name === name)) {
    showToast('Agent with this name already exists', 'error');
    return;
  }

  const model = document.getElementById('new-agent-model').value;
  const personality = document.getElementById('new-agent-personality').value.trim();

  // Determine provider from model
  let provider = 'openai';
  if (model.startsWith('claude')) provider = 'anthropic';
  else if (['llama3', 'mistral', 'codellama', 'phi3'].includes(model)) provider = 'ollama';
  else if (model.startsWith('gemini')) provider = 'google';

  // Check if API key exists for this provider
  if (provider !== 'ollama' && !state.settings.apiKeys[provider]) {
    showToast(`⚠️ No API key for ${provider}. Go to Settings → API Keys first.`, 'error');
    return;
  }

  const templateTools = {
    trading: ['web_search', 'http_request', 'run_code', 'read_file', 'write_file', 'shell_command'],
    research: ['web_search', 'http_request', 'read_file', 'write_file', 'run_code'],
    content: ['web_search', 'http_request', 'read_file', 'write_file'],
    'social-media': ['web_search', 'http_request', 'read_file', 'write_file'],
    support: ['web_search', 'read_file', 'search_files', 'http_request'],
    devops: ['shell_command', 'http_request', 'read_file', 'write_file', 'run_code', 'search_files'],
    'personal-assistant': ['web_search', 'http_request', 'read_file', 'write_file', 'run_code'],
    custom: ['web_search', 'read_file', 'write_file'],
  };

  const agent = {
    id: generateId(),
    name,
    template: selectedTemplate,
    model,
    provider,
    personality: personality || null,
    tools: templateTools[selectedTemplate] || [],
    status: 'running',
    createdAt: Date.now(),
  };

  state.agents.push(agent);
  state.chatHistories[agent.id] = [];
  saveState();

  addLog('success', `Agent "${name}" created (${selectedTemplate} / ${model})`);

  closeNewAgentModal();
  document.getElementById('new-agent-name').value = '';
  document.getElementById('new-agent-personality').value = '';

  showToast(`🤖 Agent "${name}" created!`, 'success');
  refreshDashboard();
  navigateTo('dashboard');
}

// ── Agent Actions ───────────────────────────────────────────

function toggleAgent(id) {
  const agent = state.agents.find(a => a.id === id);
  if (!agent) return;

  agent.status = agent.status === 'running' ? 'stopped' : 'running';
  saveState();

  addLog('info', `Agent "${agent.name}" ${agent.status}`);
  showToast(`Agent "${agent.name}" ${agent.status}`, 'info');

  refreshDashboard();
  refreshAgentsGrid();
}

function deleteAgent(id) {
  const agent = state.agents.find(a => a.id === id);
  if (!agent) return;

  if (!confirm(`Delete agent "${agent.name}"? This cannot be undone.`)) return;

  state.agents = state.agents.filter(a => a.id !== id);
  delete state.chatHistories[id];
  saveState();

  addLog('warn', `Agent "${agent.name}" deleted`);
  showToast(`Agent "${agent.name}" deleted`, 'info');

  refreshDashboard();
  refreshAgentsGrid();
}

function openAgentChat(id) {
  state.chatAgent = id;
  saveState();
  navigateTo('chat');
  switchChatAgent(id);
}

// ── Chat ────────────────────────────────────────────────────

function refreshChatSelector() {
  const select = document.getElementById('chat-agent-select');
  select.innerHTML = '<option value="">Select agent...</option>';
  state.agents.forEach(a => {
    const opt = document.createElement('option');
    opt.value = a.id;
    opt.textContent = `${a.name} (${a.template})`;
    if (state.chatAgent === a.id) opt.selected = true;
    select.appendChild(opt);
  });

  if (state.chatAgent) switchChatAgent(state.chatAgent);
}

function switchChatAgent(id) {
  const agent = state.agents.find(a => a.id === id);
  if (!agent) {
    document.getElementById('chat-agent-name').textContent = 'Select an agent';
    document.getElementById('chat-input').disabled = true;
    document.getElementById('chat-send').disabled = true;
    return;
  }

  state.chatAgent = id;
  saveState();

  document.getElementById('chat-agent-name').textContent = `${agent.name}`;
  document.getElementById('chat-input').disabled = false;
  document.getElementById('chat-send').disabled = false;
  document.getElementById('chat-agent-select').value = id;

  renderChatMessages(id);
}

function renderChatMessages(agentId) {
  const container = document.getElementById('chat-messages');
  const messages = state.chatHistories[agentId] || [];

  if (messages.length === 0) {
    const agent = state.agents.find(a => a.id === agentId);
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">💬</div>
        <h3>Chat with ${agent?.name || 'Agent'}</h3>
        <p>Type a message below to start the conversation.</p>
      </div>`;
    return;
  }

  container.innerHTML = messages.map(m => {
    const time = new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    let html = `<div class="chat-message ${m.role}">`;
    html += `<div>${formatMessage(m.content)}</div>`;
    if (m.tools_used?.length) {
      html += `<div class="msg-tools">🔧 ${m.tools_used.join(', ')}</div>`;
    }
    html += `<div class="msg-meta">${time}</div>`;
    html += `</div>`;
    return html;
  }).join('');

  container.scrollTop = container.scrollHeight;
}

function formatMessage(text) {
  // Basic markdown
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code style="background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:3px">$1</code>')
    .replace(/\n/g, '<br>');
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message || !state.chatAgent) return;

  const agent = state.agents.find(a => a.id === state.chatAgent);
  if (!agent) return;

  // Add user message
  if (!state.chatHistories[agent.id]) state.chatHistories[agent.id] = [];
  state.chatHistories[agent.id].push({
    role: 'user',
    content: message,
    timestamp: Date.now(),
  });

  input.value = '';
  renderChatMessages(agent.id);

  // Simulate typing (in production, this calls the actual API)
  const sendBtn = document.getElementById('chat-send');
  sendBtn.disabled = true;
  input.disabled = true;

  try {
    // Try real API call first
    let response;
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          agent_id: agent.id,
          conversation_id: `chat_${agent.id}`,
        }),
      });
      if (res.ok) {
        response = await res.json();
      }
    } catch (e) {
      // API not available — simulate response
    }

    if (!response) {
      // Simulated response for demo/offline mode
      await sleep(800 + Math.random() * 1200);
      response = simulateResponse(agent, message);
    }

    state.chatHistories[agent.id].push({
      role: 'agent',
      content: response.text || response.message || 'I received your message.',
      tools_used: response.tools_used || [],
      timestamp: Date.now(),
    });

    saveState();
    renderChatMessages(agent.id);
    addLog('info', `[${agent.name}] Chat: "${message.substring(0, 50)}..."`);

  } catch (error) {
    showToast('Error sending message', 'error');
    console.error(error);
  } finally {
    sendBtn.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

function simulateResponse(agent, message) {
  const msg = message.toLowerCase();

  if (agent.template === 'trading') {
    if (msg.includes('portfolio') || msg.includes('check')) {
      return {
        text: `📊 **Portfolio Status**\n\nConnected wallet: Not configured yet.\n\nTo connect your wallet and start monitoring, add your RPC endpoint in the agent config.\n\nI can monitor:\n- SOL balance and token holdings\n- Open positions and P&L\n- Price alerts on significant moves\n\nSet up your wallet first, then I'll run continuous monitoring.`,
        tools_used: ['http_request'],
      };
    }
    if (msg.includes('scan') || msg.includes('market')) {
      return {
        text: `🔍 **Market Scan**\n\nScanning pump.fun for opportunities matching your filters:\n- Dev Holding ≤5%\n- Top 10 Holders ≤20%\n- Insiders ≤20%\n- Token age ≤40min\n\nNo tokens currently match all criteria. The market is quiet.\nI'll alert you when a strong candidate appears.`,
        tools_used: ['web_search', 'http_request'],
      };
    }
    return {
      text: `I'm your trading agent running the ${agent.model} model. I can:\n\n• **Check portfolio** — monitor balances and P&L\n• **Scan market** — find tokens matching the 10-point checklist\n• **Evaluate token** — run the full checklist on any token\n• **Detect rug-pulls** — analyze token safety\n\nWhat would you like me to do?`,
      tools_used: [],
    };
  }

  if (agent.template === 'research') {
    return {
      text: `🔬 I'm your research agent. I can help with:\n\n• **Daily briefings** — morning news digest on your topics\n• **Deep research** — thorough investigation of any topic\n• **Topic monitoring** — track developments over time\n\nWhat would you like me to research?`,
      tools_used: msg.includes('search') || msg.includes('research') ? ['web_search'] : [],
    };
  }

  // Generic response
  return {
    text: `I received your message: "${message}"\n\nI'm ${agent.name}, a ${agent.template} agent using ${agent.model}. I'm ready to help with tasks in my domain. What would you like me to do?`,
    tools_used: [],
  };
}

function handleChatKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

// ── Settings ────────────────────────────────────────────────

function saveApiKey(provider) {
  const inputId = `key-${provider}`;
  const input = document.getElementById(inputId);
  if (!input) return;

  const value = input.value.trim();
  if (!value && provider !== 'ollama') {
    showToast(`Please enter a key for ${provider}`, 'error');
    return;
  }

  state.settings.apiKeys[provider] = value;
  saveState();

  // Update status
  const statusEl = document.getElementById(`${provider}-status`);
  if (statusEl) {
    statusEl.textContent = '✅ Configured';
    statusEl.style.color = 'var(--green)';
  }

  addLog('success', `API key saved for ${provider}`);
  showToast(`✅ ${provider} key saved`, 'success');

  // Mask the input
  if (value.length > 8) {
    input.value = value.substring(0, 4) + '•'.repeat(value.length - 8) + value.substring(value.length - 4);
  }

  refreshDashboard();
}

function saveGeneralSettings() {
  state.settings.agentName = document.getElementById('setting-agent-name').value;
  state.settings.defaultModel = document.getElementById('setting-default-model').value;
  state.settings.port = parseInt(document.getElementById('setting-port').value) || 8080;
  state.settings.autoMemory = document.getElementById('setting-auto-memory').checked;
  saveState();
  showToast('✅ Settings saved', 'success');
}

// ── Logs ────────────────────────────────────────────────────

function addLog(level, message) {
  const now = new Date();
  const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  state.logs.unshift({ time, level, message });
  if (state.logs.length > 200) state.logs = state.logs.slice(0, 200);
  saveState();
}

function refreshLogs() {
  const viewer = document.getElementById('log-viewer');
  if (state.logs.length === 0) {
    viewer.innerHTML = '<span style="color:var(--text-muted)">No logs yet. Activity will appear here.</span>';
    return;
  }

  viewer.innerHTML = state.logs.map(log => `
    <div class="log-line">
      <span class="log-time">${log.time}</span>
      <span class="log-level-${log.level}">[${log.level.toUpperCase()}]</span>
      <span>${log.message}</span>
    </div>
  `).join('');
}

function clearLogs() {
  state.logs = [];
  saveState();
  refreshLogs();
  showToast('Logs cleared', 'info');
}

// ── Memory Search ───────────────────────────────────────────

function searchMemory() {
  const query = document.getElementById('memory-search').value.trim().toLowerCase();
  if (!query) return;

  const results = [];

  // Search chat histories
  Object.entries(state.chatHistories).forEach(([agentId, messages]) => {
    const agent = state.agents.find(a => a.id === agentId);
    messages.forEach(m => {
      if (m.content.toLowerCase().includes(query)) {
        results.push({
          agent: agent?.name || 'Unknown',
          type: m.role === 'user' ? 'conversation' : 'response',
          content: m.content,
          time: new Date(m.timestamp).toLocaleString(),
        });
      }
    });
  });

  const container = document.getElementById('memory-results');
  if (results.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted)">No results for "${query}"</p>`;
  } else {
    container.innerHTML = results.map(r => `
      <div style="padding:12px; border:1px solid var(--border); border-radius:var(--radius-sm); margin-bottom:8px">
        <div style="display:flex; justify-content:space-between; margin-bottom:4px">
          <span style="font-weight:600; font-size:0.85rem">${r.agent} — ${r.type}</span>
          <span style="color:var(--text-muted); font-size:0.75rem">${r.time}</span>
        </div>
        <div style="font-size:0.85rem; color:var(--text-secondary)">${r.content.substring(0, 200)}${r.content.length > 200 ? '...' : ''}</div>
      </div>
    `).join('');
  }
}

// ── Utilities ───────────────────────────────────────────────

function generateId() {
  return 'agent_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function timeSince(timestamp) {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100px)';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// ── Init ────────────────────────────────────────────────────

loadState();
refreshDashboard();
addLog('info', 'Mission Control loaded');

// Restore API key display
['openai', 'anthropic', 'ollama', 'google'].forEach(provider => {
  if (state.settings.apiKeys[provider]) {
    const statusEl = document.getElementById(`${provider}-status`);
    if (statusEl) {
      statusEl.textContent = '✅ Configured';
      statusEl.style.color = 'var(--green)';
    }
  }
});
