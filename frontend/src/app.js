import './styles.css';
import { api } from './lib/api.js';
import { createRouter } from './lib/router.js';
import { mountShell } from './shell.js';
import { session } from './session.js';
import { prefetch } from './lib/cache.js';
import overview from './pages/user/overview.js';
import wallet from './pages/user/wallet.js';
import invest from './pages/user/invest.js';
import activity from './pages/user/activity.js';
import referrals from './pages/user/referrals.js';
import settings from './pages/user/settings.js';

const NAV = [
  { href: '#/', label: 'Overview', icon: 'home', match: '/' },
  { href: '#/wallet', label: 'Deposits & withdrawals', icon: 'wallet', match: '/wallet' },
  { href: '#/invest', label: 'Invest', icon: 'chart', match: '/invest' },
  { href: '#/activity', label: 'Activity', icon: 'list', match: '/activity' },
  { href: '#/referrals', label: 'Referrals', icon: 'gift', match: '/referrals' },
  { href: '#/settings', label: 'Settings', icon: 'gear', match: '/settings' },
];

(async () => {
  // Start loading the overview while we confirm who's signed in: two requests in parallel, not in a row.
  if (!location.hash || location.hash === '#/') prefetch('dashboard', api.me.dashboard);
  const user = await api.auth.me();          // 401 → redirected to sign in
  session.user = user;
  const shell = mountShell({ area: 'user', user, nav: NAV });
  const titles = { '/': 'Overview', '/wallet': 'Deposits & withdrawals', '/invest': 'Invest',
    '/activity': 'Activity', '/referrals': 'Referrals', '/settings': 'Settings' };
  createRouter(
    { '/': overview, '/wallet': wallet, '/invest': invest, '/activity': activity,
      '/referrals': referrals, '/settings': settings, '*': overview },
    { onRoute: (pattern, path) => { shell.setActive(path); document.title = `${titles[pattern] || 'Overview'} — Zenfort Markets`; } },
  ).start();
})();
