/**
 * ObtainHub WebUI - Application JavaScript
 * Powers the professional single-page application interface.
 */

class ObtainHubUI {
  constructor() {
    this.token = sessionStorage.getItem('ohub_token') || null;
    this.currentPage = 'dashboard';
    this.pollInterval = null;
    this.serverStartTime = null;
    this.init();
  }

  init() {
    this.setupNavigation();
    window.addEventListener('hashchange', () => this.route());
    this.route();
    // Start server uptime tracking
    this.serverStartTime = Date.now();
    setInterval(() => this.updateUptime(), 1000);
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

    // Login form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
      loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const token = document.getElementById('authToken').value.trim();
        this.login(token);
      });
    }

    // Modal close
    const modalClose = document.getElementById('modalClose');
    const modalBackdrop = document.getElementById('modalBackdrop');
    const modalCancel = document.getElementById('modalCancel');
    const closeModal = () => {
      const modal = document.getElementById('loginModal');
      if (modal) modal.classList.add('hidden');
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

    // Update form
    const updateForm = document.getElementById('updateForm');
    if (updateForm) {
      updateForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const repo = document.getElementById('updateRepo').value.trim() || undefined;
        const prerelease = document.getElementById('updatePrerelease').checked;
        this.checkUpdates(repo, prerelease);
      });
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
    else if (page === 'apps') this.loadApps();
    else if (page === 'config') this.loadConfig();
    else if (page === 'sources') this.loadSources();
    else if (page === 'downloads') {
      this.loadDownloads();
      this.startDownloadsPoll();
    } else if (page === 'updates') {
      // Updates page is loaded on demand via the form
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
      case 'apps': this.loadApps(); break;
      case 'config': this.loadConfig(); break;
      case 'sources': this.loadSources(); break;
      case 'downloads': this.loadDownloads(); break;
      case 'updates': break;
    }
    this.showToast('Refreshed', 'info');
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
  }

  showLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) modal.classList.remove('hidden');
  }

  hideLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) modal.classList.add('hidden');
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
        sessionStorage.removeItem('ohub_token');
        this.token = null;
        this.setupAuthUI();
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
      throw err;
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

  updateUptime() {
    const el = document.getElementById('statUptime');
    if (!el || !this.serverStartTime) return;
    const ms = Date.now() - this.serverStartTime;
    const h = Math.floor(ms / 3600000);
    const m = Math.floor((ms % 3600000) / 60000);
    const s = Math.floor((ms % 60000) / 1000);
    el.textContent = `${h}h ${m}m ${s}s`;
  }

  // ---- Dashboard ----
  async loadDashboard() {
    try {
      const [apps, config] = await Promise.all([
        this.api('/apps'),
        this.api('/config')
      ]);

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
    try {
      const apps = await this.api('/apps');
      document.getElementById('appsLoading').style.display = 'none';
      const wrap = document.getElementById('appsTableWrap');
      const tbody = document.getElementById('appsTableBody');
      const empty = document.getElementById('appsEmpty');

      if (!apps || apps.length === 0) {
        wrap.style.display = 'none';
        empty.style.display = 'block';
        return;
      }
      wrap.style.display = 'block';
      empty.style.display = 'none';
      tbody.innerHTML = '';

      apps.forEach(app => {
        const tr = document.createElement('tr');
        const statusClass = 'status-' + (app.status || 'unknown').toLowerCase();
        tr.innerHTML =
          '<td><code>' + this.escapeHtml(app.repo) + '</code></td>' +
          '<td>' + this.escapeHtml(app.name) + '</td>' +
          '<td><code>' + this.escapeHtml(app.version) + '</code></td>' +
          '<td><span class="badge badge-' + statusClass + '">' + this.escapeHtml(app.status) + '</span></td>' +
          '<td>' + this.escapeHtml(app.installed_at || '&ndash;') + '</td>' +
          '<td>' + this.escapeHtml(app.updated_at || '&ndash;') + '</td>' +
          '<td>' +
            '<button class="action-btn btn-danger" onclick="app.removeApp(\'' + this.escapeHtml(app.repo) + '\')">Remove</button>' +
          '</td>';
        tbody.appendChild(tr);
      });
    } catch (err) {
      document.getElementById('appsLoading').textContent = 'Failed to load apps';
      this.showToast('Failed to load apps: ' + err.message, 'error');
    }
  }

  async addApp() {
    const input = document.getElementById('addAppRepo');
    const repo = input.value.trim();
    if (!repo) { this.showToast('Please enter a repository', 'error'); return; }
    try {
      await this.api('/apps', { method: 'POST', body: { repo: repo } });
      input.value = '';
      this.showToast('App added: ' + repo, 'success');
      this.loadApps();
    } catch (err) {
      this.showToast('Failed to add app: ' + err.message, 'error');
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

  // ---- Config ----
  async loadConfig() {
    try {
      const config = await this.api('/config');
      document.getElementById('configLoading').style.display = 'none';
      const wrap = document.getElementById('configTableWrap');
      wrap.style.display = 'block';

      const sections = {
        configDirs: [
          ['Install Dir', config.install_dir],
          ['Download Dir', config.download_dir],
          ['Shim Dir', config.shim_dir]
        ],
        configNetwork: [
          ['Proxy', config.proxy || 'none'],
          ['HTTP Retries', String(config.http_retries)],
          ['HTTP Retry Delay (ms)', String(config.http_retry_delay_ms)],
          ['HTTP Retry Backoff', String(config.http_retry_backoff)],
          ['Bandwidth Limit', config.download_bandwidth_limit ? String(config.download_bandwidth_limit) + ' B/s' : 'unlimited']
        ],
        configBehavior: [
          ['Parallel Downloads', String(config.parallel_downloads)],
          ['Timeout (s)', String(config.timeout_seconds)],
          ['Auto Cleanup', config.auto_cleanup ? 'true' : 'false'],
          ['Verify Checksums', config.verify_checksums ? 'true' : 'false']
        ],
        configSchedule: [
          ['Schedule Enabled', config.schedule_enabled ? 'true' : 'false'],
          ['Interval (h)', String(config.schedule_interval_hours)],
          ['Notify on Update', config.schedule_notify_on_update ? 'true' : 'false'],
          ['Run on Startup', config.schedule_run_on_startup ? 'true' : 'false']
        ],
        configAdvanced: [
          ['Update Check Interval (h)', String(config.update_check_interval_hours)]
        ],
        configGroups: [
          ['Groups', config.groups && config.groups.length ? config.groups.join(', ') : 'none'],
          ['Token Source', config.token_source || 'not set']
        ]
      };

      Object.entries(sections).forEach(([sectionId, entries]) => {
        const dl = document.getElementById(sectionId);
        if (!dl) return;
        dl.innerHTML = '';
        entries.forEach(([key, value]) => {
          const dt = document.createElement('dt');
          dt.textContent = key;
          const dd = document.createElement('dd');
          if (key === 'Token Source') {
            dd.innerHTML = '<span class="badge badge-neutral">[stored in OS credential store]</span>';
          } else if (key === 'Groups' || key === 'Proxy') {
            dd.textContent = value;
          } else if (['true', 'false'].includes(value)) {
            dd.textContent = value;
            dd.className = value === 'true' ? 'badge badge-success' : 'badge badge-neutral';
            dd.style.display = 'inline-block';
            dd.style.padding = '2px 8px';
            dd.style.borderRadius = '4px';
          } else {
            dd.textContent = value;
          }
          dl.appendChild(dt);
          dl.appendChild(dd);
        });
      });
    } catch (err) {
      document.getElementById('configLoading').textContent = 'Failed to load config';
      this.showToast('Failed to load config: ' + err.message, 'error');
    }
  }

  // ---- Token ----
  async saveToken() {
    const input = document.getElementById('authToken');
    const token = input.value.trim();
    if (!token) { this.showToast('Please enter a token', 'error'); return; }
    try {
      await this.api('/config/github-token', { method: 'POST', body: { token: token } });
      input.value = '';
      this.hideLoginModal();
      this.showToast('Token saved', 'success');
      this.setupAuthUI();
    } catch (err) {
      this.showToast('Failed to save token: ' + err.message, 'error');
    }
  }

  // Wire up login form submit (in case it wasn't caught in init)
  async handleLoginSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('authToken');
    const token = input.value.trim();
    if (!token) { this.showToast('Please enter a token', 'error'); return; }
    try {
      await this.api('/config/github-token', { method: 'POST', body: { token: token } });
      input.value = '';
      this.hideLoginModal();
      this.showToast('Token saved', 'success');
      this.setupAuthUI();
    } catch (err) {
      this.showToast('Failed to save token: ' + err.message, 'error');
    }
  }

  // ---- Sources ----
  async loadSources() {
    try {
      const sources = await this.api('/config/sources');
      document.getElementById('sourcesLoading').style.display = 'none';
      const wrap = document.getElementById('sourcesTableWrap');
      const tbody = document.getElementById('sourcesTableBody');
      const empty = document.getElementById('sourcesEmpty');

      if (!sources || sources.length === 0) {
        wrap.style.display = 'none';
        empty.style.display = 'block';
        return;
      }
      wrap.style.display = 'block';
      empty.style.display = 'none';
      tbody.innerHTML = '';

      sources.forEach(src => {
        const tr = document.createElement('tr');
        tr.innerHTML =
          '<td><code>' + this.escapeHtml(src.name) + '</code></td>' +
          '<td><code style="font-size:0.78rem;">' + this.escapeHtml(src.url) + '</code></td>' +
          '<td><code>' + this.escapeHtml(src.src_type) + '</code></td>' +
          '<td><span class="badge ' + (src.enabled ? 'badge-success' : 'badge-neutral') + '">' + (src.enabled ? 'Enabled' : 'Disabled') + '</span></td>' +
          '<td><button class="action-btn btn-danger" onclick="app.removeSource(\'' + this.escapeHtml(src.name) + '\')">Remove</button></td>';
        tbody.appendChild(tr);
      });
    } catch (err) {
      document.getElementById('sourcesLoading').textContent = 'Failed to load sources';
      this.showToast('Failed to load sources: ' + err.message, 'error');
    }
  }

  async addSource() {
    const nameInput = document.getElementById('addSourceName');
    const urlInput = document.getElementById('addSourceUrl');
    const name = nameInput.value.trim();
    const url = urlInput.value.trim();
    if (!name || !url) { this.showToast('Please enter name and URL', 'error'); return; }
    try {
      await this.api('/config/sources', { method: 'POST', body: { name: name, url: url } });
      nameInput.value = '';
      urlInput.value = '';
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

  // ---- Downloads ----
  async loadDownloads() {
    try {
      const downloads = await this.api('/downloads');
      document.getElementById('downloadsLoading').style.display = 'none';
      const wrap = document.getElementById('downloadsTableWrap');
      const tbody = document.getElementById('downloadsTableBody');
      const empty = document.getElementById('downloadsEmpty');

      if (!downloads || downloads.length === 0) {
        wrap.style.display = 'none';
        empty.style.display = 'block';
        return;
      }
      wrap.style.display = 'block';
      empty.style.display = 'none';
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
          '<td class="speed-eta">' + (dl.speed ? this.formatBytes(dl.speed) + '/s' : '&ndash;') + (dl.eta ? ' &bull; ETA ' + dl.eta + 's' : '') + '</td>' +
          '<td><button class="action-btn btn-danger" onclick="app.cancelDownload(\'' + this.escapeHtml(dl.id) + '\')" ' + (status === 'completed' || status === 'error' ? 'disabled' : '') + '>Cancel</button></td>';
        tbody.appendChild(tr);
      });
    } catch (err) {
      document.getElementById('downloadsLoading').textContent = 'Failed to load downloads';
      this.showToast('Failed to load downloads: ' + err.message, 'error');
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

  async cancelDownload(id) {
    try {
      await this.api('/downloads/' + encodeURIComponent(id) + '/cancel', { method: 'POST' });
      this.showToast('Download cancelled', 'success');
      this.loadDownloads();
    } catch (err) {
      this.showToast('Failed to cancel download: ' + err.message, 'error');
    }
  }

  // ---- Update Check ----
  async checkUpdates(repo, prerelease) {
    const btn = document.getElementById('checkUpdatesBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg> Checking...';
    btn.disabled = true;

    try {
      const body = {};
      if (repo) body.repo = repo;
      body.prerelease = prerelease || false;
      const result = await this.api('/update-check', { method: 'POST', body: body });

      const resultDiv = document.getElementById('updateResults');
      const resultsCard = document.getElementById('updateResultsCard');
      const tbody = document.getElementById('updateResultsBody');

      resultsCard.classList.remove('hidden');
      tbody.innerHTML = '';

      if (!result || result.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No repositories to check</td></tr>';
      } else {
        result.forEach(r => {
          const tr = document.createElement('tr');
          const hasUpdate = r.update_available ? 'badge-success' : 'badge-neutral';
          tr.innerHTML =
            '<td><code>' + this.escapeHtml(r.repo) + '</code></td>' +
            '<td><code>' + this.escapeHtml(r.current_version) + '</code></td>' +
            '<td><code>' + this.escapeHtml(r.latest_version) + '</code></td>' +
            '<td><span class="badge ' + hasUpdate + '">' + (r.update_available ? 'Update available' : 'Current') + '</span></td>';
          tbody.appendChild(tr);
        });
      }
      this.showToast('Update check complete', 'success');
    } catch (err) {
      this.showToast('Update check failed: ' + err.message, 'error');
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  }

  async login(token) {
    if (!token) { this.showToast('Please enter a token', 'error'); return; }
    this.token = token;
    sessionStorage.setItem('ohub_token', token);
    this.setupAuthUI();
    this.hideLoginModal();
    this.showToast('Logged in successfully', 'success');
  }

  async logout() {
    this.token = null;
    sessionStorage.removeItem('ohub_token');
    this.stopDownloadsPoll();
    this.setupAuthUI();
    this.showToast('Logged out', 'info');
    this.navigate('dashboard');
  }
}

const app = new ObtainHubUI();