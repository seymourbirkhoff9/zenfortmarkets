/**
 * What the support assistant knows. Each topic has:
 *   keys:    words/phrases that point to it (matched after normalising, see match.js)
 *   answer:  short, plain text (rendered safely, never as HTML)
 *   links:   optional [label, href] buttons
 *   live:    optional name of a live check for signed-in customers (see widget.js)
 *   escalate: true when the honest answer is "a person needs to look at this"
 * To teach it something new, add a topic here. Keep answers short and specific.
 */
export const TOPICS = [
  { id: 'hello', keys: ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening'],
    answer: 'Hi! I can help with deposits, withdrawals, verification, investments, your account and security. What do you need?' },
  { id: 'thanks', keys: ['thanks', 'thank you', 'thx', 'great', 'perfect', 'ok thanks'],
    answer: 'You’re welcome. Anything else I can help with?' },
  { id: 'legit', keys: ['real', 'legit', 'scam', 'real money', 'demo', 'educational', 'is this safe', 'trust', 'fake'],
    answer: 'Zenfort Markets is an educational demo of how a brokerage back office works. Balances and returns are simulated. Please don’t send real funds.',
    links: [['About Zenfort', '/about.html'], ['Risk Disclosure', '/risk.html']] },

  // Deposits
  { id: 'deposit_how', keys: ['deposit', 'fund', 'top up', 'add money', 'add funds', 'send crypto', 'pay in', 'how to deposit', 'deposit address', 'wallet address'],
    answer: 'To deposit: open Deposits & withdrawals, choose Deposit, pick the asset and network, and send from your own wallet to the address shown. Then report the dollar value with the transaction hash or a screenshot. An operator checks it and credits your Main wallet.',
    links: [['Make a deposit', '/app.html#/wallet'], ['Supported networks', '/fees.html#networks']] },
  { id: 'deposit_status', keys: ['deposit pending', 'deposit not credited', 'deposit not showing', 'where is my deposit', 'deposit delay', 'deposit taking long', 'not received deposit', 'my deposit', 'not showing', 'not credited', 'sent usdt', 'sent btc', 'sent eth', 'sent crypto', 'payment not showing'],
    answer: 'Deposits are credited after an operator sees your payment arrive on-chain. You’ll get a notification and email as soon as it’s confirmed or if something needs fixing.',
    live: 'deposits', links: [['Deposits & withdrawals', '/app.html#/wallet']] },
  { id: 'deposit_wrong', keys: ['wrong network', 'wrong address', 'sent wrong', 'wrong coin', 'wrong asset', 'lost funds', 'sent to wrong'],
    answer: 'Funds sent on a different network or to the wrong address usually can’t be recovered, because blockchain transfers are irreversible. Contact support with the transaction hash and we’ll check what’s possible.',
    escalate: true },
  { id: 'deposit_rejected', keys: ['deposit rejected', 'deposit declined', 'why rejected', 'rejected deposit'],
    answer: 'The reason for a rejected deposit is shown on the deposit in Deposits & withdrawals and in your notification. Common causes: a hash that doesn’t match a payment, or an amount that doesn’t match what arrived. You can report it again with the correct details.',
    links: [['See my deposits', '/app.html#/wallet']] },

  // Withdrawals
  { id: 'withdraw_how', keys: ['withdraw', 'withdrawal', 'cash out', 'payout', 'pay out', 'send to my wallet', 'take out money', 'get my money'],
    answer: 'To withdraw: open Deposits & withdrawals, choose Withdraw, pick the payout method, paste your wallet address and enter the amount. The amount is held right away and an operator sends the payout. You’ll get the payout transaction hash.',
    links: [['Withdraw', '/app.html#/wallet?tab=withdrawal']] },
  { id: 'withdraw_status', keys: ['withdrawal pending', 'withdrawal not received', 'where is my withdrawal', 'withdrawal delay', 'payout pending', 'not received payout', 'my withdrawal'],
    answer: 'Withdrawals are paid by an operator after review. While pending, the amount is held from your Main wallet; if it’s rejected, the full amount comes back. Once paid, you’ll see the payout reference you can check on the blockchain.',
    live: 'withdrawals', links: [['My withdrawals', '/app.html#/wallet?tab=withdrawal']] },
  { id: 'withdraw_fee', keys: ['fee', 'fees', 'charge', 'cost', 'how much does it cost', 'minimum', 'limit', 'limits'],
    answer: 'There’s no deposit fee and transfers between wallets are free. Withdrawals have a flat fee per network, shown before you confirm. Minimums depend on the network.',
    links: [['Fees & limits', '/fees.html']] },
  { id: 'withdraw_kyc', keys: ['cant withdraw', 'cannot withdraw', 'withdraw blocked', 'withdraw disabled', 'verify before withdraw', 'withdrawal not allowed'],
    answer: 'Withdrawals need a verified identity. Upload an ID document from Settings. If your account shows that withdrawals are turned off, contact support to find out why.',
    live: 'kyc', links: [['Settings', '/app.html#/settings']] },

  // Identity
  { id: 'kyc', keys: ['kyc', 'verify identity', 'verification', 'id document', 'passport', 'identity', 'upload id', 'driver licence', 'national id'],
    answer: 'Upload a passport, national ID or driver’s licence from Settings → Identity verification. Use a clear photo with all four corners visible, or a PDF. An operator reviews it and you’ll be notified.',
    live: 'kyc', links: [['Verify identity', '/app.html#/settings']] },
  { id: 'kyc_rejected', keys: ['kyc rejected', 'id rejected', 'verification failed', 'document rejected', 'identity rejected'],
    answer: 'If your document was rejected, the reason is shown in Settings. Upload a new, sharper photo with all corners visible.',
    live: 'kyc', links: [['Settings', '/app.html#/settings']] },

  // Investing & wallets
  { id: 'invest', keys: ['invest', 'investment', 'plan', 'plans', 'roi', 'return', 'returns', 'interest', 'profit', 'earn', 'daily'],
    answer: 'Plans are set by the operator: a daily rate, a term and an amount range. Your amount comes from Main and is locked for the term; returns go to Profit daily and the principal returns to Main at the end. Returns aren’t guaranteed; in this demo they’re simulated.',
    links: [['See plans', '/app.html#/invest'], ['Risk Disclosure', '/risk.html']] },
  { id: 'invest_early', keys: ['cancel investment', 'end investment early', 'withdraw investment', 'stop investment', 'early exit', 'unlock'],
    answer: 'Investments can’t be ended early. The amount is locked for the full term and then returned to your Main wallet automatically.' },
  { id: 'wallets', keys: ['main wallet', 'profit wallet', 'move funds', 'move money', 'transfer between wallets', 'balance', 'my balance'],
    answer: 'Main is your spendable wallet: deposits arrive there and withdrawals and investments come from it. Profit collects investment returns. Move money between them any time with “Move between wallets” on the Overview.',
    live: 'balance', links: [['Overview', '/app.html#/']] },
  { id: 'p2p', keys: ['send to friend', 'send to customer', 'transfer to user', 'p2p', 'send money to someone', 'pay someone'],
    answer: 'You can send money instantly from your Main wallet to another customer using their account email: Overview → Send to a customer. Transfers can’t be reversed, so double-check the email.' },
  { id: 'referral', keys: ['referral', 'refer', 'invite', 'bonus', 'referral code', 'referral link'],
    answer: 'Share your code or sign-up link from the Referrals page. When someone you referred makes their first approved deposit or investment, you get a one-time bonus in your Main wallet.',
    links: [['Referrals', '/app.html#/referrals']] },

  // Account & security
  { id: 'password_forgot', keys: ['forgot password', 'reset password', 'cant log in', 'cannot login', 'cant sign in', 'locked out', 'lost password', 'password reset', 'login problem'],
    answer: 'Use “Forgot password?” on the sign-in page. We’ll email a link that works once for 30 minutes. If you’ve had too many attempts, wait 15 minutes first.',
    links: [['Reset password', '/forgot-password.html']] },
  { id: 'password_change', keys: ['change password', 'new password', 'update password'],
    answer: 'Change your password in Settings → Password. You’ll stay signed in on this device and be signed out everywhere else.',
    links: [['Settings', '/app.html#/settings']] },
  { id: 'twofa', keys: ['2fa', 'two factor', 'two-factor', 'authenticator', 'otp', 'google authenticator', 'authy', 'security code', 'verification code'],
    answer: 'Turn on two-factor sign-in in Settings: scan the QR code with an authenticator app, enter a code, and save your recovery codes. After that, sign-in asks for a 6-digit code from your phone.',
    links: [['Settings', '/app.html#/settings']] },
  { id: 'twofa_lost', keys: ['lost phone', 'lost my phone', 'new phone', 'no authenticator', 'lost authenticator', 'lost recovery codes', 'cant get code', 'code not working'],
    answer: 'If you lost your phone, choose “Use a recovery code instead” when signing in. If you don’t have recovery codes either, support can turn off two-factor after confirming your identity.',
    escalate: true },
  { id: 'email_verify', keys: ['verify email', 'confirm email', 'confirmation email', 'didnt get email', 'no email', 'email not received', 'resend email'],
    answer: 'Check spam and promotions first. You can send a new confirmation link from Settings or the Overview. Links expire after 24 hours.',
    links: [['Settings', '/app.html#/settings']] },
  { id: 'profile', keys: ['change name', 'profile photo', 'avatar', 'picture', 'phone number', 'update profile'],
    answer: 'Update your name, phone and profile photo in Settings → Profile.', links: [['Settings', '/app.html#/settings']] },
  { id: 'close', keys: ['delete account', 'close account', 'remove account', 'deactivate'],
    answer: 'You can close your account from Settings once your balance is zero. Your photo and ID document are deleted; transaction records are kept for accounting.',
    links: [['Settings', '/app.html#/settings']] },
  { id: 'restricted', keys: ['account restricted', 'account blocked', 'account suspended', 'frozen', 'restricted'],
    answer: 'If your account is restricted, deposits, withdrawals and investments are paused. Only support can explain why and lift it.', escalate: true },
  { id: 'phishing', keys: ['phishing', 'someone asked my password', 'suspicious email', 'hacked', 'unauthorized', 'not me', 'someone logged in'],
    answer: 'We’ll never ask for your password or codes. If you think someone accessed your account: reset your password now (this signs out every device), turn on two-factor sign-in, and contact support.',
    links: [['Reset password', '/forgot-password.html']], escalate: true },
  { id: 'language', keys: ['language', 'translate', 'french', 'spanish', 'arabic', 'chinese', 'other language'],
    answer: 'Use the globe button at the top of the page to translate it into your language.' },
  { id: 'human', keys: ['human', 'agent', 'person', 'support', 'contact', 'talk to someone', 'customer service', 'help me', 'complaint', 'speak to'],
    answer: 'I can pass this to our support team. They reply by email.', escalate: true },
];

export const STARTERS = [
  ['Where is my deposit?', 'deposit_status'], ['How do I withdraw?', 'withdraw_how'],
  ['Verify my identity', 'kyc'], ['I forgot my password', 'password_forgot'], ['Talk to support', 'human'],
];
