"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { authErrorMessage, getCurrentUser, register } from "@/lib/auth";
import { Divider, FormAlert, GoogleButton, PasswordField, SubmitButton, TextField } from "../_components/fields";

const RULES = [
  { label: "8+ characters", test: (p: string) => p.length >= 8 },
  { label: "A letter", test: (p: string) => /[A-Za-z]/.test(p) },
  { label: "A number", test: (p: string) => /\d/.test(p) },
];

const STRENGTH = [
  { label: "Too weak", bar: "bg-rose-400" },
  { label: "Weak", bar: "bg-orange-400" },
  { label: "Good", bar: "bg-amber-400" },
  { label: "Strong", bar: "bg-emerald-500" },
];

export function RegisterForm() {
  const router = useRouter();
  const [name, setName] = useState("");
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
  const [showPasswordError, setShowPasswordError] = useState(false);

  const passed = RULES.filter((rule) => rule.test(password)).length;
  const strength = STRENGTH[Math.min(passed + (password.length >= 12 && passed === RULES.length ? 1 : 0), 3)];
  const passwordValid = passed === RULES.length;

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading) return;
    if (!passwordValid) {
      setShowPasswordError(true);
      return;
    }
    setError("");
    setLoading(true);
    try {
      // The backend signs the new user in, so go straight to the app.
      await register(name.trim(), email.trim(), password);
      router.replace("/");
    } catch (err) {
      setError(authErrorMessage(err, "Could not create your account. Please try again."));
      setLoading(false);
    }
  };

  return (
    <div className="aroma-rise">
      <h1 className="text-[28px] font-semibold tracking-[-0.02em] text-slate-900">Create your account</h1>
      <p className="mt-1.5 text-[14.5px] text-slate-500">Start chatting with your documents in under a minute.</p>

      <div className="mt-8 space-y-5">
        <GoogleButton />
        <Divider>or</Divider>

        <form onSubmit={onSubmit} className="space-y-4">
          <FormAlert message={error} />
          <TextField
            label="Full name"
            name="name"
            autoComplete="name"
            placeholder="Shivam Kumar"
            required
            autoFocus
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <TextField
            label="Email"
            type="email"
            name="email"
            autoComplete="email"
            placeholder="you@example.com"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <PasswordField
            label="Password"
            name="password"
            autoComplete="new-password"
            placeholder="Create a password"
            required
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setShowPasswordError(false);
            }}
            error={showPasswordError ? "Use at least 8 characters with a letter and a number." : undefined}
            hint={
              password ? (
                <div className="aroma-fade-in space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="flex flex-1 gap-1">
                      {STRENGTH.map((level, i) => (
                        <span
                          key={level.label}
                          className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
                            i <= STRENGTH.indexOf(strength) ? strength.bar : "bg-slate-200"
                          }`}
                        />
                      ))}
                    </div>
                    <span className="w-14 text-right text-[11.5px] font-medium text-slate-500">{strength.label}</span>
                  </div>
                  <ul className="flex flex-wrap gap-x-4 gap-y-1">
                    {RULES.map((rule) => {
                      const ok = rule.test(password);
                      return (
                        <li key={rule.label} className={`flex items-center gap-1 text-[12px] transition-colors ${ok ? "text-emerald-600" : "text-slate-400"}`}>
                          <svg aria-hidden viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5">
                            {ok ? (
                              <path d="m3.5 8.5 3 3 6-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                            ) : (
                              <circle cx="8" cy="8" r="2" fill="currentColor" />
                            )}
                          </svg>
                          {rule.label}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ) : undefined
            }
          />
          <div className="pt-1">
            <SubmitButton loading={loading} loadingText="Creating account…">
              Create account
            </SubmitButton>
          </div>
        </form>
      </div>

      <p className="mt-8 text-center text-[13.5px] text-slate-500">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-slate-900 underline-offset-4 hover:text-orange-600 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
