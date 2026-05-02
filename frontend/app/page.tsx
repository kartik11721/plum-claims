"use client";
import { useState, useRef } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
import { useRouter } from "next/navigation";

const CATEGORIES = ["CONSULTATION","DIAGNOSTIC","PHARMACY","DENTAL","VISION","ALTERNATIVE_MEDICINE"];
const MEMBERS = [
  {id:"EMP001",name:"Rajesh Kumar"},{id:"EMP002",name:"Priya Singh"},
  {id:"EMP003",name:"Amit Verma"},{id:"EMP004",name:"Sneha Reddy"},
  {id:"EMP005",name:"Vikram Joshi"},{id:"EMP006",name:"Kavita Nair"},
  {id:"EMP007",name:"Suresh Patil"},{id:"EMP008",name:"Ravi Menon"},
  {id:"EMP009",name:"Anita Desai"},{id:"EMP010",name:"Deepak Shah"},
];

const STEPS = [
  { key: "IntakeValidator",         label: "Validating member & policy" },
  { key: "DocumentClassifierAgent", label: "Classifying documents" },
  { key: "DocumentQualityAgent",    label: "Checking document quality" },
  { key: "ExtractionAgent",         label: "Extracting information" },
  { key: "CrossDocValidator",       label: "Verifying document identity" },
  { key: "FraudSignalAgent",        label: "Checking for fraud signals" },
  { key: "PolicyOrchestratorAgent", label: "Applying policy rules" },
  { key: "DecisionSynthesizer",     label: "Generating decision" },
];

type StepStatus = "pending" | "running" | "done" | "degraded";

const CATEGORY_LABELS: Record<string, string> = {
  CONSULTATION: "Consultation",
  DIAGNOSTIC: "Diagnostics",
  PHARMACY: "Pharmacy",
  DENTAL: "Dental",
  VISION: "Vision",
  ALTERNATIVE_MEDICINE: "Alternative Medicine",
};

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stepStatuses, setStepStatuses] = useState<Record<string, StepStatus>>({});
  const [activeStep, setActiveStep] = useState<string | null>(null);
  const [form, setForm] = useState({
    member_id: "EMP001", claim_category: "CONSULTATION",
    treatment_date: "2024-11-01", claimed_amount: "1500",
    hospital_name: "", ytd_claims_amount: "5000",
  });
  const [files, setFiles] = useState<FileList | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const completedCount = Object.values(stepStatuses).filter(s => s === "done" || s === "degraded").length;
  const progressPct = STEPS.length > 0 ? Math.round((completedCount / STEPS.length) * 100) : 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!files || files.length === 0) {
      setError("Please upload at least one supporting document (e.g. prescription, hospital bill) before submitting.");
      return;
    }
    setLoading(true);
    setError("");
    setStepStatuses({});
    setActiveStep(null);

    try {
      const metadata = {
        member_id: form.member_id, policy_id: "PLUM_GHI_2024",
        claim_category: form.claim_category, treatment_date: form.treatment_date,
        claimed_amount: parseFloat(form.claimed_amount),
        hospital_name: form.hospital_name || undefined,
        ytd_claims_amount: parseFloat(form.ytd_claims_amount || "0"),
        documents: [],
      };
      const fd = new FormData();
      fd.append("metadata", JSON.stringify(metadata));
      if (files) for (let i = 0; i < files.length; i++) fd.append("files", files[i]);

      const res = await fetch(`${API_URL}/api/claims/stream`, { method: "POST", body: fd });
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const event = JSON.parse(line.slice(6));

          if (event.type === "step") {
            if (event.status === "started") {
              setActiveStep(event.step);
              setStepStatuses(prev => ({ ...prev, [event.step]: "running" }));
            } else {
              setActiveStep(null);
              setStepStatuses(prev => ({
                ...prev,
                [event.step]: event.status === "degraded" ? "degraded" : "done",
              }));
            }
          } else if (event.type === "complete") {
            router.push(`/claims/${event.claim_id}`);
            return;
          } else if (event.type === "error") {
            throw new Error(event.message);
          }
        }
      }
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  }

  return (
    <main style={{ background: "var(--plum-cream)" }} className="min-h-screen py-10 px-4">
      <div className="max-w-2xl mx-auto">

        {/* Hero header */}
        <div className="mb-8">
          <div className="mb-3 inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium"
            style={{ background: "rgba(87,14,64,0.08)", color: "#570e40" }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#ff4052", display: "inline-block" }} />
            AI-Powered Claims Processing
          </div>
          <h1 style={{ fontSize: "2rem", fontWeight: 800, color: "#2d2d2d", lineHeight: 1.15, letterSpacing: "-0.03em" }}>
            Submit a Claim
          </h1>
          <p style={{ marginTop: "0.5rem", color: "#7a6570", fontSize: "0.9375rem" }}>
            Plum Group Health Insurance — your claim is reviewed instantly by AI.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="plum-card p-8 space-y-6">

          {/* Member + Category row */}
          <div className="grid grid-cols-2 gap-5">
            <div>
              <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: 600, color: "#570e40", marginBottom: "0.375rem" }}>
                Member
              </label>
              <select className="plum-input"
                value={form.member_id} onChange={e => setForm({ ...form, member_id: e.target.value })}>
                {MEMBERS.map(m => <option key={m.id} value={m.id}>{m.name} ({m.id})</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: 600, color: "#570e40", marginBottom: "0.375rem" }}>
                Claim Category
              </label>
              <select className="plum-input"
                value={form.claim_category} onChange={e => setForm({ ...form, claim_category: e.target.value })}>
                {CATEGORIES.map(c => <option key={c} value={c}>{CATEGORY_LABELS[c] ?? c.replace(/_/g, " ")}</option>)}
              </select>
            </div>
          </div>

          {/* Date + Amount row */}
          <div className="grid grid-cols-2 gap-5">
            <div>
              <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: 600, color: "#570e40", marginBottom: "0.375rem" }}>
                Treatment Date
              </label>
              <input type="date" className="plum-input"
                value={form.treatment_date} onChange={e => setForm({ ...form, treatment_date: e.target.value })} required />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: 600, color: "#570e40", marginBottom: "0.375rem" }}>
                Claimed Amount (₹)
              </label>
              <input type="number" className="plum-input" placeholder="e.g. 1500"
                value={form.claimed_amount} onChange={e => setForm({ ...form, claimed_amount: e.target.value })} required />
            </div>
          </div>

          {/* Hospital + YTD row */}
          <div className="grid grid-cols-2 gap-5">
            <div>
              <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: 600, color: "#570e40", marginBottom: "0.375rem" }}>
                Hospital Name
              </label>
              <input type="text" className="plum-input" placeholder="e.g. Apollo Hospitals"
                value={form.hospital_name} onChange={e => setForm({ ...form, hospital_name: e.target.value })} />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: 600, color: "#570e40", marginBottom: "0.375rem" }}>
                YTD Claims (₹)
              </label>
              <input type="number" className="plum-input" placeholder="e.g. 5000"
                value={form.ytd_claims_amount} onChange={e => setForm({ ...form, ytd_claims_amount: e.target.value })} />
            </div>
          </div>

          {/* File upload */}
          <div>
            <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: 600, color: "#570e40", marginBottom: "0.375rem" }}>
              Supporting Documents
            </label>
            <input
              ref={fileInputRef}
              type="file" multiple accept="image/*,.pdf"
              style={{ display: "none" }}
              onChange={e => { setFiles(e.target.files); if (e.target.files && e.target.files.length > 0) setError(""); }}
            />
            <div
              style={{
                border: `1.5px dashed ${isDragging ? "#570e40" : "#e8c4d8"}`,
                borderRadius: "0.625rem",
                background: isDragging ? "rgba(87,14,64,0.04)" : "rgba(255,250,242,0.8)",
                cursor: "pointer",
                transition: "border-color 0.15s, background 0.15s",
              }}
              className="px-4 py-5 text-center"
              onClick={() => fileInputRef.current?.click()}
              onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
              onDragEnter={e => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={e => {
                e.preventDefault();
                setIsDragging(false);
                const dropped = e.dataTransfer.files;
                if (dropped && dropped.length > 0) {
                  setFiles(dropped);
                  setError("");
                }
              }}>
              {files && files.length > 0 ? (
                <div>
                  <span style={{ color: "#92bd33", fontWeight: 600, fontSize: "0.875rem" }}>✓ {files.length} file{files.length > 1 ? "s" : ""} selected</span>
                  <p style={{ color: "#a0a5ab", fontSize: "0.75rem", marginTop: "0.25rem" }}>
                    {Array.from(files).map(f => f.name).join(", ")}
                  </p>
                </div>
              ) : (
                <div>
                  <p style={{ color: "#7a6570", fontSize: "0.875rem", fontWeight: 500 }}>Click or drag files here</p>
                  <p style={{ color: "#a0a5ab", fontSize: "0.75rem", marginTop: "0.25rem" }}>
                    Prescription, hospital bill, lab reports — JPG, PNG, PDF
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Progress panel */}
          {loading && (
            <div style={{ background: "rgba(87,14,64,0.04)", border: "1px solid rgba(87,14,64,0.12)", borderRadius: "0.75rem" }}
              className="p-5 space-y-4">
              <div>
                <div className="flex justify-between mb-1.5" style={{ fontSize: "0.75rem", fontWeight: 600, color: "#570e40" }}>
                  <span>Processing claim…</span>
                  <span>{progressPct}%</span>
                </div>
                <div style={{ background: "rgba(87,14,64,0.12)", borderRadius: "9999px", height: "6px", overflow: "hidden" }}>
                  <div style={{
                    height: "6px", borderRadius: "9999px",
                    background: "linear-gradient(90deg, #570e40 0%, #ff4052 100%)",
                    width: `${progressPct}%`,
                    transition: "width 0.5s ease",
                  }} />
                </div>
              </div>
              <ul className="space-y-1.5">
                {STEPS.map(s => {
                  const status = stepStatuses[s.key] ?? "pending";
                  return (
                    <li key={s.key} className="flex items-center gap-2.5" style={{ fontSize: "0.8125rem" }}>
                      <span style={{ width: 20, height: 20, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                        {status === "done"     && <span style={{ color: "#92bd33", fontWeight: 700 }}>✓</span>}
                        {status === "degraded" && <span style={{ color: "#ffbf21" }}>⚠</span>}
                        {status === "running"  && (
                          <span style={{
                            display: "block", width: 14, height: 14, borderRadius: "50%",
                            border: "2px solid #ff4052", borderTopColor: "transparent",
                            animation: "spin 0.7s linear infinite",
                          }} />
                        )}
                        {status === "pending"  && <span style={{ display: "block", width: 8, height: 8, borderRadius: "50%", background: "#ced5dd", margin: "auto" }} />}
                      </span>
                      <span style={{
                        color: status === "done"     ? "#a0a5ab" :
                               status === "running"  ? "#570e40" :
                               status === "degraded" ? "#ffbf21" : "#ced5dd",
                        textDecoration: status === "done" ? "line-through" : "none",
                        fontWeight: status === "running" ? 600 : 400,
                      }}>
                        {s.label}
                      </span>
                    </li>
                  );
                })}
              </ul>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          )}

          {error && (
            <div style={{ background: "#fff0f1", border: "1px solid #ffc8cc", borderRadius: "0.5rem", padding: "0.75rem 1rem", fontSize: "0.875rem", color: "#cc3342" }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} style={{
            width: "100%", padding: "0.75rem", fontSize: "0.9375rem", fontWeight: 600,
            background: loading ? "rgba(87,14,64,0.4)" : "linear-gradient(135deg, #570e40 0%, #ff4052 100%)",
            color: "#fff", borderRadius: "0.625rem", border: "none", cursor: loading ? "not-allowed" : "pointer",
            transition: "opacity 0.15s ease",
          }}>
            {loading ? "Processing…" : "Submit Claim →"}
          </button>

          <p style={{ textAlign: "center", fontSize: "0.75rem", color: "#a0a5ab" }}>
            No misselling. No pressure. No jargon.
          </p>
        </form>
      </div>
    </main>
  );
}
