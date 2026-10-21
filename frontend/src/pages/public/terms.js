import { legalPage, raw, SITE } from './layout.js';

legalPage({
  title: 'Terms of Service',
  intro: `These terms govern your use of ${SITE.name}. By creating an account you agree to them.`,
  sections: [
    ['What this service is', [
      `${SITE.name} is a cryptocurrency trading and investment platform operated by ${SITE.operator}.`,
      'The platform provides secure wallet management, investment plans, and professional trading services for cryptocurrency assets.',
      'All transactions are processed securely and balances are maintained in USD for consistency across the platform.',
    ]],
    ['Who can use it', [
      'You must be at least 18 years old and able to form a binding agreement where you live. You may hold only one account.',
      'You are responsible for keeping your password secret and for everything done through your account.',
    ]],
    ['Your account and identity checks', [
      'You must give accurate information. We may ask for an identity document before allowing withdrawals and may refuse or reverse access if information is false.',
      'You can close your account from Settings once your balance is zero. Transaction records are kept as described in the Privacy Policy.',
    ]],
    ['Deposits and withdrawals', [
      'Deposits are credited only after an operator reviews them. Send only the asset and network shown for the method you chose; assets sent on the wrong network or to the wrong address may be lost permanently.',
      'Withdrawal requests are reviewed by an operator. The requested amount is held from your balance while pending and returned if the request is rejected. Network fees shown before you confirm are deducted from the payout.',
    ]],
    ['Investment plans', [
      'Plans, their daily rates and terms are set by the operator and may change for new investments at any time. An investment keeps the rate and term it started with.',
      'Returns are not guaranteed. Invested amounts are locked for the full term. Read the Risk Disclosure before investing.',
    ]],
    ['Things you must not do', [
      'Use the service for anything unlawful, including money laundering or fraud; access another person’s account; interfere with the service or its security; or create accounts to abuse the referral programme.',
    ]],
    ['Restricting or closing accounts', [
      'We may restrict deposits, withdrawals or the whole account, or close it, if we reasonably suspect a breach of these terms, a legal requirement applies, or to protect other users. Where we can, we will tell you why.',
    ]],
    ['Liability', [
      `The service is provided “as is”. To the extent the law allows, ${SITE.operator} is not liable for indirect or consequential loss, or for losses caused by blockchain networks, third-party wallets or events outside our reasonable control.`,
    ]],
    ['Changes to these terms', [
      'We may update these terms. When we do, the version number above changes and you will be asked to accept the new version before continuing to use your account.',
    ]],
    ['Governing law and contact', [
      `These terms are governed by the laws of ${SITE.jurisdiction}.`,
      raw(`Questions: <a class="btn-link" href="mailto:${SITE.contactEmail}">${SITE.contactEmail}</a>.`),
    ]],
  ],
});
