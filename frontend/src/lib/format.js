const plain = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Dynamic formatter cache - creates formatters on-demand for any currency
const formatterCache = new Map();

function getFormatter(currency) {
  if (formatterCache.has(currency)) {
    return formatterCache.get(currency);
  }
  
  // Create formatter on-demand for any currency
  // Use en-US locale as default, but format with the target currency
  const formatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  
  formatterCache.set(currency, formatter);
  return formatter;
}

/** Amounts arrive as decimal strings; Number is fine for display at 2dp, never for maths we send back. */
export const money = (v, currency = 'USD') => {
  const fmt = getFormatter(currency);
  return fmt.format(Number(v || 0));
};
export const amount = (v) => plain.format(Number(v || 0));
export const pct = (v) => `${Number(v).toLocaleString('en-US', { maximumFractionDigits: 4 })}%`;

const dateFmt = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
const dateTimeFmt = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
export const date = (v) => (v ? dateFmt.format(new Date(v)) : '—');
export const dateTime = (v) => (v ? dateTimeFmt.format(new Date(v)) : '—');

export function ago(v) {
  if (!v) return '—';
  const s = Math.max(0, (Date.now() - new Date(v).getTime()) / 1000);
  if (s < 60) return 'just now';
  const m = s / 60; if (m < 60) return `${Math.floor(m)} min ago`;
  const h = m / 60; if (h < 24) return `${Math.floor(h)} h ago`;
  const d = h / 24; return `${Math.floor(d)} d ago`;
}

/** "3 h 20 min" style waiting time, for review queues. */
export function waited(v) {
  if (!v) return '—';
  const mins = Math.max(0, Math.floor((Date.now() - new Date(v).getTime()) / 60000));
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  if (h < 48) return `${h} h ${mins % 60} min`;
  return `${Math.floor(h / 24)} days`;
}

export const shorten = (s, head = 8, tail = 6) => (!s ? '—' : s.length <= head + tail + 1 ? s : `${s.slice(0, head)}…${s.slice(-tail)}`);

export const TX_LABEL = {
  deposit: 'Deposit',
  withdrawal: 'Withdrawal',
  transfer: 'Wallet move',
  p2p: 'Transfer',
  investment: 'Investment',
  roi_credit: 'Investment return',
  principal_return: 'Principal returned',
  admin_credit: 'Credit',
  admin_debit: 'Debit',
  referral_bonus: 'Referral bonus',
};
export const txLabel = (t) => TX_LABEL[t] || t;

export function statusPill(status) {
  const map = { completed: ['pill-settled', 'Settled'], pending: ['pill-pending', 'Pending review'],
    rejected: ['pill-rejected', 'Rejected'], active: ['pill-settled', 'Active'],
    cancelled: ['pill-neutral', 'Cancelled'] };
  const [cls, text] = map[status] || ['pill-neutral', status];
  return { cls, text };
}
