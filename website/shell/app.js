/**
 * Seabay Shell Web — Main Application
 *
 * Manages the chat UI, LLM tool call processing, settings, and card actions.
 */

(function () {
  'use strict';

  // ── Config (persisted in localStorage) ──

  const CONFIG_KEY = 'seabay_shell_config';

  function loadConfig() {
    const defaults = {
      apiUrl: 'http://localhost:8000/v1',
      apiKey: '',
      llmUrl: 'https://api.openai.com/v1',
      llmModel: 'gpt-4o',
      llmApiKey: '',
    };
    try {
      const saved = JSON.parse(localStorage.getItem(CONFIG_KEY) || '{}');
      return { ...defaults, ...saved };
    } catch {
      return defaults;
    }
  }

  function saveConfig(cfg) {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(cfg));
  }

  // ── State ──

  let config = loadConfig();
  let api = new SeabayAPI(config.apiUrl, config.apiKey);
  let llm = new SeabayLLM(config.llmUrl, config.llmApiKey, config.llmModel);
  let agentInfo = null;
  let isProcessing = false;

  // ── DOM refs ──

  const chatMessages = document.getElementById('chat-messages');
  const messageInput = document.getElementById('message-input');
  const sendBtn = document.getElementById('send-btn');
  const settingsBtn = document.getElementById('settings-btn');
  const settingsModal = document.getElementById('settings-modal');
  const settingsForm = document.getElementById('settings-form');
  const settingsCancel = document.getElementById('settings-cancel');
  const connectionStatus = document.getElementById('connection-status');
  const agentInfoEl = document.getElementById('agent-info');

  // ── Initialize ──

  async function initialize() {
    // Try to connect to API and get agent info
    if (config.apiKey) {
      try {
        agentInfo = await api.getMyAgent();
        setConnectionStatus('online', 'Connected');
        agentInfoEl.textContent = `${agentInfo.display_name} (@${agentInfo.slug})`;
        llm.initialize(agentInfo);
      } catch (err) {
        setConnectionStatus('error', 'API Error');
        agentInfoEl.textContent = 'Connection failed';
        addSystemMessage(`Failed to connect: ${err.message}. Check settings.`);
        llm.initialize();
      }
    } else {
      setConnectionStatus('offline', 'Not configured');
      agentInfoEl.textContent = 'Configure API key in settings';
      addSystemMessage('Click the gear icon to configure your Seabay API key and LLM settings.');
      llm.initialize();
    }
  }

  function setConnectionStatus(cls, text) {
    connectionStatus.className = `status-badge ${cls}`;
    connectionStatus.textContent = text;
  }

  // ── Message rendering ──

  function addMessage(role, content, extra = null) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (typeof content === 'string') {
      // Simple text — render with basic markdown-like formatting
      contentDiv.innerHTML = renderSimpleMarkdown(content);
    }

    msgDiv.appendChild(contentDiv);

    // Append card elements if provided
    if (extra instanceof HTMLElement) {
      contentDiv.appendChild(extra);
    }

    chatMessages.appendChild(msgDiv);
    scrollToBottom();
    return msgDiv;
  }

  function addSystemMessage(text) {
    addMessage('system', text);
  }

  function addTypingIndicator() {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message assistant';
    msgDiv.id = 'typing-indicator';

    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = '<span></span><span></span><span></span>';

    msgDiv.appendChild(indicator);
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
    return msgDiv;
  }

  function removeTypingIndicator() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
  }

  function scrollToBottom() {
    const container = document.getElementById('chat-container');
    container.scrollTop = container.scrollHeight;
  }

  function renderSimpleMarkdown(text) {
    // Very basic markdown rendering
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  // ── Command handling ──

  const HELP_TEXT = `**Available commands:**

\`/help\` — Show this help
\`/status\` — Show agent status
\`/inbox\` — List inbox tasks
\`/search <query>\` — Search for agents
\`/task <id>\` — Get task details
\`/accept <id>\` — Accept a task
\`/decline <id>\` — Decline a task
\`/connect <slug>\` — View agent profile
\`/clear\` — Clear chat history
\`/settings\` — Open settings

Or just type naturally!`;

  async function handleCommand(input) {
    const parts = input.trim().split(/\s+/);
    const cmd = parts[0].toLowerCase();
    const arg = parts.slice(1).join(' ');

    switch (cmd) {
      case '/help':
        addMessage('assistant', HELP_TEXT);
        return true;

      case '/clear':
        chatMessages.innerHTML = '';
        llm.clearHistory();
        addSystemMessage('Chat history cleared.');
        return true;

      case '/settings':
        openSettings();
        return true;

      case '/status':
        try {
          const agent = await api.getMyAgent();
          const card = SeabayRenderer.agentProfileCard(agent);
          addMessage('assistant', '', card);
        } catch (err) {
          addMessage('assistant', `Failed to get status: ${err.message}`);
        }
        return true;

      case '/inbox':
        try {
          const params = arg ? { status: arg } : {};
          const result = await api.getInbox(params);
          const tasks = result.data || [];
          const card = SeabayRenderer.inboxCard(tasks, result.has_more, {
            onAccept: async (id) => { await handleTaskAction(id, 'accept'); },
            onDecline: async (id) => { await handleTaskAction(id, 'decline'); },
          });
          addMessage('assistant', `Inbox (${tasks.length} tasks):`, card);
        } catch (err) {
          addMessage('assistant', `Failed to get inbox: ${err.message}`);
        }
        return true;

      case '/search':
        if (!arg) {
          addMessage('assistant', 'Usage: `/search <query>`');
          return true;
        }
        try {
          const result = await api.searchAgents({ q: arg });
          const agents = result.data || [];
          const card = SeabayRenderer.matchResultCard(agents, `Search results for "${arg}":`);
          addMessage('assistant', '', card);
        } catch (err) {
          addMessage('assistant', `Search failed: ${err.message}`);
        }
        return true;

      case '/task':
        if (!arg) {
          addMessage('assistant', 'Usage: `/task <task_id>`');
          return true;
        }
        try {
          const task = await api.getTask(arg);
          const card = SeabayRenderer.taskDetailCard(task);
          addMessage('assistant', '', card);
        } catch (err) {
          addMessage('assistant', `Failed to get task: ${err.message}`);
        }
        return true;

      case '/accept':
        if (!arg) {
          addMessage('assistant', 'Usage: `/accept <task_id>`');
          return true;
        }
        await handleTaskAction(arg, 'accept');
        return true;

      case '/decline':
        if (!arg) {
          addMessage('assistant', 'Usage: `/decline <task_id>`');
          return true;
        }
        await handleTaskAction(arg, 'decline');
        return true;

      case '/connect':
        if (!arg) {
          addMessage('assistant', 'Usage: `/connect <agent_slug_or_id>`');
          return true;
        }
        try {
          let agent;
          try {
            agent = await api.getPublicAgent(arg);
          } catch {
            agent = await api.getAgent(arg);
          }
          const card = SeabayRenderer.agentProfileCard(agent);
          addMessage('assistant', '', card);
        } catch (err) {
          addMessage('assistant', `Agent not found: ${err.message}`);
        }
        return true;

      default:
        return false; // Not a recognized command
    }
  }

  async function handleTaskAction(taskId, action) {
    try {
      let result;
      if (action === 'accept') {
        result = await api.acceptTask(taskId);
        addMessage('assistant', `Task ${taskId} accepted. Status: ${result.status}`);
      } else {
        result = await api.declineTask(taskId);
        addMessage('assistant', `Task ${taskId} declined. Status: ${result.status}`);
      }
    } catch (err) {
      addMessage('assistant', `Failed to ${action} task: ${err.message}`);
    }
  }

  // ── Send message ──

  async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isProcessing) return;

    messageInput.value = '';
    autoResizeInput();

    // Show user message
    addMessage('user', text);

    // Check if it's a slash command
    if (text.startsWith('/')) {
      const handled = await handleCommand(text);
      if (handled) return;
      // If not a recognized command, fall through to LLM
    }

    // Check if LLM is configured
    if (!llm.isConfigured) {
      addMessage('assistant', 'LLM is not configured. Use slash commands or click the gear icon to configure your LLM API key.');
      return;
    }

    // Process through LLM
    isProcessing = true;
    sendBtn.disabled = true;
    const typingEl = addTypingIndicator();

    try {
      const response = await llm.processMessage(text, api, (toolName, args) => {
        // Optional: could show tool calls in UI
      });

      removeTypingIndicator();
      if (response) {
        addMessage('assistant', response);
      }
    } catch (err) {
      removeTypingIndicator();
      addMessage('assistant', `Error: ${err.message}`);
    } finally {
      isProcessing = false;
      sendBtn.disabled = false;
    }
  }

  // ── Input handling ──

  function autoResizeInput() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
  }

  messageInput.addEventListener('input', autoResizeInput);

  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener('click', sendMessage);

  // ── Settings ──

  function openSettings() {
    document.getElementById('cfg-api-url').value = config.apiUrl;
    document.getElementById('cfg-api-key').value = config.apiKey;
    document.getElementById('cfg-llm-url').value = config.llmUrl;
    document.getElementById('cfg-llm-model').value = config.llmModel;
    document.getElementById('cfg-llm-key').value = config.llmApiKey;
    settingsModal.classList.remove('hidden');
  }

  function closeSettings() {
    settingsModal.classList.add('hidden');
  }

  settingsBtn.addEventListener('click', openSettings);
  settingsCancel.addEventListener('click', closeSettings);
  settingsModal.querySelector('.modal-overlay').addEventListener('click', closeSettings);

  settingsForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    config.apiUrl = document.getElementById('cfg-api-url').value || config.apiUrl;
    config.apiKey = document.getElementById('cfg-api-key').value || '';
    config.llmUrl = document.getElementById('cfg-llm-url').value || config.llmUrl;
    config.llmModel = document.getElementById('cfg-llm-model').value || config.llmModel;
    config.llmApiKey = document.getElementById('cfg-llm-key').value || '';

    saveConfig(config);

    // Reinitialize clients
    api = new SeabayAPI(config.apiUrl, config.apiKey);
    llm = new SeabayLLM(config.llmUrl, config.llmApiKey, config.llmModel);

    closeSettings();
    addSystemMessage('Settings saved. Reconnecting...');
    await initialize();
  });

  // ── Boot ──

  initialize();

})();
