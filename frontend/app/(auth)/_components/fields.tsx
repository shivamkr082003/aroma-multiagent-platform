"use client";

import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";

const inputClass =
  "peer h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-[14px] text-slate-900 shadow-[0_1px_2px_rgba(15,23,42,0.04)] " +
  "placeholder:text-slate-400 outline-none transition-[border-color,box-shadow] duration-150 " +
  "hover:border-slate-300 focus:border-orange-400 focus:ring-4 focus:ring-orange-500/10 " +
  "aria-[invalid=true]:border-rose-400 aria-[invalid=true]:focus:ring-rose-500/10";

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: ReactNode;
  error?: string;
  trailing?: ReactNode;
};

export function TextField({ label, hint, error, trailing, className, ...input }: FieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;

  return (
    <div className={className}>
      <div className="mb-1.5 flex items-center justify-between">
        <label htmlFor={id} className="text-[13px] font-medium text-slate-700">
          {label}
        </label>
        {trailing}
      </div>
      <input id={id} aria-invalid={error ? true : undefined} aria-describedby={describedBy} className={inputClass} {...input} />
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-[12.5px] text-rose-600">
          {error}
        </p>
      ) : hint ? (
        <div id={`${id}-hint`} className="mt-2">
          {hint}
        </div>
      ) : null}
    </div>
  );
}

export function PasswordField({ label, hint, error, className, ...input }: Omit<FieldProps, "type" | "trailing">) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;

  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-[13px] font-medium text-slate-700">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visible ? "text" : "password"}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={`${inputClass} pr-11`}
          {...input}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-xl text-slate-400 transition-colors hover:text-slate-700 focus-visible:text-slate-700 focus-visible:outline-none"
        >
          {visible ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-[12.5px] text-rose-600">
          {error}
        </p>
      ) : hint ? (
        <div id={`${id}-hint`} className="mt-2">
          {hint}
        </div>
      ) : null}
    </div>
  );
}

export function SubmitButton({ loading, children, loadingText }: { loading: boolean; children: ReactNode; loadingText: string }) {
  return (
    <button
      type="submit"
      disabled={loading}
      className="group relative flex h-11 w-full items-center justify-center gap-2 overflow-hidden rounded-xl bg-slate-900 text-[14px] font-medium text-white
        shadow-[0_1px_2px_rgba(15,23,42,0.2),inset_0_1px_0_rgba(255,255,255,0.12)] transition-all duration-150
        hover:bg-slate-800 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-80
        focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-orange-500/20"
    >
      {/* Soft brand sheen that sweeps across on hover */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 -skew-x-12 bg-gradient-to-r from-transparent via-white/15 to-transparent opacity-0 transition-all duration-700 group-hover:left-full group-hover:opacity-100"
      />
      {loading ? (
        <>
          <Spinner />
          {loadingText}
        </>
      ) : (
        <>
          {children}
          <ArrowIcon />
        </>
      )}
    </button>
  );
}

export function Divider({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-3 text-[12px] font-medium uppercase tracking-[0.14em] text-slate-400">
      <span className="h-px flex-1 bg-slate-200" />
      {children}
      <span className="h-px flex-1 bg-slate-200" />
    </div>
  );
}

export function FormAlert({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div role="alert" className="aroma-fade-in flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-3 text-[13px] text-rose-700">
      <svg aria-hidden viewBox="0 0 20 20" fill="currentColor" className="mt-px h-4 w-4 shrink-0">
        <path fillRule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-4a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 6Zm0 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clipRule="evenodd" />
      </svg>
      {message}
    </div>
  );
}

function Spinner() {
  return <span aria-hidden className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />;
}

function ArrowIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" fill="none" className="h-4 w-4 transition-transform duration-150 group-hover:translate-x-0.5">
      <path d="M3 8h10m0 0L9 4m4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg aria-hidden viewBox="0 0 20 20" fill="none" className="h-[18px] w-[18px]">
      <path d="M1.7 10.3a1 1 0 0 1 0-.6C3 6.1 6.2 3.75 10 3.75s7 2.35 8.3 5.95a1 1 0 0 1 0 .6C17 13.9 13.8 16.25 10 16.25S3 13.9 1.7 10.3Z" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="10" cy="10" r="2.75" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg aria-hidden viewBox="0 0 20 20" fill="none" className="h-[18px] w-[18px]">
      <path d="M3 3l14 14M8.2 8.3a2.75 2.75 0 0 0 3.5 3.5M5.2 5.4C3.6 6.5 2.4 8 1.7 9.7a1 1 0 0 0 0 .6c1.3 3.6 4.5 5.95 8.3 5.95 1.6 0 3-.4 4.3-1.1M8 3.95c.65-.13 1.32-.2 2-.2 3.8 0 7 2.35 8.3 5.95a1 1 0 0 1 0 .6c-.4 1.1-1 2.1-1.75 2.95" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
