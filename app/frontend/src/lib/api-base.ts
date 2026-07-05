// Resolves the backend API base URL.
//
// Locally this defaults to the dev backend. In production the URL is injected at
// build time via VITE_API_URL. Render's Blueprint wires this from the backend
// service's `host` property, which has no scheme, so we prepend https:// when one
// is missing. Any trailing slash is trimmed so callers can safely append paths.
const raw = (import.meta.env.VITE_API_URL || 'http://localhost:8000').trim().replace(/\/+$/, '');

export const API_BASE_URL = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
