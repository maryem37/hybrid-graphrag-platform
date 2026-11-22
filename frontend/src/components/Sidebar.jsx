export default function Sidebar({ health, stats, status, mode, setMode, hops, setHops, onUpload, onIngest }) {
  const running = status?.state === 'running';
  const pct = status?.total ? Math.round((status.done / status.total) * 100) : 0;
  return (
    <aside className="side">
      <header>
        <h1>NexaGraph</h1>
        <p>Questions answered from a knowledge graph and the source passages.</p>
        <span className={`dot ${health?.neo4j ? 'ok' : 'bad'}`}>{health?.neo4j ? 'Neo4j connected' : 'Neo4j unreachable'}</span>
      </header>

      <section>
        <h3>Documents</h3>
        <ul className="files">
          {(stats?.pdfs_in_data_dir || []).map((f) => <li key={f}>{f}</li>)}
          {stats && stats.pdfs_in_data_dir.length === 0 && <li className="muted">No PDF yet</li>}
        </ul>
        <label className="btn secondary">
          Upload PDFs
          <input type="file" accept="application/pdf" multiple hidden onChange={(e) => e.target.files.length && onUpload(e.target.files)} />
        </label>
        <button className="btn" disabled={running} onClick={() => onIngest(false)}>Build knowledge graph</button>
        <button className="btn ghost" disabled={running} onClick={() => onIngest(true)}>Rebuild from scratch</button>
        {status && status.state !== 'idle' && (
          <div className={`status ${status.state}`}>
            <p>{status.message}</p>
            {running && status.total > 0 && <progress value={status.done} max={status.total} aria-label={`${pct}%`} />}
            {status.errors > 0 && <p className="muted">{status.errors} chunks skipped after errors</p>}
          </div>
        )}
      </section>

      <section>
        <h3>Graph contents</h3>
        <dl className="counts">
          <div><dt>Entities</dt><dd>{stats?.entities ?? '–'}</dd></div>
          <div><dt>Relations</dt><dd>{stats?.relationships ?? '–'}</dd></div>
          <div><dt>Passages</dt><dd>{stats?.chunks ?? '–'}</dd></div>
          <div><dt>Files</dt><dd>{stats?.documents ?? '–'}</dd></div>
        </dl>
      </section>

      <section>
        <h3>Retrieval</h3>
        <div className="seg" role="radiogroup" aria-label="Retrieval mode">
          {[['vector', 'Vector'], ['graph', 'Graph'], ['hybrid', 'Hybrid']].map(([v, l]) => (
            <button key={v} role="radio" aria-checked={mode === v} className={mode === v ? 'on' : ''} onClick={() => setMode(v)}>{l}</button>
          ))}
        </div>
        <label className="hops">Graph hops: <b>{hops}</b>
          <input type="range" min="1" max="3" value={hops} onChange={(e) => setHops(+e.target.value)} />
        </label>
        <p className="muted small">Compare Vector (classic RAG) with Hybrid on the same question to see what the graph adds.</p>
      </section>
    </aside>
  );
}
