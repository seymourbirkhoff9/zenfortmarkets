import { resolve } from 'node:path';
import { defineConfig } from 'vite';

// Multi-page build. In dev, /api is proxied to FastAPI so the browser sees a
// single origin: the httpOnly session cookie then just works, with no CORS.
const page = (name) => resolve(__dirname, name);

export default defineConfig({
  server: {
    port: 3000,
    proxy: { '/api': { target: process.env.VITE_API_PROXY || 'http://localhost:8000', changeOrigin: true } },
  },
  preview: {
    port: 3000,
    proxy: { '/api': { target: process.env.VITE_API_PROXY || 'http://localhost:8000', changeOrigin: true } },
  },
  build: {
    rollupOptions: {
      input: {
        index: page('index.html'),
        login: page('login.html'),
        signup: page('signup.html'),
        verify: page('verify-email.html'),
        app: page('app.html'),
        admin: page('admin.html'),
        terms: page('terms.html'),
        privacy: page('privacy.html'),
        risk: page('risk.html'),
        how: page('how-it-works.html'),
        fees: page('fees.html'),
        security: page('security.html'),
        faq: page('faq.html'),
        about: page('about.html'),
        contact: page('contact.html'),
      },
    },
  },
});
