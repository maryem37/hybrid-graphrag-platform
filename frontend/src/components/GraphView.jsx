import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const PALETTE = {
  Person: '#3b6fd8', Project: '#d98a00', Client: '#1f9d6b', Organization: '#7b4fc9', Department: '#c93d7a',
  Technology: '#0f9fb5', Product: '#e0662a', Location: '#7aa51f', Role: '#8a7bd1', Certification: '#b89a00',
  Industry: '#5b7083', Policy: '#8c6d4f', Concept: '#7d8a96',
};
const colorOf = (t) => PALETTE[t] || '#7d8a96';

export default function GraphView({ data, emptyText }) {
  const wrap = useRef(null);
  const [size, setSize] = useState({ w: 400, h: 400 });

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
    // Deep-clone all node/link data so d3-force never mutates the original objects.
    // Without this, after the first render d3 replaces source/target strings with
    // object references in-place; re-rendering with the same data then causes
    // "r is not a function" because d3's internal accessor receives an object instead
    // of the expected primitive id string.
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

  return (
    <div className="graph" ref={wrap}>
      {size.w > 0 && size.h > 0 && (
        <ForceGraph2D
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
