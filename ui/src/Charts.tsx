import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const AXIS_STYLE = {
  stroke: "rgba(255, 255, 255, 0.12)",
  fontSize: 11,
  fontFamily: "Plus Jakarta Sans, sans-serif",
  tick: { fill: "#94a3b8" },
};

const TOOLTIP_STYLE = {
  contentStyle: {
    background: "#0e1320",
    border: "1px solid rgba(255, 255, 255, 0.12)",
    borderRadius: 10,
    color: "#f8fafc",
    fontSize: 12,
    fontFamily: "Plus Jakarta Sans, sans-serif",
    boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.7)",
  },
  itemStyle: { color: "#cbd5e1" },
};

/** Belief Trajectory over progressive GSQL query steps */
export function Trajectory({ steps }: { steps: any[] }) {
  const data = (steps || []).map((s, i) => ({
    i,
    step: s.step,
    p: s.p,
    band: [s.ci[0], s.ci[1]],
    added: (s.added || []).join(", "),
  }));

  return (
    <ResponsiveContainer width="100%" height={210}>
      <ComposedChart data={data} margin={{ top: 10, right: 16, bottom: 25, left: -10 }}>
        <CartesianGrid stroke="rgba(255, 255, 255, 0.05)" vertical={false} />
        <XAxis dataKey="step" {...AXIS_STYLE} interval={0} angle={-20} textAnchor="end" height={35} />
        <YAxis domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} {...AXIS_STYLE} />
        <ReferenceLine y={0.5} stroke="rgba(255, 255, 255, 0.2)" strokeDasharray="3 3" />
        <Area dataKey="band" stroke="none" fill="#06b6d4" fillOpacity={0.16} isAnimationActive={false} />
        <Line
          dataKey="p"
          stroke="#06b6d4"
          strokeWidth={2.5}
          dot={{ r: 4, fill: "#06b6d4", stroke: "#090c14", strokeWidth: 2 }}
          isAnimationActive
        />
        <Tooltip
          {...TOOLTIP_STYLE}
          formatter={(v: any, n: any) =>
            n === "p"
              ? [`${(v * 100).toFixed(1)}%`, "Posterior P(fraud)"]
              : [`${(v[0] * 100).toFixed(0)}% – ${(v[1] * 100).toFixed(0)}%`, "80% Credible Interval"]
          }
          labelFormatter={(l: any, p: any) => `${l}${p?.[0]?.payload?.added ? " (+" + p[0].payload.added + ")" : ""}`}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/** Diverging Waterfall: Log-odds contribution per ledger row */
export function Ledger({ rows }: { rows: any[] }) {
  const data = [...(rows || [])]
    .filter((r) => r.kind !== "prior" || r.key === "risk_score")
    .sort((a, b) => b.contribution - a.contribution)
    .map((r) => ({
      name: r.key,
      v: +r.contribution.toFixed(2),
      label: r.label,
      src: r.source,
    }));

  return (
    <ResponsiveContainer width="100%" height={Math.max(140, data.length * 26 + 35)}>
      <BarChart data={data} layout="vertical" margin={{ top: 6, right: 20, bottom: 6, left: 10 }}>
        <CartesianGrid stroke="rgba(255, 255, 255, 0.05)" horizontal={false} />
        <XAxis type="number" {...AXIS_STYLE} />
        <YAxis type="category" dataKey="name" width={180} {...AXIS_STYLE} tick={{ fill: "#cbd5e1", fontSize: 11 }} />
        <ReferenceLine x={0} stroke="rgba(255, 255, 255, 0.3)" />
        <Tooltip
          {...TOOLTIP_STYLE}
          cursor={{ fill: "rgba(255, 255, 255, 0.03)" }}
          formatter={(v: any, _n: any, p: any) => [
            `${v > 0 ? "+" : ""}${v} log-odds (${p.payload.src})`,
            p.payload.label,
          ]}
          labelFormatter={() => ""}
        />
        <Bar dataKey="v" radius={4} barSize={14}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.v >= 0 ? "#f43f5e" : "#06b6d4"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Pattern Probability Distribution Bar Chart */
export function PatternBars({ patterns }: { patterns: any[] }) {
  const data = (patterns || []).slice(0, 6).map((p) => ({
    name: p.pattern,
    v: +(p.prob * 100).toFixed(1),
  }));

  return (
    <ResponsiveContainer width="100%" height={Math.max(90, data.length * 26 + 25)}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 10 }}>
        <XAxis type="number" domain={[0, 100]} hide />
        <YAxis type="category" dataKey="name" width={180} {...AXIS_STYLE} tick={{ fill: "#cbd5e1", fontSize: 11 }} />
        <Tooltip {...TOOLTIP_STYLE} cursor={{ fill: "rgba(255, 255, 255, 0.03)" }} formatter={(v: any) => [`${v}%`, "Likelihood"]} />
        <Bar
          dataKey="v"
          fill="#8b5cf6"
          radius={4}
          barSize={12}
          label={{ position: "right", fill: "#94a3b8", fontSize: 11, formatter: (v: any) => `${v}%` }}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Reliability Calibration Diagram: predicted vs observed */
export function Reliability({ bins }: { bins: any[] }) {
  const data = (bins || []).map((b) => ({ x: b.predicted, y: b.observed, n: b.n, bin: b.bin }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <ComposedChart data={data} margin={{ top: 10, right: 16, bottom: 20, left: -10 }}>
        <CartesianGrid stroke="rgba(255, 255, 255, 0.05)" />
        <XAxis
          type="number"
          dataKey="x"
          domain={[0, 1]}
          {...AXIS_STYLE}
          label={{ value: "Predicted Probability", position: "insideBottom", offset: -10, fill: "#64748b", fontSize: 11 }}
        />
        <YAxis type="number" domain={[0, 1]} {...AXIS_STYLE} />
        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="rgba(255, 255, 255, 0.25)" strokeDasharray="4 4" />
        <Line
          dataKey="y"
          stroke="#10b981"
          strokeWidth={2.5}
          dot={{ r: 5, fill: "#10b981", stroke: "#090c14", strokeWidth: 2 }}
          isAnimationActive={false}
        />
        <Tooltip
          {...TOOLTIP_STYLE}
          formatter={(v: any, _n: any, p: any) => [`${(v * 100).toFixed(0)}% Observed (n=${p.payload.n})`, p.payload.bin]}
          labelFormatter={() => ""}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/** Learned feature weights */
export function Weights({ weights }: { weights: any[] }) {
  const data = [...(weights || [])].sort((a, b) => b.weight - a.weight);
  const max = Math.max(...data.map((d) => Math.abs(d.weight)), 0.01);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 380, overflowY: "auto", paddingRight: 6 }}>
      {data.map((w: any) => {
        const isPos = w.weight >= 0;
        const widthPct = Math.min(100, Math.round((Math.abs(w.weight) / max) * 100));
        return (
          <div key={w.signal} style={{ display: "grid", gridTemplateColumns: "180px 1fr 60px", alignItems: "center", gap: 10, fontSize: 11.5 }}>
            <span style={{ color: "#cbd5e1", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={w.label}>
              {w.signal}
            </span>
            <div style={{ position: "relative", height: 8, background: "rgba(255, 255, 255, 0.05)", borderRadius: 999, overflow: "hidden" }}>
              <div
                style={{
                  position: "absolute",
                  left: isPos ? "50%" : `calc(50% - ${widthPct / 2}%)`,
                  width: `${widthPct / 2}%`,
                  height: "100%",
                  background: isPos ? "#f43f5e" : "#06b6d4",
                  borderRadius: 999,
                }}
              />
            </div>
            <span style={{ fontFamily: "JetBrains Mono, monospace", color: isPos ? "#f43f5e" : "#06b6d4", textAlign: "right" }}>
              {isPos ? "+" : ""}{w.weight.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
