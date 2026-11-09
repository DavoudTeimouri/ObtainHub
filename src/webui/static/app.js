/**
 * ObtainHub WebUI - Application JavaScript
 * Powers the professional single-page application interface.
 */

class ObtainHubUI {
  constructor() {
    this.token = localStorage.getItem('ohub_token') || null;
    this.currentPage = 'dashboard';
    this.pollInterval = null;
    this.authRequired = false;
    this.appsTab = 'list';
    this.installedRepos = new Set();
    this.init();
  }

  init() {
    this.setupNavigation();
    window.addEventListener('hashchange', () => this.route());
    this.loadAuthMode().then(() => this.route());
  }

  // Fetch /config (public) to learn whether the server runs with --auth.
  // When it does and there is no session token, all page fields stay locked.
  async loadAuthMode() {
    try {
      const cfg = await this.api('/config');
      this.authRequired = !!cfg.auth_required;
    } catch (e) { /* keep default: unlocked */ }
    this.applyLock();
  }

  applyLock() {
    const locked = this.authRequired && !this.token;
    document.body.classList.toggle('locked', locked);
    const hint = document.getElementById('signinHint');
    if (hint) hint.style.display = locked ? 'block' : 'none';
    // Only disable mutating form buttons; per-app action buttons stay enabled
    // so the backend 401 can guide the user to sign in. Tooltips explain lock.
    document.querySelectorAll('main .page button[type="submit"], main .page .btn-primary, main .page .btn-danger')
      .forEach(el => { el.disabled = locked; });
    // Add/remove lock tooltip on per-app action buttons
    document.querySelectorAll('main .page .action-btn').forEach(el => {
      if (locked) {
        el.title = 'Sign in required to perform this action';
        el.dataset.originalTitle = el.title || el.textContent;
      } else {
        el.title = el.dataset.originalTitle || '';
        delete el.dataset.originalTitle;
      }
    });
  }

  setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const page = item.getAttribute('data-page');
        if (item.classList.contains('disabled')) return;
        this.navigate(page);
      });
    });

    // Menu toggle for mobile
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    if (menuToggle && sidebar) {
      menuToggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
      });
    }

    // Refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        this.refreshCurrentPage();
      });
    }

    // Login form — Windows admin credentials
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
      loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const username = document.getElementById('loginUser').value.trim();
        const password = document.getElementById('loginPass').value;
        this.loginWithCredentials(username, password);
      });
    }

    // Sign in as the Windows account running ohub (no password)
    const loginCurrentUserBtn = document.getElementById('loginCurrentUserBtn');
    if (loginCurrentUserBtn) {
      loginCurrentUserBtn.addEventListener('click', () => this.loginAsCurrentUser());
    }

    // Apps page sub-tabs (List / Search & Install / Check / Update / Uninstall / Remove / Add / Sources)
    document.querySelectorAll('#appsTabs [data-apps-tab]').forEach(btn => {
      btn.addEventListener('click', () => this.showAppsTab(btn.getAttribute('data-apps-tab')));
    });

    // Command feature forms
    const wire = (id, handler) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('submit', (e) => { e.preventDefault(); handler(); });
    };
    wire('checkForm', () => this.checkAppForm());
    wire('updateForm', () => this.updateAppForm());
    wire('uninstallForm', () => this.uninstallAppForm());
    wire('removeForm', () => this.removeAppForm());
    wire('addForm', () => this.addAppForm());
    // Clear result blocks
    ['check','update','uninstall','remove','add'].forEach(cmd => {
      const btn = document.getElementById('clear' + cmd.charAt(0).toUpperCase() + cmd.slice(1) + 'Result');
      if (btn) btn.addEventListener('click', () => {
        document.getElementById(cmd + 'ResultWrap').classList.add('hidden');
        document.getElementById(cmd + 'Result').textContent = '';
      });
    });

    // Token fallback login
    const tokenLoginForm = document.getElementById('tokenLoginForm');
    if (tokenLoginForm) {
      tokenLoginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const token = document.getElementById('authToken').value.trim();
        this.login(token);
      });
    }
    const useTokenLink = document.getElementById('useTokenLink');
    if (useTokenLink) {
      useTokenLink.addEventListener('click', (e) => {
        e.preventDefault();
        loginForm.classList.add('hidden');
        tokenLoginForm.classList.remove('hidden');
      });
    }

    // Doctor / State Export / Logs buttons
    const doctorBtn = document.getElementById('doctorBtn');
    if (doctorBtn) doctorBtn.addEventListener('click', () => this.runDoctor());
    const stateBtn = document.getElementById('stateBtn');
    if (stateBtn) stateBtn.addEventListener('click', () => this.exportState());
    const logsBtn = document.getElementById('logsBtn');
    if (logsBtn) logsBtn.addEventListener('click', () => this.loadLogs());

    // Modal close
    const modalClose = document.getElementById('modalClose');
    const modalBackdrop = document.getElementById('modalBackdrop');
    const modalCancel = document.getElementById('modalCancel');
    const closeModal = () => {
      const modal = document.getElementById('loginModal');
      if (modal) modal.classList.add('hidden');
      const app = document.querySelector('.app');
      if (app) app.classList.remove('blur-bg');
      // Clear password fields after cancel/close
      const pass = document.getElementById('loginPass');
      if (pass) pass.value = '';
    };
    if (modalClose) modalClose.addEventListener('click', closeModal);
    if (modalBackdrop) modalBackdrop.addEventListener('click', closeModal);
    if (modalCancel) modalCancel.addEventListener('click', closeModal);

    // Download form toggle
    const showDownloadForm = document.getElementById('showDownloadForm');
    const hideDownloadForm = document.getElementById('hideDownloadForm');
    const downloadForm = document.getElementById('downloadForm');
    if (showDownloadForm && downloadForm) {
      showDownloadForm.addEventListener('click', (e) => {
        e.preventDefault();
        downloadForm.classList.remove('hidden');
      });
    }
    if (hideDownloadForm && downloadForm) {
      hideDownloadForm.addEventListener('click', (e) => {
        e.preventDefault();
        downloadForm.classList.add('hidden');
      });
    }

    // Download form submit
    const downloadFormEl = document.getElementById('downloadForm');
    if (downloadFormEl) {
      downloadFormEl.addEventListener('submit', (e) => {
        e.preventDefault();
        const url = document.getElementById('downloadUrl').value.trim();
        const dest = document.getElementById('downloadDest').value.trim();
        const label = document.getElementById('downloadLabel').value.trim() || undefined;
        const token = document.getElementById('downloadToken').value.trim() || undefined;
        this.startDownload(url, dest, label, token);
      });
    }

    // Search form (Apps page)
    const searchForm = document.getElementById('searchForm');
    if (searchForm) {
      searchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.searchApps();
      });
    }

    // Apps page buttons
    const checkAllBtn = document.getElementById('checkAllBtn');
    if (checkAllBtn) checkAllBtn.addEventListener('click', () => this.checkAllApps());
    const refreshAppsBtn = document.getElementById('refreshAppsBtn');
    if (refreshAppsBtn) refreshAppsBtn.addEventListener('click', () => this.loadApps());

    // Source form (Apps page)
    const showSourceForm = document.getElementById('showSourceForm');
    const hideSourceForm = document.getElementById('hideSourceForm');
    const sourceForm = document.getElementById('sourceForm');
    if (showSourceForm && sourceForm) {
      showSourceForm.addEventListener('click', (e) => { e.preventDefault(); sourceForm.classList.remove('hidden'); });
    }
    if (hideSourceForm && sourceForm) {
      hideSourceForm.addEventListener('click', (e) => { e.preventDefault(); sourceForm.classList.add('hidden'); });
    }
    if (sourceForm) {
      sourceForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.addSource();
      });
    }

    // GitHub token form (Config page)
    const tokenForm = document.getElementById('tokenForm');
    if (tokenForm) {
      tokenForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.saveConfigToken();
      });
    }
    const deleteTokenBtn = document.getElementById('deleteTokenBtn');
    if (deleteTokenBtn) {
      deleteTokenBtn.addEventListener('click', () => this.deleteConfigToken());
    }
  }

  navigate(page) {
    this.currentPage = page;
    window.location.hash = '#/' + page;

    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.remove('active');
      if (item.getAttribute('data-page') === page) item.classList.add('active');
    });

    // Update pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const target = document.getElementById('page-' + page);
    if (target) target.classList.add('active');

    // Update header
    const titleEl = document.getElementById('headerTitle');
    if (titleEl) titleEl.textContent = page.charAt(0).toUpperCase() + page.slice(1);

    // Close mobile sidebar
    const sidebar = document.getElementById('sidebar');
    if (sidebar) sidebar.classList.remove('open');

    // Setup auth UI and load page data
    this.setupAuthUI();
    if (page === 'dashboard') this.loadDashboard();
    else if (page === 'apps') { this.showAppsTab(this.appsTab); }
    else if (page === 'config') this.loadConfig();
    else if (page === 'downloads') {
      this.loadDownloads();
      this.startDownloadsPoll();
    } else if (page === 'help') {
      this.loadHelp();
    } else if (page === 'doctor') {
      // doctor page loads on demand via button
    } else if (page === 'state') {
      // state page loads on demand via button
    } else if (page === 'logs') {
      this.loadLogs();
    } else {
      this.stopDownloadsPoll();
    }
  }

  route() {
    const hash = window.location.hash.replace('#/', '') || 'dashboard';
    this.navigate(hash);
  }

  refreshCurrentPage() {
    switch (this.currentPage) {
      case 'dashboard': this.loadDashboard(); break;
      case 'apps': this.showAppsTab(this.appsTab); break;
      case 'config': this.loadConfig(); break;
      case 'downloads': this.loadDownloads(); break;
      case 'help': this.loadHelp(); break;
    }
    this.showToast('Refreshed', 'info');
  }

  showAppsTab(name) {
    this.appsTab = name;
    document.querySelectorAll('#appsTabs [data-apps-tab]').forEach(b => {
      b.classList.toggle('active', b.getAttribute('data-apps-tab') === name);
    });
    document.querySelectorAll('.apps-panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById('appsTab-' + name);
    if (panel) panel.classList.add('active');
    if (name === 'list') this.loadApps();
    else if (name === 'sources') this.loadSources();
    else if (name === 'search') {
      const q = document.getElementById('searchQuery');
      if (q) q.focus();
    }
  }

  setupAuthUI() {
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const loginBtn = document.getElementById('loginBtn');
    const authItems = document.querySelectorAll('.nav-item.auth-required');

    if (this.token) {
      if (statusDot) statusDot.className = 'status-dot authenticated';
      if (statusText) statusText.textContent = 'Authenticated';
      if (loginBtn) {
        loginBtn.textContent = 'Logout';
        loginBtn.onclick = () => this.logout();
        loginBtn.className = 'btn btn-secondary btn-sm';
      }
      authItems.forEach(el => el.classList.remove('disabled'));
    } else {
      if (statusDot) statusDot.className = 'status-dot';
      if (statusText) statusText.textContent = 'Not authenticated';
      if (loginBtn) {
        loginBtn.textContent = 'Login';
        loginBtn.onclick = () => this.showLoginModal();
        loginBtn.className = 'btn btn-secondary btn-sm';
      }
      authItems.forEach(el => el.classList.add('disabled'));
    }
    this.applyLock();
  }

  showLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) modal.classList.remove('hidden');
    const app = document.querySelector('.app');
    if (app) app.classList.add('blur-bg');
  }

  hideLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) modal.classList.add('hidden');
    const app = document.querySelector('.app');
    if (app) app.classList.remove('blur-bg');
    const pass = document.getElementById('loginPass');
    if (pass) pass.value = '';
  }

  async api(endpoint, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (this.token) headers['Authorization'] = 'Bearer ' + this.token;
    const config = { ...options, headers };
    if (config.body && typeof config.body === 'object') config.body = JSON.stringify(config.body);

    try {
      const res = await fetch(endpoint, config);
      if (res.status === 401) {
        this.stopDownloadsPoll();
        localStorage.removeItem('ohub_token');
        this.token = null;
        this.setupAuthUI();
        this.applyLock();
        this.showLoginModal();
        throw new Error('Authentication required');
      }
      if (!res.ok) {
        const errText = await res.text().catch(() => '');
        throw new Error(errText || `HTTP ${res.status}`);
      }
      const ct = res.headers.get('content-type') || '';
      if (ct.includes('application/json')) return res.json();
      return res.text();
    } catch (err) {
      if (err.message === 'Authentication required') throw err;
      throw new Error('Failed to fetch ' + endpoint + ': ' + err.message);
    }
  }

  showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <div class="toast-icon">${this.getToastIcon(type)}</div>
      <div class="toast-message">${this.escapeHtml(message)}</div>
      <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
  }

  getToastIcon(type) {
    const icons = {
      success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',
      error: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
      warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
      info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="8"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };
    return icons[type] || icons.info;
  }

  escapeHtml(text) {
    if (text == null) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }

  formatBytes(bytes) {
    if (!bytes && bytes !== 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
    return parseFloat((Math.abs(bytes) / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  formatRelativeTime(isoString) {
    if (!isoString) return '-';
    try {
      const d = new Date(isoString);
      const now = new Date();
      const diffMs = now - d;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);
      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      return `${diffDays}d ago`;
    } catch (e) {
      return isoString;
    }
  }

  // ---- Dashboard ----
  async loadDashboard() {
    try {
      const [apps, config] = await Promise.all([
        this.api('/apps'),
        this.api('/config')
      ]);
      // Show server URL so user can verify they're on the right port
      const serverUrlEl = document.getElementById('serverUrlValue');
      if (serverUrlEl) serverUrlEl.textContent = window.location.origin;

      // Update stat cards
      const statApps = document.getElementById('statApps');
      const statDownloads = document.getElementById('statDownloads');
      const statUpdates = document.getElementById('statUpdates');

      if (statApps) statApps.textContent = apps ? apps.length : 0;
      if (statDownloads) statDownloads.textContent = '0'; // Downloads not tracked yet
      if (statUpdates) statUpdates.textContent = '0'; // Will be updated by check

      // Recent activity
      const activityList = document.getElementById('activityList');
      if (activityList) {
        activityList.innerHTML = '';
        if (apps && apps.length > 0) {
          apps.slice(0, 5).forEach(app => {
            const item = document.createElement('div');
            item.className = 'activity-item';
            item.innerHTML = `
              <div class="activity-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
              </div>
              <div class="activity-content">
                <div class="activity-title">${this.escapeHtml(app.repo)}</div>
                <div class="activity-meta">v${this.escapeHtml(app.version)} &bull; ${this.formatRelativeTime(app.installed_at)}</div>
              </div>
            `;
            activityList.appendChild(item);
          });
        } else {
          activityList.innerHTML = '<div class="empty-state">No recent activity</div>';
        }
      }
    } catch (err) {
      this.showToast('Failed to load dashboard: ' + err.message, 'error');
    }
  }

  // ---- Apps ----
  async loadApps() {
    this.installedRepos = this.installedRepos || new Set();
    this.installedRepos.clear();
    const tbody = document.getElementById('appsTableBody');
    if (!tbody) return;
    try {
      const apps = await this.api('/apps');
      if (!apps || apps.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No managed applications. Search GitHub above and install one.</td></tr>';
        return;
      }
      tbody.innerHTML = '';
      apps.forEach(app => {
        this.installedRepos.add(app.repo);
        const tr = document.createElement('tr');
        const statusClass = 'status-' + (app.status || 'unknown').toLowerCase();
        const repo = this.escapeHtml(app.repo);
        const updateBadge = app.update_available
          ? '<span class="badge badge-update">Update available</span>'
          : '<span class="badge badge-neutral">-</span>';
        tr.innerHTML =
          '<td><code>' + repo + '</code></td>' +
          '<td>' + this.escapeHtml(app.name) + '</td>' +
          '<td><code>' + this.escapeHtml(app.version) + '</code></td>' +
          '<td><span class="badge badge-' + statusClass + '">' + this.escapeHtml(app.status) + '</span></td>' +
          '<td>' + updateBadge + '</td>' +
          '<td>' + this.formatRelativeTime(app.installed_at) + '</td>' +
          '<td>' + this.formatRelativeTime(app.updated_at) + '</td>' +
          '<td class="actions-cell">' +
            '<button class="action-btn" onclick="app.checkApp(\'' + repo + '\')">Check</button> ' +
            '<button class="action-btn" onclick="app.updateApp(\'' + repo + '\')">Update</button> ' +
            '<button class="action-btn" onclick="app.uninstallApp(\'' + repo + '\')">Uninstall</button> ' +
            '<button class="action-btn btn-danger" onclick="app.removeApp(\'' + repo + '\')">Remove</button>' +
          '</td>';
        tbody.appendChild(tr);
      });
    } catch (err) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Failed to load apps: ' + this.escapeHtml(err.message) + '</td></tr>';
    }
  }

  // GitHub API actions need a token — remind and guide instead of failing.
  // If auth is not required (no --auth and no token configured), proceed without token.
  async requireToken() {
    if (!this.authRequired) return true;
    try {
      const config = await this.api('/config');
      if (config && config.has_token) return true;
    } catch (e) {
      // /config is public; if it fails, the server may be unreachable.
      // Don't navigate away — just warn and let the call fail naturally.
      this.showToast('Server not reachable: ' + e.message, 'error');
      return false;
    }
    this.showToast('GitHub token required — add it in Configuration, GitHub Token (or run: ohub config set github_token <token>)', 'warning');
    this.navigate('config');
    return false;
  }

  async searchApps() {
    if (!(await this.requireToken())) return;
    const q = document.getElementById('searchQuery').value.trim();
    if (!q) { this.showToast('Enter a search query', 'error'); return; }
    const limit = document.getElementById('searchLimit').value || 10;
    const minStars = document.getElementById('searchMinStars').value || 0;
    const activeOnly = document.getElementById('searchActiveOnly').checked;
    const btn = document.getElementById('searchBtn');
    btn.disabled = true;
    btn.textContent = 'Searching...';
    try {
      const params = new URLSearchParams({ q: q, limit: limit, min_stars: minStars, active_only: activeOnly ? 'true' : 'false' });
      const results = await this.api('/search?' + params.toString());
      const wrap = document.getElementById('searchResultsWrap');
      const tbody = document.getElementById('searchResultsBody');
      wrap.classList.remove('hidden');
      if (!results || results.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No results</td></tr>';
      } else {
        tbody.innerHTML = '';
        results.forEach(r => {
          const tr = document.createElement('tr');
          const repo = this.escapeHtml(r.full_name);
          const installed = this.installedRepos && this.installedRepos.has(r.full_name);
          tr.innerHTML =
            '<td><a href="' + this.escapeHtml(r.html_url) + '" target="_blank" rel="noopener"><code>' + repo + '</code></a></td>' +
            '<td>' + this.escapeHtml(r.description || '') + '</td>' +
            '<td>' + r.stargazers_count + '</td>' +
            '<td>' + this.escapeHtml(r.language || '-') + '</td>' +
            '<td>' + this.formatRelativeTime(r.updated_at) + '</td>' +
            '<td><span class="badge ' + (installed ? 'badge-success' : 'badge-neutral') + '">' + (installed ? 'Installed' : '-') + '</span></td>' +
            '<td><button class="action-btn action-btn-primary" onclick="app.installApp(\'' + repo + '\')">' + (installed ? 'Manage' : 'Install') + '</button></td>';
          tbody.appendChild(tr);
        });
      }
    } catch (err) {
      this.showToast('Search failed: ' + err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Search';
    }
  }

  async installApp(repo) {
    if (!(await this.requireToken())) return;
    if (!confirm('Install ' + repo + '?')) return;
    this.showToast('Installing ' + repo + '...', 'info');
    try {
      await this.api('/apps/install', { method: 'POST', body: { repo: repo } });
      this.showToast('Installed: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Install failed: ' + err.message, 'error');
    }
  }

  async updateApp(repo) {
    if (!(await this.requireToken())) return;
    this.showToast('Updating ' + repo + '...', 'info');
    try {
      await this.api('/apps/update', { method: 'POST', body: { repo: repo } });
      this.showToast('Update complete: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Update failed: ' + err.message, 'error');
    }
  }

  async checkApp(repo) {
    if (!(await this.requireToken())) return;
    try {
      await this.api('/apps/check', { method: 'POST', body: { repo: repo } });
      this.showToast('Checked: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Check failed: ' + err.message, 'error');
    }
  }

  async checkAllApps() {
    if (!(await this.requireToken())) return;
    const btn = document.getElementById('checkAllBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Checking...'; }
    try {
      const apps = await this.api('/apps');
      for (const a of (apps || [])) {
        await this.api('/apps/check', { method: 'POST', body: { repo: a.repo } }).catch(() => {});
      }
      this.showToast('Update check complete for all apps', 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Check failed: ' + err.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Check All Updates'; }
    }
  }

  async uninstallApp(repo) {
    if (!(await this.requireToken())) return;
    if (!confirm('Uninstall ' + repo + '? (stays managed)')) return;
    try {
      await this.api('/apps/uninstall', { method: 'POST', body: { repo: repo, purge: false } });
      this.showToast('Uninstalled: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Uninstall failed: ' + err.message, 'error');
    }
  }

  async removeApp(repo) {
    if (!confirm('Remove ' + repo + ' from management?')) return;
    try {
      await this.api('/apps/' + encodeURIComponent(repo), { method: 'DELETE' });
      this.showToast('App removed: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Failed to remove app: ' + err.message, 'error');
    }
  }

  async runAppAction(form, endpoint, method, successMsg) {
    if (!(await this.requireToken())) return;
    const btn = document.getElementById(form.replace('Form', 'Btn'));
    const originalLabel = btn.textContent;
    const out = document.getElementById(form.replace('Form', 'Result'));
    const wrap = document.getElementById(form.replace('Form', 'ResultWrap'));
    btn.disabled = true; btn.textContent = 'Working...';
    out.textContent = '';
    wrap.classList.add('hidden');
    try {
      const body = {};
      if (method !== 'DELETE') {
        document.getElementById(form).querySelectorAll('input, select').forEach(el => {
          if (el.type === 'checkbox') {
            body[el.id] = el.checked;
          } else if (el.value.trim() !== '') {
            // Map form field IDs to backend field names.
            let key = el.id;
            if (key === 'checkRepo') key = 'repo';
            else if (key === 'updateRepo') key = 'repo';
            else if (key === 'uninstallRepo') key = 'repo';
            else if (key === 'removeRepo') key = 'repo';
            else if (key === 'addRepo') key = 'repo';
            body[key] = el.value.trim();
          }
        });
        // For Check form: if "Check all managed apps" is checked, send empty repo
        // so the backend checks all managed apps (backend handles empty repo as check-all).
        if (form === 'checkForm' && body.checkAll) {
          body.repo = body.repo || '';
        }
      }
      await this.api(endpoint, { method: method, body: method !== 'DELETE' ? body : undefined });
      out.textContent = successMsg;
      wrap.classList.remove('hidden');
      this.showToast(successMsg, 'success');
      this.loadApps();
    } catch (err) {
      out.textContent = 'Error: ' + err.message;
      wrap.classList.remove('hidden');
      this.showToast('Action failed: ' + err.message, 'error');
    } finally {
      btn.disabled = false; btn.textContent = originalLabel;
    }
  }

  async checkAppForm() { await this.runAppAction('checkForm', '/apps/check', 'POST', 'Check complete'); }
  async updateAppForm() { await this.runAppAction('updateForm', '/apps/update', 'POST', 'Update complete'); }
  async uninstallAppForm() { await this.runAppAction('uninstallForm', '/apps/uninstall', 'POST', 'Uninstalled'); }
  async removeAppForm() { await this.runAppAction('removeForm', '/apps/' + encodeURIComponent(document.getElementById('removeRepo').value.trim()), 'DELETE', 'Removed from management'); }
  async addAppForm() { await this.runAppAction('addForm', '/apps', 'POST', 'Added to management'); }

  // ---- Config ----
  async loadConfig() {
    const loading = document.getElementById('configLoading');
    const wrap = document.getElementById('configTableWrap');
    try {
      const config = await this.api('/config');
      if (loading) loading.classList.add('hidden');
      if (wrap) wrap.classList.remove('hidden');

      // Token reminder banner
      const banner = document.getElementById('tokenBanner');
      if (banner) banner.classList.toggle('hidden', !!config.has_token);
      const badge = document.getElementById('tokenStatusBadge');
      if (badge) {
        badge.textContent = config.has_token ? 'configured' : 'not set';
        badge.className = 'badge ' + (config.has_token ? 'badge-success' : 'badge-warning');
      }
      const delBtn = document.getElementById('deleteTokenBtn');
      if (delBtn) delBtn.classList.toggle('hidden', !config.has_token);

      // Build editable config fields. Key = backend field name, value = current value.
      const fields = [
        { section: 'configDirs', label: 'Install Dir', key: 'install_dir', type: 'text', value: config.install_dir },
        { section: 'configDirs', label: 'Download Dir', key: 'download_dir', type: 'text', value: config.download_dir },
        { section: 'configDirs', label: 'Shim Dir', key: 'shim_dir', type: 'text', value: config.shim_dir },
        { section: 'configNetwork', label: 'Proxy', key: 'proxy', type: 'text', value: config.proxy || '' },
        { section: 'configNetwork', label: 'HTTP Retries', key: 'http_retries', type: 'number', value: config.http_retries },
        { section: 'configNetwork', label: 'HTTP Retry Delay (ms)', key: 'http_retry_delay_ms', type: 'number', value: config.http_retry_delay_ms },
        { section: 'configNetwork', label: 'HTTP Retry Backoff', key: 'http_retry_backoff', type: 'number', value: config.http_retry_backoff, step: '0.1' },
        { section: 'configNetwork', label: 'Bandwidth Limit (B/s)', key: 'download_bandwidth_limit', type: 'number', value: config.download_bandwidth_limit || '' },
        { section: 'configBehavior', label: 'Parallel Downloads', key: 'parallel_downloads', type: 'number', value: config.parallel_downloads },
        { section: 'configBehavior', label: 'Timeout (s)', key: 'timeout_seconds', type: 'number', value: config.timeout_seconds },
        { section: 'configBehavior', label: 'Auto Cleanup', key: 'auto_cleanup', type: 'checkbox', value: config.auto_cleanup },
        { section: 'configBehavior', label: 'Verify Checksums', key: 'verify_checksums', type: 'checkbox', value: config.verify_checksums },
        { section: 'configSchedule', label: 'Schedule Enabled', key: 'schedule_enabled', type: 'checkbox', value: config.schedule_enabled },
        { section: 'configSchedule', label: 'Interval (h)', key: 'schedule_interval_hours', type: 'number', value: config.schedule_interval_hours },
        { section: 'configSchedule', label: 'Notify on Update', key: 'schedule_notify_on_update', type: 'checkbox', value: config.schedule_notify_on_update },
        { section: 'configSchedule', label: 'Run on Startup', key: 'schedule_run_on_startup', type: 'checkbox', value: config.schedule_run_on_startup },
        { section: 'configAdvanced', label: 'Update Check Interval (h)', key: 'update_check_interval_hours', type: 'number', value: config.update_check_interval_hours },
      ];

      // Group fields by section
      const bySection = {};
      fields.forEach(f => {
        if (!bySection[f.section]) bySection[f.section] = [];
        bySection[f.section].push(f);
      });

      Object.entries(bySection).forEach(([sectionId, entries]) => {
        const dl = document.getElementById(sectionId);
        if (!dl) return;
        dl.innerHTML = '';
        entries.forEach(f => {
          const dt = document.createElement('dt');
          dt.textContent = f.label;
          const dd = document.createElement('dd');
          let input;
          if (f.type === 'checkbox') {
            input = document.createElement('input');
            input.type = 'checkbox';
            input.checked = f.value === true;
            input.id = 'cfg_' + f.key;
          } else {
            input = document.createElement('input');
            input.type = f.type;
            input.value = f.value;
            input.id = 'cfg_' + f.key;
            if (f.step) input.step = f.step;
          }
          dd.appendChild(input);
          dl.appendChild(dt);
          dl.appendChild(dd);
        });
      });

      // Add Save button if not already present
      if (!document.getElementById('configSaveBtn')) {
        const saveBtn = document.createElement('button');
        saveBtn.id = 'configSaveBtn';
        saveBtn.type = 'button';
        saveBtn.className = 'btn btn-primary';
        saveBtn.textContent = 'Save Changes';
        saveBtn.onclick = () => this.saveConfig();
        wrap.parentNode.insertBefore(saveBtn, wrap.nextSibling);
      }

      // Read-only info sections
      const readOnly = {
        configGroups: [
          ['Groups', config.groups && config.groups.length ? config.groups.join(', ') : 'none'],
          ['Token Source', config.token_source || 'not set']
        ]
      };
      Object.entries(readOnly).forEach(([sectionId, entries]) => {
        const dl = document.getElementById(sectionId);
        if (!dl) return;
        dl.innerHTML = '';
        entries.forEach(([key, value]) => {
          const dt = document.createElement('dt');
          dt.textContent = key;
          const dd = document.createElement('dd');
          dd.textContent = value;
          dl.appendChild(dt);
          dl.appendChild(dd);
        });
      });

    } catch (err) {
      if (loading) loading.textContent = 'Failed to load config: ' + err.message;
      this.showToast('Failed to load config from ' + window.location.origin + '/config — ' + err.message, 'error');
    }
  }

  async saveConfig() {
    if (!(await this.requireToken())) return;
    const body = {};
    document.querySelectorAll('#configTableWrap input').forEach(el => {
      const key = el.id.replace('cfg_', '');
      if (el.type === 'checkbox') {
        body[key] = el.checked;
      } else if (el.value.trim() !== '') {
        body[key] = el.type === 'number' ? Number(el.value) : el.value.trim();
      }
    });
    try {
      await this.api('/config', { method: 'PUT', body: body });
      this.showToast('Configuration saved', 'success');
      this.loadConfig();
    } catch (err) {
      this.showToast('Failed to save config: ' + err.message, 'error');
    }
  }

  // ---- GitHub token (Config page) ----
  async saveConfigToken() {
    const input = document.getElementById('configTokenInput');
    const token = input.value.trim();
    if (!token) { this.showToast('Please enter a token', 'error'); return; }
    try {
      await this.api('/config/github-token', { method: 'POST', body: { token: token } });
      input.value = '';
      this.showToast('GitHub token saved', 'success');
      this.loadConfig();
    } catch (err) {
      this.showToast('Failed to save token: ' + err.message, 'error');
    }
  }

  async deleteConfigToken() {
    if (!confirm('Remove the stored GitHub token?')) return;
    try {
      await this.api('/config/github-token', { method: 'DELETE' });
      this.showToast('Token removed', 'success');
      this.loadConfig();
    } catch (err) {
      this.showToast('Failed to remove token: ' + err.message, 'error');
    }
  }

  async runDoctor() {
    try {
      const res = await this.api('/doctor');
      const wrap = document.getElementById('doctorResultWrap');
      const out = document.getElementById('doctorResult');
      wrap.classList.remove('hidden');
      out.textContent = typeof res === 'string' ? res : JSON.stringify(res, null, 2);
      this.showToast('Diagnosis complete', 'success');
    } catch (err) {
      this.showToast('Doctor failed: ' + err.message, 'error');
    }
  }

  async exportState() {
    try {
      const res = await this.api('/state/export');
      const wrap = document.getElementById('stateResultWrap');
      const out = document.getElementById('stateResult');
      wrap.classList.remove('hidden');
      out.textContent = typeof res === 'string' ? res : JSON.stringify(res, null, 2);
      this.showToast('State exported', 'success');
    } catch (err) {
      this.showToast('State export failed: ' + err.message, 'error');
    }
  }

  async loadLogs() {
    try {
      const res = await this.api('/logs');
      const wrap = document.getElementById('logsResultWrap');
      const out = document.getElementById('logsResult');
      wrap.classList.remove('hidden');
      out.textContent = typeof res === 'string' ? res : JSON.stringify(res, null, 2);
    } catch (err) {
      const out = document.getElementById('logsResult');
      if (out) out.textContent = 'Failed to load logs: ' + err.message;
    }
  }

  // ---- Sources (Apps page) ----
  async loadSources() {
    const tbody = document.getElementById('sourcesTableBody');
    const empty = document.getElementById('sourcesEmpty');
    if (!tbody) return;
    try {
      const sources = await this.api('/config/sources');
      if (!sources || sources.length === 0) {
        tbody.innerHTML = '';
        if (empty) empty.classList.remove('hidden');
        return;
      }
      if (empty) empty.classList.add('hidden');
      tbody.innerHTML = '';
      sources.forEach(src => {
        const tr = document.createElement('tr');
        const name = this.escapeHtml(src.name);
        tr.innerHTML =
          '<td><code>' + name + '</code></td>' +
          '<td><code style="font-size:0.78rem;">' + this.escapeHtml(src.url) + '</code></td>' +
          '<td><span class="badge ' + (src.enabled ? 'badge-success' : 'badge-neutral') + '">' + (src.enabled ? 'Enabled' : 'Disabled') + '</span></td>' +
          '<td><button class="action-btn btn-danger" onclick="app.removeSource(\'' + name + '\')">Remove</button></td>';
        tbody.appendChild(tr);
      });
    } catch (err) {
      tbody.innerHTML = '<tr><td colspan="4" class="empty-state">Failed to load sources: ' + this.escapeHtml(err.message) + '</td></tr>';
    }
  }

  async addSource() {
    const nameInput = document.getElementById('sourceName');
    const urlInput = document.getElementById('sourceUrl');
    const name = nameInput.value.trim();
    const url = urlInput.value.trim();
    if (!name || !url) { this.showToast('Please enter name and URL', 'error'); return; }
    try {
      await this.api('/config/sources', { method: 'POST', body: { name: name, url: url } });
      nameInput.value = '';
      urlInput.value = '';
      document.getElementById('sourceForm').classList.add('hidden');
      this.showToast('Source added: ' + name, 'success');
      this.loadSources();
    } catch (err) {
      this.showToast('Failed to add source: ' + err.message, 'error');
    }
  }

  async removeSource(name) {
    if (!confirm('Remove source ' + name + '?')) return;
    try {
      await this.api('/config/sources/' + encodeURIComponent(name), { method: 'DELETE' });
      this.showToast('Source removed: ' + name, 'success');
      this.loadSources();
    } catch (err) {
      this.showToast('Failed to remove source: ' + err.message, 'error');
    }
  }

  // ---- Help ----
  async loadHelp() {
    const el = document.getElementById('helpText');
    if (!el || el.dataset.loaded) return;
    try {
      el.textContent = await this.api('/help');
      el.dataset.loaded = '1';
    } catch (err) {
      el.textContent = 'Failed to load help: ' + err.message;
    }
  }

  // ---- Downloads ----
  async loadDownloads() {
    try {
      const downloads = await this.api('/downloads');
      const tbody = document.getElementById('downloadsTableBody');
      if (!tbody) return;

      if (!downloads || downloads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No downloads yet</td></tr>';
        return;
      }
      tbody.innerHTML = '';

      downloads.forEach(dl => {
        const pct = dl.total && dl.total > 0 ? Math.round((dl.downloaded / dl.total) * 100) : 0;
        const status = (dl.status || 'pending').toLowerCase();
        const statusClass = 'status-' + status;
        const tr = document.createElement('tr');
        tr.id = 'dl-row-' + this.escapeHtml(dl.id);
        tr.innerHTML =
          '<td><code>' + this.escapeHtml(dl.id) + '</code></td>' +
          '<td><code style="font-size:0.78rem;">' + this.escapeHtml(dl.url) + '</code></td>' +
          '<td><span class="badge ' + statusClass + '">' + this.escapeHtml(dl.status) + '</span></td>' +
          '<td><div class="progress-bar"><div class="progress-fill" id="dl-progress-' + this.escapeHtml(dl.id) + '" style="width:' + pct + '%;"></div></div></td>' +
          '<td>' + this.formatBytes(dl.downloaded) + ' / ' + this.formatBytes(dl.total) + '</td>' +
          '<td class="speed-eta">' + (dl.speed ? this.formatBytes(dl.speed) + '/s' : '&ndash;') + (dl.eta ? ' &bull; ETA ' + dl.eta + 's' : '') + '</td>';
        tbody.appendChild(tr);
      });
    } catch (err) {
      const tbody = document.getElementById('downloadsTableBody');
      if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Failed to load downloads: ' + this.escapeHtml(err.message) + '</td></tr>';
    }
  }

  startDownloadsPoll() {
    if (this.pollInterval) clearInterval(this.pollInterval);
    this.pollInterval = setInterval(() => this.loadDownloads(), 2000);
  }

  stopDownloadsPoll() {
    if (this.pollInterval) { clearInterval(this.pollInterval); this.pollInterval = null; }
  }

  async startDownload(url, dest, label, token) {
    if (!url) { this.showToast('Please enter a URL', 'error'); return; }
    try {
      await this.api('/downloads', { method: 'POST', body: { url: url, dest: dest, label: label, token: token } });
      this.showToast('Download started', 'success');
      this.loadDownloads();
    } catch (err) {
      this.showToast('Failed to start download: ' + err.message, 'error');
    }
  }

  async loginWithCredentials(username, password) {
    if (!username || !password) { this.showToast('Enter Windows username and password', 'error'); return; }
    try {
      const res = await this.api('/auth/login', { method: 'POST', body: { username: username, password: password } });
      this.login(res.token);
      this.showToast('Signed in as ' + (res.user || username), 'success');
    } catch (err) {
      this.showToast('Sign-in failed: ' + err.message, 'error');
    }
  }

  async loginAsCurrentUser() {
    try {
      const res = await this.api('/auth/login', { method: 'POST', body: { use_current_user: true } });
      this.login(res.token);
      this.showToast('Signed in as ' + (res.user || 'current user'), 'success');
    } catch (err) {
      this.showToast('Sign-in failed: ' + err.message, 'error');
    }
  }

  async login(token) {
    if (!token) { this.showToast('Please enter a token', 'error'); return; }
    this.token = token;
    localStorage.setItem('ohub_token', token);
    this.setupAuthUI();
    this.applyLock();
    this.hideLoginModal();
    this.showToast('Logged in successfully', 'success');
  }

  async logout() {
    this.token = null;
    localStorage.removeItem('ohub_token');
    this.stopDownloadsPoll();
    this.setupAuthUI();
    this.applyLock();
    const modal = document.getElementById('loginModal');
    if (modal) modal.classList.add('hidden');
    const app = document.querySelector('.app');
    if (app) app.classList.remove('blur-bg');
    this.showToast('Logged out', 'info');
    this.navigate('dashboard');
  }
}

const app = new ObtainHubUI();