"use client";

import { useState } from "react";

type StepEvent = { type: "step"; node: string; plan?: string };
type FinalEvent = { type: "final"; answer: string | null; steps: string[] };

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const NODE_LABELS: Record<string, string> = {
  supervisor: "🧭 Supervisor deciding next step...",
  retriever: "📄 Retriever searching documents...",
  web: "🌐 Web agent searching...",
  data: "🗄️ Data agent querying database...",
  code: "🧮 Code agent computing...",
  generate: "✍️ Generating answer...",
  critic: "🔍 Critic verifying answer...",
};

export default function Home() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [liveSteps, setLiveSteps] = useState<string[]>([]);
  const [answer, setAnswer] = useState<string | null>(null);
  const [finalSteps, setFinalSteps] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk() {
    if (!question.trim() || loading) return;

    setLoading(true);
    setLiveSteps([]);
    setAnswer(null);
    setFinalSteps([]);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/ask/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, use_memory: true }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`Server error: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const event: StepEvent | FinalEvent = JSON.parse(line.slice(6));

          if (event.type === "step") {
            const label = NODE_LABELS[event.node] || `Running ${event.node}...`;
            setLiveSteps((prev) => [...prev, label]);
          } else if (event.type === "final") {
            setAnswer(event.answer);
            setFinalSteps(event.steps);
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col items-center px-4 py-12">
      <div className="w-full max-w-2xl space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Multi-Agent AI Analyst</h1>
          <p className="text-neutral-400 text-sm mt-1">
            Ask a question — the supervisor routes it to the right agent(s).
          </p>
        </div>

        <div className="flex gap-2">
          <input
            className="flex-1 rounded-lg bg-neutral-900 border border-neutral-800 px-4 py-3 text-sm outline-none focus:border-neutral-600"
            placeholder="e.g. How many customers churned in Q3, and why?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
            disabled={loading}
          />
          <button
            onClick={handleAsk}
            disabled={loading || !question.trim()}
            className="rounded-lg bg-white text-black px-5 py-3 text-sm font-medium disabled:opacity-40"
          >
            {loading ? "..." : "Ask"}
          </button>
        </div>

        {error && (
          <div className="rounded-lg bg-red-950 border border-red-900 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {liveSteps.length > 0 && (
          <div className="rounded-lg bg-neutral-900 border border-neutral-800 px-4 py-3 space-y-1.5">
            {liveSteps.map((step, i) => (
              <div
                key={i}
                className={`text-sm ${
                  i === liveSteps.length - 1 && loading
                    ? "text-neutral-100"
                    : "text-neutral-500"
                }`}
              >
                {step}
              </div>
            ))}
          </div>
        )}

        {answer && (
          <div className="rounded-lg bg-neutral-900 border border-neutral-800 px-5 py-4 space-y-3">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{answer}</p>
            {finalSteps.length > 0 && (
              <p className="text-xs text-neutral-500 pt-2 border-t border-neutral-800">
                Trace: {finalSteps.join(" → ")}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}