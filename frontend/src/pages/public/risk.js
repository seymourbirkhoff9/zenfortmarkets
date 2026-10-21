import { legalPage, SITE } from './layout.js';

legalPage({
  title: 'Risk Disclosure',
  intro: 'Please read this before depositing or investing. It explains what can go wrong.',
  sections: [
    ['This is not investment advice', [
      `${SITE.name} is an educational demonstration. Nothing on the site is a recommendation to buy, sell or hold any asset, and it is not regulated as an investment service.`,
    ]],
    ['Returns are not guaranteed', [
      'Plan rates show what the operator intends to pay, not a promise. Returns can be delayed, reduced or stopped, and you could lose some or all of the amount you invest.',
      'A high fixed daily return is a warning sign in real financial products. Be very cautious with any real platform that offers one.',
    ]],
    ['Crypto transfers are irreversible', [
      'Sending to the wrong address, or on a different network than the one shown, usually cannot be undone. Always check the asset, network and address before you send.',
    ]],
    ['Prices move', [
      'The value of crypto assets can change sharply in minutes. The dollar value you report for a deposit, or receive for a withdrawal, depends on prices at the time of the transfer.',
    ]],
    ['Platform and operational risk', [
      'Deposits and withdrawals are reviewed by people and can take time. The service could be unavailable, restricted or closed. Only use amounts you can afford to lose.',
    ]],
    ['Before you go further', [
      'If you are unsure, do not invest. Speak to an independent, qualified adviser.',
    ]],
  ],
});
