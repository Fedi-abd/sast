/**
 * API client for the SAST Platform SPA.
 *
 * Wraps fetch with the two Django-specific concerns the views
 * shouldn't repeat:
 *
 *   1. Session cookie: Django auth lives in the `sessionid` cookie,
 *      so every call sends `credentials: 'same-origin'`. In dev the
 *      Vite proxy forwards /api to Django on :8000, so same-origin
 *      holds; in prod they share an origin too.
 *   2. CSRF: Django requires `X-CSRFToken` on POST/PATCH/DELETE,
 *      matching the `csrftoken` cookie. We read the cookie and attach
 *      the header automatically on writes.
 *
 * Endpoint functions below mirror the shapes in `docs/api-contract.md`
 * one-for-one.
 */

export class UnauthorizedError extends Error {
  constructor(message = 'Not authenticated') {
    super(message);
    this.name = 'UnauthorizedError';
  }
}

export class ApiError extends Error {
  constructor(status, body, message) {
    super(message || `Request failed (${status})`);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

function readCookie(name) {
  for (const raw of document.cookie.split(';')) {
    const [key, value] = raw.trim().split('=');
    if (key === name) return decodeURIComponent(value ?? '');
  }
  return null;
}

async function request(path, { method = 'GET', body, headers } = {}) {
  const finalHeaders = { Accept: 'application/json', ...(headers || {}) };

  if (method !== 'GET') {
    const csrf = readCookie('csrftoken');
    if (csrf) finalHeaders['X-CSRFToken'] = csrf;
    if (body !== undefined && !(body instanceof FormData)) {
      finalHeaders['Content-Type'] = 'application/json';
    }
  }

  const init = { method, headers: finalHeaders, credentials: 'same-origin' };
  if (body !== undefined) {
    init.body = body instanceof FormData ? body : JSON.stringify(body);
  }

  const response = await fetch(path, init);

  if (response.status === 401 || response.status === 403) {
    throw new UnauthorizedError();
  }
  if (!response.ok) {
    let parsed = null;
    try {
      parsed = await response.json();
    } catch {
      // non-JSON error body (404 HTML, gateway error); leave null
    }
    throw new ApiError(response.status, parsed, `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined;
  return response.json();
}

const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  del: (path) => request(path, { method: 'DELETE' }),
};

/* ---- endpoint functions (mirror docs/api-contract.md) ---- */

export const fetchMe = () => api.get('/api/me/');
export const fetchDashboard = () => api.get('/api/dashboard/');

export const fetchProjects = () => api.get('/api/projects/');
export const fetchProject = (id) => api.get(`/api/projects/${id}/`);
export const createProject = (data) => api.post('/api/projects/', data);
export const updateProject = (id, data) => api.patch(`/api/projects/${id}/`, data);
export const deleteProject = (id) => api.del(`/api/projects/${id}/`);

export const fetchScans = () => api.get('/api/scans/');
export const fetchScan = (id) => api.get(`/api/scans/${id}/`);

/**
 * Without params: the full findings list (legacy array shape, what
 * the JSON export wants). With limit/offset/severity/owasp: paginated
 * envelope {results, total, severity_counts, owasp_counts}.
 */
export function fetchScanFindings(id, { severity, owasp, type, limit, offset } = {}) {
  const params = new URLSearchParams();
  if (severity) params.set('severity', Array.isArray(severity) ? severity.join(',') : severity);
  if (owasp) params.set('owasp', Array.isArray(owasp) ? owasp.join(',') : owasp);
  if (type) params.set('type', Array.isArray(type) ? type.join(',') : type);
  if (limit != null) params.set('limit', limit);
  if (offset != null) params.set('offset', offset);
  const qs = params.toString();
  return api.get(`/api/scans/${id}/findings/` + (qs ? `?${qs}` : ''));
}

// Toggle a finding's solved flag. Solved findings drop out of the live
// list but stay counted (the "solved N/M" progress counter).
export const solveFinding = (id, solved = true) =>
  api.post(`/api/findings/${id}/solve/`, { solved });

// The report endpoint returns a PDF, not JSON. Fetch it as a blob so
// the caller can show a generating state and trigger a clean download.
// `severities` (e.g. ['HIGH']) scopes the report; null means all.
export async function fetchScanReportBlob(id, severities = null) {
  const qs = severities && severities.length ? `?severity=${severities.join(',')}` : '';
  const res = await fetch(`/api/scans/${id}/report.pdf${qs}`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/pdf' },
  });
  if (res.status === 401 || res.status === 403) throw new UnauthorizedError();
  if (!res.ok) throw new ApiError(res.status, null, `Report failed (${res.status})`);
  return res.blob();
}

export const fetchHealth = (fresh = false) =>
  api.get('/api/health/' + (fresh ? '?fresh=1' : ''));

export const triggerScan = (projectId, tool) =>
  api.post('/api/scans/trigger/', { project_id: projectId, tool });

/**
 * Cross-project findings. With limit/offset the response is the
 * paginated envelope (see fetchScanFindings); otherwise a plain array.
 */
export function fetchFindings({ severity, owasp, projectId, ordering, limit, offset } = {}) {
  const params = new URLSearchParams();
  if (severity) params.set('severity', Array.isArray(severity) ? severity.join(',') : severity);
  if (owasp) params.set('owasp', Array.isArray(owasp) ? owasp.join(',') : owasp);
  if (projectId) params.set('project_id', projectId);
  if (ordering) params.set('ordering', ordering);
  if (limit != null) params.set('limit', limit);
  if (offset != null) params.set('offset', offset);
  const qs = params.toString();
  return api.get('/api/findings/' + (qs ? `?${qs}` : ''));
}

/* ---- deployment config (any authenticated user) ---- */

export const fetchConfig = () => api.get('/api/config/');

/* ---- staff-only admin console endpoints ---- */

export const fetchAdminSonarConfig = () => api.get('/api/admin/sonarqube/');
export const updateAdminSonarConfig = (data) => api.put('/api/admin/sonarqube/', data);
export const testAdminSonarConnection = (body = {}) =>
  api.post('/api/admin/sonarqube/test/', body);

export const fetchAdminLimits = () => api.get('/api/admin/limits/');
export const updateAdminLimits = (users) => api.patch('/api/admin/limits/', { users });

export const fetchAdminUsage = (limit) =>
  api.get('/api/admin/usage/' + (limit ? `?limit=${limit}` : ''));

export const fetchAdminUsers = () => api.get('/api/admin/users/');
export const setUserActive = (id, isActive) =>
  api.patch(`/api/admin/users/${id}/`, { is_active: isActive });
export const resetUserPassword = (id) =>
  api.post(`/api/admin/users/${id}/reset-password/`, {});

export const fetchAdminSettings = () => api.get('/api/admin/settings/');
export const updateAdminSettings = (data) => api.patch('/api/admin/settings/', data);

export const fetchResetRequests = () => api.get('/api/admin/reset-requests/');
export const resolveResetRequest = (id) =>
  api.patch(`/api/admin/reset-requests/${id}/`, { handled: true });

/* ---- auth helpers ---- */

/**
 * Full-page navigation to Django's templated login. The SPA router
 * doesn't own /accounts/*; `?next=` makes Django bounce back here
 * after a successful login.
 *
 * `reason` defaults to 'session' because nearly every call site is a
 * mid-session 401/403 (expired or deactivated); the login page shows
 * a "you were signed out" notice for it. The router guard passes null
 * (a fresh, never-logged-in visit isn't a sign-out).
 */
export function redirectToLogin(next = window.location.pathname + window.location.hash, reason = 'session') {
  const url = new URL('/accounts/login/', window.location.origin);
  url.searchParams.set('next', next);
  if (reason) url.searchParams.set('reason', reason);
  if (reason === 'session') {
    // Mid-session cutoff (expired session, deactivated account): let
    // App.vue explain in a modal before the bounce. Router-guard
    // bounces pass reason=null and go straight through; those are
    // fresh visits, not interruptions.
    window.dispatchEvent(
      new CustomEvent('sast:session-ended', { detail: { url: url.toString() } }),
    );
    return;
  }
  window.location.assign(url.toString());
}

/**
 * Log out via Django. LogoutView requires POST, and we want the browser
 * to follow the 302 back to the login page, so submit a real form
 * rather than fetch (which wouldn't navigate the page). The CSRF token
 * rides along in the hidden field Django expects.
 */
export function logout() {
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = '/accounts/logout/';
  const csrf = readCookie('csrftoken');
  if (csrf) {
    const field = document.createElement('input');
    field.type = 'hidden';
    field.name = 'csrfmiddlewaretoken';
    field.value = csrf;
    form.appendChild(field);
  }
  document.body.appendChild(form);
  form.submit();
}

/* ---- client-side selectors ----
 * These take the fetched arrays as arguments rather than closing over
 * a module-global, since there's no static SCANS/FINDINGS anymore. */

export function latestScanFor(scans, projectId) {
  return (scans || [])
    .filter((s) => s.project_id === projectId)
    .sort((a, b) => new Date(b.started_at) - new Date(a.started_at))[0] || null;
}

export function severityTally(findings) {
  const arr = findings || [];
  return {
    HIGH: arr.filter((f) => f.severity === 'HIGH').length,
    MEDIUM: arr.filter((f) => f.severity === 'MEDIUM').length,
    LOW: arr.filter((f) => f.severity === 'LOW').length,
  };
}
