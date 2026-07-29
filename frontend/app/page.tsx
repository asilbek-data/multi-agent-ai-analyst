"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

/* ============ 1. SOZLAMALAR ============ */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
const LIVE = Boolean(API_URL);

const DOCUMENTS: DocumentEntry[] = [
  { file: "churn_postmortem_q2_2026.md", chunks: 11, state: "indexed" },
  { file: "pricing_and_packaging.md", chunks: 8, state: "indexed" },
  { file: "support_sla_policy.md", chunks: 7, state: "indexed" },
  { file: "product_roadmap_h2_2026.md", chunks: 9, state: "indexed" },
  { file: "customer_success_playbook.md", chunks: 12, state: "indexed" },
  { file: "security_and_compliance.md", state: "indexing" },
];

const EVAL_ROWS: EvalRow[] = [
  { question: "Why did we lose the most revenue last quarter?", routing: true, correctness: 1, faithfulness: 1 },
  { question: "How many accounts churned in Q2?", routing: true, correctness: 1, faithfulness: 1 },
  { question: "What share of MRR did MISSING_FEATURE cost us?", routing: true, correctness: 1, faithfulness: 1 },
  { question: "What is our P1 response target?", routing: true, correctness: 1, faithfulness: 1 },
  { question: "Is the SAP connector on the roadmap?", routing: true, correctness: 1, faithfulness: 1 },
  { question: "What did competitors ship this quarter?", routing: true, correctness: 1, faithfulness: 1 },
];

/** Stream matnini agentga bog'laydi. Backend so'zlari boshqacha bo'lsa shu yerni tahrirlang. */
function actorFromStatus(text: string): AgentId | null {
  const t = text.toLowerCase();
  if (t.includes("supervisor")) return "supervisor";
  if (t.includes("retriev") || t.includes("document")) return "retriever";
  if (t.includes("web") || t.includes("search")) return "web";
  if (t.includes("sql") || t.includes("data")) return "data";
  if (t.includes("code") || t.includes("python") || t.includes("calc")) return "code";
  if (t.includes("critic") || t.includes("verify")) return "critic";
  if (t.includes("generat") || t.includes("answer")) return "generate";
  return null;
}

/* ============ 2. TIPLAR ============ */

type AgentId = "supervisor" | "retriever" | "web" | "data" | "code" | "critic" | "generate";
type StepStatus = "running" | "done" | "error";

type RailStep =
  | { kind: "thought"; id: string; actor: "supervisor" | "critic"; text: string }
  | { kind: "call"; id: string; from: AgentId; to: AgentId; ms?: number; tokens?: number; status: StepStatus }
  | { kind: "branch"; id: string; label: string };

interface SourceCard { id: string; title: string; file: string; excerpt: string; relevance?: number }
interface SqlCard { id: string; question?: string; sql: string; columns?: string[]; rows?: (string | number)[][] }
interface CodeCard { id: string; language: string; code: string; result?: string }
interface TraceEvent { id: string; at: number; label: string; detail?: string }
interface DocumentEntry { file: string; chunks?: number; state: "indexed" | "indexing" | "failed" }
interface EvalRow { question: string; routing: boolean; correctness: number; faithfulness: number }

interface RunState {
  question: string; steps: RailStep[]; answer: string;
  sources: SourceCard[]; sql: SqlCard[]; code: CodeCard[]; trace: TraceEvent[];
  status: "idle" | "running" | "done" | "error"; error?: string;
}
interface Conversation { id: string; question: string; run: RunState }

const emptyRun = (question = ""): RunState => ({
  question, steps: [], answer: "", sources: [], sql: [], code: [], trace: [], status: "idle",
});

const AGENTS: Record<AgentId, { label: string; color: string; blurb: string }> = {
  supervisor: { label: "SUPERVISOR", color: "var(--a-supervisor)", blurb: "Decides which specialist runs next." },
  retriever: { label: "RETRIEVER", color: "var(--a-retriever)", blurb: "Searches your documents and returns the passages that matter." },
  web: { label: "WEB", color: "var(--a-web)", blurb: "Looks things up on the live web when your documents can't answer." },
  data: { label: "DATA", color: "var(--a-data)", blurb: "Writes a read-only SQL query and runs it against the database." },
  code: { label: "CODE", color: "var(--a-code)", blurb: "Runs Python for arithmetic the model shouldn't do in its head." },
  critic: { label: "CRITIC", color: "var(--a-critic)", blurb: "Checks the answer against the sources before you see it." },
  generate: { label: "ANSWER", color: "var(--a-generate)", blurb: "Writes the final answer from everything gathered." },
};

const TOGGLEABLE: AgentId[] = ["retriever", "web", "data", "code"];

/* ============ 3. YOZIB OLINGAN RUN (backend ulanmaganda) ============ */

const DEMO_RUN: RunState = {
  question: "Why did we lose the most revenue last quarter?",
  status: "done",
  steps: [
    { kind: "thought", id: "t1", actor: "supervisor", text: "The count has to come from the database." },
    { kind: "call", id: "c1", from: "supervisor", to: "data", ms: 1200, tokens: 512, status: "done" },
    { kind: "thought", id: "t2", actor: "supervisor", text: "The reason codes need explaining from the postmortem." },
    { kind: "call", id: "c2", from: "supervisor", to: "retriever", ms: 880, tokens: 1340, status: "done" },
    { kind: "thought", id: "t3", actor: "supervisor", text: "The share of MRR needs exact arithmetic." },
    { kind: "call", id: "c3", from: "supervisor", to: "code", ms: 640, tokens: 402, status: "done" },
    { kind: "branch", id: "b1", label: "Revision 1 · new branch" },
    { kind: "thought", id: "t4", actor: "critic", text: "The critic wants the explanation behind each code." },
    { kind: "call", id: "c4", from: "supervisor", to: "retriever", ms: 720, tokens: 1180, status: "done" },
    { kind: "call", id: "c5", from: "supervisor", to: "generate", ms: 2100, tokens: 890, status: "done" },
  ],
  answer:
    "MISSING_FEATURE was the largest driver of lost revenue in Q2 2026 — 14 of the 31 churned accounts, worth 4.2% of opening MRR. Two gaps came up in every offboarding call: native SAP and Workday connectors, and multi-step approval branching. Both are committed for Q4 on the H2 roadmap.\n\nPRICE (9 accounts) and ONBOARDING_FAILURE (5 accounts) follow. Separately, every account tagged POOR_SUPPORT had breached a P1 target in its final 90 days — the failure is slow escalation, not slow first response.",
  sources: [
    { id: "s1", title: "Q2 2026 churn postmortem — what we saw", file: "CHURN_POSTMORTEM_Q2_2026.MD",
      excerpt: "MISSING_FEATURE was the single largest driver of churn in the quarter, and by a wide margin the largest driver of lost revenue. Two gaps came up in every offboarding call: native SAP and Workday connectors, and multi-step approval branching.",
      relevance: 0.94 },
    { id: "s2", title: "Q2 2026 churn postmortem — support quality", file: "CHURN_POSTMORTEM_Q2_2026.MD",
      excerpt: "Every account tagged POOR_SUPPORT had breached P1 targets in the 90 days before they left. The pattern is not slow first response — it is slow escalation once the first responder cannot solve the problem.",
      relevance: 0.88 },
    { id: "s3", title: "Reason code dictionary", file: "CHURN_POSTMORTEM_Q2_2026.MD",
      excerpt: "MISSING_FEATURE — the customer needed a capability we do not ship and could not wait for it. PRICE — the customer left over cost. ONBOARDING_FAILURE — the account never reached activation (fewer than 3 live workflows at day 90).",
      relevance: 0.81 },
    { id: "s4", title: "H2 2026 roadmap — Q4 commitments", file: "PRODUCT_ROADMAP_H2_2026.MD",
      excerpt: "Native SAP connector (S/4HANA and ECC) and native Workday connector are both committed for Q4, with multi-step approval branching landing alongside them.",
      relevance: 0.76 },
  ],
  sql: [
    { id: "q1", question: "Churned accounts and lost MRR by reason code, Q2 2026",
      sql: "SELECT reason_code,\n       COUNT(*)      AS accounts,\n       SUM(mrr_usd)  AS lost_mrr\nFROM churn_events\nWHERE churned_on BETWEEN '2026-04-01' AND '2026-06-30'\nGROUP BY reason_code\nORDER BY lost_mrr DESC;",
      columns: ["reason_code", "accounts", "lost_mrr"],
      rows: [["MISSING_FEATURE", 14, 41800], ["PRICE", 9, 18250], ["ONBOARDING_FAILURE", 5, 9400], ["POOR_SUPPORT", 3, 6150]] },
  ],
  code: [
    { id: "k1", language: "python", code: "lost = 41800\nopening_mrr = 995_000\nround(lost / opening_mrr * 100, 1)", result: "4.2" },
  ],
  trace: [
    { id: "e1", at: 0, label: "run.start", detail: "thread 9f2c · recorded" },
    { id: "e2", at: 1200, label: "agent.data", detail: "1 query · 4 rows" },
    { id: "e3", at: 2080, label: "agent.retriever", detail: "3 chunks · top score 0.94" },
    { id: "e4", at: 2720, label: "agent.code", detail: "python · exit 0" },
    { id: "e5", at: 2760, label: "critic.reject", detail: "reason codes unexplained" },
    { id: "e6", at: 3480, label: "agent.retriever", detail: "1 chunk · reason code dictionary" },
    { id: "e7", at: 5580, label: "critic.accept", detail: "grounded in 4 sources" },
  ],
};

/* ============ 4. IKONKALAR ============ */

const svgProps = {
  width: 15, height: 15, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.7, strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
};

const IconPlus = () => (<svg {...svgProps} aria-hidden><path d="M12 5v14M5 12h14" /></svg>);
const IconChat = () => (<svg {...svgProps} aria-hidden><path d="M21 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z" /></svg>);
const IconDoc = () => (<svg {...svgProps} width={13} height={13} aria-hidden><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>);
const IconDatabase = () => (<svg {...svgProps} width={13} height={13} aria-hidden><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></svg>);
const IconGlobe = () => (<svg {...svgProps} width={13} height={13} aria-hidden><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18" /></svg>);
const IconCode = () => (<svg {...svgProps} width={13} height={13} aria-hidden><path d="m9 18-6-6 6-6M15 6l6 6-6 6" /></svg>);
const IconInfo = () => (<svg {...svgProps} width={16} height={16} aria-hidden><circle cx="12" cy="12" r="9" /><path d="M12 16v-5M12 8h.01" /></svg>);
const IconMoon = () => (<svg {...svgProps} width={16} height={16} aria-hidden><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>);
const IconSun = () => (<svg {...svgProps} width={16} height={16} aria-hidden><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>);
const IconSearch = () => (<svg {...svgProps} width={16} height={16} aria-hidden><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>);

const Mark = () => (
  <svg className="c-mark" viewBox="0 0 16 16" aria-hidden>
    <rect x="1" y="1" width="3" height="14" rx="1.5" fill="var(--a-supervisor)" />
    <circle cx="12" cy="4.5" r="2" fill="var(--a-data)" />
    <circle cx="12" cy="11.5" r="2" fill="var(--a-retriever)" />
  </svg>
);

const agentIcon: Partial<Record<AgentId, React.ReactNode>> = {
  retriever: <IconDoc />, web: <IconGlobe />, data: <IconDatabase />, code: <IconCode />,
};

/* ============ 5. STREAM ============ */

let seq = 0;
const uid = () => `n${++seq}`;

function decode(raw: string): {
  status?: string; token?: string; answer?: string;
  sources?: any[]; sql?: any; code?: any; done?: boolean; error?: string;
} {
  const trimmed = raw.trim();
  if (!trimmed || trimmed === "[DONE]") return { done: true };

  if (trimmed.startsWith("{")) {
    try {
      const j = JSON.parse(trimmed);
      const type = String(j.type ?? j.event ?? "").toLowerCase();
      if (type === "error" || j.error) return { error: String(j.error ?? j.message) };
      if (type === "done" || j.done) return { done: true };
      if (j.sources) return { sources: j.sources };
      if (j.sql) return { sql: j.sql };
      if (j.code) return { code: j.code };
      if (type === "status" || type === "step" || j.status)
        return { status: String(j.status ?? j.message ?? j.text ?? "") };
      if (j.token || j.delta || j.chunk) return { token: String(j.token ?? j.delta ?? j.chunk) };
      if (j.answer || j.content) return { answer: String(j.answer ?? j.content) };
      if (j.message) return { status: String(j.message) };
      return {};
    } catch {
      return { token: trimmed };
    }
  }
  if (trimmed.endsWith("...") || trimmed.endsWith("…")) return { status: trimmed };
  return { token: raw };
}

function useRun() {
  const [run, setRun] = useState<RunState>(emptyRun());
  const abort = useRef<AbortController | null>(null);
  const lastAt = useRef(0);
  const startedAt = useRef(0);

  const stop = useCallback(() => {
    abort.current?.abort();
    setRun((r) => (r.status === "running" ? { ...r, status: "done" } : r));
  }, []);

  const pushStatus = useCallback((text: string) => {
    const now = performance.now();
    const ms = Math.round(now - lastAt.current);
    lastAt.current = now;
    const actor = actorFromStatus(text);

    setRun((r) => {
      const steps = [...r.steps];
      for (let i = steps.length - 1; i >= 0; i--) {
        const s = steps[i];
        if (s.kind === "call" && s.status === "running") {
          steps[i] = { ...s, status: "done", ms };
          break;
        }
      }
      const isThought = !actor || actor === "supervisor" || actor === "critic";
      if (!isThought) {
        steps.push({ kind: "call", id: uid(), from: "supervisor", to: actor, status: "running" });
      } else {
        steps.push({
          kind: "thought", id: uid(),
          actor: actor === "critic" ? "critic" : "supervisor",
          text: text.replace(/\.\.\.$|…$/, ""),
        });
      }
      return {
        ...r, steps,
        trace: [...r.trace, {
          id: uid(),
          at: Math.round(now - startedAt.current),
          label: actor ? `agent.${actor}` : "supervisor.step",
          detail: text,
        }],
      };
    });
  }, []);

  const ask = useCallback(async (question: string, enabled: Record<string, boolean>) => {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    startedAt.current = performance.now();
    lastAt.current = startedAt.current;

    setRun({ ...emptyRun(question), status: "running" });

    try {
      const res = await fetch(`${API_URL}/ask/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          enabled_agents: Object.keys(enabled).filter((k) => enabled[k]),
        }),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error(`Backend returned ${res.status}`);

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += dec.decode(value, { stream: true });

        const frames = buffer.split(/\n\n/);
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          const payload = frame
            .split("\n")
            .filter((l) => l.startsWith("data:"))
            .map((l) => l.slice(5).replace(/^ /, ""))
            .join("\n");
          if (!payload) continue;

          const ev = decode(payload);
          if (ev.error) throw new Error(ev.error);
          if (ev.status) pushStatus(ev.status);
          if (ev.token) setRun((r) => ({ ...r, answer: r.answer + ev.token }));
          if (ev.answer) setRun((r) => ({ ...r, answer: ev.answer! }));
          if (ev.sources)
            setRun((r) => ({
              ...r,
              sources: ev.sources!.map((s: any, i: number) => ({
                id: `s${i}`,
                title: s.title ?? s.heading ?? s.source ?? `Source ${i + 1}`,
                file: String(s.file ?? s.filename ?? s.source ?? "").toUpperCase(),
                excerpt: s.excerpt ?? s.text ?? s.content ?? s.page_content ?? "",
                relevance: s.relevance ?? s.score,
              })),
            }));
          if (ev.sql)
            setRun((r) => ({
              ...r,
              sql: [...r.sql, {
                id: uid(),
                sql: typeof ev.sql === "string" ? ev.sql : ev.sql.query ?? ev.sql.sql,
                columns: ev.sql?.columns,
                rows: ev.sql?.rows,
              }],
            }));
          if (ev.code)
            setRun((r) => ({
              ...r,
              code: [...r.code, {
                id: uid(),
                language: ev.code.language ?? "python",
                code: typeof ev.code === "string" ? ev.code : ev.code.code ?? ev.code.source,
                result: ev.code?.result ?? ev.code?.output,
              }],
            }));
        }
      }

      setRun((r) => ({
        ...r,
        status: "done",
        steps: r.steps.map((s) =>
          s.kind === "call" && s.status === "running" ? { ...s, status: "done" } : s
        ),
      }));
    } catch (e: any) {
      if (e?.name === "AbortError") return;
      setRun((r) => ({ ...r, status: "error", error: e?.message ?? "Request failed" }));
    }
  }, [pushStatus]);

  return { run, ask, stop };
}

/* ============ 6. QISMLAR ============ */

type TabId = "console" | "evaluation";

function TopBar({ tab, onTab, theme, onTheme }: {
  tab: TabId; onTab: (t: TabId) => void; theme: "light" | "dark"; onTheme: () => void;
}) {
  return (
    <header className="c-topbar">
      <div className="c-brand"><Mark />Multi-Agent AI Analyst</div>
      <nav className="c-tabs">
        <button className="c-tab" data-on={tab === "console"} onClick={() => onTab("console")}>CONSOLE</button>
        <button className="c-tab" data-on={tab === "evaluation"} onClick={() => onTab("evaluation")}>EVALUATION</button>
      </nav>
      <div className="c-topbar-right">
        <span className="c-badge">{LIVE ? "LIVE BACKEND" : "RECORDED RUN"}</span>
        <button className="c-iconbtn" aria-label="Search"><IconSearch /></button>
        <button className="c-iconbtn" onClick={onTheme}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}>
          {theme === "dark" ? <IconSun /> : <IconMoon />}
        </button>
      </div>
    </header>
  );
}

function Sidebar({ conversations, activeId, onSelect, onNew, enabled, onToggle }: {
  conversations: Conversation[]; activeId: string | null;
  onSelect: (id: string) => void; onNew: () => void;
  enabled: Record<string, boolean>; onToggle: (id: AgentId) => void;
}) {
  return (
    <aside className="c-sidebar">
      <button className="c-new" onClick={onNew}><IconPlus />New question</button>

      <section className="c-group">
        <h2 className="c-group-title">CONVERSATIONS</h2>
        {conversations.length === 0 ? (
          <p className="c-empty">Ask something to start the first one.</p>
        ) : (
          conversations.map((c) => (
            <button key={c.id} className="c-convo" data-on={c.id === activeId} onClick={() => onSelect(c.id)}>
              <IconChat /><span>{c.question}</span>
            </button>
          ))
        )}
      </section>

      <section className="c-group">
        <h2 className="c-group-title">DOCUMENTS</h2>
        {DOCUMENTS.map((d) => (
          <div className="c-doc" key={d.file} title={d.file}>
            <IconDoc />
            <span className="c-doc-name">{d.file}</span>
            <span className="c-doc-meta">
              {d.chunks ? <span>{d.chunks}</span> : null}
              <span className="c-doc-state" data-state={d.state}>{d.state.toUpperCase()}</span>
            </span>
          </div>
        ))}
      </section>

      <section className="c-group">
        <h2 className="c-group-title">DATABASE</h2>
        <div className="c-status"><IconDatabase />{LIVE ? "Connected, read-only" : "Not connected"}</div>
      </section>

      <section className="c-group">
        <h2 className="c-group-title">AGENTS</h2>
        <p className="c-hint">Turn a specialist off and the supervisor will route around it.</p>
        {TOGGLEABLE.map((id) => {
          const a = AGENTS[id];
          const on = enabled[id];
          return (
            <button key={id} className="c-agent" data-on={on} onClick={() => onToggle(id)} aria-pressed={on}>
              <span className="c-agent-head" style={{ color: a.color }}>
                {agentIcon[id]}{a.label}
                <span className="c-agent-state">{on ? "ON" : "OFF"}</span>
              </span>
              <span className="c-agent-blurb">{a.blurb}</span>
            </button>
          );
        })}
      </section>
    </aside>
  );
}

function formatMs(ms: number) {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}S` : `${ms}MS`;
}

function ExecutionRail({ run }: { run: RunState }) {
  const total = run.steps.length;
  const settled = run.steps.filter((s) => s.kind !== "call" || s.status !== "running").length;
  const pct2 = total === 0 ? 0 : Math.round((settled / total) * 100);

  return (
    <>
      <div className="c-railhead">
        <span className="c-eyebrow">EXECUTION RAIL</span>
        {total > 0 && (
          <div className="c-progress">
            <span className="c-eyebrow">STEP {settled} OF {total}</span>
            <div className="c-progress-track">
              <div className="c-progress-fill" style={{ width: `${pct2}%` }} />
            </div>
          </div>
        )}
      </div>

      <ol className="c-rail">
        {run.steps.map((s) => {
          if (s.kind === "branch") {
            return (
              <li className="c-step c-branch-step" key={s.id}>
                <span className="c-dot" style={{ background: "var(--text-faint)" }} />
                <span className="c-branch">{s.label}</span>
              </li>
            );
          }
          if (s.kind === "thought") {
            const a = AGENTS[s.actor];
            return (
              <li className="c-step" key={s.id}>
                <span className="c-dot" style={{ background: a.color }} />
                <span className="c-step-label" style={{ color: a.color }}>{a.label}</span>
                <p className="c-step-text">{s.text}</p>
              </li>
            );
          }
          const from = AGENTS[s.from];
          const to = AGENTS[s.to];
          return (
            <li className="c-step" key={s.id} data-running={s.status === "running"}>
              <span className="c-dot" style={{ background: to.color }} />
              <span className="c-step-label">
                <span style={{ color: from.color }}>{from.label}</span>
                <span className="c-arrow">&#8594;</span>
                <span style={{ color: to.color }}>{to.label}</span>
                <span className="c-step-meta">
                  {typeof s.ms === "number" && <span>{formatMs(s.ms)}</span>}
                  {typeof s.tokens === "number" && <span>{s.tokens.toLocaleString()} TOK</span>}
                  {s.status === "running" && <span>RUNNING</span>}
                </span>
              </span>
            </li>
          );
        })}
      </ol>

      {(run.answer || run.status === "running") && (
        <div className="c-answer">
          <span className="c-eyebrow">ANSWER</span>
          <div style={{ marginTop: 14 }}>
            {run.answer.split(/\n{2,}/).map((para, i, arr) => (
              <p key={i}>
                {para}
                {run.status === "running" && i === arr.length - 1 && <span className="c-caret" />}
              </p>
            ))}
          </div>
        </div>
      )}

      {run.status === "error" && (
        <div className="c-error">
          The run stopped: {run.error}. Check that the backend is reachable and try again.
        </div>
      )}
    </>
  );
}

type PanelId = "sources" | "sql" | "code" | "trace";

function SidePanel({ run }: { run: RunState }) {
  const [tab, setTab] = useState<PanelId>("sources");
  const tabs: { id: PanelId; label: string; count: number }[] = [
    { id: "sources", label: "SOURCES", count: run.sources.length },
    { id: "sql", label: "SQL", count: run.sql.length },
    { id: "code", label: "CODE", count: run.code.length },
    { id: "trace", label: "TRACE", count: run.trace.length },
  ];

  return (
    <aside className="c-panel">
      <div className="c-paneltabs">
        {tabs.map((t) => (
          <button key={t.id} className="c-paneltab" data-on={tab === t.id} onClick={() => setTab(t.id)}>
            {t.label}{t.count > 0 ? ` ${t.count}` : ""}
          </button>
        ))}
      </div>

      <div className="c-panelbody">
        {tab === "sources" && (run.sources.length === 0 ? (
          <p className="c-empty">No passages retrieved yet. Sources appear here as the retriever returns them.</p>
        ) : (
          run.sources.map((s) => (
            <article className="c-card" key={s.id} style={{ ["--accent" as any]: "var(--a-retriever)" }}>
              <h3 className="c-card-title">{s.title}</h3>
              <p className="c-card-file">{s.file}</p>
              <p className="c-card-text">{s.excerpt}</p>
              {typeof s.relevance === "number" && (
                <div className="c-relevance">
                  RELEVANCE
                  <span className="c-relevance-track">
                    <span className="c-relevance-fill" style={{ width: `${Math.round(s.relevance * 100)}%` }} />
                  </span>
                  {s.relevance.toFixed(2)}
                </div>
              )}
            </article>
          ))
        ))}

        {tab === "sql" && (run.sql.length === 0 ? (
          <p className="c-empty">No query was needed for this question.</p>
        ) : (
          run.sql.map((q) => (
            <article className="c-card" key={q.id} style={{ ["--accent" as any]: "var(--a-data)" }}>
              {q.question && <h3 className="c-card-title">{q.question}</h3>}
              <p className="c-card-file">READ-ONLY</p>
              <pre className="c-pre">{q.sql}</pre>
              {q.columns && q.rows && (
                <table className="c-table">
                  <thead><tr>{q.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody>
                    {q.rows.map((r, i) => (
                      <tr key={i}>
                        {r.map((cell, j) => (
                          <td key={j}>{typeof cell === "number" ? cell.toLocaleString() : cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </article>
          ))
        ))}

        {tab === "code" && (run.code.length === 0 ? (
          <p className="c-empty">No code ran for this question.</p>
        ) : (
          run.code.map((k) => (
            <article className="c-card" key={k.id} style={{ ["--accent" as any]: "var(--a-code)" }}>
              <p className="c-card-file">{k.language.toUpperCase()}</p>
              <pre className="c-pre">{k.code}</pre>
              {k.result !== undefined && <div className="c-result">&#8594; {k.result}</div>}
            </article>
          ))
        ))}

        {tab === "trace" && (run.trace.length === 0 ? (
          <p className="c-empty">Events land here as the graph runs. The full trace is also in Langfuse.</p>
        ) : (
          <ul className="c-trace">
            {run.trace.map((e) => (
              <li key={e.id}>
                <time>{(e.at / 1000).toFixed(2)}s</time>
                <b>{e.label}</b>
                <span>{e.detail}</span>
              </li>
            ))}
          </ul>
        ))}
      </div>
    </aside>
  );
}

const pct = (n: number) => `${Math.round(n * 100)}%`;

function EvaluationView() {
  const n = EVAL_ROWS.length || 1;
  const routing = EVAL_ROWS.filter((r) => r.routing).length / n;
  const correctness = EVAL_ROWS.reduce((a, r) => a + r.correctness, 0) / n;
  const faithfulness = EVAL_ROWS.reduce((a, r) => a + r.faithfulness, 0) / n;

  return (
    <main className="c-main">
      <h1 className="c-question">Evaluation</h1>
      <p className="c-notice-body" style={{ marginBottom: 24, maxWidth: "62ch" }}>
        An LLM judge scores every question in the eval set on three axes: did the supervisor pick the
        right specialist, is the answer correct, and is every claim traceable to a retrieved source.
      </p>

      <div className="c-scores">
        <div className="c-score"><div className="c-score-value">{pct(routing)}</div><div className="c-score-label">ROUTING ACCURACY</div></div>
        <div className="c-score"><div className="c-score-value">{pct(correctness)}</div><div className="c-score-label">CORRECTNESS</div></div>
        <div className="c-score"><div className="c-score-value">{pct(faithfulness)}</div><div className="c-score-label">FAITHFULNESS</div></div>
        <div className="c-score"><div className="c-score-value">{EVAL_ROWS.length}</div><div className="c-score-label">QUESTIONS</div></div>
      </div>

      <table className="c-evaltable">
        <thead>
          <tr><th style={{ width: "56%" }}>QUESTION</th><th>ROUTING</th><th>CORRECT</th><th>FAITHFUL</th></tr>
        </thead>
        <tbody>
          {EVAL_ROWS.map((r) => (
            <tr key={r.question}>
              <td>{r.question}</td>
              <td className="c-pass">{r.routing ? "PASS" : "FAIL"}</td>
              <td className="c-pass">{pct(r.correctness)}</td>
              <td className="c-pass">{pct(r.faithfulness)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}

/* ============ 7. SAHIFA ============ */

export default function ConsolePage() {
  const [tab, setTab] = useState<TabId>("console");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [question, setQuestion] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [enabled, setEnabled] = useState<Record<string, boolean>>(
    Object.fromEntries(TOGGLEABLE.map((a) => [a, true]))
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const { run, ask, stop } = useRun();

  useEffect(() => {
    const saved = (typeof window !== "undefined" && localStorage.getItem("maai-theme")) as
      | "light" | "dark" | null;
    if (saved) setTheme(saved);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("maai-theme", theme); } catch {}
  }, [theme]);

  useEffect(() => {
    if (!activeId) return;
    setConversations((cs) => cs.map((c) => (c.id === activeId ? { ...c, run } : c)));
  }, [run, activeId]);

  const activeRun = useMemo(() => {
    if (activeId) return conversations.find((c) => c.id === activeId)?.run ?? run;
    return LIVE ? emptyRun() : DEMO_RUN;
  }, [activeId, conversations, run]);

  function submit() {
    const q = question.trim();
    if (!q || !LIVE) return;
    const id = `c${Date.now()}`;
    setConversations((cs) => [{ id, question: q, run: emptyRun(q) }, ...cs]);
    setActiveId(id);
    setQuestion("");
    ask(q, enabled);
  }

  function newQuestion() {
    stop();
    setActiveId(null);
    setQuestion("");
    inputRef.current?.focus();
  }

  const busy = activeRun.status === "running";

  return (
    <div className="c-shell">
      <TopBar tab={tab} onTab={setTab} theme={theme}
        onTheme={() => setTheme(theme === "dark" ? "light" : "dark")} />

      <div className="c-body">
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={setActiveId}
          onNew={newQuestion}
          enabled={enabled}
          onToggle={(id) => setEnabled((e) => ({ ...e, [id]: !e[id] }))}
        />

        {tab === "evaluation" ? (
          <EvaluationView />
        ) : (
          <main className="c-main">
            {!LIVE && (
              <div className="c-notice">
                <span style={{ color: "var(--text-muted)", lineHeight: 0, paddingTop: 2 }}><IconInfo /></span>
                <div>
                  <p className="c-notice-title">No backend connected</p>
                  <p className="c-notice-body">
                    Showing a recorded run so you can see how the console behaves. Set{" "}
                    <code>NEXT_PUBLIC_API_URL</code> to connect a live one.
                  </p>
                </div>
              </div>
            )}

            <div className="c-ask">
              <input
                ref={inputRef}
                className="c-input"
                value={question}
                placeholder="Ask a question — the supervisor routes it to the right agents."
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                disabled={!LIVE}
              />
              <button className="c-send" onClick={busy ? stop : submit} disabled={!LIVE}>
                {busy ? "Stop" : "Ask"}
              </button>
            </div>

            {activeRun.question && <h1 className="c-question">{activeRun.question}</h1>}

            {activeRun.steps.length === 0 && !activeRun.question ? (
              <p className="c-empty">
                Ask anything about your indexed documents, the database, or the live web.
              </p>
            ) : (
              <ExecutionRail run={activeRun} />
            )}
          </main>
        )}

        <SidePanel run={activeRun} />
      </div>
    </div>
  );
}