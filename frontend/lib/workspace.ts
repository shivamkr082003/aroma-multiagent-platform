import axios from "axios";
import { API } from "@/lib/auth";

const api = axios.create({ baseURL: API, withCredentials: true });

export type Project = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  chats: number;
  documents: number;
};

export type ProjectDocument = {
  file_id: string;
  file_name: string;
  uploaded_at: string | null;
  chunks: number;
};

export type ChatSummary = {
  id: string;
  title: string;
  created_at: string;
  project_id: string | null;
};

export type SavedTemplate = { id: string; title: string; prompt: string; created_at: string };

export type Stats = {
  totals: { chats: number; questions: number; documents: number | null; projects: number; templates: number };
  activity: { date: string; questions: number }[];
  response_time: { samples: number; median_s: number | null; p90_s: number | null };
  grounding: { documents: number; web: number; both: number; model: number };
  top_documents: { title: string; answers: number }[];
};

export const workspaceApi = {
  // Projects
  listProjects: () => api.get<Project[]>("/projects").then((r) => r.data),
  getProject: (id: string) => api.get<Project>(`/projects/${id}`).then((r) => r.data),
  createProject: (name: string, description: string) =>
    api.post<Project>("/projects", { name, description }).then((r) => r.data),
  updateProject: (id: string, data: { name?: string; description?: string }) =>
    api.patch<Project>(`/projects/${id}`, data).then((r) => r.data),
  deleteProject: (id: string) => api.delete(`/projects/${id}`),
  listDocuments: (id: string) => api.get<ProjectDocument[]>(`/projects/${id}/documents`).then((r) => r.data),
  uploadDocument: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<{ file_id: string }>(`/projects/${id}/documents`, form).then((r) => r.data);
  },
  deleteDocument: (id: string, fileId: string) => api.delete(`/projects/${id}/documents/${fileId}`),
  listProjectChats: (id: string) =>
    api.get<ChatSummary[]>("/sessions", { params: { project_id: id } }).then((r) => r.data),

  // Chats
  renameChat: (id: string, title: string) => api.patch<ChatSummary>(`/sessions/${id}`, { title }).then((r) => r.data),
  deleteChat: (id: string) => api.delete(`/sessions/${id}`),
  clearChats: () => api.delete("/sessions"),

  // Templates
  listTemplates: () => api.get<SavedTemplate[]>("/templates").then((r) => r.data),
  createTemplate: (title: string, prompt: string) =>
    api.post<SavedTemplate>("/templates", { title, prompt }).then((r) => r.data),
  deleteTemplate: (id: string) => api.delete(`/templates/${id}`),

  // Statistics
  getStats: () => api.get<Stats>("/stats").then((r) => r.data),
};

export function apiError(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback;
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg ?? "").filter(Boolean).join(" ") || fallback;
  return fallback;
}

export function relativeDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
