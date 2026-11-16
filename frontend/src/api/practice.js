/** Practice catalog and sessions. */
import { api } from './client';

export const fetchCatalog = () => api('/practice/catalog');
export const createSession = (body) => api('/practice/sessions', { method: 'POST', body });
export const fetchSessions = ({ limit = 20, offset = 0, mode } = {}) => api('/practice/sessions', { query: { limit, offset, mode } });
export const fetchSession = (id) => api(`/practice/sessions/${encodeURIComponent(id)}`);
export const deleteSession = (id) => api(`/practice/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' });
