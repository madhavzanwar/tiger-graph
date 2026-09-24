import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";

const TYPE_COLORS: Record<string, string> = {
  Transaction: "#06b6d4",
  Card: "#f59e0b",
  Customer: "#10b981",
  Device: "#8b5cf6",
  EmailDomain: "#ec4899",
  Region: "#3b82f6",
  FraudCase: "#f43f5e",
};

export default function GraphView({ graph }: { graph: any }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    if (!containerRef.current || !graph) return;
    const elements: any[] = [];

    for (const n of graph.nodes || []) {
      const isTrigger = Boolean(n.trigger);
      const isConfirmedFraud = n.fraud || n.outcome === "CONFIRMED_FRAUD";
      const isCleared = n.outcome === "CLEARED";

      elements.push({
        data: {
          id: String(n.id),
          label: n.label || n.id,
          type: n.type,
          color: TYPE_COLORS[n.type] || "#94a3b8",
          size: isTrigger ? 52 : n.type === "Transaction" ? 24 : 32,
          borderColor: isTrigger ? "#38bdf8" : isConfirmedFraud ? "#f43f5e" : isCleared ? "#10b981" : "rgba(255,255,255,0.15)",
          borderWidth: isTrigger ? 4 : isConfirmedFraud || isCleared ? 3 : 1.5,
        },
      });
    }

    for (const e of graph.edges || []) {
      elements.push({
        data: {
          id: `${e.source}->${e.target}-${e.type}`,
          source: String(e.source),
          target: String(e.target),
          label: e.type,
        },
      });
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            width: "data(size)",
            height: "data(size)",
            label: "data(label)",
            color: "#e2e8f0",
            "font-size": 10,
            "font-family": "Plus Jakarta Sans, sans-serif",
            "font-weight": 600,
            "text-valign": "bottom",
            "text-margin-y": 5,
            "border-width": "data(borderWidth)",
            "border-color": "data(borderColor)",
            "text-background-opacity": 0.7,
            "text-background-color": "#090c14",
            "text-background-padding": 3,
            "text-background-shape": "roundrectangle",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "rgba(255, 255, 255, 0.15)",
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "rgba(255, 255, 255, 0.25)",
            "arrow-scale": 0.8,
            "font-size": 8,
            color: "#64748b",
          },
        },
        {
          selector: "edge[label = 'SHARES_ENTITY']",
          style: {
            "line-color": "#f43f5e",
            "target-arrow-color": "#f43f5e",
            "line-style": "dashed",
            width: 2,
          },
        },
        {
          selector: "edge[label = 'SIMILAR']",
          style: {
            "line-color": "#8b5cf6",
            "line-style": "dotted",
            "target-arrow-shape": "none",
            width: 1.5,
          },
        },
      ],
      layout: {
        name: "cose",
        animate: true,
        animationDuration: 500,
        nodeRepulsion: () => 12000,
        idealEdgeLength: () => 80,
        padding: 30,
      } as any,
      wheelSensitivity: 0.25,
    });

    cyRef.current = cy;
    return () => cy.destroy();
  }, [graph]);

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => cyRef.current?.fit(undefined, 30);
  const handleResetLayout = () => {
    cyRef.current?.layout({
      name: "cose",
      animate: true,
      animationDuration: 500,
      nodeRepulsion: () => 12000,
      idealEdgeLength: () => 80,
    } as any).run();
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="graph-canvas-wrap">
        <div className="graph-controls">
          <button className="graph-btn" onClick={handleZoomIn} title="Zoom in">+</button>
          <button className="graph-btn" onClick={handleZoomOut} title="Zoom out">−</button>
          <button className="graph-btn" onClick={handleFit} title="Fit viewport">⛶</button>
          <button className="graph-btn" onClick={handleResetLayout} title="Rearrange topology">⟳</button>
        </div>
        <div ref={containerRef} className="graph-canvas" role="img" aria-label="Investigation subgraph topology" />
      </div>

      <div className="graph-legend-pills">
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <span key={type} className="legend-pill">
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />
            {type}
          </span>
        ))}
        <span className="legend-pill">
          <span style={{ width: 8, height: 8, borderRadius: "50%", border: "2px solid #f43f5e" }} />
          Confirmed Fraud
        </span>
        <span className="legend-pill">
          <span style={{ width: 8, height: 8, borderRadius: "50%", border: "2px solid #10b981" }} />
          Cleared
        </span>
      </div>
    </div>
  );
}
