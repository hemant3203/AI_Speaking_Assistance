/** Auth endpoints. The session lives in an httpOnly cookie, so tokens never touch JavaScript. */
import { api } from './client';

export const fetchMe = () => api('/auth/me', { ignoreUnauthorized: true });
export const login = (body) => api('/auth/login', { method: 'POST', body, ignoreUnauthorized: true });
export const register = (body) => api('/auth/register', { method: 'POST', body, ignoreUnauthorized: true });
export const logout = () => api('/auth/logout', { method: 'POST', ignoreUnauthorized: true });
export const updateMe = (body) => api('/auth/me', { method: 'PATCH', body });
// A wrong password here must show an inline error, not sign the user out.
export const deleteMe = (password) => api('/auth/me', { method: 'DELETE', body: { password }, ignoreUnauthorized: true });
