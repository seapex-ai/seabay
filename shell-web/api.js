/**
 * Seabay API Client for Shell Web
 *
 * Mirrors the sdk-js client patterns adapted for the shell web UI.
 */

class SeabayAPI {
  /**
   * @param {string} baseUrl - Seabay API base URL
   * @param {string} apiKey  - Seabay API key
   */
  constructor(baseUrl = 'http://localhost:8000/v1', apiKey = '') {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.apiKey = apiKey;
  }

  /**
   * Core request method.
   * @param {string} method
   * @param {string} path
   * @param {object} [body]
   * @param {object} [params]
   * @returns {Promise<object>}
   */
  async request(method, path, body = null, params = null) {
    const url = new URL(`${this.baseUrl}${path}`);
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') {
          url.searchParams.set(k, String(v));
        }
      });
    }

    const headers = {
      'Content-Type': 'application/json',
    };
    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }

    const opts = { method, headers };
    if (body && method !== 'GET') {
      opts.body = JSON.stringify(body);
    }

    const resp = await fetch(url.toString(), opts);
    if (!resp.ok) {
      let errorBody;
      try {
        errorBody = await resp.json();
      } catch {
        errorBody = { error: { code: 'unknown', message: resp.statusText } };
      }
      throw new SeabayAPIError(
        resp.status,
        errorBody?.error?.code || 'unknown',
        errorBody?.error?.message || resp.statusText
      );
    }
    return resp.json();
  }

  // ── Agent ──

  getMyAgent() {
    return this.request('GET', '/agents/me');
  }

  getAgent(agentId) {
    return this.request('GET', `/agents/${agentId}`);
  }

  searchAgents(params = {}) {
    return this.request('GET', '/agents/search', null, params);
  }

  getPublicAgent(slug) {
    return this.request('GET', `/public/agents/${slug}`);
  }

  // ── Tasks ──

  createTask(toAgentId, taskType = 'service_request', description = '', extra = {}) {
    return this.request('POST', '/tasks', {
      to_agent_id: toAgentId,
      task_type: taskType,
      description,
      idempotency_key: `shell-web-${Date.now()}`,
      ...extra,
    });
  }

  getTask(taskId) {
    return this.request('GET', `/tasks/${taskId}`);
  }

  getInbox(params = {}) {
    return this.request('GET', '/tasks/inbox', null, params);
  }

  acceptTask(taskId) {
    return this.request('POST', `/tasks/${taskId}/accept`);
  }

  declineTask(taskId, reason = null) {
    return this.request('POST', `/tasks/${taskId}/decline`, { reason });
  }

  completeTask(taskId, rating = null, notes = null) {
    return this.request('POST', `/tasks/${taskId}/complete`, { rating, notes });
  }

  // ── Health ──

  health() {
    return this.request('GET', '/health');
  }
}


class SeabayAPIError extends Error {
  constructor(status, code, message) {
    super(`Seabay API Error (${status}): ${code} — ${message}`);
    this.status = status;
    this.code = code;
  }
}
