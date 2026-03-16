const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

async function request(path, options = {}, token = null) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  officerLogin: (email, password) =>
    request('/auth/officer/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  getComplaints: (token, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/complaints${query ? '?' + query : ''}`, {}, token);
  },

  getComplaint: (token, id) =>
    request(`/complaints/${id}`, {}, token),

  updateStatus: (token, id, status, notes) =>
    request(`/complaints/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, officer_notes: notes }),
    }, token),
};
