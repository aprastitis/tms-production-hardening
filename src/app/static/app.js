function app() {
  return {
    token: localStorage.getItem('access_token') || null,
    refresh: localStorage.getItem('refresh_token') || null,
    user: null,
    form: { username: '', password: '' },
    error: '',
    flags: [],
    transactions: [],
    summary: null,
    newPassword: '',
    cpError: '',

    async init() {
      if (this.token) {
        try {
          await this.fetchMe();
          await this.refreshAll();
        } catch (e) {
          this.logout();
        }
      }
    },

    async login() {
      this.error = '';
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.form),
      });
      if (res.status === 429) { this.error = 'rate_limited'; return; }
      if (!res.ok) { this.error = 'invalid_credentials'; return; }
      const data = await res.json();
      this.token = data.access_token;
      this.refresh = data.refresh_token;
      localStorage.setItem('access_token', this.token);
      localStorage.setItem('refresh_token', this.refresh);
      this.user = data.user;
      await this.refreshAll();
    },

    async fetchMe() {
      const res = await this.authFetch('/auth/me');
      if (!res.ok) throw new Error('me_failed');
      this.user = await res.json();
    },

    async refreshAll() {
      const f = await this.authFetch('/flags?status=open');
      if (f.ok) {
        const d = await f.json();
        this.flags = d.items;
      }
      const t = await this.authFetch('/transactions');
      if (t.ok) {
        const d = await t.json();
        this.transactions = d.items;
      }
      const s = await this.authFetch('/reports/daily-summary');
      if (s.ok) this.summary = await s.json();
    },

    async resolve(flag) {
      const res = await this.authFetch(`/flags/${flag.id}/resolve`, { method: 'POST' });
      if (res.ok) await this.refreshAll();
    },

    async changePassword() {
      this.cpError = '';
      const res = await this.authFetch('/auth/me/password', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_password: this.newPassword }),
      });
      if (!res.ok) { this.cpError = 'failed'; return; }
      this.newPassword = '';
      await this.fetchMe();
    },

    async authFetch(url, opts = {}) {
      opts.headers = Object.assign({}, opts.headers || {}, {
        Authorization: 'Bearer ' + this.token,
        'Content-Type': opts.body && !opts.headers?.['Content-Type'] ? 'application/json' : (opts.headers?.['Content-Type'] || (opts.body ? 'application/json' : undefined)),
      });
      const res = await fetch(url, opts);
      if (res.status === 401) { this.logout(); throw new Error('unauthorized'); }
      return res;
    },

    logout() {
      this.token = null;
      this.refresh = null;
      this.user = null;
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    },
  };
}