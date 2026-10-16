import axios from "axios";

function defaultApi(): string {
  if (typeof window === "undefined") return "http://localhost:8000";
  // Use the page's own hostname so the session cookie stays same-site:
  // localhost and 127.0.0.1 count as different sites to the browser.
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

export const API = process.env.NEXT_PUBLIC_API_URL ?? defaultApi();

export type AuthUser = {
  id: string;
  name: string;
  email: string;
};

// The backend keeps the session in an httpOnly cookie, so every auth call
// must send credentials.
const authClient = axios.create({ baseURL: `${API}/auth`, withCredentials: true });

export async function login(email: string, password: string): Promise<AuthUser> {
  const response = await authClient.post<AuthUser>("/login", { email, password });
  return response.data;
}

export async function register(name: string, email: string, password: string): Promise<AuthUser> {
  const response = await authClient.post<AuthUser>("/register", { name, email, password });
  return response.data;
}

export async function getAuthConfig(): Promise<{ google_client_id: string | null }> {
  const response = await authClient.get<{ google_client_id: string | null }>("/config");
  return response.data;
}

/** Exchange the ID token from "Sign in with Google" for an Aroma session. */
export async function loginWithGoogle(credential: string): Promise<AuthUser> {
  const response = await authClient.post<AuthUser>("/google", { credential });
  return response.data;
}

export async function logout(): Promise<void> {
  await authClient.post("/logout");
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  try {
    const response = await authClient.get<AuthUser>("/me");
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) return null;
    throw error;
  }
}

export function authErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback;
  if (!error.response) return "Can't reach the server. Check your connection and try again.";
  const { status, data } = error.response;
  if (status === 401) return "Incorrect email or password.";
  if (status === 409) return "An account with this email already exists.";
  if (status === 429) return "Too many attempts. Please wait a minute and try again.";
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item: { msg?: string }) => item.msg ?? "").filter(Boolean).join(" ") || fallback;
  return fallback;
}
