"use client";

import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { API } from "@/lib/auth";
import { apiError } from "@/lib/workspace";

type Transport = "http" | "sse" | "stdio";

type MCPServer = {
  id: string;
  name: string;
  transport: Transport;
  url?: string | null;
  command?: string | null;
  args?: string[] | null;
  enabled: boolean;
};

type TestResult = { reachable: boolean; tools: { name: string; description?: string | null }[]; error?: string | null };

const api = axios.create({ baseURL: `${API}/mcp`, withCredentials: true });

// Public servers that work without an API key, for a one-click start.
const PRESETS = [
  {
    name: "DeepWiki",
    url: "https://mcp.deepwiki.com/mcp",
    description: "Ask questions about any public GitHub repository.",
  },
];

const TRANSPORTS: { id: Transport; label: string; hint: string }[] = [
  { id: "http", label: "HTTP", hint: "Streamable HTTP · recommended" },
  { id: "sse", label: "SSE", hint: "Older servers" },
  { id: "stdio", label: "Local", hint: "Runs a command on the server" },
];

const inputClass =
  "w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-[13.5px] text-slate-900 placeholder:text-slate-400 " +
  "outline-none transition-[border-color,box-shadow] hover:border-slate-300 focus:border-orange-400 focus:ring-4 focus:ring-orange-500/10";

export function MCPPanel({ onClose }: { onClose: () => void }) {
  const [servers, setServers] = useState<MCPServer[] | null>(null);
  const [stdioCommands, setStdioCommands] = useState<string[] | null>(null);
  const [tests, setTests] = useState<Record<string, TestResult | "testing">>({});
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.get<MCPServer[]>("/servers"), api.get<{ stdio_allowed: boolean; stdio_allowed_commands: string[] }>("/config")])
      .then(([list, config]) => {
        if (cancelled) return;
        setServers(list.data);
        // STDIO runs a process on the backend host, so it is only offered when the backend allows it.
        setStdioCommands(config.data.stdio_allowed ? config.data.stdio_allowed_commands : null);
      })
      .catch((err) => {
        if (!cancelled) {
          setServers([]);
          setError(apiError(err, "Could not load MCP servers. Is the backend running?"));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const reload = () => setReloadKey((k) => k + 1);

  const test = useCallback(async (id: string) => {
    setTests((t) => ({ ...t, [id]: "testing" }));
    try {
      const { data } = await api.post<TestResult>(`/servers/${id}/test`);
      setTests((t) => ({ ...t, [id]: data }));
    } catch (err) {
      setTests((t) => ({ ...t, [id]: { reachable: false, tools: [], error: apiError(err, "Test failed.") } }));
    }
  }, []);

  const add = async (body: Record<string, unknown>) => {
    setError("");
    const { data } = await api.post<MCPServer>("/servers", body);
    reload();
    void test(data.id); // show right away whether it works
  };

  const toggle = async (server: MCPServer) => {
    setServers((list) => list?.map((s) => (s.id === server.id ? { ...s, enabled: !s.enabled } : s)) ?? null);
    try {
      await api.post(`/servers/${server.id}/${server.enabled ? "disable" : "enable"}`);
    } catch (err) {
      setError(apiError(err, "Could not update the server."));
      reload();
    }
  };

  const remove = async (server: MCPServer) => {
    try {
      await api.delete(`/servers/${server.id}`);
      reload();
    } catch (err) {
      setError(apiError(err, "Could not remove the server."));
    }
  };

  const addedUrls = new Set(servers?.map((s) => s.url));
  const presets = PRESETS.filter((p) => !addedUrls.has(p.url));

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-[2px]" onMouseDown={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="mcp-title"
        className="aroma-rise flex max-h-[90vh] w-full max-w-[640px] flex-col overflow-hidden rounded-3xl bg-white font-sans text-slate-900 shadow-[0_30px_80px_-20px_rgba(15,23,42,0.45)]"
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="relative flex items-start gap-3.5 border-b border-slate-100 px-6 pb-5 pt-6">
          <div aria-hidden className="pointer-events-none absolute -top-16 right-10 h-40 w-40 rounded-full bg-orange-200/40 blur-3xl" />
          <div className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-orange-400 to-rose-500 text-white shadow-md shadow-rose-500/25">
            <PlugIcon className="h-5 w-5" />
          </div>
          <div className="relative min-w-0 flex-1">
            <h2 id="mcp-title" className="text-[18px] font-semibold tracking-tight">MCP Servers</h2>
            <p className="mt-0.5 text-[13px] leading-relaxed text-slate-500">
              Give Aroma new tools. During a chat it decides on its own when a tool would help.
            </p>
          </div>
          <button onClick={onClose} aria-label="Close" className="relative -mr-1.5 -mt-1 rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700">
            <svg aria-hidden className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeWidth={2.2} d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </header>

        <div className="flex-1 space-y-7 overflow-y-auto px-6 py-5">
          {error && (
            <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-[13px] text-rose-700">{error}</p>
          )}

          {/* Connected servers */}
          <section>
            <SectionTitle count={servers?.length}>Connected</SectionTitle>
            {servers === null ? (
              <div className="h-[72px] animate-pulse rounded-2xl border border-slate-200 bg-slate-50" />
            ) : servers.length === 0 ? (
              <div className="flex items-center gap-3.5 rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 px-4 py-4">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-slate-400 shadow-sm"><PlugIcon className="h-4 w-4" /></span>
                <div>
                  <p className="text-[13.5px] font-medium text-slate-800">No tools connected yet</p>
                  <p className="text-[12.5px] text-slate-500">Start with a quick-start server below, or add your own.</p>
                </div>
              </div>
            ) : (
              <ul className="space-y-2.5">
                {servers.map((s) => (
                  <ServerCard key={s.id} server={s} result={tests[s.id]} onTest={() => void test(s.id)} onToggle={() => void toggle(s)} onRemove={() => void remove(s)} />
                ))}
              </ul>
            )}
          </section>

          {/* Quick start */}
          {presets.length > 0 && (
            <section>
              <SectionTitle>Quick start</SectionTitle>
              <div className="space-y-2">
                {presets.map((p) => (
                  <PresetCard key={p.url} preset={p} onAdd={() => add({ name: p.name, transport: "http", url: p.url })} onError={setError} />
                ))}
              </div>
            </section>
          )}

          {/* Add your own */}
          <section>
            <SectionTitle>Add a server</SectionTitle>
            <AddServerForm stdioCommands={stdioCommands} onAdd={add} onError={setError} />
          </section>
        </div>

        <footer className="flex items-center gap-2 border-t border-slate-100 bg-slate-50/70 px-6 py-3 text-[12px] text-slate-500">
          <svg aria-hidden className="h-3.5 w-3.5 shrink-0 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3l7 3v5c0 4.4-3 8.3-7 9.5-4-1.2-7-5.1-7-9.5V6l7-3z M9 12l2 2 4-4" />
          </svg>
          Only connect servers you trust. API keys are encrypted and never shown again.
        </footer>
      </section>
    </div>
  );
}

function SectionTitle({ children, count }: { children: React.ReactNode; count?: number }) {
  return (
    <h3 className="mb-2.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
      {children}
      {count !== undefined && count > 0 && <span className="rounded-md bg-slate-100 px-1.5 py-px text-[10.5px] tracking-normal text-slate-500">{count}</span>}
    </h3>
  );
}

function ServerCard({
  server,
  result,
  onTest,
  onToggle,
  onRemove,
}: {
  server: MCPServer;
  result?: TestResult | "testing";
  onTest: () => void;
  onToggle: () => void;
  onRemove: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const testing = result === "testing";
  const tested = result && result !== "testing" ? result : null;
  const dot = !server.enabled ? "bg-slate-300" : tested ? (tested.reachable ? "bg-emerald-500" : "bg-rose-500") : "bg-slate-300";
  const state = !server.enabled ? "Paused" : tested ? (tested.reachable ? `Connected · ${tested.tools.length} tools` : "Can't connect") : "Not tested";
  const target = server.transport === "stdio" ? [server.command, ...(server.args ?? [])].join(" ") : server.url;

  return (
    <li className={`rounded-2xl border bg-white p-3.5 transition-colors ${server.enabled ? "border-slate-200 shadow-sm" : "border-slate-200 bg-slate-50/60"}`}>
      <div className="flex items-center gap-3">
        <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-[13px] font-bold uppercase text-slate-600">
          {server.name.slice(0, 1)}
          <span className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white ${dot}`} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className={`truncate text-[13.5px] font-semibold ${server.enabled ? "text-slate-800" : "text-slate-500"}`}>{server.name}</p>
            <span className="shrink-0 rounded-md bg-slate-100 px-1.5 py-px text-[10px] font-semibold uppercase text-slate-500">{server.transport}</span>
          </div>
          <p className="truncate font-mono text-[11.5px] text-slate-400" title={target ?? ""}>{target}</p>
        </div>
        <span className="hidden shrink-0 text-[11.5px] font-medium text-slate-500 sm:block">{state}</span>
        <button
          onClick={onTest}
          disabled={testing || !server.enabled}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-[12px] font-medium text-slate-600 transition-colors hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {testing && <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-200 border-t-orange-500" />}
          {testing ? "Testing" : "Test"}
        </button>
        <button
          role="switch"
          aria-checked={server.enabled}
          aria-label={`${server.enabled ? "Pause" : "Enable"} ${server.name}`}
          onClick={onToggle}
          className={`relative h-[22px] w-[38px] shrink-0 rounded-full transition-colors ${server.enabled ? "bg-gradient-to-r from-orange-400 to-rose-500" : "bg-slate-200"}`}
        >
          <span className={`absolute top-[3px] h-4 w-4 rounded-full bg-white shadow transition-[left] ${server.enabled ? "left-[19px]" : "left-[3px]"}`} />
        </button>
        {confirming ? (
          <button onClick={onRemove} onBlur={() => setConfirming(false)} autoFocus className="shrink-0 rounded-lg bg-rose-600 px-2.5 py-1.5 text-[12px] font-medium text-white hover:bg-rose-700">
            Remove
          </button>
        ) : (
          <button onClick={() => setConfirming(true)} aria-label={`Remove ${server.name}`} className="shrink-0 rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600">
            <svg aria-hidden className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 7l-.9 12.1A2 2 0 0116.1 21H7.9a2 2 0 01-2-1.9L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
          </button>
        )}
      </div>

      {tested && (
        <div className="aroma-fade-in mt-3 border-t border-slate-100 pt-3">
          {tested.reachable ? (
            tested.tools.length ? (
              <div className="flex flex-wrap gap-1.5">
                {tested.tools.map((t) => (
                  <span key={t.name} title={t.description ?? undefined} className="inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-2 py-1 font-mono text-[11.5px] text-emerald-800">
                    <svg aria-hidden className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.4} d="M5 13l4 4L19 7" /></svg>
                    {t.name}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-[12.5px] text-slate-500">Connected, but the server offers no tools.</p>
            )
          ) : (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-[12.5px] text-rose-700">{tested.error || "The server did not respond."}</p>
          )}
        </div>
      )}
    </li>
  );
}

function PresetCard({
  preset,
  onAdd,
  onError,
}: {
  preset: (typeof PRESETS)[number];
  onAdd: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-gradient-to-r from-orange-50/70 to-white p-3.5">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-orange-500 shadow-sm">
        <svg aria-hidden className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 6.25v13M12 6.25C10.8 5.5 9.2 5 7.5 5S4.2 5.5 3 6.25v13C4.2 18.5 5.8 18 7.5 18s3.3.5 4.5 1.25m0-13C13.2 5.5 14.8 5 16.5 5s3.3.5 4.5 1.25v13C19.8 18.5 18.2 18 16.5 18s-3.3.5-4.5 1.25" /></svg>
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[13.5px] font-semibold text-slate-800">{preset.name} <span className="ml-1 rounded-md bg-emerald-50 px-1.5 py-px text-[10px] font-semibold text-emerald-700">No API key</span></p>
        <p className="text-[12.5px] text-slate-500">{preset.description}</p>
      </div>
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await onAdd();
          } catch (err) {
            onError(apiError(err, `Could not add ${preset.name}.`));
          } finally {
            setBusy(false);
          }
        }}
        className="shrink-0 rounded-xl bg-slate-900 px-3 py-2 text-[12.5px] font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-60"
      >
        {busy ? "Adding…" : "Add"}
      </button>
    </div>
  );
}

function AddServerForm({
  stdioCommands,
  onAdd,
  onError,
}: {
  stdioCommands: string[] | null;
  onAdd: (body: Record<string, unknown>) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [transport, setTransport] = useState<Transport>("http");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const [showAuth, setShowAuth] = useState(false);
  const [headerName, setHeaderName] = useState("Authorization");
  const [headerValue, setHeaderValue] = useState("");
  const [busy, setBusy] = useState(false);

  const options = TRANSPORTS.filter((t) => t.id !== "stdio" || stdioCommands);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await onAdd({
        name,
        transport,
        ...(transport === "stdio"
          ? { command, args: args.trim() ? args.trim().split(/\s+/) : [] }
          : { url, ...(showAuth && headerName.trim() && headerValue ? { headers: { [headerName.trim()]: headerValue } } : {}) }),
      });
      setName("");
      setUrl("");
      setCommand("");
      setArgs("");
      setHeaderValue("");
      setShowAuth(false);
    } catch (err) {
      onError(apiError(err, "Could not add the server."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3 rounded-2xl border border-slate-200 p-4">
      <div role="radiogroup" aria-label="Connection type" className={`grid gap-1 rounded-xl bg-slate-100 p-1 ${options.length === 3 ? "grid-cols-3" : "grid-cols-2"}`}>
        {options.map((t) => (
          <button
            key={t.id}
            type="button"
            role="radio"
            aria-checked={transport === t.id}
            onClick={() => setTransport(t.id)}
            className={`rounded-lg px-3 py-1.5 text-left transition-all ${transport === t.id ? "bg-white shadow-sm" : "hover:bg-white/50"}`}
          >
            <span className={`block text-[12.5px] font-semibold ${transport === t.id ? "text-slate-900" : "text-slate-600"}`}>{t.label}</span>
            <span className="block text-[11px] text-slate-400">{t.hint}</span>
          </button>
        ))}
      </div>

      <Field label="Name">
        <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. GitHub" className={inputClass} />
      </Field>

      {transport === "stdio" ? (
        <div className="grid gap-3 sm:grid-cols-[1fr_1.6fr]">
          <Field label="Command">
            <input required value={command} onChange={(e) => setCommand(e.target.value)} placeholder={stdioCommands?.join(", ") || "npx"} className={`${inputClass} font-mono`} />
          </Field>
          <Field label="Arguments">
            <input value={args} onChange={(e) => setArgs(e.target.value)} placeholder="-y @modelcontextprotocol/server-everything" className={`${inputClass} font-mono`} />
          </Field>
        </div>
      ) : (
        <Field label="Server URL">
          <input required type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/mcp" className={`${inputClass} font-mono`} />
        </Field>
      )}

      {transport !== "stdio" && (
        showAuth ? (
          <div className="aroma-fade-in grid gap-3 rounded-xl bg-slate-50 p-3 sm:grid-cols-[1fr_1.6fr]">
            <Field label="Header">
              <input value={headerName} onChange={(e) => setHeaderName(e.target.value)} className={`${inputClass} font-mono`} />
            </Field>
            <Field label="Value">
              <input type="password" autoComplete="off" value={headerValue} onChange={(e) => setHeaderValue(e.target.value)} placeholder="Bearer sk-…" className={`${inputClass} font-mono`} />
            </Field>
          </div>
        ) : (
          <button type="button" onClick={() => setShowAuth(true)} className="inline-flex items-center gap-1 text-[12.5px] font-medium text-slate-500 hover:text-slate-800">
            <svg aria-hidden className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.7 5.7L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.6a1 1 0 01.3-.7l6-6A6 6 0 1121 9z" /></svg>
            Needs an API key?
          </button>
        )
      )}

      <button
        type="submit"
        disabled={busy}
        className="flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-slate-900 text-[13px] font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.12)] transition-colors hover:bg-slate-800 disabled:opacity-60"
      >
        {busy && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />}
        {busy ? "Connecting…" : "Add server"}
      </button>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[12px] font-medium text-slate-600">{label}</span>
      {children}
    </label>
  );
}

function PlugIcon({ className }: { className?: string }) {
  return (
    <svg aria-hidden className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 3v4M15 3v4M6 7h12v3a6 6 0 01-12 0V7zM12 16v5" />
    </svg>
  );
}
