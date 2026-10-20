import { api } from './lib/api.js';

/** The signed-in user, shared by every view. Call refreshUser() after profile/KYC changes. */
export const session = { user: null };
export async function refreshUser() {
  session.user = await api.auth.me();
  return session.user;
}
