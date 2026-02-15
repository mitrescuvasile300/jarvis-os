/* ═══════════════════════════════════════════════════════════
   Jarvis OS — Mission Control v2.0
   Features: Direct Jarvis chat, Agent spawning, Group Hub
   ═══════════════════════════════════════════════════════════ */

const API_BASE = window.location.origin;
const WS_BASE = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;

// ── State ──────────────────────────────────────────────────

const state = {
  agents: [],
  settings: { apiKeys: {}, defaultModel: 'gpt-5.2' },
  currentPage: 'dashboard',
  chatAgent: null,
  jarvisHistory: [],
  chatHistories: {},
  hubHistory: [],
  logs: [],
};

function loadState() {
  try {
    const saved = localStorage.getItem('jarvis_state_v2');
    if (saved) Object.assign(state, JSON.parse(saved));
  } catch (e) { console.warn('State load failed:', e); }

  // Sync agents from server on load (server is source of truth)
  syncAgentsFromServer();
}

function saveState() {
  try {
    localStorage.setItem('jarvis_state_v2', JSON.stringify(state));
  } catch (e) {}
}

// ── Navigation ──────────────────────────────────────────────

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => navigateTo(item.dataset.page));
});

function navigateTo(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
  const target = document.getElementById(`page-${page}`);
  if (target) {
    target.classList.remove('hidden');
    target.querySelector('.page-content')?.classList.add('fade-in');
  }

  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelector(`.nav-item[data-page="${page}"]`)?.classList.add('active');

  state.currentPage = page;

  if (page === 'dashboard') refreshDashboard();
  if (page === 'agents') refreshAgentsGrid();
  if (page === 'jarvis-chat') initJarvisChat();
  if (page === 'hub') initHub();
  if (page === 'logs') refreshLogs();
  if (page === 'plugins') refreshPlugins();
}

// ── Tabs ────────────────────────────────────────────────────

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const tabId = tab.dataset.tab;
    const parent = tab.closest('.page-content') || tab.parentElement.parentElement;
    tab.parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
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
    activeCount > 0 ? `${state.agents.length} total` : 'No agents yet';

  let memoryCount = state.jarvisHistory.length;
  Object.values(state.chatHistories).forEach(h => memoryCount += h.length);
  document.getElementById('stat-memory').textContent = memoryCount;

  const providers = Object.keys(state.settings.apiKeys).filter(k => state.settings.apiKeys[k]);
  if (providers.length > 0) {
    document.getElementById('stat-provider').textContent = providers[0];
    document.getElementById('stat-model-note').textContent = `${providers.length} configured`;
  }

  document.getElementById('agent-count-badge').textContent = state.agents.length;

  const container = document.getElementById('dashboard-agents-list');
  if (state.agents.length === 0) {
    container.innerHTML = `<div style="text-align:center; padding:30px; color:var(--text-muted)">
      No agents yet. Chat with Jarvis or click Create New.
    </div>`;
  } else {
    container.innerHTML = '<div class="grid grid-3">' + state.agents.map(agentCardHTML).join('') + '</div>';
  }

  // Render sidebar agent tabs
  renderSidebarAgentTabs();

  // Fetch live status from server
  fetchStatus();
}

async function fetchStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById('stat-provider').textContent = data.agent?.provider || 'Not set';
      document.getElementById('stat-model-note').textContent = data.agent?.model || '';
    }
  } catch (e) {}
}

function agentCardHTML(agent) {
  const icons = { trading: '💹', research: '🔬', content: '✍️', devops: '🛠️', support: '🎧', 'personal-assistant': '🧑‍💼', custom: '⚡' };
  const icon = icons[agent.template] || '🤖';
  return `
    <div class="agent-card" onclick="openAgentChat('${agent.id}')">
      <div class="agent-card-header">
        <div>
          <div class="agent-name">${agent.name}</div>
          <div class="agent-template">${agent.template} • ${agent.model}</div>
        </div>
        <div class="agent-avatar ${agent.template}">${icon}</div>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center">
        <span class="status status-${agent.status}">
          <span class="status-dot"></span> ${agent.status}
        </span>
        <div style="display:flex; gap:6px">
          <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); toggleAgent('${agent.id}')">${agent.status === 'running' ? '⏸' : '▶️'}</button>
          <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); deleteAgent('${agent.id}')">🗑</button>
        </div>
      </div>
      <div class="agent-meta">
        <span>🔧 ${agent.tools?.length || 0} tools</span>
        <span>💬 ${(state.chatHistories[agent.id] || []).length} msgs</span>
        <span>⏱ ${timeSince(agent.createdAt)}</span>
      </div>
    </div>`;
}

// ── Agents Grid ─────────────────────────────────────────────

function refreshAgentsGrid() {
  const grid = document.getElementById('agents-grid');
  if (state.agents.length === 0) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
      <div class="empty-icon">🤖</div>
      <h3>No agents yet</h3>
      <p>Create one manually or ask Jarvis: <em>"create a research agent"</em></p>
      <button class="btn btn-primary" onclick="openNewAgentModal()">➕ Create Agent</button>
    </div>`;
  } else {
    grid.innerHTML = state.agents.map(agentCardHTML).join('');
  }
}

// ── Sidebar Agent Tabs ────────────────────────────────────

function renderSidebarAgentTabs() {
  const container = document.getElementById('sidebar-agent-tabs');
  if (!container) return;
  const icons = { research: '🔍', trading: '📈', content: '✍️', devops: '🛠', custom: '🤖' };
  container.innerHTML = state.agents.map(a => {
    const icon = icons[a.template] || '🤖';
    const active = state.chatAgent === a.id && state.currentPage === 'chat' ? 'active' : '';
    const statusColor = a.status === 'idle' || a.status === 'running' ? 'var(--green)' : 'var(--text-muted)';
    return `<div class="nav-item ${active}" onclick="openAgentChat('${a.id}')">
      <span class="nav-icon">${icon}</span> ${a.name}
      <span class="status-dot" style="color:${statusColor};margin-left:auto">●</span>
    </div>`;
  }).join('');
}

// ── Sync agents from server ───────────────────────────────

async function syncAgentsFromServer() {
  try {
    const res = await fetch(`${API_BASE}/api/agents`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.agents) {
      state.agents = data.agents;
      saveState();
      renderSidebarAgentTabs();
      refreshAgentsGrid();
      refreshDashboard();
    }
  } catch (e) { /* server not ready */ }
}

// ── New Agent Modal ─────────────────────────────────────────

let selectedTemplate = 'trading';

document.querySelectorAll('.template-option').forEach(opt => {
  opt.addEventListener('click', () => {
    document.querySelectorAll('.template-option').forEach(o => o.classList.remove('selected'));
    opt.classList.add('selected');
    selectedTemplate = opt.dataset.template;
  });
});

function openNewAgentModal() {
  document.getElementById('new-agent-modal').classList.add('active');
  document.getElementById('new-agent-name').focus();
}

function closeNewAgentModal() {
  document.getElementById('new-agent-modal').classList.remove('active');
}

async function createAgent(opts = null) {
  const name = opts?.name || document.getElementById('new-agent-name').value.trim();
  const template = opts?.template || selectedTemplate;
  const personality = opts?.personality || document.getElementById('new-agent-personality')?.value?.trim() || '';

  if (!name) { showToast('Please enter an agent name', 'error'); return null; }

  try {
    const res = await fetch(`${API_BASE}/api/agents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, template, personality }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(`Error: ${err.error || 'Failed to create agent'}`, 'error');
      return null;
    }

    const data = await res.json();
    const agent = data.agent;

    // Sync from server to get full state
    await syncAgentsFromServer();

    addLog('success', `Agent "${name}" created (${template})`);
    closeNewAgentModal();
    showToast(`🤖 Agent "${name}" created!`, 'success');

    addHubSystemMessage(`🤖 Agent "${name}" joined the hub`);

    return agent;
  } catch (e) {
    showToast(`Error creating agent: ${e.message}`, 'error');
    return null;
  }
}

// ── Agent Actions ───────────────────────────────────────────

function toggleAgent(id) {
  const agent = state.agents.find(a => a.id === id);
  if (!agent) return;
  agent.status = agent.status === 'idle' ? 'stopped' : 'idle';
  saveState();
  showToast(`Agent "${agent.name}" ${agent.status}`, 'info');
  refreshDashboard();
  refreshAgentsGrid();
  renderSidebarAgentTabs();
}

async function deleteAgent(id) {
  const agent = state.agents.find(a => a.id === id);
  if (!agent || !confirm(`Delete "${agent.name}"?`)) return;

  try {
    await fetch(`${API_BASE}/api/agents/${id}`, { method: 'DELETE' });
  } catch (e) { /* ok if server unreachable */ }

  state.agents = state.agents.filter(a => a.id !== id);
  delete state.chatHistories[id];
  saveState();
  showToast(`Agent "${agent.name}" deleted`, 'info');
  refreshDashboard();
  refreshAgentsGrid();
  renderSidebarAgentTabs();

  if (state.chatAgent === id) {
    state.chatAgent = null;
    navigateTo('agents');
  }
}

function deleteCurrentAgent() {
  if (state.chatAgent) deleteAgent(state.chatAgent);
}

function openAgentChat(id) {
  state.chatAgent = id;
  saveState();

  const agent = state.agents.find(a => a.id === id);
  if (agent) {
    const icons = { research: '🔍', trading: '📈', content: '✍️', devops: '🛠', custom: '🤖' };
    const icon = icons[agent.template] || '🤖';
    document.getElementById('chat-agent-name').textContent = agent.name;
    document.getElementById('chat-agent-status-text').textContent = agent.status || 'idle';

    // Welcome screen
    const welcomeName = document.getElementById('agent-welcome-name');
    const welcomeDesc = document.getElementById('agent-welcome-desc');
    if (welcomeName) welcomeName.textContent = `${icon} ${agent.name}`;
    if (welcomeDesc) welcomeDesc.textContent = agent.system_prompt || `${agent.template} agent — ready to help.`;

    renderAgentChat(id);
    connectAgentWs(id);
  }
  navigateTo('chat');
  renderSidebarAgentTabs();
}

// ═══════════════════════════════════════════════════════════
// JARVIS DIRECT CHAT (always available, no agent needed)
// ═══════════════════════════════════════════════════════════

let jarvisWs = null;
let jarvisStreaming = '';

function initJarvisChat() {
  renderJarvisMessages();
  connectJarvisWs();
  setTimeout(() => {
    const input = document.getElementById('jarvis-input');
    if (input) input.focus();
  }, 100);

  // Drag & drop image support
  const chatArea = document.querySelector('#page-jarvis-chat .chat-container') ||
                   document.getElementById('page-jarvis-chat');
  if (chatArea) {
    chatArea.addEventListener('dragover', (e) => {
      e.preventDefault();
      if (!chatArea.querySelector('.drop-overlay')) {
        const overlay = document.createElement('div');
        overlay.className = 'drop-overlay';
        overlay.textContent = '📷 Drop images here';
        chatArea.style.position = 'relative';
        chatArea.appendChild(overlay);
      }
    });
    chatArea.addEventListener('dragleave', (e) => {
      if (!chatArea.contains(e.relatedTarget)) {
        chatArea.querySelector('.drop-overlay')?.remove();
      }
    });
    chatArea.addEventListener('drop', (e) => {
      e.preventDefault();
      chatArea.querySelector('.drop-overlay')?.remove();
      if (e.dataTransfer?.files) handleJarvisFiles(e.dataTransfer.files);
    });
  }
}

function connectJarvisWs() {
  if (jarvisWs && jarvisWs.readyState === WebSocket.OPEN) return;

  try {
    jarvisWs = new WebSocket(`${WS_BASE}/ws/chat?agent_id=jarvis`);

    jarvisWs.onopen = () => {
      const el = document.getElementById('jarvis-connection-status');
      if (el) { el.innerHTML = '<span class="status-dot"></span> Connected'; el.className = 'status status-running'; }
    };

    jarvisWs.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleJarvisWsMessage(data);
    };

    jarvisWs.onerror = () => { jarvisWs = null; };
    jarvisWs.onclose = () => {
      jarvisWs = null;
      const el = document.getElementById('jarvis-connection-status');
      if (el) { el.innerHTML = '<span class="status-dot"></span> Reconnecting...'; el.className = 'status status-idle'; }
      setTimeout(connectJarvisWs, 3000);
    };
  } catch (e) { jarvisWs = null; }
}

function handleJarvisWsMessage(data) {
  // Route agent messages to agent handler if we're chatting with an agent
  if (data.agent_id && data.agent_id.startsWith('agent_')) {
    handleAgentWsMessage(data, data.agent_id);
    return;
  }

  // Handle agents_updated event (Jarvis spawned an agent)
  if (data.type === 'agents_updated') {
    if (data.agents) {
      state.agents = data.agents;
      saveState();
      renderSidebarAgentTabs();
      refreshAgentsGrid();
      refreshDashboard();
      showToast('🤖 Agent list updated', 'success');
    }
    return;
  }

  const container = document.getElementById('jarvis-messages');
  if (!container) return;

  if (data.type === 'token') {
    jarvisStreaming += data.text;
    ensureStreamingBubble(container, jarvisStreaming);
  } else if (data.type === 'thinking') {
    ensureStreamingBubble(container, '⏳ Thinking...');
  } else if (data.type === 'tool_call') {
    const status = data.status === 'done' ? '✅' : '🔧';
    ensureStreamingBubble(container, jarvisStreaming + `\n${status} ${data.tool}`);
  } else if (data.type === 'done') {
    removeStreamingBubble(container);
    const finalText = data.full_text || jarvisStreaming;
    state.jarvisHistory.push({
      role: 'assistant', content: finalText,
      tools_used: data.tools_used || [], timestamp: Date.now(),
    });
    saveState();
    renderJarvisMessages();
    jarvisStreaming = '';
    enableJarvisInput(true);

    // Check if Jarvis wants to create an agent (legacy)
    detectAgentCreation(finalText);
  } else if (data.type === 'error') {
    removeStreamingBubble(container);
    showToast(`Error: ${data.message}`, 'error');
    enableJarvisInput(true);
  }
}

function renderJarvisMessages() {
  const container = document.getElementById('jarvis-messages');
  if (!container) return;

  if (state.jarvisHistory.length === 0) {
    container.innerHTML = `
      <div class="jarvis-welcome">
        <div class="jarvis-welcome-icon">⚡</div>
        <h2>Hey, I'm Jarvis</h2>
        <p>Your AI operating system. I can help with anything — ask questions, create agents, search the web, write code, or just chat.</p>
        <div class="jarvis-suggestions">
          <button class="suggestion-chip" onclick="sendJarvisMessage('What can you do?')">What can you do?</button>
          <button class="suggestion-chip" onclick="sendJarvisMessage('Create a trading agent for crypto')">Create a trading agent</button>
          <button class="suggestion-chip" onclick="sendJarvisMessage('Search the web for latest AI news')">Search AI news</button>
          <button class="suggestion-chip" onclick="sendJarvisMessage('Help me write a Python script')">Help me code</button>
        </div>
      </div>`;
    return;
  }

  container.innerHTML = state.jarvisHistory.map(m => {
    const time = new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const isUser = m.role === 'user';
    let html = `<div class="chat-message ${isUser ? 'user' : 'agent'}">`;
    // Show attached images
    if (m.images?.length) {
      html += `<div class="msg-images">`;
      m.images.forEach(src => {
        html += `<img src="${src}" alt="Attached image" onclick="openLightbox('${src}')" loading="lazy">`;
      });
      html += `</div>`;
    }
    if (m.content) html += `<div>${formatMessage(m.content)}</div>`;
    if (m.tools_used?.length) html += `<div class="msg-tools">🔧 ${m.tools_used.join(', ')}</div>`;
    html += `<div class="msg-meta">${time}</div></div>`;
    return html;
  }).join('');

  container.scrollTop = container.scrollHeight;
}

// ── Image Handling ─────────────────────────────────────────

let pendingImages = []; // Array of { dataUrl, file }

function handleJarvisFiles(files) {
  for (const file of files) {
    if (!file.type.startsWith('image/')) continue;
    if (pendingImages.length >= 5) { showToast('Max 5 images per message', 'error'); break; }
    const reader = new FileReader();
    reader.onload = (e) => {
      pendingImages.push({ dataUrl: e.target.result, name: file.name });
      renderImagePreview();
    };
    reader.readAsDataURL(file);
  }
  // Reset file input so same file can be re-selected
  document.getElementById('jarvis-file-input').value = '';
}

function handleJarvisPaste(event) {
  const items = event.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      event.preventDefault();
      const file = item.getAsFile();
      if (file) handleJarvisFiles([file]);
    }
  }
}

function renderImagePreview() {
  const strip = document.getElementById('jarvis-image-preview');
  if (!strip) return;
  if (pendingImages.length === 0) {
    strip.style.display = 'none';
    strip.innerHTML = '';
    return;
  }
  strip.style.display = 'flex';
  strip.innerHTML = pendingImages.map((img, i) => `
    <div class="image-preview-item">
      <img src="${img.dataUrl}" alt="${img.name || 'image'}">
      <button class="remove-img" onclick="removePendingImage(${i})">×</button>
    </div>
  `).join('');
}

function removePendingImage(index) {
  pendingImages.splice(index, 1);
  renderImagePreview();
}

function openLightbox(src) {
  const overlay = document.createElement('div');
  overlay.className = 'image-lightbox';
  overlay.onclick = () => overlay.remove();
  overlay.innerHTML = `<img src="${src}" alt="Full size">`;
  document.body.appendChild(overlay);
}

async function uploadImages(images) {
  // Upload images to server, returns array of image URLs/IDs
  const uploaded = [];
  for (const img of images) {
    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: img.dataUrl, name: img.name || 'image.png' }),
      });
      if (res.ok) {
        const data = await res.json();
        uploaded.push({ url: data.url, dataUrl: img.dataUrl, id: data.id });
      }
    } catch (e) {
      console.error('Image upload failed:', e);
    }
  }
  return uploaded;
}

// ── Send Message (with optional images) ───────────────────

async function sendJarvisMessage(text) {
  const input = document.getElementById('jarvis-input');
  const message = text || input?.value?.trim();
  const images = [...pendingImages];

  if (!message && images.length === 0) return;

  // Navigate to Jarvis chat if not there
  if (state.currentPage !== 'jarvis-chat') navigateTo('jarvis-chat');

  // Add user message (with image dataUrls for display)
  const userMsg = { role: 'user', content: message || '', timestamp: Date.now() };
  if (images.length > 0) {
    userMsg.images = images.map(i => i.dataUrl);
  }
  state.jarvisHistory.push(userMsg);

  // Clear input + images
  if (input) input.value = '';
  pendingImages = [];
  renderImagePreview();
  saveState();
  renderJarvisMessages();
  enableJarvisInput(false);

  // Upload images to server if any
  let uploadedImages = [];
  if (images.length > 0) {
    uploadedImages = await uploadImages(images);
    if (uploadedImages.length === 0 && images.length > 0) {
      showToast('Image upload failed, sending text only', 'error');
    }
  }

  // Try WebSocket
  if (jarvisWs && jarvisWs.readyState === WebSocket.OPEN) {
    jarvisStreaming = '';
    const payload = {
      type: 'message', text: message || '', agent_id: 'jarvis', conversation_id: 'jarvis_main',
    };
    if (uploadedImages.length > 0) {
      payload.images = uploadedImages.map(i => i.id || i.url);
    }
    jarvisWs.send(JSON.stringify(payload));
    return;
  }

  // HTTP fallback
  sendJarvisHTTP(message || '', uploadedImages);
}

async function sendJarvisHTTP(message, uploadedImages = []) {
  try {
    const body = { message, conversation_id: 'jarvis_main' };
    if (uploadedImages.length > 0) {
      body.images = uploadedImages.map(i => i.id || i.url);
    }
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (res.ok) {
      const data = await res.json();
      state.jarvisHistory.push({
        role: 'assistant', content: data.text || 'I received your message.',
        tools_used: data.tools_used || [], timestamp: Date.now(),
      });
    } else {
      state.jarvisHistory.push({
        role: 'assistant', content: '⚠️ Server returned an error. Check Settings → API Keys.',
        timestamp: Date.now(),
      });
    }
  } catch (e) {
    // Offline — simulate
    await sleep(600);
    state.jarvisHistory.push({
      role: 'assistant',
      content: simulateJarvisResponse(message),
      timestamp: Date.now(),
    });
  }

  saveState();
  renderJarvisMessages();
  enableJarvisInput(true);
}

function simulateJarvisResponse(message) {
  const msg = message.toLowerCase();
  if (msg.includes('create') && msg.includes('agent')) {
    return `I'd love to create an agent for you! Here's what I can set up:\n\n• **Trading Agent** — Crypto analysis & automated trading\n• **Research Agent** — Deep web research & daily briefings\n• **Content Agent** — Writing, social media, content creation\n• **DevOps Agent** — Infrastructure monitoring & automation\n• **Custom Agent** — Anything you want!\n\nJust tell me the name, type, and I'll spawn it. Or use the ➕ button in the sidebar.\n\n_Note: Connect an API key in Settings to enable real AI responses._`;
  }
  if (msg.includes('what can you do') || msg.includes('help')) {
    return `I'm **Jarvis**, your AI operating system. Here's what I can do:\n\n🔍 **Search the web** — Find information, news, research\n💻 **Write & run code** — Python, JavaScript, any language\n🤖 **Create agents** — Spawn specialized AI agents\n📊 **Analyze data** — Process files, charts, reports\n🔧 **Use tools** — HTTP requests, file management, shell commands\n🧠 **Remember things** — I learn from our conversations\n\n_Configure your API key in Settings for full capabilities._`;
  }
  return `I received your message. To enable full AI responses, please add an API key in **Settings → API Keys** (OpenAI, Anthropic, Google, or use Ollama for free).\n\nOnce configured, I can:\n• Answer questions with real AI\n• Search the web\n• Run code\n• Create and manage agents`;
}

function enableJarvisInput(enabled) {
  const input = document.getElementById('jarvis-input');
  const btn = document.getElementById('jarvis-send');
  if (input) { input.disabled = !enabled; if (enabled) input.focus(); }
  if (btn) btn.disabled = !enabled;
}

function handleJarvisKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendJarvisMessage();
  }
}

// ── Agent auto-detection from Jarvis response ────────────

function detectAgentCreation(text) {
  // No longer needed — Jarvis uses spawn_agent tool which triggers agents_updated event
  // Kept for backward compat with [SPAWN_AGENT:...] pattern
  const match = text.match(/\[SPAWN_AGENT:([^:]+):([^:]+):([^\]]+)\]/);
  if (match) {
    syncAgentsFromServer();
  }
}

// ═══════════════════════════════════════════════════════════
// AGENT CHAT (individual agent conversations)
// ═══════════════════════════════════════════════════════════

let agentWs = null;
let agentStreaming = '';

function connectAgentWs(agentId) {
  // Reuse the Jarvis WS connection — messages are routed by agent_id
  // No separate connection needed since the WS handler routes by agent_id field
  // Just ensure jarvis WS is connected
  if (!jarvisWs || jarvisWs.readyState !== WebSocket.OPEN) {
    connectJarvisWs();
  }
}

function handleAgentWsMessage(data, agentId) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  if (data.type === 'token') {
    agentStreaming += data.text;
    ensureStreamingBubble(container, agentStreaming);
  } else if (data.type === 'thinking') {
    ensureStreamingBubble(container, '⏳ Thinking...');
  } else if (data.type === 'done') {
    removeStreamingBubble(container);
    const finalText = data.full_text || agentStreaming;
    if (!state.chatHistories[agentId]) state.chatHistories[agentId] = [];
    state.chatHistories[agentId].push({
      role: 'agent', content: finalText,
      tools_used: data.tools_used || [], timestamp: Date.now(),
    });
    saveState();
    renderAgentChat(agentId);
    agentStreaming = '';
    enableAgentInput(true);
  } else if (data.type === 'error') {
    removeStreamingBubble(container);
    showToast(`Error: ${data.message}`, 'error');
    enableAgentInput(true);
  } else if (data.type === 'agents_updated') {
    // Server notified us that agents list changed (Jarvis spawned one)
    if (data.agents) {
      state.agents = data.agents;
      saveState();
      renderSidebarAgentTabs();
      refreshAgentsGrid();
      refreshDashboard();
    }
  }
}

function enableAgentInput(enabled) {
  const send = document.getElementById('chat-send');
  const input = document.getElementById('chat-input');
  if (send) send.disabled = !enabled;
  if (input) { input.disabled = !enabled; if (enabled) input.focus(); }
}

function renderAgentChat(agentId) {
  const container = document.getElementById('chat-messages');
  const messages = state.chatHistories[agentId] || [];

  if (messages.length === 0) {
    const agent = state.agents.find(a => a.id === agentId);
    container.innerHTML = `<div class="empty-state">
      <div class="empty-icon">💬</div>
      <h3>Chat with ${agent?.name || 'Agent'}</h3>
      <p>Type a message below to start.</p>
    </div>`;
    return;
  }

  container.innerHTML = messages.map(m => {
    const time = new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const isUser = m.role === 'user';
    let html = `<div class="chat-message ${isUser ? 'user' : 'agent'}">`;
    html += `<div>${formatMessage(m.content)}</div>`;
    if (m.tools_used?.length) html += `<div class="msg-tools">🔧 ${m.tools_used.join(', ')}</div>`;
    html += `<div class="msg-meta">${time}</div></div>`;
    return html;
  }).join('');

  container.scrollTop = container.scrollHeight;
}

async function sendAgentChatMessage() {
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message || !state.chatAgent) return;

  const agentId = state.chatAgent;
  if (!state.chatHistories[agentId]) state.chatHistories[agentId] = [];
  state.chatHistories[agentId].push({ role: 'user', content: message, timestamp: Date.now() });

  input.value = '';
  renderAgentChat(agentId);
  enableAgentInput(false);

  // Use Jarvis WebSocket with agent_id routing
  if (jarvisWs && jarvisWs.readyState === WebSocket.OPEN) {
    agentStreaming = '';
    jarvisWs.send(JSON.stringify({
      type: 'message', text: message, agent_id: agentId, conversation_id: `chat_${agentId}`,
    }));
    return;
  }

  // HTTP fallback — call agent-specific endpoint
  try {
    const res = await fetch(`${API_BASE}/api/agents/${agentId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    const data = res.ok ? await res.json() : { text: 'Error connecting to agent.' };
    state.chatHistories[agentId].push({
      role: 'agent', content: data.text || 'Received.',
      tools_used: data.tools_used || [], timestamp: Date.now(),
    });
  } catch (e) {
    state.chatHistories[agentId].push({
      role: 'agent', content: `Error: ${e.message}`, timestamp: Date.now(),
    });
  }

  saveState();
  renderAgentChat(agentId);
  enableAgentInput(true);
  input.focus();
}

function simulateAgentResponse(agent, message) {
  if (!agent) return 'I received your message.';
  return `I'm **${agent.name}** (${agent.template} agent on ${agent.model}). I received your message.\n\n_Connect an API key in Settings for real AI responses._`;
}

function handleChatKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAgentChatMessage(); }
}

// ═══════════════════════════════════════════════════════════
// AGENT HUB (group chat with all agents)
// ═══════════════════════════════════════════════════════════

function initHub() {
  renderHubAgentList();
  renderHubMessages();
}

function renderHubAgentList() {
  const list = document.getElementById('hub-agent-list');
  if (!list) return;

  let html = `
    <div class="hub-agent-item active" data-agent="jarvis">
      <div class="hub-agent-avatar jarvis">⚡</div>
      <div class="hub-agent-info">
        <div class="hub-agent-name">Jarvis</div>
        <div class="hub-agent-role">Orchestrator</div>
      </div>
      <span class="status-dot" style="color:var(--green)"></span>
    </div>`;

  state.agents.forEach(a => {
    const icons = { trading: '💹', research: '🔬', content: '✍️', devops: '🛠️', support: '🎧', 'personal-assistant': '🧑‍💼', custom: '⚡' };
    html += `
      <div class="hub-agent-item" data-agent="${a.id}">
        <div class="hub-agent-avatar agent">${icons[a.template] || '🤖'}</div>
        <div class="hub-agent-info">
          <div class="hub-agent-name">${a.name}</div>
          <div class="hub-agent-role">${a.template}</div>
        </div>
        <span class="status-dot" style="color:${a.status === 'running' ? 'var(--green)' : 'var(--red)'}"></span>
      </div>`;
  });

  list.innerHTML = html;
}

function renderHubMessages() {
  const container = document.getElementById('hub-messages');
  if (!container) return;

  if (state.hubHistory.length === 0) {
    container.innerHTML = `
      <div class="hub-system-msg">
        <span>🌐 Agent Hub — All agents communicate here. Send a message or watch them collaborate.</span>
      </div>`;
    return;
  }

  container.innerHTML = state.hubHistory.map(m => {
    if (m.type === 'system') {
      return `<div class="hub-system-msg"><span>${m.content}</span></div>`;
    }

    const time = new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const isUser = m.sender === 'You';
    const isJarvis = m.sender === 'Jarvis';
    const avatarClass = isJarvis ? 'jarvis' : 'agent';
    const icon = m.icon || (isJarvis ? '⚡' : '👤');

    return `
      <div class="hub-msg ${isUser ? 'is-user' : ''} ${isJarvis ? 'is-jarvis' : ''}">
        <div class="hub-msg-avatar ${avatarClass}">${icon}</div>
        <div class="hub-msg-body">
          <div class="hub-msg-header">
            <span class="hub-msg-name">${m.sender}</span>
            <span class="hub-msg-time">${time}</span>
          </div>
          <div class="hub-msg-text">${formatMessage(m.content)}</div>
        </div>
      </div>`;
  }).join('');

  container.scrollTop = container.scrollHeight;
}

function addHubSystemMessage(text) {
  state.hubHistory.push({ type: 'system', content: text, timestamp: Date.now() });
  saveState();
  if (state.currentPage === 'hub') renderHubMessages();
}

async function sendHubMessage() {
  const input = document.getElementById('hub-input');
  const message = input?.value?.trim();
  if (!message) return;

  input.value = '';

  // Add user message to hub
  state.hubHistory.push({
    sender: 'You', icon: '👤', content: message, timestamp: Date.now(),
  });
  saveState();
  renderHubMessages();

  // Jarvis responds in hub
  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: `[Hub message from user]: ${message}`, conversation_id: 'hub_group' }),
    });

    if (res.ok) {
      const data = await res.json();
      state.hubHistory.push({
        sender: 'Jarvis', icon: '⚡', content: data.text || 'Received.',
        timestamp: Date.now(),
      });
    }
  } catch (e) {
    state.hubHistory.push({
      sender: 'Jarvis', icon: '⚡',
      content: `I'll coordinate with the agents on this. ${state.agents.length === 0 ? 'No agents created yet — want me to create one?' : ''}`,
      timestamp: Date.now(),
    });
  }

  saveState();
  renderHubMessages();
}

function handleHubKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendHubMessage(); }
}

// ═══════════════════════════════════════════════════════════
// SHARED UTILITIES
// ═══════════════════════════════════════════════════════════

function formatMessage(text) {
  return text
    .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre style="background:rgba(0,0,0,0.3);padding:12px;border-radius:6px;overflow-x:auto;margin:8px 0;font-family:JetBrains Mono,monospace;font-size:0.82rem">$2</pre>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/_(.*?)_/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code style="background:rgba(255,255,255,0.08);padding:2px 6px;border-radius:3px;font-family:JetBrains Mono,monospace;font-size:0.85em">$1</code>')
    .replace(/\n/g, '<br>');
}

function ensureStreamingBubble(container, text) {
  let bubble = container.querySelector('.streaming-bubble');
  if (!bubble) {
    bubble = document.createElement('div');
    bubble.className = 'chat-message agent streaming-bubble';
    container.appendChild(bubble);
  }
  bubble.innerHTML = formatMessage(text) + '<span class="typing-cursor">▊</span>';
  container.scrollTop = container.scrollHeight;
}

function removeStreamingBubble(container) {
  const bubble = container.querySelector('.streaming-bubble');
  if (bubble) bubble.remove();
}

// ── Settings ────────────────────────────────────────────────

function saveApiKey(provider) {
  const input = document.getElementById(`key-${provider}`);
  if (!input) return;
  const value = input.value.trim();

  state.settings.apiKeys[provider] = value;
  saveState();

  // Also save to server
  fetch(`${API_BASE}/api/settings/keys`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, key: value }),
  }).catch(() => {});

  const statusEl = document.getElementById(`${provider}-status`);
  if (statusEl) { statusEl.textContent = '✅ Configured'; statusEl.style.color = 'var(--green)'; }

  showToast(`✅ ${provider} key saved`, 'success');
  if (value.length > 8) input.value = value.substring(0, 4) + '•'.repeat(value.length - 8) + value.substring(value.length - 4);

  refreshDashboard();
}

function saveGeneralSettings() {
  const model = document.getElementById('setting-default-model').value;
  state.settings.defaultModel = model;
  state.settings.autoMemory = document.getElementById('setting-auto-memory').checked;
  saveState();

  // Also save model to server (persisted across rebuilds)
  if (model) {
    const provider = model.startsWith('claude') ? 'anthropic'
      : model.startsWith('gemini') ? 'google'
      : model.startsWith('llama') || model.startsWith('mistral') ? 'ollama'
      : 'openai';
    fetch(`${API_BASE}/api/settings/keys`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, model, key: '' }),
    }).catch(() => {});
  }

  showToast('✅ Settings saved (including server-side)', 'success');
}

// ── Plugins ─────────────────────────────────────────────────

async function refreshPlugins() {
  try {
    const res = await fetch(`${API_BASE}/api/plugins`);
    if (res.ok) {
      const data = await res.json();
      const list = document.getElementById('plugins-list');
      if (data.plugins?.length) {
        list.innerHTML = data.plugins.map(p => `
          <div class="api-key-card">
            <div class="provider-icon" style="background:rgba(34,197,94,0.15)">🔌</div>
            <div class="provider-info">
              <div class="provider-name">${p.name}</div>
              <div class="provider-status" style="color:var(--text-muted)">${p.description}</div>
            </div>
            <span class="status status-running"><span class="status-dot"></span> loaded</span>
          </div>
        `).join('');
      } else {
        list.innerHTML = '<p style="color:var(--text-muted)">No plugins loaded. Add .py files to the plugins/ folder.</p>';
      }
    }
  } catch (e) {}
}

// ── Logs ────────────────────────────────────────────────────

function addLog(level, message) {
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  state.logs.unshift({ time, level, message });
  if (state.logs.length > 200) state.logs = state.logs.slice(0, 200);
  saveState();
}

function refreshLogs() {
  const viewer = document.getElementById('log-viewer');
  if (state.logs.length === 0) {
    viewer.innerHTML = '<span style="color:var(--text-muted)">No logs yet.</span>';
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

async function searchMemory() {
  const query = document.getElementById('memory-search').value.trim();
  if (!query) return;

  const container = document.getElementById('memory-results');

  // Try server-side search
  try {
    const res = await fetch(`${API_BASE}/api/memory/search?q=${encodeURIComponent(query)}&limit=20`);
    if (res.ok) {
      const data = await res.json();
      if (data.results?.length) {
        container.innerHTML = data.results.map(r => `
          <div style="padding:12px; border:1px solid var(--border); border-radius:var(--radius-sm); margin-bottom:8px">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px">
              <span style="font-weight:600; font-size:0.85rem">${r.type}</span>
              <span style="color:var(--text-muted); font-size:0.75rem">relevance: ${r.relevance}</span>
            </div>
            <div style="font-size:0.85rem; color:var(--text-secondary)">${r.content.substring(0, 300)}${r.content.length > 300 ? '...' : ''}</div>
          </div>
        `).join('');
        return;
      }
    }
  } catch (e) {}

  // Local search fallback
  const results = [];
  state.jarvisHistory.forEach(m => {
    if (m.content.toLowerCase().includes(query.toLowerCase())) {
      results.push({ type: 'Jarvis chat', content: m.content, time: new Date(m.timestamp).toLocaleString() });
    }
  });

  if (results.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted)">No results for "${query}"</p>`;
  } else {
    container.innerHTML = results.map(r => `
      <div style="padding:12px; border:1px solid var(--border); border-radius:var(--radius-sm); margin-bottom:8px">
        <span style="font-weight:600; font-size:0.85rem">${r.type}</span>
        <div style="font-size:0.85rem; color:var(--text-secondary); margin-top:4px">${r.content.substring(0, 200)}</div>
      </div>
    `).join('');
  }
}

// ── Utilities ───────────────────────────────────────────────

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function timeSince(ts) {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
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
['openai', 'anthropic', 'ollama', 'google'].forEach(p => {
  if (state.settings.apiKeys[p]) {
    const el = document.getElementById(`${p}-status`);
    if (el) { el.textContent = '✅ Configured'; el.style.color = 'var(--green)'; }
  }
});
