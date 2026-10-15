"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  apiError,
  relativeDate,
  workspaceApi,
  type ChatSummary,
  type Project,
  type ProjectDocument,
} from "@/lib/workspace";
import { EmptyCard, ErrorNote, Icon, PrimaryButton, ViewShell } from "./ViewShell";

type ProjectRef = { id: string; name: string };

export function ProjectsView({
  onOpenChat,
  onNewChat,
}: {
  onOpenChat: (sessionId: string, project: ProjectRef) => void;
  onNewChat: (project: ProjectRef) => void;
}) {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setProjects(await workspaceApi.listProjects());
    } catch (err) {
      setError(apiError(err, "Could not load projects."));
      setProjects([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const project = await workspaceApi.createProject(name, description);
      setName("");
      setDescription("");
      setCreating(false);
      await load();
      setOpenId(project.id);
    } catch (err) {
      setError(apiError(err, "Could not create the project."));
    } finally {
      setBusy(false);
    }
  };

  if (openId) {
    return (
      <ProjectDetail
        projectId={openId}
        onBack={() => {
          setOpenId(null);
          void load();
        }}
        onOpenChat={onOpenChat}
        onNewChat={onNewChat}
      />
    );
  }

  return (
    <ViewShell
      title="My Projects"
      subtitle="Group documents into a project. Every chat inside it can answer from all of them."
      action={
        <PrimaryButton onClick={() => setCreating((v) => !v)}>
          {Icon.plus}
          New project
        </PrimaryButton>
      }
    >
      <ErrorNote message={error} />

      {creating && (
        <form onSubmit={create} className="msg-animate mb-6 grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-[1fr_1.4fr_auto]">
          <input
            required
            autoFocus
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name, e.g. Final year thesis"
            className="rounded-xl border border-slate-200 px-3.5 py-2.5 text-[13.5px] outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-500/10"
          />
          <input
            maxLength={500}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What is it for? (optional)"
            className="rounded-xl border border-slate-200 px-3.5 py-2.5 text-[13.5px] outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-500/10"
          />
          <PrimaryButton type="submit" disabled={busy} className="justify-center">{busy ? "Creating…" : "Create"}</PrimaryButton>
        </form>
      )}

      {projects === null ? (
        <SkeletonGrid />
      ) : projects.length === 0 ? (
        <EmptyCard
          icon={Icon.folder}
          title="No projects yet"
          body="Create one for a subject, your thesis or job applications, add the documents once, and ask across all of them."
          action={<PrimaryButton onClick={() => setCreating(true)}>{Icon.plus}Create your first project</PrimaryButton>}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => setOpenId(p.id)}
              className="group flex flex-col rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-orange-200 hover:shadow-md"
            >
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-orange-400 to-rose-500 text-white shadow-sm">
                {Icon.folder}
              </div>
              <p className="truncate text-[14px] font-semibold text-slate-800">{p.name}</p>
              <p className="mt-1 line-clamp-2 min-h-[2.5em] text-[12.5px] text-slate-500">{p.description || "No description"}</p>
              <div className="mt-3 flex items-center gap-3 border-t border-slate-100 pt-3 text-[12px] text-slate-500">
                <span className="inline-flex items-center gap-1">{Icon.doc}{p.documents} {p.documents === 1 ? "document" : "documents"}</span>
                <span className="inline-flex items-center gap-1">{Icon.chat}{p.chats} {p.chats === 1 ? "chat" : "chats"}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </ViewShell>
  );
}

function ProjectDetail({
  projectId,
  onBack,
  onOpenChat,
  onNewChat,
}: {
  projectId: string;
  onBack: () => void;
  onOpenChat: (sessionId: string, project: ProjectRef) => void;
  onNewChat: (project: ProjectRef) => void;
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [docs, setDocs] = useState<ProjectDocument[]>([]);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [uploading, setUploading] = useState<string[]>([]);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => setReloadKey((k) => k + 1);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      workspaceApi.getProject(projectId),
      workspaceApi.listDocuments(projectId),
      workspaceApi.listProjectChats(projectId),
    ])
      .then(([p, d, c]) => {
        if (cancelled) return;
        setProject(p);
        setDocs(d);
        setChats(c);
      })
      .catch((err) => {
        if (!cancelled) setError(apiError(err, "Could not load this project."));
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, reloadKey]);

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setError("");
    const list = Array.from(files);
    setUploading(list.map((f) => f.name));
    for (const file of list) {
      try {
        await workspaceApi.uploadDocument(projectId, file);
      } catch (err) {
        setError(apiError(err, `Could not upload ${file.name}.`));
      }
      setUploading((names) => names.filter((n) => n !== file.name));
    }
    if (fileInput.current) fileInput.current.value = "";
    reload();
  };

  const removeDoc = async (doc: ProjectDocument) => {
    if (!window.confirm(`Remove "${doc.file_name}" from this project?`)) return;
    try {
      await workspaceApi.deleteDocument(projectId, doc.file_id);
      reload();
    } catch (err) {
      setError(apiError(err, "Could not remove the document."));
    }
  };

  const rename = async () => {
    if (!project) return;
    const next = window.prompt("Rename project", project.name)?.trim();
    if (!next || next === project.name) return;
    try {
      setProject(await workspaceApi.updateProject(projectId, { name: next }));
    } catch (err) {
      setError(apiError(err, "Could not rename the project."));
    }
  };

  const remove = async () => {
    if (!project) return;
    if (!window.confirm(`Delete "${project.name}"? Its ${docs.length} documents and ${chats.length} chats will be deleted too.`)) return;
    try {
      await workspaceApi.deleteProject(projectId);
      onBack();
    } catch (err) {
      setError(apiError(err, "Could not delete the project."));
    }
  };

  const ref = project ? { id: project.id, name: project.name } : null;

  return (
    <ViewShell
      title={project?.name ?? "Loading…"}
      subtitle={project?.description || "Documents here are searched by every chat in this project."}
      action={
        <div className="flex items-center gap-2">
          <button onClick={onBack} className="inline-flex items-center gap-1 rounded-xl px-3 py-2 text-[12.5px] font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-800">
            {Icon.back}
            All projects
          </button>
          <button onClick={rename} aria-label="Rename project" className="rounded-xl p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700">{Icon.pencil}</button>
          <button onClick={remove} aria-label="Delete project" className="rounded-xl p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600">{Icon.trash}</button>
          {ref && <PrimaryButton onClick={() => onNewChat(ref)}>{Icon.plus}New chat</PrimaryButton>}
        </div>
      }
    >
      <ErrorNote message={error} />
      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-slate-800">Documents <span className="font-normal text-slate-400">· {docs.length}</span></h3>
            <button
              onClick={() => fileInput.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-[12px] font-medium text-slate-600 hover:border-slate-300 hover:text-slate-900"
            >
              {Icon.upload}
              Add documents
            </button>
            <input ref={fileInput} type="file" accept=".pdf,.txt,.docx" multiple hidden onChange={(e) => void upload(e.target.files)} />
          </div>
          {docs.length === 0 && uploading.length === 0 ? (
            <button
              onClick={() => fileInput.current?.click()}
              className="flex w-full flex-col items-center rounded-xl border border-dashed border-slate-300 px-4 py-10 text-center hover:border-orange-300 hover:bg-orange-50/40"
            >
              <span className="mb-2 text-orange-500">{Icon.upload}</span>
              <span className="text-[13px] font-medium text-slate-700">Upload PDFs, DOCX or TXT</span>
              <span className="mt-0.5 text-[12px] text-slate-400">Notes, papers, syllabus, your resume…</span>
            </button>
          ) : (
            <ul className="divide-y divide-slate-100">
              {uploading.map((n) => (
                <li key={`up-${n}`} className="flex items-center gap-3 py-2.5 text-[13px] text-slate-500">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-orange-200 border-t-orange-500" />
                  <span className="truncate">{n}</span>
                  <span className="ml-auto shrink-0 text-[11.5px] text-slate-400">Reading…</span>
                </li>
              ))}
              {docs.map((d) => (
                <li key={d.file_id} className="group flex items-center gap-3 py-2.5">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-rose-50 text-rose-500">{Icon.doc}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-slate-800">{d.file_name}</p>
                    <p className="text-[11.5px] text-slate-400">{relativeDate(d.uploaded_at)} · {d.chunks} passages</p>
                  </div>
                  <button onClick={() => removeDoc(d)} aria-label={`Remove ${d.file_name}`} className="rounded-lg p-1.5 text-slate-300 opacity-0 transition-opacity hover:bg-rose-50 hover:text-rose-600 focus:opacity-100 group-hover:opacity-100">
                    {Icon.trash}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-[13px] font-semibold text-slate-800">Chats <span className="font-normal text-slate-400">· {chats.length}</span></h3>
          {chats.length === 0 ? (
            <div className="rounded-xl bg-slate-50 px-4 py-8 text-center">
              <p className="text-[13px] text-slate-500">No chats in this project yet.</p>
              {ref && (
                <button onClick={() => onNewChat(ref)} className="mt-2 text-[12.5px] font-semibold text-orange-600 hover:text-orange-700">
                  Start the first chat →
                </button>
              )}
            </div>
          ) : (
            <ul className="space-y-1">
              {chats.map((c) => (
                <li key={c.id}>
                  <button onClick={() => ref && onOpenChat(c.id, ref)} className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left hover:bg-slate-50">
                    <span className="text-slate-400">{Icon.chat}</span>
                    <span className="min-w-0 flex-1 truncate text-[13px] text-slate-700">{c.title || "New conversation"}</span>
                    <span className="shrink-0 text-[11.5px] text-slate-400">{relativeDate(c.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </ViewShell>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-hidden>
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-[150px] animate-pulse rounded-2xl border border-slate-200 bg-white" />
      ))}
    </div>
  );
}
