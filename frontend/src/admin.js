import './styles.css';
import { api } from './lib/api.js';
import { createRouter } from './lib/router.js';
import { invalidate, prefetch } from './lib/cache.js';
import { mountShell } from './shell.js';
import { session } from './session.js';
import overview from './pages/admin/overview.js';
import { depositsQueue, withdrawalsQueue } from './pages/admin/queues.js';
import kyc from './pages/admin/kyc.js';
import customers from './pages/admin/customers.js';
import customer from './pages/admin/customer.js';
import ledger from './pages/admin/ledger.js';
import plans from './pages/admin/plans.js';
import methods from './pages/admin/methods.js';
import broadcast from './pages/admin/broadcast.js';
import audit from './pages/admin/audit.js';
import investments from './pages/admin/investments.js';
import fx from './pages/admin/fx.js';

const NAV = [
  { href: '#/', label: 'Overview', icon: 'home', match: '/' },
  { section: 'Review' },
  { href: '#/deposits', label: 'Deposits', icon: 'down', match: '/deposits', badge: 'deposits' },
  { href: '#/withdrawals', label: 'Withdrawals', icon: 'up', match: '/withdrawals', badge: 'withdrawals' },
  { href: '#/kyc', label: 'Identity checks', icon: 'id', match: '/kyc', badge: 'kyc' },
  { section: 'Records' },
  { href: '#/customers', label: 'Customers', icon: 'users', match: '/customers' },
  { href: '#/investments', label: 'Investments', icon: 'chart', match: '/investments' },
  { href: '#/ledger', label: 'Ledger', icon: 'list', match: '/ledger' },
  { href: '#/audit', label: 'Audit log', icon: 'shield', match: '/audit' },
  { section: 'Configuration' },
  { href: '#/plans', label: 'Investment plans', icon: 'layers', match: '/plans' },
  { href: '#/methods', label: 'Payment methods', icon: 'coin', match: '/methods' },
  { href: '#/fx', label: 'FX Rates', icon: 'exchange', match: '/fx' },
  { href: '#/broadcast', label: 'Email customers', icon: 'mail', match: '/broadcast' },
];

const TITLES = { '/': 'Overview', '/deposits': 'Deposits', '/withdrawals': 'Withdrawals', '/kyc': 'Identity checks',
  '/customers': 'Customers', '/customers/:id': 'Customer', '/ledger': 'Ledger', '/audit': 'Audit log',
  '/plans': 'Investment plans', '/investments': 'Investments', '/methods': 'Payment methods', '/fx': 'FX Rates', '/broadcast': 'Email customers' };

(async () => {
  // Preload only if this browser was an admin last time; avoids a pointless 403 for customers.
  let wasAdmin = false; try { wasAdmin = sessionStorage.getItem('zf-admin') === '1'; } catch { /* private mode */ }
  if (wasAdmin && (!location.hash || location.hash === '#/')) prefetch('admin:overview', api.admin.overview);
  const user = await api.auth.me();
  try { sessionStorage.setItem('zf-admin', user.is_admin ? '1' : '0'); } catch { /* private mode */ }
  if (!user.is_admin) { location.href = '/app.html'; return; }
  session.user = user;
  const shell = mountShell({ area: 'admin', user, nav: NAV });

  // Queue badges: kept fresh so the operator sees new work without reloading.
  const refreshBadges = async () => {
    if (document.hidden) return;
    try {
      shell.setBadges(await api.admin.queueCounts());   // one query on the server
    } catch { /* silent */ }
  };
  refreshBadges();
  setInterval(refreshBadges, 30_000);
  document.addEventListener('visibilitychange', refreshBadges);
  window.addEventListener('zf:queues-changed', () => { invalidate('admin:'); refreshBadges(); });

  createRouter({
    '/': overview, '/deposits': depositsQueue, '/withdrawals': withdrawalsQueue, '/kyc': kyc,
    '/customers': customers, '/customers/:id': customer, '/ledger': ledger, '/audit': audit,
    '/plans': plans, '/investments': investments, '/methods': methods, '/fx': fx, '/broadcast': broadcast, '*': overview,
  }, { onRoute: (pattern, path) => { shell.setActive(path); document.title = `${TITLES[pattern] || 'Overview'} — Zenfort operations`; } }).start();
})();
