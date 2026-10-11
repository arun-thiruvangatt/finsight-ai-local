import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../api";

type Msg = { role: "user" | "ai"; text: string; meta?: any; error?: boolean };
const SUGGESTIONS = [
  "How much did I spend on food last month?", "Why did my spending increase this month?",
  "What are my largest recurring expenses?", "Am I on track with my monthly budget?",
  "Show me unusual transactions.", "How much can I safely allocate toward my goal?",
];

export default function Assistant() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [conv, setConv] = useState<number | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    setMsgs((m) => [...m, { role: "user", text }]); setQ(""); setBusy(true);
    try {
      const r = await api("/ai/ask", { method: "POST", body: { question: text, conversation_id: conv } });
      setConv(r.conversation_id);
      setMsgs((m) => [...m, { role: "ai", text: r.answer, meta: r }]);
    } catch (e: any) { setMsgs((m) => [...m, { role: "ai", text: e.message, error: true }]); }
    finally { setBusy(false); }
  };
  const submit = (e: FormEvent) => { e.preventDefault(); send(q); };

  return (
    <div className="page chat">
      <h1>FinSight AI</h1>
      <div className="messages">
        {!msgs.length && (<div className="suggest">
          <p className="muted">Ask about your finances. Every number comes from your data via backend tools.</p>
          {SUGGESTIONS.map((s) => <button key={s} className="ghost" onClick={() => send(s)}>{s}</button>)}
        </div>)}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role} ${m.error ? "err" : ""}`}>
            <small className="muted">{m.role === "user" ? "You" : "AI"}</small>
            <div className="text">{m.text}</div>
            {m.meta && (<>
              {m.meta.unverified_numbers?.length > 0 && <p className="warn-text">⚠ Not found in your data: {m.meta.unverified_numbers.join(", ")}</p>}
              <details><summary>Supporting data · tools: {m.meta.tools_used.join(", ") || "none"} · {m.meta.source === "llm" ? "AI-composed" : "rule-based"}</summary>
                <pre>{JSON.stringify(m.meta.data, null, 2)}</pre><small className="muted">{m.meta.disclaimer}</small></details>
            </>)}
          </div>
        ))}
        {busy && <div className="msg ai"><small className="muted">AI</small><div className="text muted">Thinking…</div></div>}
        <div ref={end} />
      </div>
      <form className="composer" onSubmit={submit}>
        <input placeholder="Ask about your finances…" value={q} onChange={(e) => setQ(e.target.value)} maxLength={1000} />
        <button disabled={busy}>Send</button>
      </form>
    </div>
  );
}
