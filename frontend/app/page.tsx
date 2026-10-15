"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import axios from "axios";
import { useRouter } from "next/navigation";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";

type Message = {
  role: "user" | "ai";
  content: string;
  audio?: string;
  id: string;
  thinking?: boolean;
  attachedFile?: { name: string; size: number; type: string; url?: string };
  // Set while the answer streams in: what the agent is doing right now.
  status?: string;
  streaming?: boolean;
  sources?: Source[];
  autoPlay?: boolean; // speak voice replies as soon as they arrive
};

// Browsers record different formats (Safari: mp4); the server converts any of them.
const VOICE_MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
const MIN_RECORDING_MS = 700;

function micErrorMessage(error: unknown): string {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined")
    return "This browser can't record audio. Try Chrome, Edge or Safari.";
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return "Microphone access is blocked. Click the lock icon in the address bar and allow the microphone. On a Mac, also allow your browser in System Settings → Privacy & Security → Microphone.";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "No microphone found. Connect one and try again.";
  if (name === "NotReadableError") return "Another app is using your microphone. Close it and try again.";
  return "Couldn't start recording. Check that this site may use your microphone (lock icon in the address bar), then try again.";
}

type Session = {
  id: string;
  title: string;
  created_at: string;
  project_id?: string | null;
};

type View = "chat" | "templates" | "projects" | "stats" | "help";
type ProjectRef = { id: string; name: string };

const VIEW_TITLES: Record<Exclude<View, "chat">, string> = {
  templates: "Templates",
  projects: "My Projects",
  stats: "Statistics",
  help: "Updates & FAQ",
};


import { API, getCurrentUser, logout, type AuthUser } from "@/lib/auth";
import { streamChat, UnauthorizedError, type Source } from "@/lib/chatStream";
import { workspaceApi } from "@/lib/workspace";
import { HelpView } from "./_components/HelpView";
import { ProjectsView } from "./_components/ProjectsView";
import { StatsView } from "./_components/StatsView";
import { TemplatesView } from "./_components/TemplatesView";
import { MCPPanel } from "./_components/MCPPanel";

// Every API call carries the httpOnly session cookie.
axios.defaults.withCredentials = true;

function generateId() {
  return Math.random().toString(36).slice(2, 10);
}

// ── Copy-to-clipboard button (used on code blocks) ─────────────
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[12px] font-medium
        text-slate-500 hover:text-slate-800 transition-colors duration-150"
    >
      {copied ? (
        <>
          <svg
            className="w-3.5 h-3.5 text-emerald-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          Copied
        </>
      ) : (
        <>
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
          Copy code
        </>
      )}
    </button>
  );
}

// ── Code block renderer with tab-style header + copy button ────
function CodeBlock({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  const codeText = String(children ?? "").replace(/\n$/, "");
  const language = /language-(\w+)/.exec(className || "")?.[1] || "text";
  const languageLabel = language.toUpperCase();

  return (
    <div className="my-3 rounded-2xl overflow-hidden border border-slate-200 bg-[#fbfbfc]">
      <div className="flex items-center justify-between px-3 py-2 bg-white border-b border-slate-200">
        <span className="text-[11px] font-semibold text-slate-500 px-2.5 py-1 rounded-lg bg-slate-100">
          {languageLabel}
        </span>
        <CopyButton text={codeText} />
      </div>
      <SyntaxHighlighter
        language={language}
        style={oneLight}
        showLineNumbers
        customStyle={{
          margin: 0,
          padding: "14px 16px",
          background: "transparent",
          fontSize: "12.5px",
          lineHeight: 1.65,
        }}
        lineNumberStyle={{
          color: "#cbd5e1",
          minWidth: "2em",
          paddingRight: "1em",
          userSelect: "none",
        }}
        codeTagProps={{ style: { fontFamily: "'Geist Mono', monospace" } }}
      >
        {codeText}
      </SyntaxHighlighter>
    </div>
  );
}

// ── Share button (Web Share API with clipboard fallback) ───────
function ShareButton({ getShareText }: { getShareText: () => string }) {
  const [status, setStatus] = useState<"idle" | "copied">("idle");

  const handleShare = async () => {
    const text = getShareText();
    if (!text.trim()) return;

    if (typeof navigator !== "undefined" && (navigator as any).share) {
      try {
        await (navigator as any).share({
          title: "AI Chat Helper conversation",
          text,
        });
        return;
      } catch {
        // cancelled or unsupported — fall through to clipboard
      }
    }

    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setStatus("copied");
    setTimeout(() => setStatus("idle"), 1800);
  };

  return (
    <button
      onClick={handleShare}
      title="Share conversation"
      className="w-9 h-9 flex items-center justify-center rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors duration-150"
    >
      {status === "copied" ? (
        <svg
          className="w-4 h-4 text-emerald-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 13l4 4L19 7"
          />
        </svg>
      ) : (
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
          />
        </svg>
      )}
    </button>
  );
}

// ── Animated thinking bubble ───────────────────────────────────
function ThinkingBubble() {
  return (
    <div className="flex items-start gap-3">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-orange-400 to-rose-500 flex items-center justify-center shadow-sm">
        <span className="text-xs font-bold text-white">A</span>
      </div>
      <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm px-5 py-3.5 shadow-sm">
        <div className="flex items-center gap-1.5">
          <span className="text-[10.5px] text-slate-400 font-medium tracking-[0.18em] uppercase mr-2">
            Thinking
          </span>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-orange-400"
              style={{
                animation: `dot-pulse 1.4s ease-in-out ${i * 0.2}s infinite`,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Recording waveform ─────────────────────────────────────────
function RecordingIndicator() {
  return (
    <div className="flex items-center gap-1 px-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <span
          key={i}
          className="w-[3px] bg-gradient-to-b from-rose-400 to-rose-500 rounded-full"
          style={{
            height: `${10 + (i % 3) * 6}px`,
            animation: `wave 0.7s ease-in-out ${i * 0.1}s infinite alternate`,
          }}
        />
      ))}
    </div>
  );
}

// ── Left nav item ────────────────────────────────────────────
function NavItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-[13px] font-medium transition-colors duration-150
        ${active ? "bg-white text-slate-900 shadow-sm border border-slate-200" : "text-slate-500 hover:text-slate-800 hover:bg-white/60"}`}
    >
      <span className="flex items-center gap-2.5">
        {icon}
        {label}
      </span>
    </button>
  );
}

// ── History panel item ──────────────────────────────────────
function HistoryItem({
  session,
  active,
  onClick,
  onRename,
  onDelete,
}: {
  session: Session;
  active: boolean;
  onClick: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(session.title);

  if (editing) {
    const finish = (save: boolean) => {
      setEditing(false);
      const title = draft.trim();
      if (save && title && title !== session.title) onRename(title);
    };
    return (
      <input
        autoFocus
        value={draft}
        maxLength={120}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => finish(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter") finish(true);
          if (e.key === "Escape") finish(false);
        }}
        aria-label="Chat title"
        className="w-full rounded-xl border border-orange-300 bg-white px-3 py-2.5 text-[12.5px] font-semibold text-slate-700 outline-none ring-4 ring-orange-500/10"
      />
    );
  }

  return (
    <div className="group relative">
      <button
        onClick={onClick}
        className={`w-full flex items-start gap-2.5 text-left px-3 py-2.5 pr-14 rounded-xl transition-colors duration-150
          ${active ? "bg-orange-50 border border-orange-200" : "hover:bg-slate-50 border border-transparent"}`}
      >
        <span
          className={`mt-0.5 w-3.5 h-3.5 rounded-[5px] border flex-shrink-0 ${
            active ? "bg-orange-400 border-orange-400" : "border-slate-300"
          }`}
        />
        <span className="min-w-0">
          <p className="text-[12.5px] font-semibold text-slate-700 truncate">
            {session.title || "New conversation"}
          </p>
          <p className="text-[11px] text-slate-400 truncate mt-0.5">
            {session.project_id && <span className="text-orange-600">Project · </span>}
            {new Date(session.created_at).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })}
          </p>
        </span>
      </button>
      <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 gap-0.5 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
        <button
          onClick={() => {
            setDraft(session.title);
            setEditing(true);
          }}
          aria-label={`Rename ${session.title || "chat"}`}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-white hover:text-slate-700"
        >
          <svg aria-hidden className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15.2 5.2l3.6 3.6M4 20l4.2-1 10.6-10.6a2.5 2.5 0 00-3.6-3.6L4.6 15.4 4 20z" />
          </svg>
        </button>
        <button
          onClick={onDelete}
          aria-label={`Delete ${session.title || "chat"}`}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-white hover:text-rose-600"
        >
          <svg aria-hidden className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 7l-.9 12.1A2 2 0 0116.1 21H7.9a2 2 0 01-2-1.9L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>
    </div>
  );
}

// ── File attachment preview in chat ────────────────────────────
function FileAttachmentBubble({
  attachedFile,
}: {
  attachedFile: Message["attachedFile"];
}) {
  if (!attachedFile) return null;

  const isImage = attachedFile.type.startsWith("image/");
  const isPDF = attachedFile.type === "application/pdf";
  const sizeKB = (attachedFile.size / 1024).toFixed(0);

  const handleOpen = () => {
    if (attachedFile.url) window.open(attachedFile.url, "_blank");
  };

  if (isImage && attachedFile.url) {
    return (
      <div className="flex justify-end mb-1">
        <div
          className="max-w-[72%] rounded-2xl rounded-tr-sm overflow-hidden cursor-pointer border border-slate-200 hover:border-orange-300 transition-all duration-300 group relative shadow-sm"
          onClick={handleOpen}
        >
          <img
            src={attachedFile.url}
            alt={attachedFile.name}
            className="w-full max-h-64 object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
          <p className="text-white/90 text-[11px] px-3 py-1.5 bg-black/45 truncate backdrop-blur-sm">
            {attachedFile.name}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-end mb-1">
      <button
        onClick={handleOpen}
        className="flex items-center gap-3 bg-orange-50 hover:bg-orange-100 border border-orange-200 px-4 py-3 rounded-2xl rounded-tr-sm transition-all duration-200 group max-w-[72%]"
      >
        <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-orange-100 group-hover:bg-orange-200 transition flex items-center justify-center">
          {isPDF ? (
            <svg
              className="w-5 h-5 text-orange-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          ) : (
            <svg
              className="w-5 h-5 text-orange-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
              />
            </svg>
          )}
        </div>
        <div className="flex-1 min-w-0 text-left">
          <p className="text-slate-700 text-[13px] font-medium truncate">
            {attachedFile.name}
          </p>
          <p className="text-slate-400 text-[11px] mt-0.5 flex items-center gap-1">
            <span>
              {isPDF ? "PDF" : attachedFile.type.split("/")[1]?.toUpperCase()}
            </span>
            <span>·</span>
            <span>{sizeKB} KB</span>
          </p>
        </div>
      </button>
    </div>
  );
}

// ── Message action bar (thumbs up/down, copy, regenerate) ──────
function MessageActions({
  content,
  onRegenerate,
}: {
  content: string;
  onRegenerate?: () => void;
}) {
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  return (
    <div className="flex items-center gap-1 mt-2 ml-1">
      <button
        onClick={() => setFeedback(feedback === "up" ? null : "up")}
        className={`w-7 h-7 flex items-center justify-center rounded-lg transition-colors ${
          feedback === "up"
            ? "text-emerald-500 bg-emerald-50"
            : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"
        }`}
      >
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2"
          />
        </svg>
      </button>
      <button
        onClick={() => setFeedback(feedback === "down" ? null : "down")}
        className={`w-7 h-7 flex items-center justify-center rounded-lg transition-colors ${
          feedback === "down"
            ? "text-rose-500 bg-rose-50"
            : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"
        }`}
      >
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.737 3h4.017c.163 0 .326.02.485.06L17 4m-7 10v5a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2"
          />
        </svg>
      </button>
      <button
        onClick={handleCopy}
        className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        title="Copy response"
      >
        {copied ? (
          <svg
            className="w-3.5 h-3.5 text-emerald-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        ) : (
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.8}
              d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
        )}
      </button>
      {onRegenerate && (
        <button
          onClick={onRegenerate}
          className="flex items-center gap-1.5 ml-2 px-2.5 py-1 rounded-lg text-[12px] font-medium text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.8}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          Regenerate response
        </button>
      )}
    </div>
  );
}

// ── Live agent status (shown until the first answer token) ─────
function AgentStatus({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2.5 py-0.5" role="status" aria-live="polite">
      <span className="relative flex h-4 w-4 items-center justify-center">
        <span className="absolute h-4 w-4 animate-ping rounded-full bg-orange-300/50" />
        <span className="h-2 w-2 rounded-full bg-gradient-to-br from-orange-400 to-rose-500" />
      </span>
      <span key={label} className="aroma-shimmer msg-animate text-[13px] font-medium">
        {label}
      </span>
    </div>
  );
}

// Turn "[2]" (or "【2】", which some models emit) into a markdown link
// that ReactMarkdown renders as a citation badge.
function linkCitations(content: string, sources?: Source[]): string {
  if (!sources?.length) return content;
  const ids = new Set(sources.map((s) => s.id));
  return content.replace(/[[【](\d{1,2})[\]】](?![(:])/g, (match, n) => (ids.has(Number(n)) ? `[${n}](#cite-${n})` : match));
}

function SourceList({
  sources,
  active,
  onSelect,
}: {
  sources: Source[];
  active: number | null;
  onSelect: (id: number | null) => void;
}) {
  const activeSource = sources.find((s) => s.id === active && s.type === "document");
  return (
    <div className="mt-2.5 ml-1">
      <p className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-slate-400">Sources</p>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((source) => {
          const isActive = source.id === active;
          const chipClass = `group inline-flex max-w-[260px] items-center gap-1.5 rounded-lg border px-2 py-1 text-[12px] transition-colors ${
            isActive ? "border-orange-300 bg-orange-50 text-orange-800" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
          }`;
          const number = (
            <span className={`flex h-4 min-w-4 items-center justify-center rounded px-1 text-[10px] font-semibold ${isActive ? "bg-orange-500 text-white" : "bg-slate-100 text-slate-500"}`}>
              {source.id}
            </span>
          );
          if (source.type === "web" && source.url) {
            let domain = source.url;
            try {
              domain = new URL(source.url).hostname.replace(/^www\./, "");
            } catch {}
            return (
              <a key={source.id} href={source.url} target="_blank" rel="noopener noreferrer" className={chipClass} title={source.url}>
                {number}
                <svg aria-hidden className="h-3.5 w-3.5 shrink-0 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="9" strokeWidth={1.8} />
                  <path strokeWidth={1.8} d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z" />
                </svg>
                <span className="truncate">{source.title !== domain ? source.title : domain}</span>
                {source.title !== domain && <span className="shrink-0 text-slate-400">{domain}</span>}
              </a>
            );
          }
          return (
            <button key={source.id} type="button" onClick={() => onSelect(isActive ? null : source.id)} className={chipClass} aria-expanded={isActive}>
              {number}
              <svg aria-hidden className="h-3.5 w-3.5 shrink-0 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5zM14 3v5h5" />
              </svg>
              <span className="truncate">{source.title}</span>
              {source.page && <span className="shrink-0 text-slate-400">p.{source.page}</span>}
            </button>
          );
        })}
      </div>
      {activeSource?.snippet && (
        <blockquote className="msg-animate mt-2 rounded-xl border border-orange-200 bg-orange-50/60 px-3.5 py-2.5 text-[12.5px] leading-relaxed text-slate-600">
          <span className="mb-1 block text-[11px] font-semibold text-orange-700">
            [{activeSource.id}] {activeSource.title}
            {activeSource.page ? ` · page ${activeSource.page}` : ""}
          </span>
          {activeSource.snippet}
          {activeSource.snippet.length >= 280 ? "…" : ""}
        </blockquote>
      )}
    </div>
  );
}

// ── Chat message ───────────────────────────────────────────────
function ChatMessage({
  msg,
  isLastAi,
  onRegenerate,
}: {
  msg: Message;
  isLastAi?: boolean;
  onRegenerate?: () => void;
}) {
  const isUser = msg.role === "user";
  const [activeSource, setActiveSource] = useState<number | null>(null);

  if (isUser) {
    return (
      <div>
        {msg.attachedFile && (
          <FileAttachmentBubble attachedFile={msg.attachedFile} />
        )}
        {msg.content && (
          <div className="flex justify-end">
            <div className="max-w-[72%] bg-slate-900 text-white px-4 py-3 rounded-2xl rounded-tr-sm text-sm leading-relaxed">
              {msg.content}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-orange-400 to-rose-500 flex items-center justify-center shadow-sm mt-0.5">
        <span className="text-xs font-bold text-white">A</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm px-5 py-4 shadow-sm">
          {msg.streaming && !msg.content ? (
            <AgentStatus label={msg.status ?? "Thinking…"} />
          ) : (
          <div
            className={`prose prose-sm max-w-none leading-relaxed ${msg.streaming ? "aroma-streaming" : ""}
              prose-p:text-slate-700 prose-p:leading-relaxed
              prose-headings:text-slate-900 prose-headings:font-semibold
              prose-code:bg-orange-50 prose-code:text-orange-600 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:before:content-[''] prose-code:after:content-['']
              prose-a:text-orange-600 prose-a:no-underline hover:prose-a:underline
              prose-strong:text-slate-900 prose-li:text-slate-700
              prose-ul:space-y-1 prose-ol:space-y-1
              prose-blockquote:border-l-orange-400 prose-blockquote:text-slate-500`}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }: any) {
                  const isBlock =
                    /language-(\w+)/.test(className || "") ||
                    String(children).includes("\n");
                  if (isBlock)
                    return (
                      <CodeBlock className={className}>{children}</CodeBlock>
                    );
                  return (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
                pre({ children }: any) {
                  return <>{children}</>;
                },
                a({ href, children }: { href?: string; children?: React.ReactNode }) {
                  const cite = typeof href === "string" && href.startsWith("#cite-") ? Number(href.slice(6)) : null;
                  if (cite !== null) {
                    const source = msg.sources?.find((s) => s.id === cite);
                    return (
                      <button
                        type="button"
                        onClick={() => setActiveSource((current) => (current === cite ? null : cite))}
                        title={source ? `${source.title}${source.page ? ` · page ${source.page}` : ""}` : undefined}
                        className={`not-prose mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-md px-1 align-middle text-[10.5px] font-semibold transition-colors ${
                          activeSource === cite ? "bg-orange-500 text-white" : "bg-orange-100 text-orange-700 hover:bg-orange-200"
                        }`}
                      >
                        {children}
                      </button>
                    );
                  }
                  return (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  );
                },
              }}
            >
              {linkCitations(msg.content, msg.sources)}
            </ReactMarkdown>
          </div>
          )}
        </div>
        {!!msg.sources?.length && (
          <SourceList sources={msg.sources} active={activeSource} onSelect={setActiveSource} />
        )}
        {msg.audio && (
          <div className="mt-2 ml-1">
            <audio controls autoPlay={msg.autoPlay} className="h-8 w-full max-w-xs rounded-full">
              <source src={`${API}${msg.audio}`} />
            </audio>
          </div>
        )}
        {!msg.streaming && (
          <MessageActions
            content={msg.content}
            onRegenerate={isLastAi ? onRegenerate : undefined}
          />
        )}
      </div>
    </div>
  );
}

// ── File preview chip (input area) ────────────────────────────
function FileChip({ file, onRemove }: { file: File; onRemove: () => void }) {
  const isImage = file.type.startsWith("image/");
  const isPDF = file.type === "application/pdf";
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => {
    if (isImage) {
      const url = URL.createObjectURL(file);
      setPreview(url);
      return () => URL.revokeObjectURL(url);
    }
  }, [file, isImage]);

  return (
    <div className="flex items-center gap-2 bg-white border border-slate-200 px-2.5 py-1.5 rounded-xl max-w-[220px] group shadow-sm">
      {isImage && preview ? (
        <img
          src={preview}
          alt=""
          className="w-7 h-7 rounded-lg object-cover flex-shrink-0"
        />
      ) : (
        <div
          className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${isPDF ? "bg-rose-50" : "bg-orange-50"}`}
        >
          {isPDF ? (
            <svg
              className="w-3.5 h-3.5 text-rose-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          ) : (
            <svg
              className="w-3.5 h-3.5 text-orange-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
              />
            </svg>
          )}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-[11px] text-slate-600 truncate leading-tight">
          {file.name}
        </p>
        <p className="text-[10px] text-slate-400">
          {(file.size / 1024).toFixed(0)} KB
        </p>
      </div>
      <button
        onClick={onRemove}
        className="ml-1 text-slate-300 hover:text-slate-600 transition flex-shrink-0 opacity-0 group-hover:opacity-100"
      >
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </div>
  );
}

// ── Drag overlay ───────────────────────────────────────────────
function DragOverlay() {
  return (
    <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-white/92 backdrop-blur-md border-2 border-dashed border-orange-300 pointer-events-none">
      <div className="w-16 h-16 rounded-2xl bg-orange-50 border border-orange-200 flex items-center justify-center mb-4 animate-[float_2.4s_ease-in-out_infinite]">
        <svg
          className="w-8 h-8 text-orange-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
      </div>
      <p className="text-slate-800 font-semibold text-base tracking-tight">
        Drop your file here
      </p>
      <p className="text-slate-400 text-sm mt-1">PDF or image</p>
    </div>
  );
}

// ── Empty state ────────────────────────────────────────────────
function EmptyState({ onSuggestion }: { onSuggestion: (s: string) => void }) {
  const suggestions = [
    { icon: "📄", text: "Summarize a document for me" },
    { icon: "💡", text: "Help me brainstorm ideas" },
    { icon: "🔍", text: "Explain a complex topic simply" },
    { icon: "💻", text: "Write and review my code" },
  ];

  return (
    <div className="relative flex flex-col items-center justify-center h-full px-6 text-center select-none">
      <div className="relative w-14 h-14 rounded-2xl bg-gradient-to-br from-orange-400 to-rose-500 flex items-center justify-center shadow-md mb-5">
        <span className="text-xl font-black text-white">A</span>
      </div>
      <h2 className="text-[22px] font-semibold text-slate-800 mb-2 tracking-tight">
        How can I help you today?
      </h2>
      <p className="text-slate-400 text-[13px] mb-8 max-w-xs leading-relaxed">
        Ask anything, upload a PDF or image, or speak your question.
      </p>
      <div className="grid grid-cols-2 gap-2.5 w-full max-w-sm">
        {suggestions.map((s) => (
          <button
            key={s.text}
            onClick={() => onSuggestion(s.text)}
            className="bg-white border border-slate-200 hover:border-orange-300
              text-slate-500 hover:text-slate-800 text-[12px] text-left px-3.5 py-3 rounded-xl
              transition-colors duration-150 leading-snug flex items-start gap-2.5 shadow-sm"
          >
            <span className="text-base leading-none mt-0.5">{s.icon}</span>
            <span>{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}



// ── Main component ─────────────────────────────────────────────
function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

function SplashScreen({ error, onRetry }: { error?: boolean; onRetry?: () => void }) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-5 bg-white font-sans">
      <div className={`flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-orange-400 to-rose-500 shadow-md shadow-rose-500/20 ${error ? "" : "animate-pulse"}`}>
        <span className="text-lg font-black text-white">A</span>
      </div>
      {error ? (
        <div className="text-center">
          <p className="text-[14px] font-medium text-slate-800">Can&apos;t reach the server</p>
          <p className="mt-1 text-[13px] text-slate-500">Make sure the backend is running, then try again.</p>
          <button onClick={onRetry} className="mt-4 rounded-xl bg-slate-900 px-4 py-2 text-[13px] font-medium text-white hover:bg-slate-800">
            Try again
          </button>
        </div>
      ) : (
        <span className="sr-only">Loading</span>
      )}
    </div>
  );
}

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getCurrentUser()
      .then((current) => {
        if (cancelled) return;
        if (current) setUser(current);
        else router.replace("/login");
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [router, attempt]);

  // If the session expires mid-use, any API call returns 401: send the user back to sign in.
  useEffect(() => {
    const id = axios.interceptors.response.use(undefined, (error) => {
      if (axios.isAxiosError(error) && error.response?.status === 401) router.replace("/login");
      return Promise.reject(error);
    });
    return () => axios.interceptors.response.eject(id);
  }, [router]);

  const handleLogout = useCallback(async () => {
    try {
      await logout();
    } finally {
      router.replace("/login");
    }
  }, [router]);

  if (failed)
    return (
      <SplashScreen
        error
        onRetry={() => {
          setFailed(false);
          setAttempt((n) => n + 1);
        }}
      />
    );
  if (!user) return <SplashScreen />;
  return <ChatApp user={user} onLogout={handleLogout} />;
}

function ChatApp({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [file, setFile] = useState<File | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const recordingStartedAt = useRef(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [mcpOpen, setMcpOpen] = useState(false);
  const [view, setView] = useState<View>("chat");
  // The project the current chat belongs to (its documents are searched too).
  const [chatProject, setChatProject] = useState<ProjectRef | null>(null);
  const dragCounter = useRef(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunks = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const mainAreaRef = useRef<HTMLDivElement | null>(null);

  const objectURLsRef = useRef<string[]>([]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const refreshSessions = useCallback(async () => {
    try {
      const res = await axios.get<Session[]>(`${API}/sessions`);
      if (Array.isArray(res.data)) {
        const sorted = res.data.sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        );
        setSessions(sorted);
      }
    } catch {
      // The history panel just stays as it was.
    }
  }, []);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    return () => {
      objectURLsRef.current.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0)
      setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    dragCounter.current = 0;

    const dropped = e.dataTransfer.files[0];
    if (!dropped) return;

    const allowed = [
      "application/pdf",
      "image/png",
      "image/jpeg",
      "image/gif",
      "image/webp",
    ];
    if (allowed.includes(dropped.type)) {
      setFile(dropped);
      inputRef.current?.focus();
    } else {
      alert("Only PDF and image files are supported.");
    }
  }, []);

  const loadSession = async (id: string, project?: ProjectRef) => {
    const res = await axios.get(`${API}/messages/${id}`);
    setMessages(
      res.data.map((m: any) => ({
        role: m.role,
        content: m.content,
        sources: m.sources,
        id: generateId(),
      })),
    );
    setSessionId(id);
    setSidebarOpen(false);
    setView("chat");
    const projectId = sessions.find((s) => s.id === id)?.project_id;
    if (project) setChatProject(project);
    else if (projectId) {
      setChatProject({ id: projectId, name: "Project" });
      workspaceApi.getProject(projectId).then((p) => setChatProject({ id: p.id, name: p.name })).catch(() => {});
    } else setChatProject(null);
  };

  const newChat = (project: ProjectRef | null = null) => {
    setChatProject(project);
    setView("chat");
    objectURLsRef.current.forEach((url) => URL.revokeObjectURL(url));
    objectURLsRef.current = [];
    setSessionId(crypto.randomUUID());
    setMessages([]);
    setFile(null);
    setSidebarOpen(false);
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  const startRecording = async () => {
    setVoiceError("");
    let stream: MediaStream;
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") throw new Error("unsupported");
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      setVoiceError(micErrorMessage(error));
      return;
    }
    streamRef.current = stream;
    const mimeType = VOICE_MIME_TYPES.find((t) => MediaRecorder.isTypeSupported?.(t));
    const mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    mediaRecorderRef.current = mediaRecorder;
    audioChunks.current = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size) audioChunks.current.push(e.data);
    };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      if (Date.now() - recordingStartedAt.current < MIN_RECORDING_MS) {
        setVoiceError("That was too short. Hold on a moment longer while you speak.");
        return;
      }
      void sendVoice(mediaRecorder.mimeType || "audio/webm");
    };
    mediaRecorder.onerror = () => {
      setRecording(false);
      stream.getTracks().forEach((t) => t.stop());
      setVoiceError("Recording stopped unexpectedly. Please try again.");
    };

    recordingStartedAt.current = Date.now();
    mediaRecorder.start();
    setRecording(true);

    setTimeout(() => {
      if (mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        setRecording(false);
      }
    }, 10000);
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  };

  const sendVoice = async (mimeType: string) => {
    const blob = new Blob(audioChunks.current, { type: mimeType });
    const extension = mimeType.includes("mp4") ? "mp4" : mimeType.includes("ogg") ? "ogg" : "webm";
    const formData = new FormData();
    formData.append("file", new File([blob], `voice.${extension}`, { type: mimeType }));
    // Voice joins the open chat (and its project) like a typed message.
    formData.append("session_id", sessionId);
    if (chatProject) formData.append("project_id", chatProject.id);

    const aiId = generateId();
    setMessages((prev) => [...prev, { role: "ai", content: "", id: aiId, streaming: true, status: "Transcribing your question…" }]);
    setLoading(true);

    try {
      const res = await axios.post(`${API}/voice`, formData);
      setMessages((prev) =>
        prev.flatMap((m) =>
          m.id === aiId
            ? [
                { role: "user" as const, content: `🎤 ${res.data.user_text}`, id: generateId() },
                { role: "ai" as const, content: res.data.response, audio: res.data.audio_url ?? undefined, autoPlay: true, id: aiId },
              ]
            : [m],
        ),
      );
    } catch (error) {
      setMessages((prev) => prev.filter((m) => m.id !== aiId));
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
      setVoiceError(typeof detail === "string" ? detail : "Voice processing failed. Please try again.");
    } finally {
      setLoading(false);
      void refreshSessions();
    }
  };

  const sendMessage = useCallback(
    async (overrideInput?: string) => {
      const text = overrideInput ?? input;
      if (!text.trim() && !file) return;

      const currentFile = file;

      let fileObjectURL: string | undefined;
      if (currentFile) {
        fileObjectURL = URL.createObjectURL(currentFile);
        objectURLsRef.current.push(fileObjectURL);
      }

      const newMessages: Message[] = [];

      if (currentFile || text.trim()) {
        newMessages.push({
          role: "user",
          content: text.trim(),
          id: generateId(),
          attachedFile: currentFile
            ? {
                name: currentFile.name,
                size: currentFile.size,
                type: currentFile.type,
                url: fileObjectURL,
              }
            : undefined,
        });
      }

      // The AI reply appears immediately and fills in as the stream arrives.
      const aiId = generateId();
      newMessages.push({
        role: "ai",
        content: "",
        id: aiId,
        streaming: true,
        status: currentFile ? `Uploading ${currentFile.name}…` : "Thinking…",
      });
      const updateAi = (change: (m: Message) => Message) =>
        setMessages((prev) => prev.map((m) => (m.id === aiId ? change(m) : m)));

      setMessages((prev) => [...prev, ...newMessages]);
      setInput("");
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setLoading(true);

      try {
        if (currentFile) {
          const fd = new FormData();
          fd.append("file", currentFile);
          fd.append("session_id", sessionId);
          await axios.post(`${API}/upload`, fd);
        }

        await streamChat({
          message: text || "Summarize document",
          session_id: sessionId,
          // Only read by the server when this message starts the chat.
          ...(chatProject ? { project_id: chatProject.id } : {}),
        }, (event) => {
          switch (event.type) {
            case "status":
              updateAi((m) => ({ ...m, status: event.label }));
              break;
            case "sources":
              updateAi((m) => ({ ...m, sources: [...(m.sources ?? []), ...event.sources] }));
              break;
            case "token":
              updateAi((m) => ({ ...m, content: m.content + event.text }));
              break;
            case "reset":
              updateAi((m) => ({ ...m, content: "" }));
              break;
            case "done":
              updateAi((m) => ({ ...m, content: event.response, sources: event.sources, streaming: false, status: undefined }));
              break;
            case "error":
              updateAi((m) => ({ ...m, content: event.message, streaming: false, status: undefined }));
              break;
          }
        });
      } catch (error) {
        if (error instanceof UnauthorizedError) {
          window.location.assign("/login");
          return;
        }
        updateAi((m) => ({ ...m, content: "⚠️ Something went wrong. Please try again.", streaming: false, status: undefined }));
      } finally {
        // If the connection dropped mid-answer, keep what arrived and stop the spinner.
        updateAi((m) => (m.streaming ? { ...m, streaming: false, status: undefined } : m));
        setLoading(false);
        void refreshSessions(); // new chats and their titles show up in History
      }
    },
    [input, file, sessionId, chatProject, refreshSessions],
  );

  const regenerateLast = useCallback(() => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    setMessages((prev) => {
      const idx = prev.map((m) => m.role).lastIndexOf("ai");
      return idx >= 0 ? prev.slice(0, idx) : prev;
    });
    sendMessage(lastUser.content);
  }, [messages, sendMessage]);

  const renameChat = async (id: string, title: string) => {
    try {
      await workspaceApi.renameChat(id, title);
    } finally {
      void refreshSessions();
    }
  };

  const deleteChat = async (id: string) => {
    if (!window.confirm("Delete this chat? Its messages and attached files will be removed.")) return;
    try {
      await workspaceApi.deleteChat(id);
      if (id === sessionId) newChat();
    } finally {
      void refreshSessions();
    }
  };

  const clearHistory = async () => {
    if (!window.confirm("Delete all chats outside your projects? This can't be undone.")) return;
    try {
      await workspaceApi.clearChats();
      newChat();
    } finally {
      void refreshSessions();
    }
  };

  const useTemplate = (prompt: string) => {
    setView("chat");
    setInput(prompt);
    window.setTimeout(() => inputRef.current?.focus(), 0);
  };

  const openView = (next: View) => {
    setView(next);
    setSidebarOpen(false);
  };

  const filteredSessions = sessions.filter((s) =>
    (s.title || "").toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const lastAiId = [...messages].reverse().find((m) => m.role === "ai")?.id;

  const buildShareText = () => {
    if (messages.length === 0) return "";
    return messages
      .map(
        (m) => `${m.role === "user" ? "You" : "AI Chat Helper"}: ${m.content}`,
      )
      .join("\n\n");
  };

  return (
    <>
      {mcpOpen && <MCPPanel onClose={() => setMcpOpen(false)} />}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500&display=swap');
        * { font-family: 'Geist', system-ui, sans-serif; }
        code, pre { font-family: 'Geist Mono', monospace; }

        @keyframes dot-pulse {
          0%, 100% { opacity: 0.25; transform: scale(0.75); }
          50% { opacity: 1; transform: scale(1); }
        }
        @keyframes wave {
          0% { transform: scaleY(0.4); }
          100% { transform: scaleY(1.6); }
        }
        @keyframes msg-in {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
        .msg-animate { animation: msg-in 0.22s ease forwards; }
        .sidebar-fade { animation: fade-in 0.18s ease forwards; }

        @media (prefers-reduced-motion: reduce) {
          *, *::before, *::after {
            animation-duration: 0.001ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.001ms !important;
          }
        }

        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(148,163,184,0.35); border-radius: 99px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(148,163,184,0.55); }

        :focus-visible {
          outline: 2px solid rgba(251,146,60,0.5);
          outline-offset: 2px;
          border-radius: 6px;
        }
        /* The chat input bar already shows focus via its own border color change
           (.focus-within:border-orange-300 on the wrapper). Suppress the browser's
           native focus ring on the text field itself so it doesn't double up. */
        .chat-input-field:focus,
        .chat-input-field:focus-visible {
          outline: none;
        }
        .search-field:focus,
        .search-field:focus-visible {
          outline: none;
        }

        /* Search input: a single, clean focus/hover state — no extra glow/scale layering */
        .search-input {
          transition: background-color 150ms ease, border-color 150ms ease;
        }
        .search-input:hover {
          background-color: #ffffff;
        }
        .search-input:focus-within {
          background-color: #ffffff;
          border-color: #fdba74;
        }
      `}</style>

      <div
        className="relative flex h-screen bg-[#f6f6f8] text-slate-800 overflow-hidden"
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        {isDragging && <DragOverlay />}

        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/30 z-30 lg:hidden sidebar-fade"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* ── Left nav ── */}
        <aside
          className={`fixed lg:static inset-y-0 left-0 z-40 w-[230px] bg-[#f1f1f4] border-r border-slate-200
            flex flex-col transition-transform duration-300 ease-in-out
            ${sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}
        >
          <div className="flex items-center gap-2.5 px-4 pt-5 pb-4">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-orange-400 to-rose-500 flex items-center justify-center shadow-sm">
              <span className="text-[13px] font-black text-white">A</span>
            </div>
            <span className="font-semibold text-slate-800 text-[15px] tracking-tight">
              Aroma AI
            </span>
          </div>

          <nav className="flex-1 overflow-y-auto px-3 space-y-1">
            <NavItem
              active={view === "chat"}
              onClick={() => openView("chat")}
              label="AI Chat Helper"
              icon={
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.8}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
              }
            />
            <NavItem
              active={view === "templates"}
              onClick={() => openView("templates")}
              label="Templates"
              icon={
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.8}
                    d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2"
                  />
                </svg>
              }
            />
            <NavItem
              active={view === "projects"}
              onClick={() => openView("projects")}
              label="My Projects"
              icon={
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.8}
                    d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
                  />
                </svg>
              }
            />
            <NavItem
              active={view === "stats"}
              onClick={() => openView("stats")}
              label="Statistics"
              icon={
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.8}
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                  />
                </svg>
              }
            />
            <NavItem
              label="MCP Servers"
              onClick={() => setMcpOpen(true)}
              icon={
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.8}
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.8}
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
              }
            />
            <NavItem
              active={view === "help"}
              onClick={() => openView("help")}
              label="Updates & FAQ"
              icon={
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.8}
                    d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              }
            />
          </nav>

          <div className="px-3 py-3 border-t border-slate-200">
            <div className="flex items-center gap-2.5 rounded-xl px-1.5 py-1">
              <div className="w-8 h-8 shrink-0 rounded-full bg-gradient-to-br from-orange-400 to-rose-500 flex items-center justify-center shadow-sm">
                <span className="text-[11px] font-bold text-white">{initials(user.name)}</span>
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[12.5px] font-semibold text-slate-800 truncate">{user.name}</p>
                <p className="text-[11.5px] text-slate-400 truncate">{user.email}</p>
              </div>
            <button
              onClick={onLogout}
              title="Log out"
              aria-label="Log out"
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/70 transition-colors"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.8}
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
            </button>
            </div>
          </div>
        </aside>

        {/* ── Main area ── */}
        <div
          ref={mainAreaRef}
          className="relative z-10 flex-1 flex flex-col min-w-0"
        >
          {/* Header */}
          <header className="flex items-center justify-between gap-3 px-5 py-3.5 border-b border-slate-200 bg-white flex-shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <button
                className="lg:hidden p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
                onClick={() => setSidebarOpen(true)}
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                </svg>
              </button>
              <h1 className="text-[15px] font-semibold text-slate-800 truncate">
                {view === "chat"
                  ? sessions.find((s) => s.id === sessionId)?.title || "AI Chat Helper"
                  : VIEW_TITLES[view]}
              </h1>
              {view === "chat" && chatProject && (
                <button
                  onClick={() => openView("projects")}
                  title="This chat also searches the project's documents"
                  className="hidden sm:inline-flex shrink-0 items-center gap-1 rounded-lg border border-orange-200 bg-orange-50 px-2 py-0.5 text-[11.5px] font-medium text-orange-700 hover:bg-orange-100"
                >
                  <svg aria-hidden className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
                  </svg>
                  {chatProject.name}
                </button>
              )}
            </div>

            <div className="flex items-center gap-2.5 flex-1 max-w-md">
              {/* Search — single clean hover/focus state defined in .search-input, no layered effects */}
              <div className={`search-input relative flex-1 hidden ${view === "chat" ? "sm:flex" : ""} items-center bg-slate-100 border border-transparent rounded-xl px-3 py-2`}>
                <svg
                  className="w-3.5 h-3.5 text-slate-400 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0"
                  />
                </svg>
                <input
                  type="text"
                  placeholder="Search…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="search-field w-full bg-transparent outline-none text-[12.5px] text-slate-700 placeholder:text-slate-400 ml-2"
                />
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => fileInputRef.current?.click()}
                title="Upload file"
                className="w-9 h-9 flex items-center justify-center rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors duration-150"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
              </button>
              <ShareButton getShareText={buildShareText} />
              <button className="w-9 h-9 flex items-center justify-center rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors duration-150">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.8}
                    d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                  />
                </svg>
              </button>
              <button
                onClick={() => newChat(view === "chat" ? chatProject : null)}
                className="hidden md:flex items-center gap-1.5 ml-1 px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-[12.5px] font-medium transition-colors duration-150"
              >
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2.5}
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                New
              </button>
            </div>
          </header>

          {view === "templates" ? (
            <TemplatesView onUse={useTemplate} />
          ) : view === "projects" ? (
            <ProjectsView
              onOpenChat={(id, project) => void loadSession(id, project)}
              onNewChat={(project) => newChat(project)}
            />
          ) : view === "stats" ? (
            <StatsView />
          ) : view === "help" ? (
            <HelpView />
          ) : (
          <div className="flex-1 flex min-h-0">
            {/* Messages column */}
            <div className="flex-1 flex flex-col min-w-0">
              <div className="flex-1 overflow-y-auto">
                {messages.length === 0 && !loading ? (
                  <EmptyState onSuggestion={(s) => sendMessage(s)} />
                ) : (
                  <div className="max-w-[680px] mx-auto px-4 py-6 space-y-5">
                    {messages.map((msg) => (
                      <div key={msg.id} className="msg-animate">
                        <ChatMessage
                          msg={msg}
                          isLastAi={msg.id === lastAiId}
                          onRegenerate={regenerateLast}
                        />
                      </div>
                    ))}
                    {loading && !messages.some((m) => m.streaming) && <ThinkingBubble />}
                    <div ref={bottomRef} />
                  </div>
                )}
              </div>

              {/* ── Input area ── */}
              <div className="px-4 pb-4 pt-2.5 bg-white border-t border-slate-200 flex-shrink-0">
                <div className="max-w-[680px] mx-auto">
                  {voiceError && (
                    <div role="alert" className="msg-animate mb-2 flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-[12.5px] leading-relaxed text-rose-700">
                      <svg aria-hidden className="mt-px h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 3l18 18M9 9v2a3 3 0 005.1 2.1M15 9.3V5a3 3 0 00-5.7-1.3M19 11a7 7 0 01-1.2 3.9M5 11a7 7 0 0011.6 5.3M12 18v3" />
                      </svg>
                      <span className="flex-1">{voiceError}</span>
                      <button onClick={() => setVoiceError("")} aria-label="Dismiss" className="-m-1 rounded-lg p-1 text-rose-400 hover:bg-rose-100 hover:text-rose-700">
                        <svg aria-hidden className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeWidth={2.2} d="M6 6l12 12M18 6L6 18" /></svg>
                      </button>
                    </div>
                  )}
                  {file && (
                    <div className="mb-2">
                      <FileChip
                        file={file}
                        onRemove={() => {
                          setFile(null);
                          if (fileInputRef.current)
                            fileInputRef.current.value = "";
                        }}
                      />
                    </div>
                  )}

                  <div
                    className={`flex items-center gap-1.5 bg-slate-50 border rounded-2xl px-2.5 py-2
                      transition-colors duration-150
                      ${
                        recording
                          ? "border-rose-300"
                          : isDragging
                            ? "border-orange-300"
                            : "border-slate-200 focus-within:border-orange-300"
                      }`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="application/pdf,image/*"
                      className="hidden"
                      onChange={(e) => setFile(e.target.files?.[0] || null)}
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      title="Attach file"
                      className="flex-shrink-0 p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors"
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                        />
                      </svg>
                    </button>

                    <div className="flex-1 min-w-0">
                      {recording ? (
                        <div className="flex items-center h-9">
                          <RecordingIndicator />
                          <span className="text-[12px] text-rose-500 ml-1">
                            Recording…
                          </span>
                        </div>
                      ) : (
                        <input
                          ref={inputRef}
                          className="chat-input-field w-full bg-transparent outline-none text-[13.5px] text-slate-800
                            placeholder:text-slate-400 py-1.5 leading-relaxed"
                          value={input}
                          onChange={(e) => setInput(e.target.value)}
                          placeholder="Start typing"
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                              e.preventDefault();
                              sendMessage();
                            }
                          }}
                          disabled={loading}
                        />
                      )}
                    </div>

                    <button
                      onClick={recording ? stopRecording : startRecording}
                      title={recording ? "Stop recording" : "Voice input"}
                      className={`flex-shrink-0 p-1.5 rounded-lg transition-colors duration-150
                        ${recording ? "text-rose-500 bg-rose-50" : "text-slate-400 hover:text-slate-700 hover:bg-slate-200/60"}`}
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                        />
                      </svg>
                    </button>

                    <button
                      onClick={() => sendMessage()}
                      disabled={loading || (!input.trim() && !file)}
                      className={`flex-shrink-0 p-2 rounded-xl transition-colors duration-150
                        ${
                          (!input.trim() && !file) || loading
                            ? "bg-slate-200 text-slate-400 cursor-not-allowed"
                            : "bg-gradient-to-br from-orange-400 to-rose-500 text-white"
                        }`}
                    >
                      {loading ? (
                        <svg
                          className="w-4 h-4 animate-spin"
                          fill="none"
                          viewBox="0 0 24 24"
                        >
                          <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                          />
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                          />
                        </svg>
                      ) : (
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 10l7-7m0 0l7 7m-7-7v18"
                          />
                        </svg>
                      )}
                    </button>
                  </div>

                  <p className="text-center text-[10px] text-slate-400 mt-2">
                    Aroma AI can make mistakes. Verify important information.
                  </p>
                </div>
              </div>
            </div>

            {/* ── History panel ── */}
            <aside className="hidden xl:flex w-[270px] border-l border-slate-200 bg-white flex-col flex-shrink-0">
              <div className="flex items-center justify-between px-4 pt-4 pb-3">
                <h3 className="text-[13px] font-semibold text-slate-800">
                  History
                </h3>
                <span className="text-[11px] text-slate-400">
                  {filteredSessions.length}/50
                </span>
              </div>
              <div className="flex-1 overflow-y-auto px-3 space-y-1">
                {filteredSessions.map((s) => (
                  <HistoryItem
                    key={s.id}
                    session={s}
                    active={s.id === sessionId}
                    onClick={() => loadSession(s.id)}
                    onRename={(title) => void renameChat(s.id, title)}
                    onDelete={() => void deleteChat(s.id)}
                  />
                ))}
                {filteredSessions.length === 0 && (
                  <div className="text-center py-10 text-slate-400 text-[12px]">
                    {searchQuery
                      ? "No matching conversations"
                      : "No conversations yet"}
                  </div>
                )}
              </div>
              <div className="p-3 border-t border-slate-200">
                <button
                  onClick={() => void clearHistory()}
                  className="w-full flex items-center justify-center gap-1.5 text-[12.5px] font-medium text-slate-500 hover:text-rose-600 px-3 py-2 rounded-xl hover:bg-slate-100 transition-colors"
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.8}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                  Clear history
                </button>
              </div>
            </aside>
          </div>
          )}
        </div>
      </div>
    </>
  );
}
