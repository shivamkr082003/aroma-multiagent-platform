"use client";

import axios from "axios";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getAuthConfig, loginWithGoogle } from "@/lib/auth";
import { Divider } from "./fields";

// Minimal typing for the Google Identity Services script.
type GoogleId = {
  initialize: (config: { client_id: string; callback: (response: { credential: string }) => void; ux_mode?: "popup" }) => void;
  renderButton: (parent: HTMLElement, options: Record<string, string | number>) => void;
};
declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } };
  }
}

let scriptPromise: Promise<void> | null = null;

function loadGoogleScript(): Promise<void> {
  scriptPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      scriptPromise = null; // allow a retry on the next visit
      reject(new Error("Could not load Google sign-in."));
    };
    document.head.appendChild(script);
  });
  return scriptPromise;
}

/**
 * Google's official "Sign in with Google" button plus the "or" divider.
 * Renders nothing when the server has no GOOGLE_CLIENT_ID configured.
 */
export function GoogleSignIn({ mode, onError }: { mode: "signin" | "signup"; onError: (message: string) => void }) {
  const router = useRouter();
  const container = useRef<HTMLDivElement | null>(null);
  const [clientId, setClientId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getAuthConfig()
      .then((config) => setClientId(config.google_client_id))
      .catch(() => setClientId(null));
  }, []);

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;
    loadGoogleScript()
      .then(() => {
        const google = window.google?.accounts.id;
        if (cancelled || !google || !container.current) return;
        google.initialize({
          client_id: clientId,
          ux_mode: "popup",
          callback: async ({ credential }) => {
            setBusy(true);
            onError("");
            try {
              await loginWithGoogle(credential);
              router.replace("/");
            } catch (error) {
              const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
              onError(typeof detail === "string" ? detail : "Google sign-in failed. Please try again.");
              setBusy(false);
            }
          },
        });
        google.renderButton(container.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          shape: "rectangular",
          text: mode === "signup" ? "signup_with" : "continue_with",
          logo_alignment: "center",
          // Google's button takes a pixel width (max 400): match the form.
          width: Math.min(400, Math.max(200, container.current.offsetWidth)),
        });
      })
      .catch(() => onError("Couldn't load Google sign-in. Check your connection, or use email instead."));
    return () => {
      cancelled = true;
    };
  }, [clientId, mode, onError, router]);

  if (!clientId) return null;

  return (
    <>
      <div className="relative">
        {/* Fixed height so the form doesn't jump while Google's iframe loads */}
        <div ref={container} className={`flex h-11 w-full justify-center ${busy ? "pointer-events-none opacity-50" : ""}`} />
        {busy && (
          <p className="mt-2 text-center text-[12.5px] text-slate-500" role="status">
            Signing you in with Google…
          </p>
        )}
      </div>
      <Divider>or</Divider>
    </>
  );
}
