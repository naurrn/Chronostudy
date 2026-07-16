const BASE = "";
function getToken() { return localStorage.getItem("cs_token"); }
function setToken(t) { localStorage.setItem("cs_token", t); }
function removeToken() { localStorage.removeItem("cs_token"); }
function getUser() { return JSON.parse(localStorage.getItem("cs_user") || "null"); }
function setUser(u) { localStorage.setItem("cs_user", JSON.stringify(u)); }
function removeUser() { localStorage.removeItem("cs_user"); }

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(BASE + path, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Terjadi kesalahan." }));
    throw new Error(err.detail || "Terjadi kesalahan.");
  }
  return res;
}

async function apiJSON(path, options = {}) {
  const res = await apiFetch(path, options);
  return res.json();
}

async function register(nama, email, password) {
  return apiJSON("/api/auth/register", {
    method: "POST", body: JSON.stringify({ nama, email, password })
  });
}

async function login(email, password) {
  const data = await apiJSON("/api/auth/login", {
    method: "POST", body: JSON.stringify({ email, password })
  });
  setToken(data.token);
  setUser(data.user);
  return data.user;
}

async function getMe() {
  return apiJSON("/api/auth/me");
}

async function submitMEQ(jawaban) {
  return apiJSON("/api/meq/submit", {
    method: "POST", body: JSON.stringify({ jawaban })
  });
}

async function getMEQQuestions() {
  return apiJSON("/api/meq/questions");
}

async function getJadwalOptions() {
  return apiJSON("/api/jadwal/options");
}

async function generateJadwal(payload) {
  return apiJSON("/api/jadwal/generate", {
    method: "POST", body: JSON.stringify(payload)
  });
}

async function getJadwalTerakhir() {
  return apiJSON("/api/jadwal/terakhir");
}

async function getRiwayat() {
  return apiJSON("/api/jadwal/riwayat");
}

async function getJadwalById(id) {
  return apiJSON(`/api/jadwal/riwayat/${encodeURIComponent(id)}`);
}

async function getJadwalHarian(hari) {
  return apiJSON(`/api/jadwal/harian/${encodeURIComponent(hari)}`);
}

async function downloadPDF() {
  const res = await apiFetch("/api/jadwal/pdf");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "jadwal_chronostudy.pdf";
  a.click(); URL.revokeObjectURL(url);
}

async function sendChat(message) {
  return apiJSON("/api/chat", {
    method: "POST", body: JSON.stringify({ message })
  });
}

function logout() {
  removeToken(); removeUser();
  window.location.href = "index.html";
}

function requireAuth(redirectIfMEQDone = false) {
  const token = getToken();
  const user = getUser();
  if (!token || !user) { window.location.href = "auth.html"; return null; }
  if (redirectIfMEQDone && user.skor_meq) {
    window.location.href = "input.html"; return null;
  }
  return user;
}