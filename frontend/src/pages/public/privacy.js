import { legalPage, raw, SITE } from './layout.js';

legalPage({
  title: 'Privacy Policy',
  intro: `How ${SITE.name} collects, uses and protects your personal information.`,
  sections: [
    ['Who is responsible', [
      `${SITE.operator} operates ${SITE.name} and is responsible for your personal information.`,
      raw(`Contact: <a class="btn-link" href="mailto:${SITE.contactEmail}">${SITE.contactEmail}</a>.`),
    ]],
    ['What we collect', [
      'Account details: name, email address, country, optional phone number and profile photo, and your password (stored only as a secure hash).',
      'Identity documents you upload for verification.',
      'Financial activity: deposits, withdrawals, wallet addresses you provide, transaction hashes, payment screenshots, investments and transfers.',
      'Technical data needed to run the service: sign-in session cookie and server logs of requests.',
    ]],
    ['Why we use it', [
      'To run your account and process the requests you make; to verify identity and prevent fraud; to send you service messages (for example, when a deposit is approved); and to meet legal obligations.',
      'We do not sell your personal information and we do not use it for advertising.',
    ]],
    ['Cookies', [
      'We use one essential cookie to keep you signed in. It is not used for tracking. The site also remembers your light/dark preference in your browser.',
    ]],
    ['Who we share it with', [
      'Service providers who process data for us: our database and file storage provider (Supabase), our email provider (Resend) and our hosting providers. They may only use it to provide their service to us.',
      'Authorities, where the law requires it.',
    ]],
    ['Where it is stored and how it is protected', [
      'Data is stored with our providers, which may be outside your country. Identity documents and payment screenshots are kept in private storage and opened only by authorised operators through short-lived links. Connections are encrypted.',
    ]],
    ['How long we keep it', [
      'Account and transaction records are kept for as long as your account is open and afterwards for as long as needed for legal, accounting or dispute purposes. When you close your account, your profile photo and identity document are deleted and your name and email are removed from the account record.',
    ]],
    ['Your rights', [
      `Depending on where you live, you may ask to access, correct or delete your information, or object to how it is used. Email ${SITE.contactEmail}. You can also complain to your local data protection authority.`,
    ]],
    ['Changes', [
      'If we change this policy, the version number above changes and you will be asked to accept the new version.',
    ]],
  ],
});
