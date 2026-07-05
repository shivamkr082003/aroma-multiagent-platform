"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import axios from "axios";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";

type Message = {
  role: "user" | "ai";
  content: string;
  audio?: string;
  id: string;
  thinking?: boolean;
  attachedFile?: { name: string; size: number; type: string; url?: string };
};

type Session = {
  id: string;
  title: string;
  created_at: string;
};

const API = "http://127.0.0.1:8000";

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
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
}) {
  return (
    <button
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
}: {
  session: Session;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-start gap-2.5 text-left px-3 py-2.5 rounded-xl transition-colors duration-150
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
          {new Date(session.created_at).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
          })}
        </p>
      </span>
    </button>
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
          <div
            className="prose prose-sm max-w-none leading-relaxed
              prose-p:text-slate-700 prose-p:leading-relaxed
              prose-headings:text-slate-900 prose-headings:font-semibold
              prose-code:bg-orange-50 prose-code:text-orange-600 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:before:content-[''] prose-code:after:content-['']
              prose-a:text-orange-600 prose-a:no-underline hover:prose-a:underline
              prose-strong:text-slate-900 prose-li:text-slate-700
              prose-ul:space-y-1 prose-ol:space-y-1
              prose-blockquote:border-l-orange-400 prose-blockquote:text-slate-500"
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
              }}
            >
              {msg.content}
            </ReactMarkdown>
          </div>
        </div>
        {msg.audio && (
          <div className="mt-2 ml-1">
            <audio controls className="h-8 w-full max-w-xs rounded-full">
              <source src={`${API}${msg.audio}`} />
            </audio>
          </div>
        )}
        <MessageActions
          content={msg.content}
          onRegenerate={isLastAi ? onRegenerate : undefined}
        />
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
export default function Home() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [file, setFile] = useState<File | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isDragging, setIsDragging] = useState(false);
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

  useEffect(() => {
    axios.get(`${API}/sessions`).then((res) => {
      if (Array.isArray(res.data)) {
        const sorted = res.data.sort(
          (a: any, b: any) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        );
        setSessions(sorted);
      }
    });
  }, []);

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

  const loadSession = async (id: string) => {
    const res = await axios.get(`${API}/messages/${id}`);
    setMessages(
      res.data.map((m: any) => ({
        role: m.role,
        content: m.content,
        id: generateId(),
      })),
    );
    setSessionId(id);
    setSidebarOpen(false);
  };

  const newChat = () => {
    objectURLsRef.current.forEach((url) => URL.revokeObjectURL(url));
    objectURLsRef.current = [];
    setSessionId(crypto.randomUUID());
    setMessages([]);
    setFile(null);
    setSidebarOpen(false);
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    const mediaRecorder = new MediaRecorder(stream);
    mediaRecorderRef.current = mediaRecorder;
    audioChunks.current = [];

    mediaRecorder.ondataavailable = (e) => audioChunks.current.push(e.data);
    mediaRecorder.onstop = () => {
      sendVoice();
      stream.getTracks().forEach((t) => t.stop());
    };

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
    streamRef.current?.getTracks().forEach((t) => t.stop());
  };

  const sendVoice = async () => {
    const blob = new Blob(audioChunks.current, { type: "audio/webm" });
    const voiceFile = new File([blob], "voice.webm");
    const formData = new FormData();
    formData.append("file", voiceFile);
    setLoading(true);

    try {
      const res = await axios.post(`${API}/voice`, formData);
      setMessages((prev) => [
        ...prev,
        { role: "user", content: `🎤 ${res.data.user_text}`, id: generateId() },
        {
          role: "ai",
          content: res.data.response,
          audio: res.data.audio_url,
          id: generateId(),
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: "⚠️ Voice processing failed. Please try again.",
          id: generateId(),
        },
      ]);
    } finally {
      setLoading(false);
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

        const res = await axios.post(`${API}/chat`, {
          message: text || "Summarize document",
          session_id: sessionId,
        });

        setMessages((prev) => [
          ...prev,
          { role: "ai", content: res.data.response, id: generateId() },
        ]);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            role: "ai",
            content: "⚠️ Something went wrong. Please try again.",
            id: generateId(),
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [input, file, sessionId],
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
              active
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
              label="Settings"
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

          <div className="px-4 py-3 border-t border-slate-200">
            <button className="flex items-center gap-2 text-[12.5px] text-slate-400 hover:text-slate-700 transition-colors">
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
              Log out
            </button>
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
                {sessions.find((s) => s.id === sessionId)?.title ||
                  "AI Chat Helper"}
              </h1>
            </div>

            <div className="flex items-center gap-2.5 flex-1 max-w-md">
              {/* Search — single clean hover/focus state defined in .search-input, no layered effects */}
              <div className="search-input relative flex-1 hidden sm:flex items-center bg-slate-100 border border-transparent rounded-xl px-3 py-2">
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
                onClick={newChat}
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
                    {loading && <ThinkingBubble />}
                    <div ref={bottomRef} />
                  </div>
                )}
              </div>

              {/* ── Input area ── */}
              <div className="px-4 pb-4 pt-2.5 bg-white border-t border-slate-200 flex-shrink-0">
                <div className="max-w-[680px] mx-auto">
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
                  onClick={newChat}
                  className="w-full flex items-center justify-center gap-1.5 text-[12.5px] font-medium text-slate-500 hover:text-slate-800 px-3 py-2 rounded-xl hover:bg-slate-100 transition-colors"
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
        </div>
      </div>
    </>
  );
}
