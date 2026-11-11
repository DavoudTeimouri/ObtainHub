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
    this.addedFromCandidates = new Set();
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
    // Disable mutating form buttons and all per-app action buttons when locked
    document.querySelectorAll('main .page button[type="submit"], main .page .btn-primary, main .page .btn-danger, main .page .action-btn')
      .forEach(el => { el.disabled = locked; });
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

    // Candidates scan button
    const candidatesBtn = document.getElementById('candidatesBtn');
    if (candidatesBtn) {
      candidatesBtn.addEventListener('click', () => this.loadCandidates());
    }
    const clearCandidatesBtn = document.getElementById('clearCandidatesResult');
    if (clearCandidatesBtn) {
      clearCandidatesBtn.addEventListener('click', () => {
        document.getElementById('candidatesResultWrap').classList.add('hidden');
        document.getElementById('candidatesTableBody').innerHTML = '';
      });
    }

    // Vendor exclusion on Detect Installed
    this.excludedVendors = new Set();
    const vendorWrap = document.getElementById('vendorExclusionWrap');
    const vendorList = document.getElementById('vendorList');
    if (vendorList) {
      vendorList.addEventListener('click', e => {
        const cb = e.target.closest('input[type="checkbox"]');
        if (!cb) return;
        const vendor = cb.value;
        if (cb.checked) this.excludedVendors.add(vendor);
        else this.excludedVendors.delete(vendor);
        this.renderCandidates();
      });
    }

    // Candidate repo picker modal
    const pickModal = document.getElementById('pickModal');
    const closePick = () => { if (pickModal) pickModal.classList.add('hidden'); };
    const pickClose = document.getElementById('pickClose');
    const pickBackdrop = document.getElementById('pickBackdrop');
    if (pickClose) pickClose.addEventListener('click', closePick);
    if (pickBackdrop) pickBackdrop.addEventListener('click', closePick);
    const pickSearch = document.getElementById('pickSearch');
    if (pickSearch) {
      let pickTimer = null;
      pickSearch.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); this.searchPick(); }
      });
      pickSearch.addEventListener('input', () => {
        clearTimeout(pickTimer);
        pickTimer = setTimeout(() => this.searchPick(), 600);
      });
    }
    const pickSearchBtn = document.getElementById('pickSearchBtn');
    if (pickSearchBtn) pickSearchBtn.addEventListener('click', () => this.searchPick());

    // Table filters (Managed Apps / Detect Installed / Downloads)
    ['appsFilter', 'candidatesFilter', 'downloadsFilter'].forEach(id => {
      const input = document.getElementById(id);
      if (input) input.addEventListener('input', () => this.applyTableFilters());
    });

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
    const checkAllAppsBtn = document.getElementById('checkAllAppsBtn');
    if (checkAllAppsBtn) checkAllAppsBtn.addEventListener('click', () => this.checkAllApps());
    const refreshCheckBtn = document.getElementById('refreshCheckBtn');
    if (refreshCheckBtn) refreshCheckBtn.addEventListener('click', () => { this.loadApps(); this.renderCheckResults(this.installedApps || []); });
    const checkRepoBtn = document.getElementById('checkRepoBtn');
    if (checkRepoBtn) checkRepoBtn.addEventListener('click', () => this.checkRepo());
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
    this.stopDownloadsPoll();
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
    }    else if (page === 'doctor') {
      // doctor page loads on demand via button
    } else if (page === 'state') {
      // state page loads on demand via button
    } else if (page === 'logs') {
      this.loadLogs();
    } else if (page === 'about') {
      this.loadAbout();
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
      case 'about': this.loadAbout(); break;
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
    else if (name === 'candidates') {
      // Auto-start the scan the first time the tab is opened.
      if (!this.candidatesScanned) this.loadCandidates();
    }
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
    // Background polls pass {silent:true} so the loading overlay doesn't flash.
    const silent = !!options.silent;
    if (!silent) this.showLoading(true);
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (this.token) headers['Authorization'] = 'Bearer ' + this.token;
    const { silent: _silent, ...fetchOptions } = options;
    const config = { ...fetchOptions, headers };
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
    } finally {
      if (!silent) this.showLoading(false);
    }
  }

  showLoading(show) {
    let overlay = document.getElementById('loadingOverlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'loadingOverlay';
      overlay.className = 'loading-overlay';
      overlay.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><span>Working...</span></div>';
      document.body.appendChild(overlay);
    }
    overlay.style.display = show ? 'flex' : 'none';
    // Disable all action buttons while loading to prevent duplicate concurrent requests
    document.querySelectorAll('main .page .action-btn, main .page button[type="submit"]')
      .forEach(el => { el.disabled = show; });
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
      this.installedApps = apps || [];
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
          ? '<span class="badge badge-update">Update available → v' + this.escapeHtml(app.latest_version || '') + '</span>'
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
      this.applyTableFilters();
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
    return false;
  }

  async searchApps() {
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
            '<td>' + this.formatRelativeTime(r.published_at || r.updated_at) + '</td>' +
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
    if (!confirm('Install "' + repo + '"? This will download and register it under ObtainHub management.')) return;
    try {
      const res = await this.api('/apps/install', { method: 'POST', body: { repo: repo } });
      this.showToast('Installed: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Install failed: ' + err.message, 'error');
    }
  }

  async updateApp(repo) {
    if (!(await this.requireToken())) return;
    if (!confirm('Update "' + repo + '" to the latest release?')) return;
    try {
      const res = await this.api('/apps/update', { method: 'POST', body: { repo: repo } });
      this.showToast('Update complete: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Update failed: ' + err.message, 'error');
    }
  }

  async checkApp(repo) {
    if (!(await this.requireToken())) return;
    if (!confirm('Check "' + repo + '" for updates?')) return;
    try {
      const res = await this.api('/apps/check', { method: 'POST', body: { repo: repo } });
      this.showToast('Checked: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Check failed: ' + err.message, 'error');
    }
  }

  async checkAllApps() {
    if (!(await this.requireToken())) return;
    const btn = document.getElementById('checkAllAppsBtn') || document.getElementById('checkAllBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Checking...'; }
    try {
      const apps = await this.api('/apps');
      const prereleaseEl = document.getElementById('checkPrerelease');
      const resetEl = document.getElementById('checkReset');
      const prerelease = prereleaseEl ? prereleaseEl.checked : false;
      const reset = resetEl ? resetEl.checked : false;
      for (const a of (apps || [])) {
        await this.api('/apps/check', { method: 'POST', body: { repo: a.repo, prerelease, reset: reset ? true : undefined } }).catch(() => {});
      }
      this.showToast('Update check complete for all apps', 'success');
      const fresh = await this.api('/apps');
      this.installedApps = fresh || [];
      this.renderCheckResults(this.installedApps);
    } catch (err) {
      this.showToast('Check failed: ' + err.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Check All Updates'; }
    }
  }

  async checkRepo() {
    if (!(await this.requireToken())) return;
    const repo = document.getElementById('checkRepo').value.trim();
    if (!repo) { this.showToast('Enter a repository (owner/repo)', 'error'); return; }
    const btn = document.getElementById('checkRepoBtn');
    const orig = btn.textContent;
    btn.disabled = true; btn.textContent = 'Checking...';
    try {
      const prereleaseEl = document.getElementById('checkPrerelease');
      const resetEl = document.getElementById('checkReset');
      const prerelease = prereleaseEl ? prereleaseEl.checked : false;
      const reset = resetEl ? resetEl.checked : false;
      await this.api('/apps/check', { method: 'POST', body: { repo, prerelease, reset: reset ? true : undefined } });
      this.showToast('Checked: ' + repo, 'success');
      const fresh = await this.api('/apps');
      this.installedApps = fresh || [];
      this.renderCheckResults(this.installedApps);
    } catch (err) {
      this.showToast('Check failed: ' + err.message, 'error');
    } finally {
      btn.disabled = false; btn.textContent = orig;
    }
  }

  renderCheckResults(apps) {
    const tbody = document.getElementById('checkTableBody');
    const count = document.getElementById('checkCount');
    const wrap = document.getElementById('checkResultWrap');
    if (!tbody) return;
    const list = apps || [];
    const withUpdates = list.filter(a => a.update_available);
    count.textContent = list.length + ' apps &middot; ' + withUpdates.length + ' update' + (withUpdates.length === 1 ? '' : 's') + ' available';
    wrap.classList.remove('hidden');
    tbody.innerHTML = '';
    if (withUpdates.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">All apps are up to date.</td></tr>';
      return;
    }
    withUpdates.forEach(app => {
      const statusClass = 'status-' + (app.status || 'unknown').toLowerCase();
      const repo = app.repo;
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td><code>' + this.escapeHtml(repo) + '</code></td>' +
        '<td><code>' + this.escapeHtml(app.version) + '</code></td>' +
        '<td><code style="color:var(--success);font-weight:600">' + this.escapeHtml(app.latest_version || '') + '</code></td>' +
        '<td><span class="badge badge-update">Update available</span></td>' +
        '<td><span class="badge badge-' + statusClass + '">' + this.escapeHtml(app.status) + '</span></td>' +
        '<td><button class="action-btn btn-primary" onclick="app.updateApp(\'' + repo + '\')">Update</button></td>';
      tbody.appendChild(tr);
    });
  }

  async uninstallApp(repo) {
    if (!(await this.requireToken())) return;
    if (!confirm('Uninstall "' + repo + '"? (stays managed)')) return;
    try {
      await this.api('/apps/uninstall', { method: 'POST', body: { repo: repo, purge: false, interactive: true } });
      this.showToast('Uninstalled: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Uninstall failed: ' + err.message, 'error');
    }
  }

  async removeApp(repo) {
    if (!(await this.requireToken())) return;
    if (!confirm('Remove "' + repo + '" from management?')) return;
    try {
      await this.api('/apps/' + encodeURIComponent(repo), { method: 'DELETE' });
      this.showToast('App removed: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Failed to remove app: ' + err.message, 'error');
    }
  }

  async runAppAction(form, endpoint, method, successMsg) {
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

  async updateAppForm() {
    const repo = document.getElementById('updateRepo').value.trim();
    if (!repo) { this.showToast('Enter a repository (owner/repo)', 'error'); return; }
    if (!confirm('Update "' + repo + '" to the latest release?')) return;
    await this.runAppAction('updateForm', '/apps/update', 'POST', 'Update complete');
  }
  async uninstallAppForm() { await this.runAppAction('uninstallForm', '/apps/uninstall', 'POST', 'Uninstalled'); }
  async removeAppForm() { await this.runAppAction('removeForm', '/apps/' + encodeURIComponent(document.getElementById('removeRepo').value.trim()), 'DELETE', 'Removed from management'); }
  async addAppForm() {
    const addType = document.getElementById('addType').value;
    const addRepo = document.getElementById('addRepo').value.trim();
    if (!addRepo) { this.showToast('Please enter repository/URL/path', 'error'); return; }
    const body = { repo: addRepo, add_type: addType };
    try {
      await this.api('/apps', { method: 'POST', body });
      document.getElementById('addRepo').value = '';
      this.showToast('Added to management: ' + addRepo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Failed to add: ' + err.message, 'error');
    }
  }

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

  async loadAbout() {
    try {
      const info = await this.api('/version');
      const ver = info && info.version ? info.version : 'unknown';
      document.getElementById('aboutVersion').textContent = ver;
      document.getElementById('aboutBuildVersion').textContent = ver;
      document.getElementById('aboutPlatform').textContent = navigator.platform;
      document.getElementById('aboutRust').textContent = '1.85+';
      document.getElementById('aboutBuildTime').textContent = new Date().toISOString();
    } catch (err) {
      document.getElementById('aboutVersion').textContent = 'unknown';
      document.getElementById('aboutBuildVersion').textContent = 'unknown';
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

  async loadCandidates() {
    const btn = document.getElementById('candidatesBtn');
    const wrap = document.getElementById('candidatesResultWrap');
    const tbody = document.getElementById('candidatesTableBody');
    if (!tbody) return;
    btn.disabled = true;
    btn.textContent = 'Scanning...';
    wrap.classList.remove('hidden');
    try {
      const candidates = await this.api('/apps/candidates', { method: 'POST' });
      this.candidatesData = candidates || [];
      if (!this.candidatesData.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No unmanaged installed apps found. <button type="button" class="btn btn-secondary" onclick="app.showAppsTab(\'add\')">Add manually</button></td></tr>';
        return;
      }
      this.renderCandidates();
      this.populateVendors();
    } catch (err) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Scan failed: ' + this.escapeHtml(err.message) + '</td></tr>';
    } finally {
      this.candidatesScanned = true;
      this.applyTableFilters();
      btn.disabled = false;
      btn.textContent = 'Scan for Installed Apps';
    }
  }

  // Render the Detect Installed table from this.candidatesData. Apps already
  // added to management are removed from the data, so they never reappear
  // without a fresh scan (and the server excludes tracked apps anyway).
  renderCandidates() {
    const tbody = document.getElementById('candidatesTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    const vendorWrap = document.getElementById('vendorExclusionWrap');
    if (vendorWrap) vendorWrap.classList.toggle('hidden', this.candidatesData.length === 0);
    this.candidatesData.forEach((c, i) => {
      if (this.addedFromCandidates.has(c.name)) return;
      // Vendor exclusion: skip apps whose vendor is excluded
      const vendor = this.extractVendor(c.name);
      if (this.excludedVendors.has(vendor)) return;
      const candList = c.candidates && c.candidates.length
        ? c.candidates.map(r => '<button type="button" class="repo-chip" title="Add ' + this.escapeHtml(r) + ' to management" onclick="app.quickAdd(\'' + r + '\')">' + this.escapeHtml(r) + '</button>').join(' ')
        : '<span class="empty-state">search on Add</span>';
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td><code>' + this.escapeHtml(c.name) + '</code></td>' +
        '<td>' + this.escapeHtml(c.version || 'unknown') + '</td>' +
        '<td><code style="font-size:0.75rem;">' + this.escapeHtml(c.install_path || '-') + '</code></td>' +
        '<td>' + candList + '</td>' +
        '<td><button class="action-btn btn-primary" onclick="app.pickCandidate(' + i + ')">Add</button></td>';
      tbody.appendChild(tr);
    });
    this.applyTableFilters();
  }

  // Extract a vendor name from an installed app's display name (matches CLI
  // ohub check --candidates vendor exclusion behaviour).
  extractVendor(name) {
    if (!name) return '';
    const known = [
      'Microsoft', 'Adobe', 'Oracle', 'Apple', 'Intel', 'NVIDIA', 'AMD',
      'Google', 'Mozilla', 'Valve', 'JetBrains', 'VMware', 'Realtek',
      'Synaptics', 'Elan', 'Broadcom', 'Qualcomm', 'HP', 'Dell', 'Lenovo',
      'ASUS', 'Acer', 'Canon', 'Logitech', 'Razer', 'Corsair', 'Zoom',
      'Slack', 'Discord', 'Spotify', 'Samsung', 'Toshiba', 'Fujitsu',
      'Brother', 'EPSON', 'Skype',
    ];
    const lower = name.toLowerCase();
    for (const v of known) {
      if (lower.includes(v.toLowerCase())) return v;
    }
    return name.split(/\s+/)[0] || name;
  }

  // Build vendor exclusion checkboxes from the detected apps' vendor names.
  populateVendors() {
    const list = document.getElementById('vendorList');
    if (!list) return;
    list.innerHTML = '';
    const vendors = new Set();
    (this.candidatesData || []).forEach(c => vendors.add(this.extractVendor(c.name)));
    [...vendors].sort().forEach(vendor => {
      const label = document.createElement('label');
      label.className = 'vendor-chip';
      label.innerHTML =
        '<input type="checkbox" value="' + this.escapeHtml(vendor) + '" ' +
        (this.excludedVendors.has(vendor) ? 'checked' : '') + '>' +
        this.escapeHtml(vendor);
      list.appendChild(label);
    });
  }

  // One-click add of a specific candidate repo straight from the results table.
  async quickAdd(repo) {
    try {
      // Find the candidate entry this repo came from, to send its detected
      // install_path and version to the install endpoint.
      const entry = (this.candidatesData || []).find(c =>
        (c.candidates || []).includes(repo)
      );
      const body = { repo: repo };
      if (entry) {
        if (entry.install_path) body.install_path = entry.install_path;
        if (entry.version && entry.version !== 'unknown') body.version = entry.version;
      }
      await this.api('/apps', { method: 'POST', body });
      this.addedFromCandidates.add(repo);
      this.candidatesData = this.candidatesData.filter(c => c.name !== repo);
      this.renderCandidates();
      this.showToast('Added to management: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Failed to add ' + repo + ': ' + err.message, 'error');
    }
  }

  // Open the repo picker for a detected app; offers its candidate repos and a
  // GitHub search box so the user chooses which repo to add to management.
  pickCandidate(index) {
    const entry = (this.candidatesData || [])[index];
    if (!entry) return;
    this.pickAppName = entry.name;
    this.pickOptions = (entry.candidates || []).slice();
    document.getElementById('pickAppName').textContent = entry.name;
    const search = document.getElementById('pickSearch');
    search.value = entry.name;
    this.renderPickOptions();
    document.getElementById('pickModal').classList.remove('hidden');
    search.focus();
  }

  renderPickOptions() {
    const box = document.getElementById('pickResults');
    if (!this.pickOptions.length) {
      box.innerHTML = '<p class="empty-state">No candidate repos — search above.</p>';
      return;
    }
    box.innerHTML = '';
    this.pickOptions.forEach((repo, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn btn-secondary pick-option';
      b.textContent = repo;
      b.onclick = () => this.confirmAdd(i);
      box.appendChild(b);
    });
  }

  async searchPick() {
    const q = document.getElementById('pickSearch').value.trim();
    if (!q) return;
    const box = document.getElementById('pickResults');
    box.innerHTML = '<p class="empty-state">Searching...</p>';
    try {
      const res = await this.api('/search?q=' + encodeURIComponent(q) + '&limit=8');
      const items = (res && res.items) ? res.items : (Array.isArray(res) ? res : []);
      this.pickOptions = items.map(it => it.full_name || it.repo).filter(Boolean);
      this.renderPickOptions();
    } catch (err) {
      box.innerHTML = '<p class="empty-state">Search failed: ' + this.escapeHtml(err.message) + '</p>';
    }
  }

  async confirmAdd(index) {
    const repo = this.pickOptions[index];
    if (!repo) return;
    try {
      // Send detected install_path and version from the registry scan so the
      // installed app is tracked at its real location with its real version.
      const entry = (this.candidatesData || []).find(c => c.name === this.pickAppName);
      const body = { repo: repo };
      if (entry) {
        if (entry.install_path) body.install_path = entry.install_path;
        if (entry.version && entry.version !== 'unknown') body.version = entry.version;
      }
      await this.api('/apps', { method: 'POST', body });
      this.addedFromCandidates.add(this.pickAppName);
      this.candidatesData = this.candidatesData.filter(c => c.name !== this.pickAppName);
      this.renderCandidates();
      this.showToast('Added: ' + this.pickAppName + ' as ' + repo, 'success');
      document.getElementById('pickModal').classList.add('hidden');
      this.loadApps();
    } catch (err) {
      this.showToast('Failed to add: ' + err.message, 'error');
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
    // Help content is now pure HTML (multi-page guide). Nothing to fetch.
    const el = document.getElementById('helpText');
    if (el) el.style.display = 'none';
    this.showHelpTab('getting-started', null);
  }

  showHelpTab(tabName, btnEl) {
    // Hide all help pages
    document.querySelectorAll('.help-page').forEach(p => p.classList.remove('active'));
    // Deactivate all tabs
    document.querySelectorAll('.help-tab').forEach(t => t.classList.remove('active'));
    // Show selected page
    const page = document.getElementById('helpPage-' + tabName);
    if (page) page.classList.add('active');
    // Activate selected tab
    if (btnEl) btnEl.classList.add('active');
    else {
      const defaultBtn = document.querySelector('.help-tab[data-help-tab="' + tabName + '"]');
      if (defaultBtn) defaultBtn.classList.add('active');
    }
  }

  // ---- Table filters ----
  applyTableFilters() {
    const pairs = [
      ['appsFilter', 'appsTableBody'],
      ['candidatesFilter', 'candidatesTableBody'],
      ['downloadsFilter', 'downloadsTableBody'],
    ];
    pairs.forEach(([inputId, tbodyId]) => {
      const input = document.getElementById(inputId);
      const tbody = document.getElementById(tbodyId);
      if (!input || !tbody) return;
      const q = input.value.trim().toLowerCase();
      tbody.querySelectorAll('tr').forEach(tr => {
        const match = !q || tr.textContent.toLowerCase().includes(q);
        tr.style.display = match ? '' : 'none';
      });
    });
  }

  // ---- Downloads ----
  async loadDownloads(silent = false) {
    try {
      const downloads = await this.api('/downloads', { silent });
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
      this.applyTableFilters();
    } catch (err) {
      const tbody = document.getElementById('downloadsTableBody');
      if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Failed to load downloads: ' + this.escapeHtml(err.message) + '</td></tr>';
    }
  }

  startDownloadsPoll() {
    if (this.pollInterval) clearInterval(this.pollInterval);
    this.pollInterval = setInterval(() => this.loadDownloads(true), 2000);
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

window.app = new ObtainHubUI();