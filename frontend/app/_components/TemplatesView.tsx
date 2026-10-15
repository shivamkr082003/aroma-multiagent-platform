"use client";

import { useCallback, useEffect, useState } from "react";
import { apiError, workspaceApi, type SavedTemplate } from "@/lib/workspace";
import { EmptyCard, ErrorNote, Icon, PrimaryButton, ViewShell } from "./ViewShell";

type BuiltIn = { title: string; description: string; category: string; prompt: string };

const BUILT_IN: BuiltIn[] = [
  { category: "Study", title: "Summarize my document", description: "Key points, definitions and a 5-line summary.",
    prompt: "Summarize the uploaded document: list the key points, define important terms, and end with a 5-line summary." },
  { category: "Study", title: "Make exam notes", description: "Revision notes with likely exam questions.",
    prompt: "Turn the uploaded document into concise revision notes with headings, then list 10 likely exam questions with short answers." },
  { category: "Study", title: "Explain like I'm new", description: "A hard topic, step by step with an example.",
    prompt: "Explain this topic simply, step by step, with one real-world example and one common misconception: " },
  { category: "Career", title: "Review my resume", description: "Strengths, gaps and stronger bullet points.",
    prompt: "Review my uploaded resume for a software engineering role: list strengths, gaps, and rewrite the 3 weakest bullet points with measurable impact." },
  { category: "Career", title: "Mock interview", description: "Questions one at a time, with feedback.",
    prompt: "Act as an interviewer for a backend developer role. Ask me one question at a time, wait for my answer, then give feedback before the next question." },
  { category: "Career", title: "Viva preparation", description: "Likely viva questions on my project.",
    prompt: "Based on my uploaded project report, ask me the 10 most likely viva questions and give a strong model answer for each." },
  { category: "Writing", title: "Professional email", description: "Clear, polite email from rough notes.",
    prompt: "Write a short, polite professional email from these notes: " },
  { category: "Writing", title: "Improve my writing", description: "Clearer and more concise, same meaning.",
    prompt: "Rewrite this to be clearer and more concise without changing its meaning, then list what you changed: " },
  { category: "Code", title: "Explain this code", description: "What it does, line by line, and its pitfalls.",
    prompt: "Explain what this code does step by step, point out bugs or edge cases, and suggest one improvement:\n" },
  { category: "Code", title: "Write tests", description: "Unit tests covering normal and edge cases.",
    prompt: "Write unit tests for this function covering normal cases, edge cases and errors:\n" },
];

const CATEGORIES = ["All", ...Array.from(new Set(BUILT_IN.map((t) => t.category)))];

export function TemplatesView({ onUse }: { onUse: (prompt: string) => void }) {
  const [category, setCategory] = useState("All");
  const [saved, setSaved] = useState<SavedTemplate[]>([]);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setSaved(await workspaceApi.listTemplates());
    } catch (err) {
      setError(apiError(err, "Could not load your templates."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await workspaceApi.createTemplate(title, prompt);
      setTitle("");
      setPrompt("");
      setCreating(false);
      await load();
    } catch (err) {
      setError(apiError(err, "Could not save the template."));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (template: SavedTemplate) => {
    if (!window.confirm(`Delete the template "${template.title}"?`)) return;
    try {
      await workspaceApi.deleteTemplate(template.id);
      await load();
    } catch (err) {
      setError(apiError(err, "Could not delete the template."));
    }
  };

  const shown = BUILT_IN.filter((t) => category === "All" || t.category === category);

  return (
    <ViewShell
      title="Templates"
      subtitle="Start from a ready-made prompt, or save the ones you use often."
      action={
        <PrimaryButton onClick={() => setCreating((v) => !v)}>
          {Icon.plus}
          New template
        </PrimaryButton>
      }
    >
      <ErrorNote message={error} />

      {creating && (
        <form onSubmit={save} className="msg-animate mb-8 space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <input
            required
            autoFocus
            maxLength={80}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Template name, e.g. Weekly lab report"
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-[13.5px] outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-500/10"
          />
          <textarea
            required
            maxLength={4000}
            rows={4}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="The prompt Aroma should receive…"
            className="w-full resize-y rounded-xl border border-slate-200 px-3.5 py-2.5 text-[13.5px] outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-500/10"
          />
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setCreating(false)} className="rounded-xl px-3.5 py-2 text-[12.5px] font-medium text-slate-500 hover:bg-slate-100">
              Cancel
            </button>
            <PrimaryButton type="submit" disabled={busy}>{busy ? "Saving…" : "Save template"}</PrimaryButton>
          </div>
        </form>
      )}

      <section className="mb-10">
        <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Your templates</h3>
        {saved.length === 0 ? (
          <EmptyCard
            icon={Icon.spark}
            title="No saved templates yet"
            body="Save a prompt you reuse — a report format, a review checklist — and start it in one click."
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {saved.map((t) => (
              <TemplateCard key={t.id} title={t.title} description={t.prompt} onUse={() => onUse(t.prompt)} onDelete={() => remove(t)} />
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Ready-made</h3>
          <div className="flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1" role="tablist" aria-label="Template category">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                role="tab"
                aria-selected={category === c}
                onClick={() => setCategory(c)}
                className={`rounded-lg px-3 py-1 text-[12px] font-medium transition-colors ${
                  category === c ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {shown.map((t) => (
            <TemplateCard key={t.title} title={t.title} description={t.description} tag={t.category} onUse={() => onUse(t.prompt)} />
          ))}
        </div>
      </section>
    </ViewShell>
  );
}

function TemplateCard({
  title,
  description,
  tag,
  onUse,
  onDelete,
}: {
  title: string;
  description: string;
  tag?: string;
  onUse: () => void;
  onDelete?: () => void;
}) {
  return (
    <div className="group flex flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:border-orange-200 hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[14px] font-semibold text-slate-800">{title}</p>
        {tag && <span className="shrink-0 rounded-md bg-slate-100 px-2 py-0.5 text-[10.5px] font-semibold text-slate-500">{tag}</span>}
      </div>
      <p className="mt-1.5 line-clamp-2 flex-1 text-[12.5px] leading-relaxed text-slate-500">{description}</p>
      <div className="mt-3 flex items-center justify-between">
        <button onClick={onUse} className="inline-flex items-center gap-1 text-[12.5px] font-semibold text-orange-600 hover:text-orange-700">
          Use template
          <span aria-hidden className="transition-transform group-hover:translate-x-0.5">→</span>
        </button>
        {onDelete && (
          <button onClick={onDelete} aria-label={`Delete ${title}`} className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600">
            {Icon.trash}
          </button>
        )}
      </div>
    </div>
  );
}
