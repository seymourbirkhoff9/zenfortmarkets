/**
 * API client. One place that knows how to talk to FastAPI.
 *
 * - Same-origin `/api` (Vite proxies it in dev; put both behind one domain in prod).
 *   Override with VITE_API_BASE if the API lives elsewhere.
 * - Session is an httpOnly cookie set by /api/auth/login; JS never sees the token.
 * - Every request sends X-Requested-With, which the backend requires for
 *   cookie-authenticated writes (CSRF guard).
 * - Errors are normalised to ApiError with a human message, including
 *   FastAPI 422 validation arrays.
 */
const BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(status, message, fields = {}) {
    super(message);
    this.status = status;
    this.fields = fields;   // { field_name: message } for form highlighting
  }
}

function parseDetail(detail) {
  if (!detail) return { message: '', fields: {} };
  if (typeof detail === 'string') return { message: detail, fields: {} };
  if (Array.isArray(detail)) {
    const fields = {};
    const msgs = detail.map((d) => {
      const msg = String(d.msg || '').replace(/^Value error, /, '');
      const name = (d.loc || []).filter((p) => p !== 'body').join('.');
      if (name) fields[name] = msg;
      return msg;
    });
    return { message: [...new Set(msgs)].join(' '), fields };
  }
  return { message: 'Something went wrong. Try again.', fields: {} };
}

let onUnauthorized = () => {
  const next = encodeURIComponent(location.pathname + location.hash);
  location.href = `/login.html?next=${next}`;
};
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

// In-flight request count, for the top progress bar (see shell.js).
let busy = 0;
const setBusy = (d) => { busy += d; window.dispatchEvent(new CustomEvent('zf:busy', { detail: busy })); };

export async function request(path, opts = {}) {
  setBusy(1);
  try { return await send(path, opts); } finally { setBusy(-1); }
}

// ── Friendly, consistent error messages ──────────────────────────────
const MESSAGES = {
  offline: 'You’re offline. Check your internet connection and try again.',
  network: 'We couldn’t reach Zenfort Markets. Check your connection and try again.',
  timeout: 'This is taking longer than usual. Check your connection and try again.',
  waking: 'Zenfort Markets is starting up or busy. Please try again in a few seconds.',
  server: 'Something went wrong on our side. Please try again in a moment.',
  missing: 'This service isn’t available right now. Please try again shortly.',
  limit: 'Too many attempts. Please wait a minute and try again.',
  generic: 'Something went wrong. Please try again.',
};
const TIMEOUT_MS = 45_000;                 // a sleeping free-tier server can take ~30–50 s to wake
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function messageFor(status, detail) {
  // Prefer the server's own explanation when it's a real sentence, not a bare status phrase.
  const generic = !detail || /^(not found|internal server error|bad gateway|service unavailable|method not allowed)\.?$/i.test(detail);
  if (!generic) return detail;
  if (status === 404) return MESSAGES.missing;
  if (status === 429) return MESSAGES.limit;
  if (status === 502 || status === 503 || status === 504) return MESSAGES.waking;
  if (status >= 500) return MESSAGES.server;
  return MESSAGES.generic;
}

async function send(path, { method = 'GET', body, query, raw = false, quiet401 = false } = {}) {
  const url = new URL(BASE + path, location.origin);
  if (query) Object.entries(query).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v); });

  // Reads are retried when the server is waking up or the connection blips; writes never are,
  // so an action can't accidentally happen twice.
  const attempts = method === 'GET' ? 3 : 1;
  let res;
  for (let i = 0; i < attempts; i += 1) {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) throw new ApiError(0, MESSAGES.offline);
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    try {
      res = await fetch(url, {
        method,
        credentials: 'include',
        signal: ctrl.signal,
        headers: {
          'X-Requested-With': 'zenfort',
          ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (err) {
      clearTimeout(timer);
      if (i < attempts - 1) { await sleep(1500 * (i + 1)); continue; }
      throw new ApiError(0, err?.name === 'AbortError' ? MESSAGES.timeout : MESSAGES.network);
    }
    clearTimeout(timer);
    if ([502, 503, 504].includes(res.status) && i < attempts - 1) { await sleep(2000 * (i + 1)); continue; }
    break;
  }

  if (res.status === 401 && !quiet401) { onUnauthorized(); throw new ApiError(401, 'Sign in to continue.'); }
  if (res.status === 204) return null;

  const data = await res.json().catch(() => null);   // proxies and gateways may answer with HTML
  if (!res.ok) {
    const { message, fields } = parseDetail(data?.detail);
    throw new ApiError(res.status, messageFor(res.status, typeof data?.detail === 'string' ? data.detail : (data?.detail ? message : null)), fields);
  }
  return raw ? { data, headers: res.headers } : data;
}

const get = (p, query, opts) => request(p, { query, ...opts });
const post = (p, body) => request(p, { method: 'POST', body: body ?? {} });
const patch = (p, body) => request(p, { method: 'PATCH', body: body ?? {} });
const del = (p) => request(p, { method: 'DELETE' });

export const api = {
  auth: {
    login: (email, password) => request('/auth/login', { method: 'POST', body: { email, password }, quiet401: true }),
    loginTwoFactor: (challenge, code) => request('/auth/login/2fa', { method: 'POST', body: { challenge, code }, quiet401: true }),
    forgotPassword: (email) => request('/auth/forgot-password', { method: 'POST', body: { email }, quiet401: true }),
    resetPassword: (token, new_password) => request('/auth/reset-password', { method: 'POST', body: { token, new_password }, quiet401: true }),
    twoFactorStatus: () => get('/auth/2fa'),
    twoFactorSetup: (password) => request('/auth/2fa/setup', { method: 'POST', body: { password }, quiet401: true }),
    twoFactorEnable: (code) => post('/auth/2fa/enable', { code }),
    twoFactorDisable: (password, code) => request('/auth/2fa/disable', { method: 'POST', body: { password, code }, quiet401: true }),
    twoFactorNewCodes: (password, code) => request('/auth/2fa/recovery-codes', { method: 'POST', body: { password, code }, quiet401: true }),
    logout: () => post('/auth/logout'),
    signup: (payload) => post('/auth/signup', payload),
    me: (opts) => get('/auth/me', undefined, opts),
    updateMe: (payload) => patch('/auth/me', payload),
    changePassword: (payload) => request('/auth/change-password', { method: 'POST', body: payload, quiet401: true }),
    verifyEmail: (token) => request('/auth/verify-email', { method: 'POST', body: { token }, quiet401: true }),
    resendVerification: () => post('/auth/resend-verification'),
    submitKyc: (dataUrl) => post('/auth/kyc/submit', { kyc_document_url: dataUrl }),
    closeAccount: () => del('/auth/account'),
    exitImpersonation: () => post('/auth/impersonation/exit'),
    acceptTerms: () => post('/auth/accept-terms'),
    uploadAvatar: (image) => post('/auth/avatar', { image }),
    removeAvatar: () => del('/auth/avatar'),
  },
  wallets: {
    list: () => get('/wallets'),
    methods: () => get('/wallets/payment-methods'),
    transactions: (query) => get('/wallets/transactions', query),
    transaction: (id) => get(`/wallets/transactions/${id}`),
    transfer: (payload) => post('/wallets/transfer', payload),
    p2p: (payload) => post('/wallets/p2p-transfer', payload),
    deposit: (payload) => post('/wallets/deposits', payload),
    withdraw: (payload) => post('/wallets/withdrawals', payload),
  },
  investments: {
    plans: () => get('/investments/plans'),
    mine: () => get('/investments/my-investments'),
    create: (plan_id, amount) => post('/investments', { plan_id, amount, accept_risk: true }),
  },
  notifications: {
    list: () => get('/notifications'),
    unread: () => get('/notifications/unread-count'),
    read: (id) => patch(`/notifications/${id}/read`),
    readAll: () => patch('/notifications/read-all'),
  },
  referrals: { stats: () => get('/users/me/referrals') },
  support: { send: (payload) => request('/support/requests', { method: 'POST', body: payload, quiet401: true }) },
  me: {
    dashboard: () => get('/users/me/dashboard'),
    context: () => get('/users/me/context'),   // standing + balances + payment methods, for money dialogs
  },
  admin: {
    stats: () => get('/admin/stats'),
    overview: () => get('/admin/overview'),
    queueCounts: () => get('/admin/queue-counts'),
    users: (query) => get('/admin/users', query),
    user: (id) => get(`/admin/users/${id}`),
    setUserFlags: (id, flags) => patch(`/admin/users/${id}/status`, flags),
    setRole: (id, isAdmin) => patch(`/admin/users/${id}/role`, { is_admin: isAdmin }),
    impersonate: (id) => post(`/admin/users/${id}/impersonate`),
    resetTwoFactor: (id) => post(`/admin/users/${id}/reset-2fa`),
    credit: (payload) => post('/admin/credit', payload),
    debit: (payload) => post('/admin/wallets/debit', payload),
    transactions: (query) => request('/admin/transactions', { query, raw: true }),
    transaction: (id) => get(`/admin/transactions/${id}`),
    pendingDeposits: () => get('/admin/deposits/pending'),
    pendingWithdrawals: () => get('/admin/withdrawals/pending'),
    reviewDeposit: (id, payload) => patch(`/admin/deposits/${id}/review`, payload),
    reviewWithdrawal: (id, payload) => patch(`/admin/withdrawals/${id}/review`, payload),
    pendingKyc: () => get('/admin/kyc/pending'),
    kycDocument: (id) => get(`/admin/kyc/${id}/document`),
    reviewKyc: (id, payload) => patch(`/admin/kyc/${id}/review`, payload),
    plans: () => get('/admin/plans'),
    createPlan: (payload) => post('/admin/plans', payload),
    updatePlan: (id, payload) => patch(`/admin/plans/${id}`, payload),
    deletePlan: (id) => del(`/admin/plans/${id}`),
    investments: (query) => get('/admin/investments', query),
    runRoi: () => post('/admin/investments/process-roi'),
    methods: () => get('/admin/payment-methods'),
    createMethod: (payload) => post('/admin/payment-methods', payload),
    updateMethod: (id, payload) => patch(`/admin/payment-methods/${id}`, payload),
    deleteMethod: (id) => del(`/admin/payment-methods/${id}`),
    audit: (query) => get('/admin/audit-logs', query),
    broadcast: (payload) => post('/admin/emails/broadcast', payload),
    broadcastHistory: () => get('/admin/emails/history'),
    emailUser: (payload) => post('/admin/emails/send-user', payload),
  },
};
