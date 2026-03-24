/**
 * Card Renderer for Seabay Shell Web
 *
 * Renders Seabay cards (task_approval, match_result, agent profiles, inbox)
 * as interactive HTML elements.
 */

class SeabayRenderer {
  /**
   * Render a task approval card.
   * @param {object} task
   * @param {object} callbacks - { onAccept(taskId), onDecline(taskId) }
   * @returns {HTMLElement}
   */
  static taskApprovalCard(task, callbacks = {}) {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="card-header">
        <span>Task Approval Required</span>
        <span class="badge risk-${(task.risk_level || 'r0').toLowerCase()}">${task.risk_level || 'R0'}</span>
      </div>
      <div class="card-body">
        <div class="card-field">
          <span class="label">Task ID</span>
          <span class="value">${SeabayRenderer.esc(task.id || '?')}</span>
        </div>
        <div class="card-field">
          <span class="label">Type</span>
          <span class="value">${SeabayRenderer.esc(task.task_type || '?')}</span>
        </div>
        <div class="card-field">
          <span class="label">From</span>
          <span class="value">${SeabayRenderer.esc(task.from_agent_id || '?')}</span>
        </div>
        ${task.description ? `
        <div class="card-field">
          <span class="label">Description</span>
          <span class="value">${SeabayRenderer.esc(task.description)}</span>
        </div>` : ''}
        <div class="card-field">
          <span class="label">Status</span>
          <span class="value"><span class="badge status-pending">${SeabayRenderer.esc(task.status || 'pending')}</span></span>
        </div>
      </div>
      <div class="card-actions">
        <button class="btn success accept-btn">Accept</button>
        <button class="btn danger decline-btn">Decline</button>
      </div>
    `;

    const acceptBtn = card.querySelector('.accept-btn');
    const declineBtn = card.querySelector('.decline-btn');

    acceptBtn.addEventListener('click', () => {
      acceptBtn.disabled = true;
      declineBtn.disabled = true;
      acceptBtn.textContent = 'Accepting...';
      if (callbacks.onAccept) callbacks.onAccept(task.id);
    });

    declineBtn.addEventListener('click', () => {
      acceptBtn.disabled = true;
      declineBtn.disabled = true;
      declineBtn.textContent = 'Declining...';
      if (callbacks.onDecline) callbacks.onDecline(task.id);
    });

    return card;
  }

  /**
   * Render match results with selectable candidates.
   * @param {Array} agents
   * @param {string} summary
   * @param {function} onSelect - callback(agentId)
   * @returns {HTMLElement}
   */
  static matchResultCard(agents, summary = '', onSelect = null) {
    const container = document.createElement('div');

    if (summary) {
      const summaryEl = document.createElement('p');
      summaryEl.style.marginBottom = '8px';
      summaryEl.textContent = summary;
      container.appendChild(summaryEl);
    }

    if (!agents || agents.length === 0) {
      const empty = document.createElement('p');
      empty.style.color = 'var(--text-secondary)';
      empty.textContent = 'No matches found.';
      container.appendChild(empty);
      return container;
    }

    agents.forEach((agent, idx) => {
      const card = document.createElement('div');
      card.className = 'card';
      card.style.marginBottom = '8px';

      const skills = (agent.skills || agent.profile?.skills || []);
      const skillsHtml = skills.length
        ? `<div class="skills-row">${skills.map(s => `<span class="skill-tag">${SeabayRenderer.esc(s)}</span>`).join('')}</div>`
        : '';

      const reasons = agent.why_matched || agent.reasons || [];
      const reasonsHtml = reasons.length
        ? `<ul class="reason-list">${reasons.map(r => `<li>${SeabayRenderer.esc(r)}</li>`).join('')}</ul>`
        : '';

      const agentRef = agent.agent_ref || agent.agent_id || agent.id || '?';
      const displayName = agent.display_name || 'Unknown';
      const verification = agent.verification || agent.verification_level || 'none';

      card.innerHTML = `
        <div class="card-header">
          <span>#${idx + 1} ${SeabayRenderer.esc(displayName)}</span>
          <span class="badge status-${agent.status === 'online' ? 'online' : 'offline'}">${SeabayRenderer.esc(verification)}</span>
        </div>
        <div class="card-body">
          <div class="card-field">
            <span class="label">Agent</span>
            <span class="value">${SeabayRenderer.esc(agentRef)}</span>
          </div>
          ${agent.location ? `<div class="card-field"><span class="label">Location</span><span class="value">${SeabayRenderer.esc(agent.location)}</span></div>` : ''}
          ${agent.last_active ? `<div class="card-field"><span class="label">Last Active</span><span class="value">${SeabayRenderer.esc(agent.last_active)}</span></div>` : ''}
          ${agent.success_rate_30d != null ? `<div class="card-field"><span class="label">Success Rate</span><span class="value">${Math.round(agent.success_rate_30d * 100)}%</span></div>` : ''}
          ${agent.match_score != null ? `<div class="card-field"><span class="label">Score</span><span class="value">${agent.match_score.toFixed(1)}</span></div>` : ''}
          ${skillsHtml}
          ${reasonsHtml}
        </div>
        ${onSelect ? '<div class="card-actions"><button class="btn primary select-btn">Select This Agent</button></div>' : ''}
      `;

      if (onSelect) {
        card.querySelector('.select-btn').addEventListener('click', () => {
          onSelect(agentRef);
        });
      }

      container.appendChild(card);
    });

    return container;
  }

  /**
   * Render a task detail card.
   * @param {object} task
   * @returns {HTMLElement}
   */
  static taskDetailCard(task) {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="card-header">
        <span>Task Details</span>
        <span class="badge risk-${(task.risk_level || 'r0').toLowerCase()}">${task.risk_level || 'R0'}</span>
      </div>
      <div class="card-body">
        <div class="card-field"><span class="label">Task ID</span><span class="value">${SeabayRenderer.esc(task.id || '?')}</span></div>
        <div class="card-field"><span class="label">Type</span><span class="value">${SeabayRenderer.esc(task.task_type || '?')}</span></div>
        <div class="card-field"><span class="label">Status</span><span class="value"><span class="badge status-${SeabayRenderer.statusClass(task.status)}">${SeabayRenderer.esc(task.status || '?')}</span></span></div>
        <div class="card-field"><span class="label">From</span><span class="value">${SeabayRenderer.esc(task.from_agent_id || '?')}</span></div>
        <div class="card-field"><span class="label">To</span><span class="value">${SeabayRenderer.esc(task.to_agent_id || '?')}</span></div>
        ${task.description ? `<div class="card-field"><span class="label">Description</span><span class="value">${SeabayRenderer.esc(task.description)}</span></div>` : ''}
        ${task.created_at ? `<div class="card-field"><span class="label">Created</span><span class="value">${SeabayRenderer.esc(task.created_at)}</span></div>` : ''}
      </div>
    `;
    return card;
  }

  /**
   * Render an agent profile card.
   * @param {object} agent
   * @returns {HTMLElement}
   */
  static agentProfileCard(agent) {
    const profile = agent.profile || {};
    const skills = profile.skills || [];
    const languages = profile.languages || [];

    const card = document.createElement('div');
    card.className = 'card';

    const skillsHtml = skills.length
      ? `<div class="skills-row">${skills.map(s => `<span class="skill-tag">${SeabayRenderer.esc(s)}</span>`).join('')}</div>`
      : '';

    card.innerHTML = `
      <div class="card-header">
        <span>${SeabayRenderer.esc(agent.display_name || 'Unknown')}</span>
        <span class="badge status-${agent.status === 'online' ? 'online' : 'offline'}">${SeabayRenderer.esc(agent.status || 'offline')}</span>
      </div>
      <div class="card-body">
        <div class="card-field"><span class="label">Slug</span><span class="value">@${SeabayRenderer.esc(agent.slug || '?')}</span></div>
        <div class="card-field"><span class="label">Type</span><span class="value">${SeabayRenderer.esc(agent.agent_type || '?')}</span></div>
        <div class="card-field"><span class="label">Verification</span><span class="value">${SeabayRenderer.esc(agent.verification_level || 'none')}</span></div>
        ${profile.bio ? `<div class="card-field"><span class="label">Bio</span><span class="value">${SeabayRenderer.esc(profile.bio)}</span></div>` : ''}
        ${profile.location_city ? `<div class="card-field"><span class="label">Location</span><span class="value">${SeabayRenderer.esc(profile.location_city)}${profile.location_country ? ', ' + SeabayRenderer.esc(profile.location_country) : ''}</span></div>` : ''}
        ${languages.length ? `<div class="card-field"><span class="label">Languages</span><span class="value">${SeabayRenderer.esc(languages.join(', '))}</span></div>` : ''}
        ${skillsHtml}
      </div>
    `;
    return card;
  }

  /**
   * Render inbox task list.
   * @param {Array} tasks
   * @param {boolean} hasMore
   * @param {object} callbacks - { onAccept(id), onDecline(id) }
   * @returns {HTMLElement}
   */
  static inboxCard(tasks, hasMore = false, callbacks = {}) {
    const container = document.createElement('div');

    if (!tasks || tasks.length === 0) {
      const empty = document.createElement('p');
      empty.style.color = 'var(--text-secondary)';
      empty.textContent = 'Inbox is empty.';
      container.appendChild(empty);
      return container;
    }

    tasks.forEach(task => {
      const card = document.createElement('div');
      card.className = 'card';
      card.style.marginBottom = '8px';

      const needsAction = task.status === 'pending_accept';

      card.innerHTML = `
        <div class="card-body" style="padding: 10px 14px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <strong>${SeabayRenderer.esc(task.task_type || '?')}</strong>
              <span class="badge risk-${(task.risk_level || 'r0').toLowerCase()}" style="margin-left: 6px;">${task.risk_level || 'R0'}</span>
            </div>
            <span class="badge status-${SeabayRenderer.statusClass(task.status)}">${SeabayRenderer.esc(task.status || '?')}</span>
          </div>
          ${task.description ? `<p style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">${SeabayRenderer.esc(task.description.substring(0, 100))}</p>` : ''}
        </div>
        ${needsAction ? `
        <div class="card-actions">
          <button class="btn success accept-btn" style="font-size: 11px; padding: 4px 12px;">Accept</button>
          <button class="btn danger decline-btn" style="font-size: 11px; padding: 4px 12px;">Decline</button>
        </div>` : ''}
      `;

      if (needsAction) {
        card.querySelector('.accept-btn')?.addEventListener('click', () => {
          if (callbacks.onAccept) callbacks.onAccept(task.id);
        });
        card.querySelector('.decline-btn')?.addEventListener('click', () => {
          if (callbacks.onDecline) callbacks.onDecline(task.id);
        });
      }

      container.appendChild(card);
    });

    if (hasMore) {
      const more = document.createElement('p');
      more.style.cssText = 'font-size: 12px; color: var(--text-secondary); text-align: center; margin-top: 8px;';
      more.textContent = '... more tasks available';
      container.appendChild(more);
    }

    return container;
  }

  // ── Utility ──

  static esc(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  static statusClass(status) {
    if (['completed'].includes(status)) return 'completed';
    if (['pending_accept', 'pending_delivery', 'in_progress', 'accepted', 'delivered'].includes(status)) return 'pending';
    if (['failed', 'declined'].includes(status)) return 'failed';
    return 'offline';
  }
}
