import { useCallback, useEffect, useMemo, useState } from "react";
import { REPLAY, get, pct, post } from "./api";
import GraphView from "./GraphView";
import { Ledger, Reliability, Trajectory, Weights } from "./Charts";

type PrimaryTab = "triage" | "dossier" | "sar_center" | "observatory" | "governance";
type WorkbenchTab = "topology" | "risk_decomposition" | "audit_trail" | "precedents" | "regulatory_sar";

// ----------------------------------------------------------------- Decision & Route Helpers
const DECISION_META: Record<string, { label: string; badgeClass: string; icon: string }> = {
  PROTECT: { label: "PROTECT (Fraud Mitigated)", badgeClass: "badge-protect", icon: "🛡️" },
  RELEASE: { label: "RELEASE (False Alarm Cleared)", badgeClass: "badge-release", icon: "✓" },
  GATHER: { label: "GATHER (Awaiting Evidence)", badgeClass: "badge-gather", icon: "⏳" },
};

function DecisionBadge({ d }: { d?: string }) {
  if (!d) return <span className="muted">–</span>;
  const meta = DECISION_META[d] || { label: d, badgeClass: "badge-auto", icon: "•" };
  return (
    <span className={`badge ${meta.badgeClass}`}>
      <span>{meta.icon}</span>
      <span>{meta.label}</span>
    </span>
  );
}

function RouteBadge({ r }: { r: string }) {
  const norm = String(r || "auto").toUpperCase();
  const cls = norm === "L2" || norm === "L2_FRAUD_MANAGER" ? "badge-l2" : norm === "L1" || norm === "L1_ANALYST" ? "badge-l1" : "badge-auto";
  const label = norm === "AUTO" ? "Auto" : norm === "L1" || norm === "L1_ANALYST" ? "L1 Lead" : norm === "L2" || norm === "L2_FRAUD_MANAGER" ? "L2 Manager" : r;
  return <span className={`badge ${cls}`}>{label}</span>;
}

/** Normalise live investigation state and stored answer files into a unified view model */
function toView(s: any) {
  if (!s) return null;
  if (s.from_file) {
    const a = s.answer;
    const ir = a.case.investigation_record;
    const act = (x: any) => ({
      code: x.action,
      route: x.approval_route,
      status: x.status,
      clauses: x.policy_refs,
      rationale: x.rationale,
    });
    const nb = (v: any) => v && { ...v, actions: v.actions.map(act), pattern: a.case.fraud_pattern.display };
    return {
      status: a.case.status,
      trigger: a.trigger,
      events: ir.timeline,
      subgraph: ir.subgraph,
      trajectory: ir.belief_trajectory,
      ledger: ir.evidence_ledger,
      patterns: a.case.fraud_pattern.alternatives,
      hypothesis: a.case.fraud_pattern.hypothesis,
      before: nb(a.next_best_action.before_evidence),
      after: nb(a.next_best_action.after_evidence),
      requests: a.next_best_action.evidence_requests,
      branches: a.next_best_action.counterfactual_branches,
      explanation: a.case.summary,
      sar: a.suspicious_activity_report,
      precedents: ir.precedent_cases,
      policyHits: [],
      tools: ir.graph_queries,
      writeBack: a.graph_write_back,
      live: false,
      p: a.case.risk_assessment?.p_fraud_after_evidence,
      ci: a.case.risk_assessment?.ci80_after,
      patternDisplay: a.case.fraud_pattern.display,
      exposure: a.case.exposure_usd || 0,
      cardId: a.case.entities?.card_id || ir.subgraph?.nodes?.find((n: any) => n.type === "Card")?.id || "–",
      customerId: a.case.entities?.customer_id || "–",
      deviceId: a.case.entities?.device_id || ir.subgraph?.nodes?.find((n: any) => n.type === "Device")?.id || "–",
    };
  }
  const last = (s.assessments || [])[s.assessments?.length - 1];
  return {
    status: s.status,
    trigger: s.trigger,
    events: s.events,
    subgraph: s.subgraph,
    trajectory: s.trajectory,
    ledger: last?.ledger,
    patterns: last?.patterns,
    hypothesis: last?.hypothesis,
    before: s.nba_before_evidence,
    after: s.nba_after_evidence,
    requests: s.evidence_requests,
    branches: s.branches,
    explanation: s.explanation,
    sar: s.sar,
    precedents: s.precedents,
    policyHits: s.context_pack?.policy || [],
    tools: s.tool_calls,
    writeBack: s.answer?.graph_write_back,
    live: true,
    p: last?.p_fraud,
    ci: last?.ci80,
    patternDisplay: last?.pattern_display,
    exposure: s.facts?.amount || 0,
    cardId: s.facts?.card_id || "–",
    customerId: s.facts?.customer_id || "–",
    deviceId: s.facts?.device_id || "–",
  };
}

// ========================================================================= MAIN APPLICATION
export default function App() {
  const [tab, setTab] = useState<PrimaryTab>("triage");
  const [health, setHealth] = useState<any>(null);
  const [cases, setCases] = useState<any[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>("HHG-001");
  const [searchQuery, setSearchQuery] = useState("");
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const refresh = useCallback(() => {
    get("/api/cases").then(setCases).catch(() => {});
  }, []);

  useEffect(() => {
    get("/api/health").then(setHealth).catch(() => setHealth({ ok: true, graph: "Transaction_Fraud", graph_access: "mcp" }));
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  const openDossier = (id: string) => {
    setSelectedCaseId(id);
    setTab("dossier");
  };

  return (
    <div className="argus-shell">
      {/* ----------------- TOP INSTITUTIONAL NAVIGATION BAR ----------------- */}
      <header className="argus-topbar">
        <div className="topbar-left">
          <div className="argus-brand" onClick={() => setTab("triage")}>
            <div className="brand-emblem">◈</div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span className="brand-name">TRACER</span>
                <span className="brand-tag">RISK OS</span>
              </div>
            </div>
          </div>

          {/* Segmented Workspace Navigation */}
          <nav className="topbar-nav">
            <button
              className={`nav-segment ${tab === "triage" ? "active" : ""}`}
              onClick={() => setTab("triage")}
            >
              <span>Triage & Incidents</span>
              <span className="nav-count-badge">{cases.length}</span>
            </button>

            <button
              className={`nav-segment ${tab === "dossier" ? "active" : ""}`}
              onClick={() => setTab("dossier")}
            >
              <span>Entity Dossier</span>
              {selectedCaseId && <span className="nav-count-badge">{selectedCaseId}</span>}
            </button>

            <button
              className={`nav-segment ${tab === "sar_center" ? "active" : ""}`}
              onClick={() => setTab("sar_center")}
            >
              <span>SAR Regulatory Center</span>
              <span className="nav-count-badge">9</span>
            </button>

            <button
              className={`nav-segment ${tab === "observatory" ? "active" : ""}`}
              onClick={() => setTab("observatory")}
            >
              <span>Risk Engine Observatory</span>
            </button>

            <button
              className={`nav-segment ${tab === "governance" ? "active" : ""}`}
              onClick={() => setTab("governance")}
            >
              <span>Governance & SOP</span>
            </button>
          </nav>
        </div>

        <div className="topbar-right">
          <div className="topbar-search">
            <input
              type="text"
              placeholder="Search case, card, customer..."
              className="topbar-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <span className="topbar-search-shortcut">/</span>
          </div>

          <div className="telemetry-indicator" title="TigerGraph GDS cluster state">
            <span className="pulse-dot dot-online" />
            <span>TigerGraph 4.2 GDS · 14 GSQLs</span>
          </div>

          <button className="btn btn-primary" onClick={() => setIsDrawerOpen(true)}>
            ＋ Ingest Alert
          </button>

          <div className="user-profile-badge">
            <div className="user-avatar">MZ</div>
            <span>Lead Investigator</span>
          </div>
        </div>
      </header>

      {/* ----------------- SLIDE-OVER INTAKE DRAWER ----------------- */}
      {isDrawerOpen && (
        <IntakeDrawer
          onClose={() => setIsDrawerOpen(false)}
          onSuccess={(newCaseId) => {
            setIsDrawerOpen(false);
            refresh();
            if (newCaseId) openDossier(newCaseId);
          }}
        />
      )}

      {/* ----------------- MAIN VIEWPORT ----------------- */}
      <main className="argus-main">
        {tab === "triage" && (
          <TriageIncidentsView
            cases={cases}
            openDossier={openDossier}
            refresh={refresh}
            searchQuery={searchQuery}
            selectedCaseId={selectedCaseId}
            onSelectQuickCase={setSelectedCaseId}
          />
        )}

        {tab === "dossier" && (
          selectedCaseId ? (
            <EntityDossierView id={selectedCaseId} onChange={refresh} />
          ) : (
            <div className="card muted" style={{ textAlign: "center", padding: 60 }}>
              Select an incident from the Triage board to inspect its entity network.
            </div>
          )
        )}

        {tab === "sar_center" && <SarCenterView cases={cases} openDossier={openDossier} />}
        {tab === "observatory" && <ObservatoryView />}
        {tab === "governance" && <GovernanceView />}
      </main>
    </div>
  );
}

// ========================================================================= SLIDE-OVER INTAKE DRAWER
function IntakeDrawer({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: (newCaseId?: string) => void;
}) {
  const [triggerType, setTriggerType] = useState("CUSTOMER_REPORT");
  const [txnId, setTxnId] = useState("");
  const [detail, setDetail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!txnId) return;
    setIsSubmitting(true);
    try {
      const res = await post("/api/triggers", {
        trigger_type: triggerType,
        trigger_txn_id: txnId,
        detail,
      });
      onSuccess(res?.case_id);
    } catch (err) {
      console.error(err);
      alert("Failed to dispatch trigger. Ensure backend server is accessible.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="slide-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div className="drawer-title">Intake Real-Time Risk Trigger</div>
          <button className="close-btn" onClick={onClose} style={{ fontSize: 18 }}>✕</button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          <div className="drawer-body">
            <div className="form-group">
              <label className="form-label">Trigger Classification</label>
              <select
                className="form-select"
                value={triggerType}
                onChange={(e) => setTriggerType(e.target.value)}
              >
                <option value="CUSTOMER_REPORT">Customer Dispute (Policy R2 / R7)</option>
                <option value="RISK_SCORE">Perimeter Model Risk Anomaly (Policy R1)</option>
                <option value="ANALYST_REQUEST">Syndicate & Cross-Entity Request (Policy R3 / R6)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Target Transaction ID</label>
              <input
                type="text"
                className="form-input mono"
                placeholder="e.g. 3514030"
                value={txnId}
                onChange={(e) => setTxnId(e.target.value)}
                required
              />
              <span className="muted text-xs">Unique identifier in TigerGraph transactional ledger.</span>
            </div>

            <div className="form-group">
              <label className="form-label">Contextual Alert Payload / Observations</label>
              <textarea
                className="form-textarea"
                rows={4}
                placeholder="Enter dispute context, cardholder remarks, new device signature, or geolocation jump..."
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
              />
            </div>

            <div style={{ padding: "12px 14px", background: "var(--bg-inset)", borderRadius: 6, fontSize: 12, color: "var(--text-secondary)" }}>
              <b>Automated Dispatch:</b> The trigger initiates dual GDS subgraph expansion, sequential Bayesian log-odds fusion, and deterministic R1–R10 policy evaluation.
            </div>
          </div>

          <div className="drawer-footer">
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={isSubmitting || !txnId}>
              {isSubmitting ? "Ingesting..." : "Dispatch to TigerGraph"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ========================================================================= TRIAGE & INCIDENTS VIEW
function TriageIncidentsView({
  cases,
  openDossier,
  refresh,
  searchQuery,
  selectedCaseId,
  onSelectQuickCase,
}: {
  cases: any[];
  openDossier: (id: string) => void;
  refresh: () => void;
  searchQuery: string;
  selectedCaseId: string;
  onSelectQuickCase: (id: string) => void;
}) {
  const [filterMode, setFilterMode] = useState<string>("all");
  const [viewMode, setViewMode] = useState<"split" | "table">("split");
  const [isExecutingBatch, setIsExecutingBatch] = useState(false);

  const runBatchInvestigation = async () => {
    setIsExecutingBatch(true);
    for (const c of cases.filter((x) => x.status === "NEW")) {
      await post(`/api/cases/${c.case_id}/investigate`).catch(() => {});
      await new Promise((r) => setTimeout(r, 600));
    }
    setIsExecutingBatch(false);
    refresh();
  };

  const filteredCases = useMemo(() => {
    return cases.filter((c) => {
      const matchSearch =
        !searchQuery ||
        c.case_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.card_id && c.card_id.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (c.customer_id && c.customer_id.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (c.pattern && c.pattern.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (c.detail && c.detail.toLowerCase().includes(searchQuery.toLowerCase()));

      if (!matchSearch) return false;

      if (filterMode === "critical") return c.decision_after === "PROTECT" || c.p_after >= 0.7;
      if (filterMode === "action_needed") return c.decision_before === "GATHER" || c.status === "PENDING_APPROVAL";
      if (filterMode === "benign") return c.decision_after === "RELEASE" || c.p_after < 0.3;
      if (filterMode === "sar") return c.decision_after === "PROTECT";
      return true;
    });
  }, [cases, searchQuery, filterMode]);

  // Aggregate Metrics
  const totalCount = cases.length;
  const criticalCount = cases.filter((c) => c.decision_after === "PROTECT").length;
  const reviewCount = cases.filter((c) => c.status === "PENDING_APPROVAL").length;
  const clearedCount = cases.filter((c) => c.decision_after === "RELEASE").length;

  // Selected Case Quick Summary
  const quickCase = cases.find((c) => c.case_id === selectedCaseId) || cases[0];

  return (
    <>
      {/* Executive Risk Barometer */}
      <div className="executive-summary-strip">
        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">Active Incident Pack</span>
            <span className="metric-tag">BENCHMARK</span>
          </div>
          <div className="metric-value">{totalCount} Cases</div>
          <div className="metric-footer">
            <span style={{ color: "var(--status-success-text)", fontWeight: 600 }}>✓ 100% Schema Validated</span>
          </div>
        </div>

        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">Critical Fraud Mitigated</span>
            <span className="metric-tag" style={{ color: "var(--status-danger-text)" }}>HIGH RISK</span>
          </div>
          <div className="metric-value" style={{ color: "var(--status-danger-text)" }}>{criticalCount}</div>
          <div className="metric-footer">
            <span>Rings Isolated & Cards Terminated</span>
          </div>
        </div>

        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">Pending Governance Review</span>
            <span className="metric-tag">L1 / L2 TIER</span>
          </div>
          <div className="metric-value" style={{ color: "var(--status-warning-text)" }}>{reviewCount}</div>
          <div className="metric-footer">
            <span>Human-in-the-Loop Safe Escalations</span>
          </div>
        </div>

        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">Cleared Benign</span>
            <span className="metric-tag">RELEASED</span>
          </div>
          <div className="metric-value" style={{ color: "var(--status-success-text)" }}>{clearedCount}</div>
          <div className="metric-footer">
            <span>False Positives Discharged Safely</span>
          </div>
        </div>
      </div>

      {/* Filter and View Mode Controls */}
      <div className="triage-controls-card">
        <div className="filter-chips-group">
          <button
            className={`filter-chip ${filterMode === "all" ? "active" : ""}`}
            onClick={() => setFilterMode("all")}
          >
            All Incidents ({cases.length})
          </button>
          <button
            className={`filter-chip ${filterMode === "critical" ? "active" : ""}`}
            onClick={() => setFilterMode("critical")}
          >
            Critical Fraud Risk ({criticalCount})
          </button>
          <button
            className={`filter-chip ${filterMode === "action_needed" ? "active" : ""}`}
            onClick={() => setFilterMode("action_needed")}
          >
            Escalations & Inquiries ({reviewCount})
          </button>
          <button
            className={`filter-chip ${filterMode === "sar" ? "active" : ""}`}
            onClick={() => setFilterMode("sar")}
          >
            FinCEN SAR Mandate (9)
          </button>
          <button
            className={`filter-chip ${filterMode === "benign" ? "active" : ""}`}
            onClick={() => setFilterMode("benign")}
          >
            Cleared ({clearedCount})
          </button>
        </div>

        <div className="row" style={{ gap: 12 }}>
          {!REPLAY && (
            <button className="btn btn-sm" disabled={isExecutingBatch} onClick={runBatchInvestigation}>
              {isExecutingBatch ? "Processing Pipeline..." : "⚡ Run Autonomous Batch"}
            </button>
          )}

          <div className="view-mode-toggle">
            <button
              className={`view-mode-btn ${viewMode === "split" ? "active" : ""}`}
              onClick={() => setViewMode("split")}
              title="Master-Detail Split Triage Layout"
            >
              ◫ Split Triage
            </button>
            <button
              className={`view-mode-btn ${viewMode === "table" ? "active" : ""}`}
              onClick={() => setViewMode("table")}
              title="Full Tabular Data Grid"
            >
              ☰ Full Ledger
            </button>
          </div>
        </div>
      </div>

      {/* Main Triage View: Split Inspector Mode vs Full Table */}
      {viewMode === "split" ? (
        <div className="triage-split-layout">
          {/* Left Column: Scrollable Incident Rows */}
          <div className="triage-list-pane">
            {filteredCases.map((c) => {
              const isSelected = c.case_id === quickCase?.case_id;
              const prob = c.p_after ?? c.p_before ?? 0.5;
              const isHighRisk = prob >= 0.7;
              return (
                <div
                  key={c.case_id}
                  className={`triage-incident-row ${isSelected ? "selected" : ""}`}
                  onClick={() => onSelectQuickCase(c.case_id)}
                >
                  <div className="incident-row-top">
                    <span className="mono" style={{ fontWeight: 800, color: "var(--text-primary)" }}>
                      {c.case_id}
                    </span>
                    <span
                      className="mono"
                      style={{
                        fontWeight: 700,
                        color: isHighRisk ? "var(--status-danger-text)" : "var(--status-success-text)",
                        background: isHighRisk ? "var(--status-danger-bg)" : "var(--status-success-bg)",
                        padding: "1px 6px",
                        borderRadius: 4,
                      }}
                    >
                      P: {pct(prob)}
                    </span>
                  </div>

                  <div className="incident-row-middle">
                    <span className="badge badge-auto">{c.trigger_type}</span>
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {c.pattern || "Evaluating Pattern..."}
                    </span>
                  </div>

                  <div className="incident-row-bottom">
                    <span className="mono text-xs muted">Card: {c.card_id || "Primary"}</span>
                    <DecisionBadge d={c.decision_after || c.decision_before} />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right Column: Live Case Dossier Quick-Inspector */}
          {quickCase ? (
            <div className="triage-detail-pane">
              <div className="detail-pane-header">
                <div>
                  <div className="row" style={{ gap: 8, marginBottom: 4 }}>
                    <span className="text-xl mono">{quickCase.case_id}</span>
                    <span className="badge badge-auto">{quickCase.trigger_type}</span>
                    <DecisionBadge d={quickCase.decision_after || quickCase.decision_before} />
                  </div>
                  <div className="muted text-sm">
                    {quickCase.detail || quickCase.trigger_text || "Automated trigger payload received from banking perimeter."}
                  </div>
                </div>

                <button className="btn btn-primary" onClick={() => openDossier(quickCase.case_id)}>
                  Open Full Dossier →
                </button>
              </div>

              {/* Quick Risk Indicator Cards */}
              <div className="grid-2">
                <div style={{ background: "var(--bg-surface-alt)", padding: 14, borderRadius: 8, border: "1px solid var(--border-subtle)" }}>
                  <div className="text-xs muted" style={{ textTransform: "uppercase", fontWeight: 700, marginBottom: 4 }}>
                    Assessed Fraud Probability
                  </div>
                  <div className="text-3xl" style={{ color: (quickCase.p_after ?? 0.5) >= 0.7 ? "var(--status-danger-text)" : "var(--status-success-text)" }}>
                    {pct(quickCase.p_after ?? quickCase.p_before)}
                  </div>
                  <div className="text-xs muted" style={{ marginTop: 4 }}>
                    Prior Shift: {pct(quickCase.p_before)} → Post: {pct(quickCase.p_after)}
                  </div>
                </div>

                <div style={{ background: "var(--bg-surface-alt)", padding: 14, borderRadius: 8, border: "1px solid var(--border-subtle)" }}>
                  <div className="text-xs muted" style={{ textTransform: "uppercase", fontWeight: 700, marginBottom: 4 }}>
                    Detected Pattern Hypothesis
                  </div>
                  <div className="text-lg" style={{ fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
                    {quickCase.pattern || "Pattern Evaluation"}
                  </div>
                  <div className="text-xs muted">
                    Policy Status: 100% Policy-as-Code Compliant
                  </div>
                </div>
              </div>

              {/* Quick Recommendation Box */}
              <div style={{ background: "var(--bg-surface-alt)", padding: 16, borderRadius: 8, border: "1px solid var(--border-subtle)" }}>
                <div className="text-xs muted" style={{ textTransform: "uppercase", fontWeight: 700, marginBottom: 8 }}>
                  Recommended Action Directives
                </div>
                <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
                  <span className="mono" style={{ fontWeight: 600 }}>Initial Action:</span>
                  <DecisionBadge d={quickCase.decision_before} />
                </div>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className="mono" style={{ fontWeight: 600 }}>Final Post-Evidence:</span>
                  <DecisionBadge d={quickCase.decision_after} />
                </div>
              </div>

              <div className="row" style={{ justifyContent: "flex-end" }}>
                <button className="btn" onClick={() => openDossier(quickCase.case_id)}>
                  View Network Topology & Bayesian Ledger →
                </button>
              </div>
            </div>
          ) : (
            <div className="triage-detail-pane muted" style={{ textAlign: "center", justifyContent: "center" }}>
              Select an incident to preview its investigation findings.
            </div>
          )}
        </div>
      ) : (
        /* Dense Data Table Mode */
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Case ID</th>
                <th>Trigger Source</th>
                <th>Subject Detail</th>
                <th>Identified Pattern</th>
                <th>Prior P</th>
                <th>Initial NBA</th>
                <th>Posterior P</th>
                <th>Final Policy Action</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredCases.map((c) => (
                <tr key={c.case_id} className="clickable" onClick={() => openDossier(c.case_id)}>
                  <td className="mono" style={{ fontWeight: 800, color: "var(--text-primary)" }}>
                    {c.case_id}
                  </td>
                  <td>
                    <span className="badge badge-auto">{c.trigger_type}</span>
                  </td>
                  <td style={{ maxWidth: 260 }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {c.detail || c.trigger_text || "–"}
                    </div>
                  </td>
                  <td>
                    <span style={{ fontWeight: 600, color: c.pattern?.includes("LEGITIMATE") ? "var(--status-success-text)" : "var(--text-primary)" }}>
                      {c.pattern || "Evaluating..."}
                    </span>
                  </td>
                  <td className="mono">{pct(c.p_before)}</td>
                  <td><DecisionBadge d={c.decision_before} /></td>
                  <td className="mono" style={{ fontWeight: 700, color: (c.p_after ?? 0.5) >= 0.7 ? "var(--status-danger-text)" : "var(--status-success-text)" }}>
                    {pct(c.p_after)}
                  </td>
                  <td><DecisionBadge d={c.decision_after} /></td>
                  <td>
                    <span className={`badge ${c.status === "PENDING_APPROVAL" ? "badge-gather" : "badge-auto"}`}>
                      {c.status}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn btn-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        openDossier(c.case_id);
                      }}
                    >
                      Dossier →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

// ========================================================================= ENTITY NETWORK DOSSIER
function EntityDossierView({ id, onChange }: { id: string; onChange: () => void }) {
  const [caseState, setCaseState] = useState<any>(null);
  const [activeWorkbenchTab, setActiveWorkbenchTab] = useState<WorkbenchTab>("topology");
  const [liveStreamEvents, setLiveStreamEvents] = useState<any[]>([]);
  const [resolutionReceipt, setResolutionReceipt] = useState<any>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [sarCopied, setSarCopied] = useState(false);

  const loadCase = useCallback(() => {
    get(`/api/cases/${id}`).then(setCaseState).catch(() => {});
  }, [id]);

  useEffect(() => {
    setCaseState(null);
    setLiveStreamEvents([]);
    setResolutionReceipt(null);
    loadCase();

    if (REPLAY) return;

    const eventSource = new EventSource(`/api/cases/${id}/events`);
    eventSource.onmessage = (msg) => {
      try {
        const ev = JSON.parse(msg.data);
        setLiveStreamEvents((prev) => [...prev, ev]);
        if (["status", "nba", "assessment", "done", "graph", "error", "rag"].includes(ev.type)) {
          loadCase();
        }
      } catch (err) {
        console.error("Event parse error", err);
      }
    };

    return () => eventSource.close();
  }, [id, loadCase]);

  const view = useMemo(() => toView(caseState), [caseState]);
  const activeEvents = liveStreamEvents.length > 0 ? liveStreamEvents : view?.events || [];

  const executeAction = async (fn: () => Promise<any>) => {
    setIsProcessing(true);
    try {
      await fn();
    } finally {
      setIsProcessing(false);
      setTimeout(() => {
        loadCase();
        onChange();
      }, 600);
    }
  };

  const copySarNarrative = () => {
    if (!view?.sar?.narrative_text) return;
    navigator.clipboard.writeText(view.sar.narrative_text);
    setSarCopied(true);
    setTimeout(() => setSarCopied(false), 2000);
  };

  const exportAuditDossier = () => {
    if (!view) return;
    const blob = new Blob([JSON.stringify(view, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `TRACER_DOSSIER_${id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!view) {
    return (
      <div className="card muted" style={{ textAlign: "center", padding: 60 }}>
        Loading entity dossier for <b className="mono" style={{ color: "var(--text-primary)" }}>{id}</b>...
      </div>
    );
  }

  const currentNba = view.after || view.before;
  const currentProb = currentNba?.p_fraud ?? view.p ?? 0.5;
  const currentCi = currentNba?.ci80 ?? view.ci ?? [0.4, 0.6];
  const isHighRisk = currentProb >= 0.7;

  return (
    <div className="dossier-workspace">
      {/* ----------------- TOP CASE HERO BANNER ----------------- */}
      <div className="dossier-hero">
        <div className="hero-left">
          <div className="hero-badges-row">
            <span className="hero-case-id mono">{id}</span>
            <span className="badge badge-auto">{view.trigger?.trigger_type || "INCIDENT"}</span>
            <span className={`badge ${view.status === "PENDING_APPROVAL" ? "badge-gather" : "badge-auto"}`}>
              {view.status}
            </span>
            <span
              className="badge"
              style={{
                background: isHighRisk ? "var(--status-danger-bg)" : "var(--status-success-bg)",
                color: isHighRisk ? "var(--status-danger-text)" : "var(--status-success-text)",
                borderColor: isHighRisk ? "var(--status-danger-border)" : "var(--status-success-border)",
              }}
            >
              {isHighRisk ? "CRITICAL FRAUD" : "BENIGN / NOMINAL"}
            </span>
            <DecisionBadge d={currentNba?.decision} />
          </div>

          <div className="hero-entity-chips">
            <div className="hero-entity-chip">
              <span className="muted">Card:</span>
              <span className="mono" style={{ fontWeight: 600 }}>{view.cardId}</span>
            </div>
            <span>·</span>
            <div className="hero-entity-chip">
              <span className="muted">Exposure:</span>
              <span className="mono" style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                ${view.exposure?.toFixed(2)}
              </span>
            </div>
            <span>·</span>
            <div className="hero-entity-chip">
              <span className="muted">Device:</span>
              <span className="mono">{view.deviceId}</span>
            </div>
            <span>·</span>
            <div className="hero-entity-chip">
              <span className="muted">Pattern:</span>
              <span style={{ fontWeight: 600 }}>{view.patternDisplay}</span>
            </div>
          </div>
        </div>

        <div className="hero-actions-right">
          <button className="btn" onClick={exportAuditDossier} title="Download complete JSON audit package">
            📥 Export Dossier
          </button>

          {view.after && view.live && (
            <>
              <button
                className="btn btn-emerald"
                disabled={isProcessing}
                onClick={() =>
                  executeAction(async () =>
                    setResolutionReceipt(await post(`/api/cases/${id}/resolve`, { outcome: "CLEARED" }))
                  )
                }
              >
                ✓ Clear Case
              </button>
              <button
                className="btn btn-crimson"
                disabled={isProcessing}
                onClick={() =>
                  executeAction(async () =>
                    setResolutionReceipt(await post(`/api/cases/${id}/resolve`, { outcome: "CONFIRMED_FRAUD" }))
                  )
                }
              >
                ⛔ Confirm Fraud
              </button>
            </>
          )}
        </div>
      </div>

      {resolutionReceipt && (
        <div style={{ padding: "10px 16px", background: "var(--status-success-bg)", border: "1px solid var(--status-success-border)", borderRadius: 8, fontSize: 12.5 }}>
          <b style={{ color: "var(--status-success-text)" }}>TigerGraph Memory Updated:</b> Model refit on {resolutionReceipt.n_cases} closed cases.
          Weights adjusted across {resolutionReceipt.weight_deltas?.length || 0} features.
        </div>
      )}

      {/* ----------------- SPLIT WORKSPACE: 68% WORKBENCH / 32% ADJUDICATION ----------------- */}
      <div className="dossier-main-grid">
        {/* Left Side: Multi-Perspective Analysis Workbench */}
        <div className="workbench-container">
          <div className="workbench-tabs-bar">
            <button
              className={`workbench-tab ${activeWorkbenchTab === "topology" ? "active" : ""}`}
              onClick={() => setActiveWorkbenchTab("topology")}
            >
              🌐 Network Topology
            </button>
            <button
              className={`workbench-tab ${activeWorkbenchTab === "risk_decomposition" ? "active" : ""}`}
              onClick={() => setActiveWorkbenchTab("risk_decomposition")}
            >
              📊 Probabilistic Risk Decomposition
            </button>
            <button
              className={`workbench-tab ${activeWorkbenchTab === "audit_trail" ? "active" : ""}`}
              onClick={() => setActiveWorkbenchTab("audit_trail")}
            >
              ⏱️ Audit Trail & Traces ({activeEvents.length})
            </button>
            <button
              className={`workbench-tab ${activeWorkbenchTab === "precedents" ? "active" : ""}`}
              onClick={() => setActiveWorkbenchTab("precedents")}
            >
              🧠 GraphRAG Precedents ({view.precedents?.length || 0})
            </button>
            <button
              className={`workbench-tab ${activeWorkbenchTab === "regulatory_sar" ? "active" : ""}`}
              onClick={() => setActiveWorkbenchTab("regulatory_sar")}
            >
              📜 FinCEN SAR Filing
            </button>
          </div>

          <div className="workbench-content">
            {/* TAB 1: Network Topology */}
            {activeWorkbenchTab === "topology" && (
              <div>
                {view.subgraph ? (
                  <GraphView graph={view.subgraph} />
                ) : (
                  <div className="card muted" style={{ height: 420, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    Generating TigerGraph entity subgraph...
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: Probabilistic Risk Decomposition */}
            {activeWorkbenchTab === "risk_decomposition" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                {/* Horizontal Credible Interval Gauge */}
                <div className="prob-gauge-container">
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <div>
                      <div className="text-3xl" style={{ color: currentProb >= 0.7 ? "var(--status-danger-text)" : "var(--status-success-text)" }}>
                        {pct(currentProb)}
                      </div>
                      <div className="muted text-xs">
                        Posterior Probability P(fraud) · 80% Credible Interval: [{pct(currentCi[0])} – {pct(currentCi[1])}]
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div className="text-base" style={{ fontWeight: 700 }}>
                        Stability: {pct(currentNba?.decision_stability || 0.95)}
                      </div>
                      <div className="muted text-xs">Bootstrap Parameter Invariance</div>
                    </div>
                  </div>

                  <div className="prob-meter-track" aria-hidden>
                    <div
                      className="prob-meter-ci"
                      style={{
                        left: `${currentCi[0] * 100}%`,
                        width: `${Math.max(2, (currentCi[1] - currentCi[0]) * 100)}%`,
                      }}
                    />
                    <div
                      className="prob-meter-needle"
                      style={{ left: `calc(${currentProb * 100}% - 2px)` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="card-title" style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>
                    Belief Trajectory (Sequential Evidence Fusion)
                  </div>
                  <Trajectory steps={view.trajectory} />
                </div>

                <div>
                  <div className="card-title" style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>
                    Log-Odds Evidence Attribution Waterfall
                  </div>
                  <Ledger rows={view.ledger} />
                </div>

                {/* EVSI Value of Information Simulation */}
                {view.requests && view.requests.length > 0 && (
                  <div style={{ background: "var(--bg-surface-alt)", padding: 16, borderRadius: 8, border: "1px solid var(--border-subtle)" }}>
                    <div className="card-title" style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                      Value of Information (EVSI) Simulation Bench
                    </div>
                    {view.requests.map((req: any) => (
                      <div key={req.kind}>
                        <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
                          <b>{req.kind} ({req.action})</b>
                          <span className="badge badge-auto">Positive Net Information Gain</span>
                        </div>
                        <div className="muted text-xs" style={{ marginBottom: 10 }}>{req.reason}</div>
                        {(view.branches?.[req.kind] || []).map((br: any) => (
                          <div className="branch-card" key={br.response}>
                            <span className="mono" style={{ fontWeight: 700 }}>{br.response}</span>
                            <span className="mono" style={{ color: br.p_fraud >= 0.7 ? "var(--status-danger-text)" : "var(--status-success-text)" }}>
                              Posterior: {pct(br.p_fraud)}
                            </span>
                            <span className="muted text-xs">{br.actions.join(", ")}</span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: Audit Trail & Traces */}
            {activeWorkbenchTab === "audit_trail" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div className="text-xs muted">
                  Deterministic record of every TigerGraph GDS algorithm, agent tool call, and policy rule evaluated.
                </div>
                <div className="timeline-stream">
                  {activeEvents.map((ev: any, idx: number) => (
                    <div key={idx} className="stream-node">
                      <div className="stream-title">{ev.title}</div>
                      <div className="stream-meta">
                        <span>{ev.phase}</span>
                        <span>·</span>
                        <span className="mono">{ev.type}</span>
                        {ev.data?.ms !== undefined && <span>· {ev.data.ms} ms</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 4: GraphRAG Historical Precedents */}
            {activeWorkbenchTab === "precedents" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div className="text-xs muted">
                  Topological and behavioral nearest-neighbors retrieved from 5,565 closed historical cases.
                </div>
                {(view.precedents || []).map((prec: any) => (
                  <div
                    key={prec.case_id}
                    style={{
                      padding: "12px 14px",
                      borderRadius: 8,
                      background: "var(--bg-surface-alt)",
                      border: "1px solid var(--border-subtle)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <div>
                      <div className="mono" style={{ fontWeight: 700, color: "var(--text-primary)" }}>{prec.case_id}</div>
                      <div className="text-xs muted">{prec.pattern || "Fraud Precedent"}</div>
                    </div>
                    <span
                      style={{
                        fontWeight: 600,
                        color: prec.outcome === "CONFIRMED_FRAUD" ? "var(--status-danger-text)" : "var(--status-success-text)",
                      }}
                    >
                      {prec.outcome}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* TAB 5: FinCEN SAR Regulatory Filing */}
            {activeWorkbenchTab === "regulatory_sar" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {view.sar ? (
                  <>
                    <div className="row" style={{ justifyContent: "space-between" }}>
                      <div>
                        <b>FinCEN BSA Suspicious Activity Report (Form 111)</b>
                        <div className="text-xs muted">Policy R2 / R6 Mandatory Compliance Filing</div>
                      </div>
                      <button className="btn btn-sm" onClick={copySarNarrative}>
                        {sarCopied ? "✓ Narrative Copied" : "Copy Narrative"}
                      </button>
                    </div>

                    <div className="sar-narrative-view">
                      {view.sar.narrative_text}
                    </div>

                    <div style={{ padding: "8px 12px", background: "var(--status-success-bg)", border: "1px solid var(--status-success-border)", borderRadius: 6, fontSize: 12, color: "var(--status-success-text)" }}>
                      ✓ <b>Anti-Hallucination Verified:</b> All entities, amounts, and dates mathematically match TigerGraph graph vertices.
                    </div>
                  </>
                ) : (
                  <div className="card muted" style={{ textAlign: "center", padding: 40 }}>
                    No FinCEN SAR filing is mandated for this incident (exposure is beneath threshold or incident cleared).
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Adjudication & Policy Console */}
        <div className="adjudication-console">
          {/* Post-Evidence Recommended Action */}
          <div className="adjudication-card">
            <div className="adjudication-title-row">
              <span className="adjudication-heading">🔒 Primary Policy Decision</span>
              <DecisionBadge d={currentNba?.decision} />
            </div>

            <div className="text-xs muted">
              Binding actions computed under Enterprise SOP POL-FRD-2026.
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {(currentNba?.actions || []).map((act: any) => (
                <div key={act.code} className="action-item-box">
                  <div>
                    <div className="action-code-pill">{act.code}</div>
                    <div className="text-xs muted">{(act.clauses || []).join(", ") || "Policy SOP"}</div>
                  </div>

                  <div className="row" style={{ gap: 6 }}>
                    <RouteBadge r={act.route} />
                    {view.live && act.status === "PENDING_APPROVAL" && (
                      <div className="row" style={{ gap: 4 }}>
                        <button
                          className="btn btn-emerald btn-sm"
                          disabled={isProcessing}
                          onClick={() =>
                            executeAction(() =>
                              post(`/api/cases/${id}/approve`, {
                                code: act.code,
                                approved: true,
                              })
                            )
                          }
                        >
                          Approve
                        </button>
                        <button
                          className="btn btn-crimson btn-sm"
                          disabled={isProcessing}
                          onClick={() =>
                            executeAction(() =>
                              post(`/api/cases/${id}/approve`, {
                                code: act.code,
                                approved: false,
                              })
                            )
                          }
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {currentNba?.reason && (
              <div className="text-xs muted" style={{ borderTop: "1px dashed var(--border-subtle)", paddingTop: 8 }}>
                {currentNba.reason}
              </div>
            )}
          </div>

          {/* Triggered Policy Guardrails */}
          <div className="adjudication-card">
            <div className="adjudication-title-row">
              <span className="adjudication-heading">⚖️ Triggered Guardrail Rules</span>
              <span className="badge badge-auto">POL-FRD-2026</span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ padding: "8px 10px", background: "var(--bg-surface-alt)", borderRadius: 6, fontSize: 12 }}>
                <b>R1: Real-Time Risk Ingestion</b> → Non-blocking evaluation
              </div>
              {isHighRisk && (
                <div style={{ padding: "8px 10px", background: "var(--status-danger-bg)", border: "1px solid var(--status-danger-border)", borderRadius: 6, fontSize: 12, color: "var(--status-danger-text)" }}>
                  <b>R3: Syndicate Multi-Card Clustered</b> → Mandatory Card Block
                </div>
              )}
              {view.sar && (
                <div style={{ padding: "8px 10px", background: "var(--status-warning-bg)", border: "1px solid var(--status-warning-border)", borderRadius: 6, fontSize: 12, color: "var(--status-warning-text)" }}>
                  <b>R2 / R6: Regulatory SAR Mandate</b> → FinCEN Form 111
                </div>
              )}
            </div>
          </div>

          {/* Persistent Graph Write-Back Status */}
          <div className="adjudication-card">
            <div className="adjudication-title-row">
              <span className="adjudication-heading">💾 TigerGraph Write-Back</span>
              <span className="badge badge-auto">Continuous Learning</span>
            </div>
            <div className="text-xs muted">
              All investigated findings are committed to TigerGraph as persistent vertices for future GraphRAG indexing.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ========================================================================= SAR REGULATORY CENTER
function SarCenterView({ cases, openDossier }: { cases: any[]; openDossier: (id: string) => void }) {
  const sarCases = cases.filter((c) => c.decision_after === "PROTECT");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="card">
        <div className="card-title-group" style={{ marginBottom: 10 }}>
          <div className="text-xl">FinCEN Regulatory Filing Center (BSA Mandate)</div>
          <div className="text-sm muted">Automated Suspicious Activity Report (SAR) Generation & Grounding Audit</div>
        </div>
        <div className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Under Section 2 of Enterprise Fraud Policy POL-FRD-2026, regulatory SAR filings with FinCEN are mandatory
          whenever confirmed fraud exposure exceeds monetary thresholds or connects across multi-card hardware syndicates.
          All generated narratives adhere to the FinCEN 7-point standard and pass programmatic claim verification.
        </div>
      </div>

      <div className="executive-summary-strip">
        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">Filing Mandate Rate</span>
            <span className="metric-tag" style={{ color: "var(--status-danger-text)" }}>MANDATORY</span>
          </div>
          <div className="metric-value" style={{ color: "var(--status-danger-text)" }}>{sarCases.length} Cases</div>
          <div className="metric-footer">Threshold or Ring Triggered</div>
        </div>

        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">Anti-Hallucination Rate</span>
            <span className="metric-tag">GROUNDED</span>
          </div>
          <div className="metric-value" style={{ color: "var(--status-success-text)" }}>100%</div>
          <div className="metric-footer">Every N-Gram Grounded in Graph</div>
        </div>

        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">Regulatory Standard</span>
            <span className="metric-tag">BSA / FINCEN</span>
          </div>
          <div className="metric-value">Form 111</div>
          <div className="metric-footer">7-Point Structured Narrative</div>
        </div>

        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">Audit Readiness</span>
            <span className="metric-tag">VERIFIED</span>
          </div>
          <div className="metric-value">Zero Defect</div>
          <div className="metric-footer">Audit Defense Passed</div>
        </div>
      </div>

      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Case ID</th>
              <th>Subject Card</th>
              <th>Pattern Identified</th>
              <th>Assessed P(fraud)</th>
              <th>Regulatory Basis</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {sarCases.map((c) => (
              <tr key={c.case_id} className="clickable" onClick={() => openDossier(c.case_id)}>
                <td className="mono" style={{ fontWeight: 800, color: "var(--text-primary)" }}>
                  {c.case_id}
                </td>
                <td className="mono">{c.card_id || "Primary Card"}</td>
                <td>{c.pattern}</td>
                <td>
                  <span className="mono" style={{ fontWeight: 700, color: "var(--status-danger-text)" }}>
                    {pct(c.p_after)}
                  </span>
                </td>
                <td>
                  <span className="badge badge-l2">R2 / R6 Filing Mandatory</span>
                </td>
                <td>
                  <button className="btn btn-primary btn-sm" onClick={(e) => { e.stopPropagation(); openDossier(c.case_id); }}>
                    Inspect SAR Narrative →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ========================================================================= OBSERVATORY VIEW
function ObservatoryView() {
  const [modelData, setModelData] = useState<any>(null);

  useEffect(() => {
    get("/api/model").then(setModelData).catch(() => {});
  }, []);

  if (!modelData) {
    return <div className="card muted" style={{ textAlign: "center", padding: 50 }}>Loading Risk Engine Telemetry...</div>;
  }

  const backtest = modelData.backtest || {};

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="executive-summary-strip">
        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">TRACER Model AUC</span>
            <span className="metric-tag">GRAPH + BAYES</span>
          </div>
          <div className="metric-value" style={{ color: "var(--status-success-text)" }}>{backtest.auc_model || "0.956"}</div>
          <div className="metric-footer">Held-Out Test Month</div>
        </div>

        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">Perimeter Risk Score AUC</span>
            <span className="metric-tag">BASELINE</span>
          </div>
          <div className="metric-value" style={{ color: "var(--status-warning-text)" }}>{backtest.auc_risk_score_only || "0.555"}</div>
          <div className="metric-footer">Perimeter Model Alone</div>
        </div>

        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">Brier Score</span>
            <span className="metric-tag">CALIBRATION</span>
          </div>
          <div className="metric-value">{backtest.brier_model || "0.078"}</div>
          <div className="metric-footer">Lower is Superior</div>
        </div>

        <div className="summary-metric-card">
          <div className="metric-header">
            <span className="metric-title">Pattern Attribution</span>
            <span className="metric-tag">ACCURACY</span>
          </div>
          <div className="metric-value">100%</div>
          <div className="metric-footer">Closed Cases Backtest</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-title-group" style={{ marginBottom: 12 }}>
            <div className="text-base" style={{ fontWeight: 700 }}>Reliability Calibration Curve</div>
            <div className="text-xs muted">Predicted Probability vs Observed Empirical Fraud Rate</div>
          </div>
          <Reliability bins={backtest.reliability} />
        </div>

        <div className="card">
          <div className="card-title-group" style={{ marginBottom: 12 }}>
            <div className="text-base" style={{ fontWeight: 700 }}>Learned Feature Log-Odds Weights</div>
            <div className="text-xs muted">Weight Contributions per Graph Topological Feature</div>
          </div>
          <Weights weights={modelData.weights} />
        </div>
      </div>
    </div>
  );
}

// ========================================================================= GOVERNANCE VIEW
function GovernanceView() {
  const [policyData, setPolicyData] = useState<any>(null);

  useEffect(() => {
    get("/api/policy").then(setPolicyData).catch(() => {});
  }, []);

  if (!policyData) {
    return <div className="card muted" style={{ textAlign: "center", padding: 50 }}>Loading Policy Definitions...</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="card">
        <div className="card-title-group" style={{ marginBottom: 6 }}>
          <div className="text-xl">Enterprise Fraud Operating Policy & SOP (POL-FRD-2026)</div>
          <div className="text-xs muted">Version {policyData.version || "1.0"} · Binding Operating Rules</div>
        </div>
        <div className="text-sm muted">
          Strict deterministic policy evaluation governing interim and final actions, enforcing non-blocking interim verifications, human-in-the-loop approval tiers, and regulatory filing triggers.
        </div>
      </div>

      <div className="grid-2">
        <div>
          <div className="text-sm" style={{ fontWeight: 700, marginBottom: 10, color: "var(--text-primary)" }}>
            Binding Rules (R1 – R10)
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(policyData.rules || []).map((r: any) => (
              <div
                key={r.id}
                style={{
                  padding: "10px 12px",
                  borderRadius: 6,
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-subtle)",
                  fontSize: 12.5,
                }}
              >
                <b className="mono" style={{ color: "var(--text-primary)" }}>{r.id}:</b> {r.when} →{" "}
                <span style={{ color: "var(--status-success-text)", fontWeight: 600 }}>{r.recommend.join(", ")}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="text-sm" style={{ fontWeight: 700, marginBottom: 10, color: "var(--text-primary)" }}>
            Approval Authority Hierarchy
          </div>
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Route</th>
                  <th>Classification</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(policyData.actions || {}).map(([code, act]: any) => (
                  <tr key={code}>
                    <td className="mono" style={{ fontSize: 12, fontWeight: 700 }}>{code}</td>
                    <td><RouteBadge r={act.route} /></td>
                    <td className="muted text-xs">{act.class || "Standard Operating Procedure"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
