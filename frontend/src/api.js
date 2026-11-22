const json = async (res) => {
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch { /* keep status text */ }
    throw new Error(msg);
  }
  return res.json();
};
const post = (url, body) =>
  fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(json);

export const api = {
  health: () => fetch('/api/health').then(json),
  stats: () => fetch('/api/stats').then(json),
  graph: (limit = 120) => fetch(`/api/graph?limit=${limit}`).then(json),
  ask: (question, mode, hops) => post('/api/ask', { question, mode, hops }),
  ingest: (reset) => post('/api/ingest', { reset }),
  ingestStatus: () => fetch('/api/ingest/status').then(json),
  upload: (files) => {
    const fd = new FormData();
    [...files].forEach((f) => fd.append('files', f));
    return fetch('/api/upload', { method: 'POST', body: fd }).then(json);
  },
};
