import { useEffect, useRef, useState } from 'react';

const SAMPLES = [
  'Which Vice President does Maya Patel ultimately report to?',
  'Who is the account manager of the client of Project Titan, and which office are they in?',
  'Which projects use Neo4j and which clients are they for?',
  'Which employees hold the Neo4j Certified Professional certification?',
];

function Answer({ text = '', onCite }) {
  const str = typeof text === 'string' ? text : String(text || '');
  const parts = str.split(/(\[S\d+\])/g);
  return (
    <p className="answer">
      {parts.map((p, i) => {
        const m = p.match(/^\[(S\d+)\]$/);
        return m ? (
          <button key={i} className="cite" onClick={() => onCite && onCite(m[1])}>{m[1]}</button>
        ) : (
          <span key={i}>{p}</span>
        );
      })}
    </p>
  );
}

export default function Chat({ messages, busy, onAsk, onSelectGraph, ready }) {
  const [text, setText] = useState('');
  const [openSource, setOpenSource] = useState(null);
  const end = useRef(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: 'smooth' }), [messages, busy]);

  const submit = (e) => {
    e.preventDefault();
    if (text.trim() && !busy) { onAsk(text.trim()); setText(''); }
  };

  return (
    <section className="chat" aria-label="Conversation">
      <div className="thread">
        {messages.length === 0 && (
          <div className="empty">
            <h2>Ask a question that spans several documents</h2>
            <p>{ready ? 'Try one of these:' : 'Upload your PDFs and build the knowledge graph first, then ask:'}</p>
            <div className="samples">
              {SAMPLES.map((s) => (
                <button key={s} disabled={busy} onClick={() => onAsk(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="msg user">{m.text}</div>
          ) : (
            <div key={i} className={`msg bot ${m.error ? 'error' : ''}`}>
              {m.error ? <p className="answer">{m.text}</p> : <Answer text={m.text} onCite={(s) => setOpenSource({ i, s })} />}
              {m.meta && (
                <div className="meta">
                  <span>{m.meta.mode || 'hybrid'}</span>
                  <span>{m.meta.facts ?? 0} graph facts</span>
                  <span>{((m.meta.latency_ms || 0) / 1000).toFixed(1)} s</span>
                  {Array.isArray(m.meta.linked) && m.meta.linked.length > 0 && <span>linked: {m.meta.linked.slice(0, 4).join(', ')}</span>}
                  {m.meta.graph && <button className="link" onClick={() => onSelectGraph(m.meta.graph)}>Show reasoning graph</button>}
                </div>
              )}
              {m.meta && Array.isArray(m.meta.sources) && m.meta.sources.length > 0 && (
                <ul className="sources">
                  {m.meta.sources.map((s, sIdx) => (
                    <li key={s.label || sIdx} className={openSource && openSource.i === i && openSource.s === s.label ? 'open' : ''}>
                      <button onClick={() => setOpenSource(openSource?.i === i && openSource?.s === s.label ? null : { i, s: s.label })}>
                        <b>{s.label}</b> {s.source} · p.{s.page}
                      </button>
                      {openSource && openSource.i === i && openSource.s === s.label && <blockquote>{s.snippet}…</blockquote>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ),
        )}
        {busy && <div className="msg bot pending">Searching the graph and the passages…</div>}
        <div ref={end} />
      </div>
      <form onSubmit={submit} className="composer">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about people, projects, clients…" aria-label="Question" />
        <button type="submit" disabled={busy || !text.trim()}>Ask</button>
      </form>
    </section>
  );
}
