/**
 * Picks the best topic for a message. Normalises text (case, punctuation, common
 * misspellings/contractions), matches phrases first, then single words with light
 * stemming. Returns { topic, score } or null when nothing is a confident match.
 */
import { TOPICS } from './kb.js';

const FIX = { 'cant': 'cant', "can't": 'cant', 'cannot': 'cant', "didn't": 'didnt', 'withdrawl': 'withdrawal', 'withdrawel': 'withdrawal',
  'withdrawls': 'withdrawal', 'deposite': 'deposit', 'depost': 'deposit', 'pasword': 'password', 'passwrd': 'password', 'logn': 'login',
  'log in': 'login', 'sign in': 'login', 'signin': 'login', 'kyc': 'kyc', 'acct': 'account', 'pls': 'please', 'plz': 'please',
  'recieve': 'receive', 'recieved': 'received', 'havent': 'not', "haven't": 'not', 'isnt': 'not', "isn't": 'not', 'wasnt': 'not' };

export function normalise(text) {
  let s = ` ${String(text).toLowerCase().replace(/[’']/g, "'")} `;
  Object.entries(FIX).forEach(([a, b]) => { s = s.replace(new RegExp(`(?<=\\s)${a.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?=\\s|[.,!?])`, 'g'), b); });
  return s.replace(/[^a-z0-9\s-]/g, ' ').replace(/\s+/g, ' ').trim();
}

const stem = (w) => w.replace(/(ings|ing|ed|es|s)$/, '') || w;
const STOP = new Set(['the', 'a', 'an', 'i', 'my', 'me', 'to', 'is', 'it', 'of', 'and', 'or', 'how', 'do', 'can', 'for', 'on', 'in', 'what', 'why',
  'when', 'where', 'please', 'you', 'your', 'this', 'that', 'with', 'have', 'has', 'am', 'are', 'be', 'was', 'there', 'get', 'help']);

export function match(text) {
  const norm = normalise(text);
  const words = new Set(norm.split(' ').filter((w) => !STOP.has(w)).map(stem));
  let best = null;
  for (const t of TOPICS) {
    let score = 0;
    for (const key of t.keys) {
      const k = normalise(key);
      const kw = k.split(' ').filter((w) => !STOP.has(w)).map(stem);
      if (!kw.length) continue;
      if (kw.length > 1) {
        // A phrase counts when all its meaningful words appear, in any order ("forgot MY password").
        if (kw.every((w) => words.has(w))) score += 2 + 1.5 * kw.length + (` ${norm} `.includes(` ${k} `) ? 1 : 0);
      } else if (words.has(kw[0])) score += 2 + (k.includes(' ') && ` ${norm} `.includes(` ${k} `) ? 3 : 0);  // exact phrase bonus
    }
    if (score && (!best || score > best.score)) best = { topic: t, score };
  }
  return best && best.score >= 2 ? best : null;
}
