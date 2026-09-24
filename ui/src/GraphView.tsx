import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";

const TYPE_COLORS: Record<string, string> = {
  Transaction: "#182230",   // Deep Oxford Navy
  Card: "#D97706",          // Warm Amber
  Customer: "#059669",      // Dignified Emerald
  Device: "#4F46E5",        // Deep Indigo
  EmailDomain: "#DB2777",   // Muted Magenta
  Region: "#2563EB",        // Royal Blue
  FraudCase: "#DC2626",     // Refined Crimson
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
          color: TYPE_COLORS[n.type] || "#64748B",
          size: isTrigger ? 48 : n.type === "Transaction" ? 24 : 32,
          borderColor: isTrigger ? "#0284C7" : isConfirmedFraud ? "#DC2626" : isCleared ? "#16A34A" : "#FFFFFF",
          borderWidth: isTrigger ? 3 : isConfirmedFraud || isCleared ? 3 : 2,
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
            color: "#1E293B",
            "font-size": 10.5,
            "font-family": "Inter, sans-serif",
            "font-weight": 600,
            "text-valign": "bottom",
            "text-margin-y": 4,
            "border-width": "data(borderWidth)",
            "border-color": "data(borderColor)",
            "text-background-opacity": 0.85,
            "text-background-color": "#FFFFFF",
            "text-background-padding": 3,
            "text-background-shape": "roundrectangle",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#CBD5E1",
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#94A3B8",
            "arrow-scale": 0.7,
            "font-size": 8,
            color: "#64748B",
          },
        },
        {
          selector: "edge[label = 'SHARES_ENTITY']",
          style: {
            "line-color": "#EF4444",
            "target-arrow-color": "#EF4444",
            "line-style": "dashed",
            width: 2,
          },
        },
        {
          selector: "edge[label = 'SIMILAR']",
          style: {
            "line-color": "#6366F1",
            "line-style": "dotted",
            "target-arrow-shape": "none",
            width: 1.5,
          },
        },
      ],
      layout: {
        name: "cose",
        animate: true,
        animationDuration: 400,
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
      animationDuration: 400,
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
          <button className="graph-btn" onClick={handleFit} title="Fit to view">⛶</button>
          <button className="graph-btn" onClick={handleResetLayout} title="Rearrange layout">↻</button>
        </div>
        <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
      </div>

      {/* Refined clean legend */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, fontSize: 11.5, color: "var(--text-secondary)", padding: "0 2px" }}>
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <div key={type} style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />
            <span>{type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
