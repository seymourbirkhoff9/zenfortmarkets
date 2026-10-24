import { legalPage } from './layout.js';

legalPage({
  title: 'Risk Disclosure',
  intro: 'Please read this before depositing or investing. It explains what can go wrong.',
  sections: [
    ['Crypto transfers are irreversible', [
      'Sending to the wrong address, or on a different network than the one shown, usually cannot be undone. Always check the asset, network and address before you send.',
    ]],
    ['Prices move', [
      'The value of crypto assets can change sharply in minutes. The dollar value you report for a deposit, or receive for a withdrawal, depends on prices at the time of the transfer.',
    ]],
    ['Platform and operational risk', [
      'Deposits and withdrawals are reviewed by people and can take time. The service could be unavailable, restricted or closed. Only use amounts you can afford to lose.',
    ]],
  ],
});
