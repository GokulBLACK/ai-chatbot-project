import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

type Msg = { role: "user" | "assistant"; content: string };

export default function App() {
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      role: "assistant",
      content:
        "I'm here to explain judicial bail decisions while enforcing strict legal boundaries. Please provide the case details or bail order for analysis.",
    },
  ]);
  const [loading, setLoading] = useState(false);

  // "lex" = Legal Literacy Mode, "normal" = Normal Chat Mode
  const [mode, setMode] = useState<"lex" | "normal">("lex");
  const [activeJson, setActiveJson] = useState<string>("No JSON uploaded");

  const fileRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  const canSend = useMemo(() => input.trim().length > 0 && !loading, [input, loading]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs, loading]);

  async function uploadFiles(files: FileList) {
    if (!files || files.length === 0) return;

    const fd = new FormData();
    for (const f of Array.from(files)) fd.append("files", f);

    setLoading(true);
    try {
      // Your backend main.py adds prefix="/api"
      // and routes.py should define @router.post("/lexexplain/upload")
      const res = await fetch("/api/lexexplain/upload", { method: "POST", body: fd });
      const data = await res.json();
      if (data.ok) setActiveJson(`Uploaded: ${data.uploaded?.length ?? 0} files`);
      else setActiveJson("Upload failed");
    } catch {
      setActiveJson("Upload failed");
    } finally {
      setLoading(false);
    }
  }

  async function sendWithMode(msg: string, forcedMode?: "lex" | "normal") {
    const msgText = msg.trim();
    if (!msgText || loading) return;

    setInput("");
    setMsgs((p) => [...p, { role: "user", content: msgText }]);
    setLoading(true);

    try {
      const useMode = forcedMode ?? mode;

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: conversationId,
          message: msgText,
          mode: useMode,
        }),
      });

      const data = await res.json();
      setConversationId(data.conversation_id);
      setMsgs((p) => [...p, { role: "assistant", content: data.assistant }]);
    } finally {
      setLoading(false);
    }
  }

  async function send(text?: string) {
    // Normal send uses the currently selected mode
    await sendWithMode(text ?? input);
  }

  return (
    <div className="shell">
      {/* LEFT SIDEBAR */}
      <aside className="sidebar">
        <div className="sbTitle">
          <div className="sbLogo">⚖</div>
          <div>
            <div className="sbName">Bail Decision Bot</div>
            <div className="sbMode">
              <span>Mode</span>
              <select
                className="sbSelect"
                value={mode}
                onChange={(e) => setMode(e.target.value as "lex" | "normal")}
                disabled={loading}
                title="Mode"
              >
                <option value="lex">Legal Literacy Mode</option>
                <option value="normal">Normal Chat Mode</option>
              </select>
            </div>
          </div>
        </div>

        <div className="sbNav">
          <button className="sbItem sbItemActive">Bail Decision Bot</button>
          <button className="sbItem">Case Overview</button>
          <button className="sbItem">Legal Doctrines</button>
          <button className="sbItem">Settings</button>
        </div>

        <div className="sbNotice">
          <div className="sbNoticeHead">
            <span className="infoDot">i</span>
            <span>Legal Notice</span>
          </div>
          <div className="sbNoticeText">
            Clarify bail decisions based on statutes.
            <br />
            No legal advice provided.
          </div>
        </div>
      </aside>

      {/* MAIN */}
      <main className="main">
        {/* TOP BANNER */}
        <div className="banner">
          <div className="bannerIcon">⚖</div>
          <div className="bannerText">
            <div className="bannerTitle">Bail Decision Justification & Legal Boundary Compliance Bot</div>
            <div className="bannerSub">
              Explains bail decisions without giving advice or predicting outcomes.
            </div>
          </div>
          <div className="bannerInfo" title="Info">
            i
          </div>
        </div>

        {/* CHAT CARD */}
        <section className="chatCard">
          <div className="chatScroll" ref={listRef}>
            {msgs.map((m, i) => (
              <div key={i} className={`msgRow ${m.role === "user" ? "right" : "left"}`}>
                {m.role === "assistant" && <div className="avatar">🤖</div>}

                <div className={`bubble ${m.role}`}>
                  {m.role === "assistant" ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                  ) : (
                    <div className="plain">{m.content}</div>
                  )}
                  <div className="time">
                    {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </div>
                </div>
              </div>
            ))}

            {loading && <div className="typing">Working…</div>}
          </div>

          {/* COMPOSER */}
          <div className="composer">
            <div className="inputWrap">
              <input
                className="input"
                value={input}
                placeholder="Ask about a bail decision..."
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => (e.key === "Enter" ? send() : null)}
              />

              <button
                className="iconBtn"
                title="Upload JSON files"
                onClick={() => fileRef.current?.click()}
                disabled={loading}
              >
                📎
              </button>

              <button className="sendBtn" disabled={!canSend} onClick={() => send()}>
                Send ➤
              </button>
            </div>

            {/* IMPORTANT: chips force lex mode so they always produce LexExplain outputs */}
            <div className="chips">
              <button
                className="chip"
                onClick={() => sendWithMode("Explain bail order in structured reasoning flow", "lex")}
              >
                Explain Bail Order
              </button>

              <button
                className="chip"
                onClick={() => sendWithMode("Give statute details used in this bail decision", "lex")}
              >
                Statute Details
              </button>

              <button
                className="chip"
                onClick={() => sendWithMode("Explain risk factors and how conditions mitigate them", "lex")}
              >
                Risk Factors
              </button>

              <span className="chipMeta">{activeJson}</span>
            </div>

            <div className="alert">
              <div className="alertIcon">🛡</div>
              <div>
                <div className="alertTitle">Boundary Alert</div>
                <div className="alertText">
                  This bot does not provide legal advice, predict outcomes, or determine guilt or innocence.
                  <span className="alertLink"> What this means</span>
                </div>
              </div>
            </div>
          </div>

          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            multiple
            style={{ display: "none" }}
            onChange={(e) => {
              if (e.target.files) uploadFiles(e.target.files);
              e.currentTarget.value = "";
            }}
          />
        </section>
      </main>
    </div>
  );
}
