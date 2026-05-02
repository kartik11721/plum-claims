"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Decision = {
  claim_id: string; decision: string; approved_amount: number;
  confidence: number; member_message: string; ops_summary: string;
  rejection_reasons: string[]; line_item_breakdown: LineItem[];
  applied_rules: string[]; degraded_components: string[];
  early_stop?: { stop_reason: string; member_message: string };
  trace_id: string;
};
type LineItem = { description: string; claimed_amount: number; approved_amount: number; status: string; reason?: string };
type TraceEvent = { step: string; status: string; duration_ms: number; input_summary: object; output_summary: object; error?: string; timestamp: string };
type Trace = { trace_id: string; events: TraceEvent[]; total_duration_ms: number; degradation_factor: number };

const DECISION_BADGE: Record<string, { bg: string; text: string; border: string }> = {
  APPROVED:       { bg: "#f0faf0", text: "#1a7f37", border: "#b7e4c7" },
  PARTIAL:        { bg: "#fffbeb", text: "#92400e", border: "#fde68a" },
  REJECTED:       { bg: "#fff0f1", text: "#cc3342", border: "#ffc8cc" },
  MANUAL_REVIEW:  { bg: "#fff7ed", text: "#9a3412", border: "#fed7aa" },
  NEEDS_DOCUMENTS:{ bg: "#eff8ff", text: "#1e40af", border: "#bfdbfe" },
};

const STATUS_COLORS: Record<string, string> = {
  OK: "#92bd33", DEGRADED: "#ff4052", EARLY_STOP: "#ffbf21", SKIPPED: "#ced5dd",
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = value > 0.8 ? "#92bd33" : value > 0.5 ? "#ffbf21" : "#ff4052";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
      <div style={{ flex: 1, background: "#f0e8e0", borderRadius: "9999px", height: 6 }}>
        <div style={{ width: `${pct}%`, height: 6, borderRadius: "9999px", background: color, transition: "width 0.4s" }} />
      </div>
      <span style={{ fontSize: "0.8125rem", fontWeight: 600, color: "#2d2d2d" }}>{pct}%</span>
    </div>
  );
}

function TraceRow({ event }: { event: TraceEvent }) {
  const [open, setOpen] = useState(false);
  const statusColor = STATUS_COLORS[event.status] ?? "#a0a5ab";
  const icon = event.status === "OK" ? "✓" : event.status === "DEGRADED" ? "⚠" : event.status === "EARLY_STOP" ? "⏹" : "○";
  const badge = DECISION_BADGE[event.status];

  return (
    <div style={{ border: "1px solid #f0e8e0", borderRadius: "0.625rem", overflow: "hidden" }}>
      <button onClick={() => setOpen(!open)}
        style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.75rem 1rem", background: open ? "#fffaf2" : "#fff", textAlign: "left", cursor: "pointer", border: "none" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <span style={{ fontFamily: "monospace", fontSize: "0.875rem", color: statusColor, fontWeight: 700 }}>{icon}</span>
          <span style={{ fontSize: "0.875rem", fontWeight: 500, color: "#2d2d2d" }}>{event.step}</span>
          {badge
            ? <span style={{ fontSize: "0.6875rem", padding: "0.125rem 0.5rem", borderRadius: "9999px", background: badge.bg, color: badge.text, border: `1px solid ${badge.border}`, fontWeight: 600 }}>{event.status}</span>
            : <span style={{ fontSize: "0.6875rem", padding: "0.125rem 0.5rem", borderRadius: "9999px", background: "#f5f0ee", color: "#7a6570", border: "1px solid #e8ddd8" }}>{event.status}</span>
          }
        </div>
        <span style={{ fontSize: "0.75rem", color: "#a0a5ab" }}>{event.duration_ms.toFixed(0)}ms {open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div style={{ borderTop: "1px solid #f0e8e0", padding: "0.75rem 1rem", background: "#fffaf2" }} className="space-y-2">
          {event.error && (
            <div style={{ fontSize: "0.75rem", color: "#cc3342", fontFamily: "monospace", background: "#fff0f1", padding: "0.5rem", borderRadius: "0.375rem" }}>
              {event.error}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p style={{ fontSize: "0.6875rem", fontWeight: 600, color: "#7a6570", marginBottom: "0.25rem" }}>Input</p>
              <pre style={{ fontSize: "0.6875rem", color: "#41495e", background: "#fff", border: "1px solid #f0e8e0", borderRadius: "0.375rem", padding: "0.5rem", overflow: "auto", maxHeight: 160 }}>
                {JSON.stringify(event.input_summary, null, 2)}
              </pre>
            </div>
            <div>
              <p style={{ fontSize: "0.6875rem", fontWeight: 600, color: "#7a6570", marginBottom: "0.25rem" }}>Output</p>
              <pre style={{ fontSize: "0.6875rem", color: "#41495e", background: "#fff", border: "1px solid #f0e8e0", borderRadius: "0.375rem", padding: "0.5rem", overflow: "auto", maxHeight: 160 }}>
                {JSON.stringify(event.output_summary, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ClaimDecision() {
  const { id } = useParams<{ id: string }>();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [dr, tr] = await Promise.all([
          fetch(`${API_URL}/api/claims/${id}`).then(r => r.json()),
          fetch(`${API_URL}/api/claims/${id}/trace`).then(r => r.json()),
        ]);
        setDecision(dr); setTrace(tr);
      } catch (e: any) { setError(e.message); }
      finally { setLoading(false); }
    }
    load();
  }, [id]);

  if (loading) return (
    <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{
          width: 36, height: 36, borderRadius: "50%",
          border: "3px solid rgba(87,14,64,0.15)", borderTopColor: "#ff4052",
          animation: "spin 0.8s linear infinite", margin: "0 auto 12px",
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <p style={{ color: "#7a6570", fontSize: "0.875rem" }}>Loading decision…</p>
      </div>
    </div>
  );

  if (error) return (
    <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "#fff0f1", border: "1px solid #ffc8cc", borderRadius: "0.75rem", padding: "1.5rem 2rem", color: "#cc3342", textAlign: "center" }}>
        <p style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Failed to load</p>
        <p style={{ fontSize: "0.875rem" }}>{error}</p>
      </div>
    </div>
  );

  if (!decision) return null;

  const badge = DECISION_BADGE[decision.decision] ?? { bg: "#f5f0ee", text: "#7a6570", border: "#e8ddd8" };

  return (
    <main style={{ background: "var(--plum-cream)", minHeight: "100vh" }} className="py-10 px-4">
      <div className="max-w-3xl mx-auto space-y-6">

        {/* Breadcrumb */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Link href="/" style={{ fontSize: "0.8125rem", color: "#ff4052", textDecoration: "none", fontWeight: 500 }}>
            ← Submit New Claim
          </Link>
          <span style={{ fontSize: "0.6875rem", color: "#a0a5ab", fontFamily: "monospace" }}>{decision.claim_id}</span>
        </div>

        {/* Decision card */}
        <div className="plum-card p-8">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "1.5rem" }}>
            <div>
              <span style={{ display: "inline-flex", alignItems: "center", padding: "0.375rem 1rem", borderRadius: "9999px", fontSize: "0.8125rem", fontWeight: 700, background: badge.bg, color: badge.text, border: `1px solid ${badge.border}` }}>
                {decision.decision}
              </span>
              {decision.approved_amount > 0 && (
                <p style={{ marginTop: "0.75rem", fontSize: "2.5rem", fontWeight: 800, color: "#2d2d2d", letterSpacing: "-0.04em", lineHeight: 1 }}>
                  ₹{decision.approved_amount.toLocaleString()}
                </p>
              )}
            </div>
            <div style={{ textAlign: "right" }}>
              <p style={{ fontSize: "0.6875rem", color: "#7a6570", fontWeight: 600, marginBottom: "0.375rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                AI Confidence
              </p>
              <div style={{ width: 128 }}><ConfidenceBar value={decision.confidence} /></div>
            </div>
          </div>

          {/* Member message */}
          <div style={{ background: "rgba(87,14,64,0.04)", border: "1px solid rgba(87,14,64,0.1)", borderRadius: "0.625rem", padding: "1rem", marginBottom: "1.25rem" }}>
            <p style={{ fontSize: "0.75rem", fontWeight: 700, color: "#570e40", marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Message to Member
            </p>
            <p style={{ fontSize: "0.875rem", color: "#41495e", lineHeight: 1.6 }}>{decision.member_message}</p>
          </div>

          {decision.degraded_components.length > 0 && (
            <div style={{ background: "#fffbeb", border: "1px solid #fde68a", borderRadius: "0.5rem", padding: "0.75rem 1rem", marginBottom: "1rem" }}>
              <p style={{ fontSize: "0.75rem", fontWeight: 600, color: "#92400e" }}>
                ⚠ Degraded components: {decision.degraded_components.join(", ")}. Manual review recommended.
              </p>
            </div>
          )}

          {/* Line items */}
          {decision.line_item_breakdown.length > 0 && (
            <div style={{ marginBottom: "1.5rem" }}>
              <p style={{ fontSize: "0.8125rem", fontWeight: 700, color: "#2d2d2d", marginBottom: "0.5rem" }}>Line Items</p>
              <div style={{ border: "1px solid #f0e8e0", borderRadius: "0.625rem", overflow: "hidden" }}>
                <table style={{ width: "100%", fontSize: "0.8125rem", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ background: "#fffaf2" }}>
                      <th style={{ textAlign: "left", padding: "0.625rem 1rem", fontSize: "0.6875rem", fontWeight: 700, color: "#7a6570", textTransform: "uppercase", letterSpacing: "0.05em" }}>Description</th>
                      <th style={{ textAlign: "right", padding: "0.625rem 1rem", fontSize: "0.6875rem", fontWeight: 700, color: "#7a6570", textTransform: "uppercase", letterSpacing: "0.05em" }}>Claimed</th>
                      <th style={{ textAlign: "right", padding: "0.625rem 1rem", fontSize: "0.6875rem", fontWeight: 700, color: "#7a6570", textTransform: "uppercase", letterSpacing: "0.05em" }}>Approved</th>
                      <th style={{ textAlign: "center", padding: "0.625rem 1rem", fontSize: "0.6875rem", fontWeight: 700, color: "#7a6570", textTransform: "uppercase", letterSpacing: "0.05em" }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {decision.line_item_breakdown.map((item, i) => {
                      const isRejected = item.status === "REJECTED";
                      const isApproved = item.status === "APPROVED";
                      return (
                        <tr key={i} style={{ borderTop: "1px solid #f0e8e0", background: isRejected ? "#fff8f8" : "#fff" }}>
                          <td style={{ padding: "0.75rem 1rem", color: "#2d2d2d" }}>
                            {item.description}
                            {item.reason && <span style={{ display: "block", fontSize: "0.6875rem", color: "#ff4052", marginTop: "0.125rem" }}>{item.reason}</span>}
                          </td>
                          <td style={{ padding: "0.75rem 1rem", textAlign: "right", color: "#7a6570" }}>₹{item.claimed_amount.toLocaleString()}</td>
                          <td style={{ padding: "0.75rem 1rem", textAlign: "right", fontWeight: 600, color: isRejected ? "#ced5dd" : "#2d2d2d" }}>
                            {isRejected ? "—" : `₹${item.approved_amount.toLocaleString()}`}
                          </td>
                          <td style={{ padding: "0.75rem 1rem", textAlign: "center" }}>
                            <span style={{
                              fontSize: "0.6875rem", padding: "0.125rem 0.5rem", borderRadius: "9999px", fontWeight: 600,
                              background: isApproved ? "#f0faf0" : isRejected ? "#fff0f1" : "#fffbeb",
                              color: isApproved ? "#1a7f37" : isRejected ? "#cc3342" : "#92400e",
                              border: `1px solid ${isApproved ? "#b7e4c7" : isRejected ? "#ffc8cc" : "#fde68a"}`,
                            }}>
                              {item.status}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Applied rules */}
          {decision.applied_rules.length > 0 && (
            <div>
              <p style={{ fontSize: "0.8125rem", fontWeight: 700, color: "#2d2d2d", marginBottom: "0.5rem" }}>Rules Applied</p>
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                {decision.applied_rules.map((rule, i) => (
                  <li key={i} style={{ display: "flex", gap: "0.5rem", fontSize: "0.75rem", color: "#41495e" }}>
                    <span style={{ color: "#ff4052", flexShrink: 0 }}>→</span>{rule}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Trace card */}
        {trace && (
          <div className="plum-card p-8">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
              <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "#2d2d2d" }}>Audit Trace</h2>
              <div style={{ display: "flex", gap: "1rem", fontSize: "0.75rem", color: "#7a6570" }}>
                <span>{trace.events.length} steps</span>
                <span>{trace.total_duration_ms.toFixed(0)}ms total</span>
                {trace.degradation_factor < 1 && (
                  <span style={{ color: "#ffbf21", fontWeight: 600 }}>degradation ×{trace.degradation_factor.toFixed(2)}</span>
                )}
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {trace.events.map((evt, i) => <TraceRow key={i} event={evt} />)}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
