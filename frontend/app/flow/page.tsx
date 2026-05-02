"use client";
import { useEffect, useState } from "react";
import Link from "next/link";

type StepStatus = "pending" | "running" | "done" | "degraded";
type DisplayStatus = StepStatus | "idle";

interface AgentDef {
  key: string;
  label: string;
  role: string;
  badge?: string;
  subAgents?: { key: string; label: string }[];
}

interface Stage {
  layout: "single" | "parallel";
  connectorAbove: "none" | "straight" | "fork" | "join";
  parallelLabel?: string;
  nodes: AgentDef[];
}

const STAGES: Stage[] = [
  {
    layout: "single",
    connectorAbove: "none",
    nodes: [{
      key: "IntakeValidator",
      label: "Intake Validator",
      role: "Validates member ID, policy ID, and minimum claim amount",
    }],
  },
  {
    layout: "parallel",
    connectorAbove: "fork",
    parallelLabel: "parallel",
    nodes: [
      {
        key: "DocumentClassifierAgent",
        label: "Document Classifier",
        role: "Classifies each uploaded document type — prescription, bill, lab report…",
      },
      {
        key: "DocumentQualityAgent",
        label: "Document Quality",
        role: "Checks readability — detects blurry scans, missing pages, corrupt files",
      },
    ],
  },
  {
    layout: "single",
    connectorAbove: "join",
    nodes: [{
      key: "ExtractionAgent",
      label: "Extraction Agent",
      role: "Extracts structured data from each document — runs one agent per document, all in parallel",
      badge: "fan-out per doc",
    }],
  },
  {
    layout: "single",
    connectorAbove: "straight",
    nodes: [{
      key: "CrossDocValidator",
      label: "Cross-Doc Validator",
      role: "Verifies that patient name and identity are consistent across all uploaded documents",
    }],
  },
  {
    layout: "parallel",
    connectorAbove: "fork",
    parallelLabel: "parallel",
    nodes: [
      {
        key: "FraudSignalAgent",
        label: "Fraud Signal Agent",
        role: "Detects fraud patterns — same-day duplicate claims, amount mismatches, repeated providers",
      },
      {
        key: "PolicyOrchestratorAgent",
        label: "Policy Orchestrator",
        role: "Delegates to 6 sub-agents in sequence; short-circuits on first rejection",
        subAgents: [
          { key: "MemberValidationAgent",  label: "Member Validation" },
          { key: "ExclusionCheckerAgent",  label: "Exclusion Check" },
          { key: "WaitingPeriodAgent",     label: "Waiting Period" },
          { key: "PreAuthCheckerAgent",    label: "Pre-Auth Check" },
          { key: "PerClaimLimitAgent",     label: "Per-Claim Limit" },
          { key: "BenefitCalculatorAgent", label: "Benefit Calculator" },
        ],
      },
    ],
  },
  {
    layout: "single",
    connectorAbove: "join",
    nodes: [{
      key: "DecisionSynthesizer",
      label: "Decision Synthesizer",
      role: "Aggregates all signals and produces the final decision with a plain-language member message",
    }],
  },
];

const ST: Record<DisplayStatus, { bg: string; border: string; text: string; dot: string; glow: string }> = {
  idle:     { bg: "#faf7f9",                   border: "#e4d0dc", text: "#9a8490", dot: "#d4bece", glow: "none" },
  pending:  { bg: "#faf7f9",                   border: "#e4d0dc", text: "#7a6570", dot: "#d4bece", glow: "none" },
  running:  { bg: "rgba(87,14,64,0.07)",       border: "#570e40", text: "#3d0a2d", dot: "#570e40", glow: "0 0 0 3px rgba(87,14,64,0.18), 0 4px 20px rgba(87,14,64,0.14)" },
  done:     { bg: "rgba(146,189,51,0.08)",     border: "#92bd33", text: "#3d5a10", dot: "#92bd33", glow: "none" },
  degraded: { bg: "rgba(255,191,33,0.08)",     border: "#ffbf21", text: "#6b4400", dot: "#ffbf21", glow: "none" },
};

function StatusIcon({ status }: { status: DisplayStatus }) {
  if (status === "running") {
    return (
      <span style={{
        display: "inline-block", width: 14, height: 14, borderRadius: "50%", flexShrink: 0,
        border: "2.5px solid #570e40", borderTopColor: "transparent",
        animation: "spin 0.7s linear infinite",
      }} />
    );
  }
  if (status === "done")     return <span style={{ color: "#92bd33", fontWeight: 700, fontSize: "0.875rem", lineHeight: 1 }}>&#10003;</span>;
  if (status === "degraded") return <span style={{ color: "#ffbf21", fontSize: "0.875rem", lineHeight: 1 }}>&#9888;</span>;
  return (
    <span style={{
      display: "inline-block", width: 8, height: 8, borderRadius: "50%",
      background: ST[status].dot, flexShrink: 0,
    }} />
  );
}

function SubAgentRow({ label, status }: { label: string; status: DisplayStatus }) {
  const st = ST[status];
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: "5px 10px", borderRadius: 6,
      background: st.bg, border: `1px solid ${st.border}`,
      transition: "all 0.25s ease",
    }}>
      <StatusIcon status={status} />
      <span style={{ fontSize: "0.75rem", fontWeight: 500, color: st.text }}>{label}</span>
    </div>
  );
}

function NodeCard({ def, stepStatuses }: { def: AgentDef; stepStatuses: Record<string, StepStatus> }) {
  const raw = stepStatuses[def.key];
  const status: DisplayStatus = raw ?? "idle";
  const st = ST[status];

  const parentIsActive = status === "running";
  const anySubRunning = def.subAgents?.some(sa => stepStatuses[sa.key] === "running") ?? false;
  const isHighlighted = parentIsActive || anySubRunning;

  return (
    <div style={{
      flex: 1,
      background: st.bg, border: `1.5px solid ${st.border}`, borderRadius: 12,
      padding: "14px 18px",
      boxShadow: isHighlighted ? st.glow : "0 1px 6px rgba(0,0,0,0.05)",
      transition: "all 0.3s ease",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <StatusIcon status={status} />
        <span style={{ fontSize: "0.875rem", fontWeight: 700, color: st.text, letterSpacing: "-0.01em", flex: 1 }}>
          {def.label}
        </span>
        {parentIsActive && !def.subAgents && (
          <span style={{
            fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.04em",
            background: "#570e40", color: "#fff", borderRadius: 4, padding: "2px 7px",
          }}>LIVE</span>
        )}
        {def.badge && (
          <span style={{
            fontSize: "0.65rem", fontWeight: 600,
            background: "rgba(87,14,64,0.10)", color: "#570e40",
            borderRadius: 4, padding: "2px 7px",
          }}>{def.badge}</span>
        )}
      </div>
      <p style={{ fontSize: "0.75rem", color: "#9a8490", margin: 0, lineHeight: 1.45 }}>
        {def.role}
      </p>
      {def.subAgents && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
          {def.subAgents.map(sa => (
            <SubAgentRow key={sa.key} label={sa.label} status={stepStatuses[sa.key] ?? "idle"} />
          ))}
        </div>
      )}
    </div>
  );
}

function Connector({ type }: { type: "straight" | "fork" | "join" }) {
  const color = "#dcc4d2";
  let d = "";
  if (type === "straight") d = "M 50 0 L 50 32";
  else if (type === "fork")  d = "M 50 0 L 50 16 M 50 16 L 25 16 L 25 32 M 50 16 L 75 16 L 75 32";
  else                       d = "M 25 0 L 25 16 M 75 0 L 75 16 M 25 16 L 50 16 M 75 16 L 50 16 M 50 16 L 50 32";

  return (
    <svg width="100%" height="32" viewBox="0 0 100 32" preserveAspectRatio="none" style={{ display: "block" }}>
      <path d={d} stroke={color} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ParallelBadge({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6, justifyContent: "center" }}>
      <span style={{ flex: 1, height: 1, background: "#e4d0dc", maxWidth: 40, display: "block" }} />
      <span style={{
        fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.06em",
        color: "#a07888", background: "#f5eef3", border: "1px solid #e4d0dc",
        borderRadius: 4, padding: "2px 8px", textTransform: "uppercase",
      }}>{label}</span>
      <span style={{ flex: 1, height: 1, background: "#e4d0dc", maxWidth: 40, display: "block" }} />
    </div>
  );
}

export default function FlowPage() {
  const [stepStatuses, setStepStatuses] = useState<Record<string, StepStatus>>({});
  const [phase, setPhase] = useState<"idle" | "processing" | "complete" | "error">("idle");
  const [claimId, setClaimId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    const ch = new BroadcastChannel("plum-claims-flow");
    ch.onmessage = (e) => {
      const msg = e.data;
      if (msg.type === "reset") {
        setStepStatuses({});
        setPhase("processing");
        setClaimId(null);
        setErrorMsg("");
      } else if (msg.type === "step") {
        const next: StepStatus = msg.status === "started" ? "running"
          : msg.status === "degraded" ? "degraded" : "done";
        setStepStatuses(prev => ({ ...prev, [msg.step]: next }));
      } else if (msg.type === "complete") {
        setClaimId(msg.claim_id);
        setPhase("complete");
      } else if (msg.type === "error") {
        setErrorMsg(msg.message);
        setPhase("error");
      }
    };
    return () => ch.close();
  }, []);

  return (
    <main style={{ background: "var(--plum-cream)", minHeight: "100vh", padding: "32px 16px 64px" }}>
      <style>{`
        @keyframes spin    { to { transform: rotate(360deg); } }
        @keyframes breathe { 0%,100% { opacity:1; } 50% { opacity:0.55; } }
      `}</style>
      <div style={{ maxWidth: 820, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: 28, display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 6, padding: "3px 10px", borderRadius: 999, background: "rgba(87,14,64,0.08)", fontSize: "0.75rem", fontWeight: 600, color: "#570e40" }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: phase === "processing" ? "#ff4052" : "#d4bece", display: "inline-block", ...(phase === "processing" ? { animation: "breathe 1.4s ease-in-out infinite" } : {}) }} />
              Multi-Agent Pipeline
            </div>
            <h1 style={{ fontSize: "1.625rem", fontWeight: 800, color: "#2d2d2d", margin: 0, letterSpacing: "-0.03em" }}>
              Live Agent Flow
            </h1>
            <p style={{ fontSize: "0.8125rem", color: "#7a6570", margin: "3px 0 0" }}>
              Plum Group Health Insurance — real-time claim processing view
            </p>
          </div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
            <Link href="/" style={{ fontSize: "0.8125rem", color: "#570e40", fontWeight: 600, textDecoration: "none", padding: "5px 12px", border: "1.5px solid #e4d0dc", borderRadius: 8, background: "#fff" }}>
              Submit claim
            </Link>
            {phase === "complete" && claimId && (
              <Link href={`/claims/${claimId}`} target="_blank" style={{ fontSize: "0.8125rem", color: "#3d5a10", fontWeight: 600, textDecoration: "none", padding: "5px 12px", border: "1.5px solid #92bd33", borderRadius: 8, background: "rgba(146,189,51,0.08)" }}>
                View result →
              </Link>
            )}
          </div>
        </div>

        {/* Status banner */}
        {phase === "idle" && (
          <div style={{ marginBottom: 20, padding: "10px 16px", borderRadius: 10, background: "#f5eef3", border: "1px solid #e4d0dc", fontSize: "0.8125rem", color: "#7a6570" }}>
            Waiting for a claim submission — open the{" "}
            <Link href="/" style={{ color: "#570e40", fontWeight: 600 }}>submit page</Link>
            {" "}in another tab to see this flow update live.
          </div>
        )}
        {phase === "error" && errorMsg && (
          <div style={{ marginBottom: 20, padding: "10px 16px", borderRadius: 10, background: "#fff0f1", border: "1px solid #ffc8cc", fontSize: "0.8125rem", color: "#cc3342" }}>
            Pipeline error: {errorMsg}
          </div>
        )}
        {phase === "complete" && (
          <div style={{ marginBottom: 20, padding: "10px 16px", borderRadius: 10, background: "rgba(146,189,51,0.09)", border: "1px solid #92bd33", fontSize: "0.8125rem", color: "#3d5a10", fontWeight: 600 }}>
            Pipeline complete.{claimId && <> Claim <code style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{claimId}</code> processed.</>}
          </div>
        )}

        {/* Pipeline diagram */}
        <div style={{ display: "flex", flexDirection: "column" }}>
          {STAGES.map((stage, i) => (
            <div key={i}>
              {stage.connectorAbove !== "none" && (
                <Connector type={stage.connectorAbove} />
              )}

              {stage.layout === "parallel" && stage.parallelLabel && (
                <ParallelBadge label={stage.parallelLabel} />
              )}

              <div style={{
                display: "flex",
                gap: 16,
                ...(stage.layout === "single" ? { maxWidth: 540, margin: "0 auto", width: "100%" } : {}),
              }}>
                {stage.nodes.map(node => (
                  <NodeCard key={node.key} def={node} stepStatuses={stepStatuses} />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Legend */}
        <div style={{ marginTop: 28, padding: "12px 18px", borderRadius: 10, background: "#f5eef3", border: "1px solid #e4d0dc" }}>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", fontSize: "0.75rem", color: "#7a6570", alignItems: "center" }}>
            <span style={{ fontWeight: 600, color: "#9a8490" }}>Legend</span>
            {([
              ["idle",     "Waiting"],
              ["running",  "Running"],
              ["done",     "Complete"],
              ["degraded", "Degraded"],
            ] as [DisplayStatus, string][]).map(([s, label]) => (
              <div key={s} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <StatusIcon status={s} />
                <span>{label}</span>
              </div>
            ))}
            <span style={{ marginLeft: "auto", color: "#c0b0bb" }}>Updates via BroadcastChannel from the submit tab</span>
          </div>
        </div>

      </div>
    </main>
  );
}
