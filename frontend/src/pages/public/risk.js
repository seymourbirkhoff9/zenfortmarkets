import { legalPage, SITE } from './layout.js';

legalPage({
  title: 'Risk Disclosure',
  intro: 'Please read this before depositing or investing. It explains what can go wrong.',
  sections: [
    ['Investment risks', [
      `${SITE.name} provides investment opportunities but cryptocurrency investments carry inherent risks. Past performance does not guarantee future results.`,
      'You should carefully consider your financial situation and risk tolerance before investing.',
    ]],
    ['Returns are not guaranteed', [
      'Plan rates show expected returns based on historical performance and market conditions. Returns can vary based on market volatility and you could lose some or all of the amount you invest.',
      'Cryptocurrency markets are highly volatile. Only invest amounts you can afford to lose.',
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
