import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import Sidebar from './components/Sidebar.jsx';
import Chat from './components/Chat.jsx';
import GraphView from './components/GraphView.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';

export default function App() {
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [status, setStatus] = useState(null);
  const [overview, setOverview] = useState(null);
  const [focus, setFocus] = useState(null); // reasoning graph of an answer
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState('hybrid');
  const [hops, setHops] = useState(2);

  const refresh = useCallback(async () => {
    try {
      setHealth(await api.health());
      setStats(await api.stats());
      setOverview(await api.graph(120));
    } catch { /* backend not ready yet */ }
  }, []);

  useEffect(() => { refresh(); api.ingestStatus().then(setStatus).catch(() => {}); }, [refresh]);

  useEffect(() => {
    if (status?.state !== 'running') return undefined;
    const id = setInterval(async () => {
      const s = await api.ingestStatus();
      setStatus(s);
      if (s.state !== 'running') refresh();
    }, 2000);
    return () => clearInterval(id);
  }, [status?.state, refresh]);

  const ask = async (question) => {
    setMessages((m) => [...m, { role: 'user', text: question }]);
    setBusy(true);
    try {
      const res = await api.ask(question, mode, hops);
      setMessages((m) => [...m, { role: 'bot', text: res.answer, meta: res }]);
      setFocus(res.graph);
    } catch (e) {
      setMessages((m) => [...m, { role: 'bot', error: true, text: `Could not answer: ${e.message}` }]);
    } finally {
      setBusy(false);
    }
  };

  const upload = async (files) => { await api.upload(files); refresh(); };
  const ingest = async (reset) => {
    try { setStatus(await api.ingest(reset)); } catch (e) { setStatus({ state: 'error', message: e.message }); }
  };

  const shown = focus || overview;
  return (
    <div className="app">
      <Sidebar {...{ health, stats, status, mode, setMode, hops, setHops }} onUpload={upload} onIngest={ingest} />
      <Chat messages={messages} busy={busy} onAsk={ask} onSelectGraph={setFocus} ready={(stats?.entities || 0) > 0} />
      <section className="panel" aria-label="Knowledge graph">
        <div className="panel-head">
          <h2>{focus ? 'Reasoning graph for the last answer' : 'Most connected entities'}</h2>
          {focus && <button className="link" onClick={() => setFocus(null)}>Show overview</button>}
        </div>
        <ErrorBoundary>
          <GraphView data={shown} emptyText="The graph appears here once the documents are processed." />
        </ErrorBoundary>
      </section>
    </div>
  );
}
