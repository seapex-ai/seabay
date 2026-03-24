/**
 * LLM Integration for Seabay Shell Web
 *
 * Connects to any OpenAI-compatible endpoint (configurable).
 */

const SEABAY_SYSTEM_PROMPT = `You are Seabay Shell, a natural language interface for the Seabay Agent platform.
Seabay is a cross-platform agent connection and collaboration control layer.

You help users:
- Find and discover agents (translation, summarization, scheduling, code review, research, etc.)
- Create tasks and send them to agents
- Check their inbox for incoming tasks
- Accept or decline tasks
- Monitor task status and get results

IMPORTANT RULES:
1. When the user wants to find an agent, use the search_agents tool first.
2. When the user wants to send work to an agent, use create_task.
3. When the user asks about their tasks, use check_inbox or get_task.
4. For high-risk operations (R2/R3), always ask for user confirmation.
5. Be conversational and helpful.
6. When showing results, be concise but include key details.
7. Always respond in the same language the user is using.
`;

const SEABAY_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'search_agents',
      description: 'Search for agents on the Seabay platform by skills, location, language, or keywords.',
      parameters: {
        type: 'object',
        properties: {
          q: { type: 'string', description: 'Free-text search query' },
          skills: { type: 'string', description: 'Comma-separated skills filter' },
          location: { type: 'string', description: 'Location filter' },
          language: { type: 'string', description: 'Language code filter' },
          agent_type: { type: 'string', enum: ['service', 'personal'], description: 'Agent type filter' },
        },
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'create_task',
      description: 'Create a new task and send it to a specific agent.',
      parameters: {
        type: 'object',
        properties: {
          to_agent_id: { type: 'string', description: 'Target agent ID' },
          task_type: { type: 'string', description: 'Task type', default: 'service_request' },
          description: { type: 'string', description: 'Task description' },
        },
        required: ['to_agent_id', 'description'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'check_inbox',
      description: "Check the user's task inbox.",
      parameters: {
        type: 'object',
        properties: {
          status: { type: 'string', description: 'Filter by status' },
          limit: { type: 'integer', description: 'Max items', default: 20 },
        },
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'get_task',
      description: 'Get detailed information about a specific task.',
      parameters: {
        type: 'object',
        properties: {
          task_id: { type: 'string', description: 'Task ID' },
        },
        required: ['task_id'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'accept_task',
      description: 'Accept an incoming task.',
      parameters: {
        type: 'object',
        properties: {
          task_id: { type: 'string', description: 'Task ID to accept' },
        },
        required: ['task_id'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'decline_task',
      description: 'Decline an incoming task.',
      parameters: {
        type: 'object',
        properties: {
          task_id: { type: 'string', description: 'Task ID to decline' },
          reason: { type: 'string', description: 'Decline reason' },
        },
        required: ['task_id'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'get_agent_profile',
      description: 'Get agent profile by ID or slug.',
      parameters: {
        type: 'object',
        properties: {
          agent_id: { type: 'string', description: 'Agent ID or slug' },
        },
        required: ['agent_id'],
      },
    },
  },
];


class SeabayLLM {
  /**
   * @param {string} baseUrl - OpenAI-compatible API URL
   * @param {string} apiKey  - LLM API key
   * @param {string} model   - Model name
   */
  constructor(baseUrl = 'https://api.openai.com/v1', apiKey = '', model = 'gpt-4o') {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.apiKey = apiKey;
    this.model = model;
    this.messages = [];
    this._initialized = false;
  }

  /** Initialize with system prompt and optional agent info. */
  initialize(agentInfo = null) {
    let prompt = SEABAY_SYSTEM_PROMPT;
    if (agentInfo) {
      prompt += `\n\nCurrent user agent: ${agentInfo.display_name} (@${agentInfo.slug})`;
      prompt += `\nAgent type: ${agentInfo.agent_type}`;
      prompt += `\nAgent ID: ${agentInfo.id}`;
    }
    this.messages = [{ role: 'system', content: prompt }];
    this._initialized = true;
  }

  get isConfigured() {
    return Boolean(this.apiKey && this.baseUrl);
  }

  /**
   * Send chat completion request.
   * @param {Array} messages
   * @returns {Promise<object>} - The first choice from the API response
   */
  async chatCompletion(messages) {
    const resp = await fetch(`${this.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        messages,
        tools: SEABAY_TOOLS,
        tool_choice: 'auto',
        temperature: 0.7,
        max_tokens: 2048,
      }),
    });

    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(`LLM API error (${resp.status}): ${err}`);
    }

    const data = await resp.json();
    return data.choices?.[0] || { message: { role: 'assistant', content: 'No response generated.' } };
  }

  /**
   * Process a user message — handles tool call loops.
   * @param {string} userMessage
   * @param {SeabayAPI} api - The API client for executing tool calls
   * @param {function} onToolCall - Callback(toolName, args) for UI feedback
   * @returns {Promise<string>} - Final assistant text response
   */
  async processMessage(userMessage, api, onToolCall = null) {
    if (!this._initialized) {
      this.initialize();
    }

    this.messages.push({ role: 'user', content: userMessage });

    const MAX_ROUNDS = 5;
    let rounds = 0;

    while (rounds < MAX_ROUNDS) {
      const choice = await this.chatCompletion(this.messages);
      const message = choice.message;

      // If no tool calls, return the text
      if (!message.tool_calls || message.tool_calls.length === 0) {
        const content = message.content || '';
        this.messages.push({ role: 'assistant', content });
        return content;
      }

      // Record assistant message with tool calls
      this.messages.push({
        role: 'assistant',
        content: message.content || '',
        tool_calls: message.tool_calls,
      });

      // Execute each tool call
      for (const tc of message.tool_calls) {
        const funcName = tc.function.name;
        let funcArgs;
        try {
          funcArgs = JSON.parse(tc.function.arguments);
        } catch {
          funcArgs = {};
        }

        if (onToolCall) onToolCall(funcName, funcArgs);

        const result = await executeSeabayTool(api, funcName, funcArgs);
        this.messages.push({
          role: 'tool',
          tool_call_id: tc.id,
          content: JSON.stringify(result),
        });
      }

      rounds++;
    }

    // If we hit max rounds, get a final text response
    const finalChoice = await this.chatCompletion(this.messages);
    const content = finalChoice.message?.content || 'I completed the requested operations.';
    this.messages.push({ role: 'assistant', content });
    return content;
  }

  /** Clear conversation history (keep system prompt). */
  clearHistory() {
    this.messages = this.messages.filter(m => m.role === 'system');
  }
}


/**
 * Execute a Seabay tool call against the API.
 * @param {SeabayAPI} api
 * @param {string} toolName
 * @param {object} args
 * @returns {Promise<object>}
 */
async function executeSeabayTool(api, toolName, args) {
  try {
    switch (toolName) {
      case 'search_agents': {
        const params = {};
        if (args.q) params.q = args.q;
        if (args.skills) params.skills = args.skills;
        if (args.location) params.location = args.location;
        if (args.language) params.language = args.language;
        if (args.agent_type) params.agent_type = args.agent_type;
        return await api.searchAgents(params);
      }
      case 'create_task':
        return await api.createTask(
          args.to_agent_id,
          args.task_type || 'service_request',
          args.description || ''
        );
      case 'check_inbox': {
        const params = {};
        if (args.status) params.status = args.status;
        if (args.limit) params.limit = String(args.limit);
        return await api.getInbox(params);
      }
      case 'get_task':
        return await api.getTask(args.task_id);
      case 'accept_task':
        return await api.acceptTask(args.task_id);
      case 'decline_task':
        return await api.declineTask(args.task_id, args.reason);
      case 'get_agent_profile':
        try {
          return await api.getAgent(args.agent_id);
        } catch {
          return await api.getPublicAgent(args.agent_id);
        }
      default:
        return { error: `Unknown tool: ${toolName}` };
    }
  } catch (err) {
    return { error: err.message || String(err) };
  }
}
