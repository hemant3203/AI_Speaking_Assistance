/** Analytics overview. `days` is 7, 30, 90, or 0 for all time. */
import { api } from './client';

export const fetchOverview = (days = 30) => api('/analytics/overview', { query: { days } });
