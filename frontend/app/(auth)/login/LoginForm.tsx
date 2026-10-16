"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { authErrorMessage, getCurrentUser, login } from "@/lib/auth";
import { FormAlert, PasswordField, SubmitButton, TextField } from "../_components/fields";
import { GoogleSignIn } from "../_components/GoogleSignIn";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Already signed in? Skip the form.
  useEffect(() => {
    getCurrentUser()
      .then((user) => user && router.replace("/"))
      .catch(() => {});
  }, [router]);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading) return;
    setError("");
    setLoading(true);
    try {
      await login(email.trim(), password);
      router.replace("/");
    } catch (err) {
      setError(authErrorMessage(err, "Could not sign you in. Please try again."));
      setLoading(false);
    }
  };

  return (
    <div className="aroma-rise">
      <h1 className="text-[28px] font-semibold tracking-[-0.02em] text-slate-900">Welcome back</h1>
      <p className="mt-1.5 text-[14.5px] text-slate-500">Sign in to continue your conversations.</p>

      <div className="mt-8 space-y-5">
        <GoogleSignIn mode="signin" onError={setError} />

        <form onSubmit={onSubmit} className="space-y-4">
          <FormAlert message={error} />
          <TextField
            label="Email"
            type="email"
            name="email"
            autoComplete="email"
            placeholder="you@example.com"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <PasswordField
            label="Password"
            name="password"
            autoComplete="current-password"
            placeholder="Enter your password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <div className="pt-1">
            <SubmitButton loading={loading} loadingText="Signing in…">
              Sign in
            </SubmitButton>
          </div>
        </form>
      </div>

      <p className="mt-8 text-center text-[13.5px] text-slate-500">
        New to Aroma?{" "}
        <Link href="/register" className="font-medium text-slate-900 underline-offset-4 hover:text-orange-600 hover:underline">
          Create an account
        </Link>
      </p>
    </div>
  );
}
