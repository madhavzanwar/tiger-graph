import { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";

const TYPE_COLORS: Record<string, string> = {
  Transaction: "#151E28",   // Oxford Navy / Charcoal
  Card: "#D97706",          // Warm Amber
  Customer: "#059669",      // Dignified Emerald
  Device: "#4F46E5",        // Deep Indigo
  EmailDomain: "#DB2777",   // Muted Magenta
  Region: "#2563EB",        // Royal Blue
  FraudCase: "#DC2626",     // Refined Crimson
};

interface GraphViewProps {
  graph: any;
  onSelectNode?: (nodeData: any) => void;
}

export default function GraphView({ graph, onSelectNode }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [activeLayout, setActiveLayout] = useState<string>("cose");

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
          size: isTrigger ? 46 : n.type === "Transaction" ? 22 : 30,
          borderColor: isTrigger ? "#0284C7" : isConfirmedFraud ? "#DC2626" : isCleared ? "#16A34A" : "#FFFFFF",
          borderWidth: isTrigger ? 3 : isConfirmedFraud || isCleared ? 3 : 2,
          raw: n,
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
            color: "#151E28",
            "font-size": 10.5,
            "font-family": "Inter, sans-serif",
            "font-weight": 600,
            "text-valign": "bottom",
            "text-margin-y": 5,
            "border-width": "data(borderWidth)",
            "border-color": "data(borderColor)",
            "text-background-opacity": 0.88,
            "text-background-color": "#FFFFFF",
            "text-background-padding": 3,
            "text-background-shape": "roundrectangle",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 4,
            "border-color": "#151E28",
            "border-opacity": 1,
            "shadow-blur": 12,
            "shadow-color": "rgba(21, 30, 40, 0.25)",
            "shadow-opacity": 1,
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
            "arrow-scale": 0.75,
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
            width: 2.2,
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
        name: activeLayout,
        animate: true,
        animationDuration: 400,
        nodeRepulsion: () => 14000,
        idealEdgeLength: () => 85,
        padding: 35,
      } as any,
      wheelSensitivity: 0.25,
    });

    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      const data = node.data();
      const degree = node.degree();
      const nodeInfo = { ...data, degree };
      setSelectedNode(nodeInfo);
      if (onSelectNode) onSelectNode(nodeInfo);
    });

    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null);
      }
    });

    cyRef.current = cy;
    return () => cy.destroy();
  }, [graph, activeLayout, onSelectNode]);

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => cyRef.current?.fit(undefined, 35);
  const applyLayout = (name: string) => {
    setActiveLayout(name);
    cyRef.current?.layout({
      name,
      animate: true,
      animationDuration: 400,
      nodeRepulsion: () => 14000,
      idealEdgeLength: () => 85,
    } as any).run();
  };

  const nodeCount = graph?.nodes?.length || 0;
  const edgeCount = graph?.edges?.length || 0;

  return (
    <div className="graph-workbench">
      <div className="graph-canvas-wrap">
        {/* Floating Top Controls Toolbar */}
        <div className="graph-controls-bar">
          <div className="graph-tools-left">
            <span className="graph-telemetry-badge">
              <b>{nodeCount}</b> Vertices · <b>{edgeCount}</b> Edges
            </span>
            <div className="layout-switcher">
              <span className="layout-label">Layout:</span>
              <button
                className={`layout-btn ${activeLayout === "cose" ? "active" : ""}`}
                onClick={() => applyLayout("cose")}
                title="Force-Directed CoSE Physics"
              >
                Force
              </button>
              <button
                className={`layout-btn ${activeLayout === "concentric" ? "active" : ""}`}
                onClick={() => applyLayout("concentric")}
                title="Concentric Radial Circles"
              >
                Concentric
              </button>
              <button
                className={`layout-btn ${activeLayout === "breadthfirst" ? "active" : ""}`}
                onClick={() => applyLayout("breadthfirst")}
                title="Hierarchical Tree"
              >
                Tree
              </button>
              <button
                className={`layout-btn ${activeLayout === "circle" ? "active" : ""}`}
                onClick={() => applyLayout("circle")}
                title="Circular Ring"
              >
                Circle
              </button>
            </div>
          </div>

          <div className="graph-tools-right">
            <button className="graph-btn" onClick={handleZoomIn} title="Zoom in">+</button>
            <button className="graph-btn" onClick={handleZoomOut} title="Zoom out">−</button>
            <button className="graph-btn" onClick={handleFit} title="Fit entire topology to viewport">⛶ Fit</button>
            <button className="graph-btn" onClick={() => applyLayout(activeLayout)} title="Recompute layout">↻ Redraw</button>
          </div>
        </div>

        {/* Cytoscape Canvas Container */}
        <div ref={containerRef} className="cytoscape-canvas" />

        {/* Selected Node Inspector Flyout */}
        {selectedNode && (
          <div className="node-inspector-flyout">
            <div className="node-inspector-header">
              <div className="row" style={{ gap: 6 }}>
                <span
                  style={{
                    width: 9,
                    height: 9,
                    borderRadius: "50%",
                    background: selectedNode.color,
                  }}
                />
                <span className="node-inspector-type">{selectedNode.type}</span>
              </div>
              <button className="close-btn" onClick={() => setSelectedNode(null)}>✕</button>
            </div>
            <div className="node-inspector-id mono">{selectedNode.id}</div>
            <div className="node-inspector-details">
              <div>Connected Degree: <b>{selectedNode.degree} edges</b></div>
              {selectedNode.raw?.fraud && (
                <div style={{ color: "var(--status-danger-text)", fontWeight: 600 }}>
                  Flagged Fraudulent Vertex
                </div>
              )}
              {selectedNode.raw?.trigger && (
                <div style={{ color: "var(--status-info-text)", fontWeight: 600 }}>
                  Primary Trigger Vertex
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Structured Category Legend Bar */}
      <div className="graph-legend-strip">
        <span className="legend-title">Entity Types:</span>
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <div key={type} className="legend-chip">
            <span className="legend-dot" style={{ background: color }} />
            <span>{type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
