/**
 * smartsupp.js — Smartsupp Live Chat & Visitor Tracking
 * Key: 81a7757de0b4677ad950ebec932ec3a7a4426fc8
 */

const SMARTSUPP_KEY = '81a7757de0b4677ad950ebec932ec3a7a4426fc8';

export function initSmartsupp(user = null) {
  if (typeof window === 'undefined') return;

  // Never load on admin dashboard to prevent admin from self-triggering visitor alerts
  if (window.location.pathname.includes('/admin.html')) return;

  if (!window._smartsuppLoaded) {
    window._smartsuppLoaded = true;

    window._smartsupp = window._smartsupp || {};
    window._smartsupp.key = SMARTSUPP_KEY;
    // Offset slightly above the built-in Help button so both remain accessible
    window._smartsupp.offsetY = 72;

    window.smartsupp || (function(d) {
      var s, c, o = window.smartsupp = function() { o._.push(arguments); };
      o._ = [];
      s = d.getElementsByTagName('script')[0];
      c = d.createElement('script');
      c.type = 'text/javascript';
      c.charset = 'utf-8';
      c.async = true;
      c.src = 'https://www.smartsuppchat.com/loader.js?';
      if (s && s.parentNode) {
        s.parentNode.insertBefore(c, s);
      } else {
        d.head.appendChild(c);
      }
    })(document);
  }

  // Identify logged in user if available
  if (user && typeof window.smartsupp === 'function') {
    try {
      if (user.full_name) window.smartsupp('name', user.full_name);
      if (user.email) window.smartsupp('email', user.email);
      if (user.phone) window.smartsupp('phone', user.phone);
      window.smartsupp('variables', {
        id: { value: String(user.id), label: 'User ID' },
        currency: { value: user.display_currency || 'USD', label: 'Currency' },
        language: { value: user.preferred_language || 'en', label: 'Language' },
      });
    } catch {
      // safe fallback
    }
  }
}

/**
 * Track SPA route changes in Smartsupp
 */
export function trackSmartsuppRoute(path) {
  if (typeof window !== 'undefined' && typeof window.smartsupp === 'function') {
    try {
      window.smartsupp('track', 'pageview', { path: path || (location.pathname + location.hash) });
    } catch {
      // safe fallback
    }
  }
}

// Auto-initialize on public and auth pages
if (typeof window !== 'undefined' && !window.location.pathname.includes('/admin.html')) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initSmartsupp());
  } else {
    initSmartsupp();
  }
}

