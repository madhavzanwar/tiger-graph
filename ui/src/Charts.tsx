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
  stroke: "#E2DDD5",
  fontSize: 11,
  fontFamily: "Inter, sans-serif",
  tick: { fill: "#717780" },
};

const TOOLTIP_STYLE = {
  contentStyle: {
    background: "#FFFFFF",
    border: "1px solid #E2DDD5",
    borderRadius: 8,
    color: "#191C20",
    fontSize: 12,
    fontFamily: "Inter, sans-serif",
    boxShadow: "0 8px 20px -3px rgba(25, 28, 32, 0.08)",
  },
  itemStyle: { color: "#484E56" },
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
        <CartesianGrid stroke="#EAE5DB" vertical={false} />
        <XAxis dataKey="step" {...AXIS_STYLE} interval={0} angle={-15} textAnchor="end" height={35} />
        <YAxis domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} {...AXIS_STYLE} />
        <ReferenceLine y={0.5} stroke="#CBD5E1" strokeDasharray="3 3" />
        <Area dataKey="band" stroke="none" fill="#182230" fillOpacity={0.08} isAnimationActive={false} />
        <Line
          dataKey="p"
          stroke="#182230"
          strokeWidth={2.2}
          dot={{ r: 3.5, fill: "#182230", stroke: "#FFFFFF", strokeWidth: 1.5 }}
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
        <CartesianGrid stroke="#EAE5DB" horizontal={false} />
        <XAxis type="number" {...AXIS_STYLE} />
        <YAxis type="category" dataKey="name" width={180} {...AXIS_STYLE} tick={{ fill: "#484E56", fontSize: 11 }} />
        <ReferenceLine x={0} stroke="#94A3B8" />
        <Tooltip
          {...TOOLTIP_STYLE}
          cursor={{ fill: "rgba(25, 28, 32, 0.03)" }}
          formatter={(v: any, _n: any, p: any) => [
            `${v > 0 ? "+" : ""}${v} log-odds (${p.payload.src})`,
            p.payload.label,
          ]}
        />
        <Bar dataKey="v" radius={[3, 3, 3, 3]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.v >= 0 ? "#DC2626" : "#16A34A"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Reliability curve: predicted probability vs observed fraud rate */
export function Reliability({ bins }: { bins: any[] }) {
  const data = (bins || []).map((b: any) => ({
    pred: +((b.pred ?? b.predicted ?? 0)).toFixed(2),
    obs: +((b.obs ?? b.observed ?? 0)).toFixed(2),
    count: b.count ?? b.n ?? 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={data} margin={{ top: 10, right: 16, bottom: 10, left: -10 }}>
        <CartesianGrid stroke="#EAE5DB" />
        <XAxis dataKey="pred" domain={[0, 1]} type="number" {...AXIS_STYLE} tickFormatter={(v) => `${v}`} />
        <YAxis domain={[0, 1]} {...AXIS_STYLE} tickFormatter={(v) => `${v}`} />
        <Line dataKey="pred" stroke="#94A3B8" strokeDasharray="3 3" dot={false} isAnimationActive={false} />
        <Line dataKey="obs" stroke="#182230" strokeWidth={2.2} dot={{ r: 4, fill: "#182230", stroke: "#FFFFFF", strokeWidth: 1.5 }} />
        <Tooltip
          {...TOOLTIP_STYLE}
          formatter={(v: any, n: any, p: any) => [
            `${v}`,
            n === "obs" ? `Observed rate (${p.payload.count} cases)` : "Predicted midpoint",
          ]}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/** Feature weights bar chart */
export function Weights({ weights }: { weights: Array<{ signal: string; weight: number; label: string }> }) {
  const data = (weights || [])
    .filter((w) => w.weight !== 0)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 12);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7, padding: "4px 0" }}>
      {data.map((w) => {
        const max = 3.5;
        const widthPct = Math.min(100, Math.max(8, (Math.abs(w.weight) / max) * 100));
        return (
          <div key={w.signal} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 11.5 }}>
            <span style={{ width: 140, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={w.label}>
              {w.signal}
            </span>
            <div style={{ flex: 1, height: 7, background: "var(--bg-inset)", borderRadius: 3, overflow: "hidden" }}>
              <div
                style={{
                  width: `${widthPct}%`,
                  height: "100%",
                  background: w.weight >= 0 ? "#DC2626" : "#16A34A",
                  borderRadius: 3,
                }}
              />
            </div>
            <span className="mono" style={{ width: 45, textAlign: "right", fontWeight: 600, color: "var(--text-primary)" }}>
              {w.weight >= 0 ? `+${w.weight.toFixed(2)}` : w.weight.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Pattern distribution bar chart */
export function PatternBars({ patterns }: { patterns: Record<string, number> }) {
  const data = Object.entries(patterns || {}).map(([k, v]) => ({ name: k, count: v }));

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 10 }}>
        <CartesianGrid stroke="#EAE5DB" horizontal={false} />
        <XAxis type="number" {...AXIS_STYLE} />
        <YAxis type="category" dataKey="name" width={140} {...AXIS_STYLE} tick={{ fill: "#484E56", fontSize: 11 }} />
        <Tooltip {...TOOLTIP_STYLE} />
        <Bar dataKey="count" fill="#182230" radius={[3, 3, 3, 3]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
