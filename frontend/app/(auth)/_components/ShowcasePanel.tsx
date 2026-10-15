"use client";

import { useEffect, useState, type ReactNode } from "react";

const SCENE_MS = 6500;

type Scene = {
  tab: string;
  attachment?: string;
  question: string;
  tool: { icon: ReactNode; label: string };
  answer: ReactNode;
};

const SCENES: Scene[] = [
  {
    tab: "Documents",
    attachment: "resume.pdf",
    question: "Which of my projects uses Redis?",
    tool: { icon: <DocIcon />, label: "Read resume.pdf · 5 passages" },
    answer: (
      <>
        <strong className="font-semibold text-white">Aroma AI</strong> uses Redis to cache chat history, so repeat
        questions skip the round-trip to the database.
      </>
    ),
  },
  {
    tab: "Web",
    question: "What changed with middleware in Next.js 16?",
    tool: { icon: <GlobeIcon />, label: "Searched the web · 4 sources" },
    answer: (
      <>
        Middleware is now called <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[12px] text-orange-200">proxy</code>.
        Rename the file and the exported function — the matcher config works the same.
      </>
    ),
  },
  {
    tab: "Tools",
    question: "Open an issue for the Safari login bug",
    tool: { icon: <PlugIcon />, label: "github · create_issue" },
    answer: (
      <>
        Done — opened <strong className="font-semibold text-white">#42 “Login fails on Safari”</strong> in
        aroma-ai and labelled it <span className="text-orange-200">bug</span>.
      </>
    ),
  },
];

const FEATURES = [
  { icon: <DocIcon />, label: "Chat with your files" },
  { icon: <MicIcon />, label: "Voice in & out" },
  { icon: <GlobeIcon />, label: "Live web search" },
  { icon: <PlugIcon />, label: "Your MCP tools" },
];

export function ShowcasePanel() {
  const [scene, setScene] = useState(0);
  // 0 = question, 1 = thinking, 2 = tool used, 3 = answer
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const timers = [
      window.setTimeout(() => setStage(1), 500),
      window.setTimeout(() => setStage(2), 1300),
      window.setTimeout(() => setStage(3), 2100),
      window.setTimeout(() => {
        setStage(0);
        setScene((s) => (s + 1) % SCENES.length);
      }, SCENE_MS),
    ];
    return () => timers.forEach(window.clearTimeout);
  }, [scene]);

  const current = SCENES[scene];

  return (
    <aside className="relative hidden overflow-hidden bg-[#0b0b12] lg:flex lg:flex-col">
      {/* Aurora */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="aroma-drift absolute -left-40 -top-40 h-[560px] w-[560px] rounded-full bg-orange-500/30 blur-[130px]" />
        <div className="aroma-drift-slow absolute -bottom-48 -right-32 h-[520px] w-[520px] rounded-full bg-rose-500/25 blur-[130px]" />
        <div className="absolute left-1/3 top-1/2 h-[260px] w-[260px] rounded-full bg-amber-300/10 blur-[100px]" />
        <div
          className="absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              "linear-gradient(to right, white 1px, transparent 1px), linear-gradient(to bottom, white 1px, transparent 1px)",
            backgroundSize: "44px 44px",
            maskImage: "radial-gradient(ellipse 70% 60% at 50% 45%, black, transparent)",
            WebkitMaskImage: "radial-gradient(ellipse 70% 60% at 50% 45%, black, transparent)",
          }}
        />
      </div>

      <div className="relative z-10 flex flex-1 flex-col px-12 py-10 xl:px-16">
        <Brand dark />

        <div className="my-auto max-w-[520px] py-12">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[12px] font-medium text-white/70 backdrop-blur">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
            Documents · Voice · Web · MCP
          </p>
          <h2 className="text-[38px] font-semibold leading-[1.1] tracking-[-0.02em] text-white xl:text-[44px]">
            One assistant for your{" "}
            <span className="bg-gradient-to-r from-orange-300 via-orange-400 to-rose-400 bg-clip-text text-transparent">
              files, voice and the web.
            </span>
          </h2>
          <p className="mt-4 max-w-[440px] text-[15px] leading-relaxed text-white/55">
            Ask questions about your PDFs, talk hands-free, and plug in your own tools — all in one conversation.
          </p>

          {/* Live chat preview */}
          <div className="mt-10 rounded-2xl border border-white/10 bg-white/[0.04] p-1.5 shadow-[0_30px_80px_-20px_rgba(0,0,0,0.6)] backdrop-blur-xl">
            <div className="flex items-center gap-1 rounded-xl bg-white/[0.03] p-1">
              {SCENES.map((s, i) => (
                <button
                  key={s.tab}
                  type="button"
                  aria-pressed={i === scene}
                  onClick={() => {
                    // Re-selecting the current tab would reset the stage without restarting the timers.
                    if (i === scene) return;
                    setStage(0);
                    setScene(i);
                  }}
                  className={`relative flex-1 overflow-hidden rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors ${
                    i === scene ? "bg-white/[0.08] text-white" : "text-white/45 hover:text-white/75"
                  }`}
                >
                  {s.tab}
                  {i === scene && (
                    <span
                      key={scene}
                      aria-hidden
                      className="aroma-progress absolute inset-x-0 bottom-0 h-px origin-left bg-gradient-to-r from-orange-400 to-rose-400"
                      style={{ animationDuration: `${SCENE_MS}ms` }}
                    />
                  )}
                </button>
              ))}
            </div>

            <div key={scene} className="h-[228px] space-y-3 px-3.5 pb-4 pt-4" aria-live="polite">
              <div className="aroma-rise flex flex-col items-end gap-1.5">
                {current.attachment && (
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.05] px-2 py-1 text-[11.5px] text-white/70">
                    <span className="flex h-4 w-4 items-center justify-center rounded bg-rose-500/80 text-[8px] font-bold text-white">PDF</span>
                    {current.attachment}
                  </span>
                )}
                <p className="max-w-[85%] rounded-2xl rounded-br-md bg-gradient-to-br from-orange-400 to-rose-500 px-3.5 py-2 text-[13.5px] text-white shadow-lg shadow-rose-500/20">
                  {current.question}
                </p>
              </div>

              {stage >= 1 && (
                <div className="flex gap-2.5">
                  <AromaAvatar />
                  <div className="min-w-0 flex-1 space-y-2">
                    {stage === 1 && <TypingDots />}
                    {stage >= 2 && (
                      <span className="aroma-rise inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-[11.5px] text-white/60">
                        <span className="text-orange-300">{current.tool.icon}</span>
                        {current.tool.label}
                        <CheckIcon />
                      </span>
                    )}
                    {stage >= 3 && <p className="aroma-rise text-[13.5px] leading-relaxed text-white/80">{current.answer}</p>}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <ul className="grid max-w-[520px] grid-cols-2 gap-x-6 gap-y-3 text-[13px] text-white/55">
          {FEATURES.map((f) => (
            <li key={f.label} className="flex items-center gap-2 whitespace-nowrap">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-orange-300">
                {f.icon}
              </span>
              {f.label}
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

export function Brand({ dark = false }: { dark?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-orange-400 to-rose-500 shadow-sm shadow-rose-500/30">
        <span className="text-[13px] font-black text-white">A</span>
      </div>
      <span className={`text-[15px] font-semibold tracking-tight ${dark ? "text-white" : "text-slate-800"}`}>Aroma AI</span>
    </div>
  );
}

function AromaAvatar() {
  return (
    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-orange-400 to-rose-500">
      <span className="text-[10px] font-bold text-white">A</span>
    </div>
  );
}

function TypingDots() {
  return (
    <span className="inline-flex h-6 items-center gap-1" aria-label="Aroma is thinking">
      {[0, 150, 300].map((delay) => (
        <span key={delay} className="aroma-dot h-1.5 w-1.5 rounded-full bg-white/50" style={{ animationDelay: `${delay}ms` }} />
      ))}
    </span>
  );
}

function CheckIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5 text-emerald-400">
      <path d="m3.5 8.5 3 3 6-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function DocIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5">
      <path d="M9 1.75H4.5a1 1 0 0 0-1 1v10.5a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V5.25L9 1.75Z M9 1.75v3.5h3.5 M5.75 8.5h4.5 M5.75 11h3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GlobeIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5">
      <circle cx="8" cy="8" r="6.25" stroke="currentColor" strokeWidth="1.3" />
      <path d="M1.75 8h12.5M8 1.75c1.7 1.8 2.5 3.9 2.5 6.25S9.7 12.45 8 14.25C6.3 12.45 5.5 10.35 5.5 8S6.3 3.55 8 1.75Z" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  );
}

function PlugIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5">
      <path d="M6 1.75v3M10 1.75v3M4 4.75h8v2.5a4 4 0 0 1-8 0v-2.5ZM8 11.25v3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5">
      <rect x="5.75" y="1.75" width="4.5" height="8" rx="2.25" stroke="currentColor" strokeWidth="1.3" />
      <path d="M3.25 7.5a4.75 4.75 0 0 0 9.5 0M8 12.25v2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}
