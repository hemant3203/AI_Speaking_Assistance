/** System status. Needs no auth, and says whether the coach can run at all. */
import { api } from './client';

export const fetchHealth = () => api('/health', { ignoreUnauthorized: true });
