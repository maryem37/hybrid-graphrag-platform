import { useEffect, useMemo, useRef, useState } from 'react';

// react-force-graph-2d and its d3 dependencies are CommonJS modules.
// Vite's Rollup production bundler mangles the CJS/ESM interop and turns
// the d3-force link `id` accessor into undefined (minified as `r`), which
// throws "r is not a function" on the very first render.
// Using a dynamic import AFTER mount bypasses the static-analysis bundling
// path and forces correct CJS evaluation at runtime.

const PALETTE = {
  Person: '#3b6fd8', Project: '#d98a00', Client: '#1f9d6b', Organization: '#7b4fc9', Department: '#c93d7a',
  Technology: '#0f9fb5', Product: '#e0662a', Location: '#7aa51f', Role: '#8a7bd1', Certification: '#b89a00',
  Industry: '#5b7083', Policy: '#8c6d4f', Concept: '#7d8a96',
};
const colorOf = (t) => PALETTE[t] || '#7d8a96';

export default function GraphView({ data, emptyText }) {
  const wrap = useRef(null);
  const [size, setSize] = useState({ w: 400, h: 400 });
  const [ForceGraph2D, setForceGraph2D] = useState(null);

  // Load the library dynamically on the client, after mount.
  useEffect(() => {
    import('react-force-graph-2d').then((mod) => {
      setForceGraph2D(() => mod.default);
    });
  }, []);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setSize({ w: Math.round(width), h: Math.round(height) });
        }
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const graphData = useMemo(() => {
    // Deep-clone all node/link data so d3-force never mutates the original
    // API response objects in React state across re-renders.
    const rawNodes = data?.nodes ? JSON.parse(JSON.stringify(data.nodes)) : [];
    const rawLinks = data?.links ? JSON.parse(JSON.stringify(data.links)) : [];
    const nodeMap = new Map();
    rawNodes.forEach((n) => {
      if (n && n.id) {
        nodeMap.set(String(n.id), { ...n, id: String(n.id) });
      }
    });
    const validLinks = [];
    rawLinks.forEach((l) => {
      const srcId = typeof l.source === 'object' ? l.source?.id : l.source;
      const tgtId = typeof l.target === 'object' ? l.target?.id : l.target;
      if (srcId && tgtId && nodeMap.has(String(srcId)) && nodeMap.has(String(tgtId))) {
        validLinks.push({ ...l, source: String(srcId), target: String(tgtId) });
      }
    });
    return { nodes: Array.from(nodeMap.values()), links: validLinks };
  }, [data]);

  const types = useMemo(() => [...new Set(graphData.nodes.map((n) => n.type))].filter(Boolean), [graphData]);
  const fg = typeof window !== 'undefined' ? (getComputedStyle(document.documentElement).getPropertyValue('--ink').trim() || '#14262b') : '#14262b';

  // A stable key derived from the node IDs. When the graph dataset changes
  // (e.g. switching between overview and reasoning graph), changing the key
  // forces a full unmount + remount of ForceGraph2D, giving d3-force a clean
  // internal state instead of trying to reconcile stale simulation data.
  const graphKey = graphData.nodes.map((n) => n.id).sort().join('|') || 'empty';

  return (
    <div className="graph" ref={wrap}>
      {ForceGraph2D && size.w > 0 && size.h > 0 && (
        <ForceGraph2D
          key={graphKey}
          width={size.w}
          height={size.h}
          graphData={graphData}
          backgroundColor="rgba(0,0,0,0)"
          cooldownTicks={120}
          linkColor={() => 'rgba(120,135,150,0.45)'}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          linkLabel={(l) => l.label || ''}
          nodeLabel={(n) => `${n.name || n.id} (${n.type || 'Entity'})`}
          nodeCanvasObject={(node, ctx, scale) => {
            if (!node || typeof node.x !== 'number' || typeof node.y !== 'number' || !isFinite(node.x) || !isFinite(node.y)) return;
            const s = Math.max(0.1, scale || 1);
            const r = node.seed ? 7 : 4.5;
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
            ctx.fillStyle = colorOf(node.type);
            ctx.fill();
            if (node.seed) {
              ctx.lineWidth = Math.max(0.5, 2 / s);
              ctx.strokeStyle = fg;
              ctx.stroke();
            }
            if ((node.seed || s > 1.6) && node.name) {
              ctx.font = `${Math.max(6, (node.seed ? 12 : 10) / s)}px system-ui, sans-serif`;
              ctx.fillStyle = fg;
              ctx.textAlign = 'center';
              ctx.fillText(String(node.name), node.x, node.y + r + 9 / s);
            }
          }}
        />
      )}
      {graphData.nodes.length === 0 && (
        <p className="graph-empty">{emptyText}</p>
      )}
      {types.length > 0 && (
        <ul className="legend">
          {types.map((t) => (
            <li key={t}><span style={{ background: colorOf(t) }} />{t}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
