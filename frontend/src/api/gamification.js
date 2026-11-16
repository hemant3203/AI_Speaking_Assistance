/** Streaks, XP, quests, badges and the sparks shop. */
import { api } from './client';

export const fetchProfile = () => api('/gamification/profile');
export const fetchBadges = () => api('/gamification/badges');
export const fetchShop = () => api('/gamification/shop');
export const purchaseItem = (id) => api(`/gamification/shop/${encodeURIComponent(id)}/purchase`, { method: 'POST' });
export const equipCoach = (id) => api(`/gamification/coaches/${encodeURIComponent(id)}/equip`, { method: 'POST' });
export const fetchActivity = (limit = 20) => api('/gamification/activity', { query: { limit } });
