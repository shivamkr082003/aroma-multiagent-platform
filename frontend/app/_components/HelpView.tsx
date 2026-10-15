import { ViewShell } from "./ViewShell";

const UPDATES = [
  { tag: "New", title: "Projects", body: "Group documents into a project; every chat inside it answers from all of them." },
  { tag: "New", title: "Templates & statistics", body: "Start from ready-made prompts or save your own, and see your activity at a glance." },
  { tag: "Improved", title: "Smarter document search", body: "Hybrid keyword + semantic search with reranking finds the right passage far more often, especially names and numbers." },
  { tag: "New", title: "Live answers with sources", body: "Answers stream in as they're written, show what Aroma is doing, and cite the exact passage they used." },
  { tag: "New", title: "Accounts", body: "Sign in to keep your chats, documents and tools private to you." },
  { tag: "New", title: "MCP tools", body: "Connect your own MCP servers so Aroma can use their tools during a chat." },
];

const FAQ = [
  { q: "Which files can I upload?", a: "PDF, DOCX and TXT. Attach a file in the chat to use it in that chat only, or add it to a project to use it in every chat of that project." },
  { q: "How do I know an answer came from my document?", a: "Answers that use your documents show numbered badges like [1] and a Sources list. Click a badge or a source to see the exact passage and page." },
  { q: "Why did Aroma search the web?", a: "When a question needs recent or outside information, Aroma searches the web and lists those pages as sources. Links found inside your documents may also be opened." },
  { q: "Who can see my chats and documents?", a: "Only you. Every chat, document, project and MCP server is tied to your account, and the server checks ownership on every request." },
  { q: "What are MCP servers?", a: "MCP (Model Context Protocol) servers give Aroma extra tools, such as creating a GitHub issue. Add one under MCP Servers; Aroma will use its tools when a question needs them." },
  { q: "Can I use voice?", a: "Yes. Press the microphone in the chat box, speak your question, and Aroma replies with text and audio." },
  { q: "Does deleting a chat remove its documents?", a: "Yes. Deleting a chat removes its messages and any files attached in it. Documents in a project stay until you remove them from the project." },
];

export function HelpView() {
  return (
    <ViewShell title="Updates & FAQ" subtitle="What's new in Aroma, and answers to common questions.">
      <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
        <section>
          <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">What&apos;s new</h3>
          <ol className="relative space-y-4 border-l border-slate-200 pl-5">
            {UPDATES.map((u) => (
              <li key={u.title} className="relative">
                <span className="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-gradient-to-br from-orange-400 to-rose-500" />
                <div className="flex items-center gap-2">
                  <p className="text-[13.5px] font-semibold text-slate-800">{u.title}</p>
                  <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${u.tag === "New" ? "bg-orange-50 text-orange-700" : "bg-slate-100 text-slate-600"}`}>
                    {u.tag}
                  </span>
                </div>
                <p className="mt-0.5 text-[12.5px] leading-relaxed text-slate-500">{u.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section>
          <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Frequently asked</h3>
          <div className="space-y-2">
            {FAQ.map((f) => (
              <details key={f.q} className="group rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm open:shadow-md">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-[13.5px] font-medium text-slate-800">
                  {f.q}
                  <span aria-hidden className="text-slate-400 transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-2 text-[12.5px] leading-relaxed text-slate-500">{f.a}</p>
              </details>
            ))}
          </div>
        </section>
      </div>
    </ViewShell>
  );
}
