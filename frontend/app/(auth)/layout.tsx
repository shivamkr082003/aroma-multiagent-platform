import { Brand, ShowcasePanel } from "./_components/ShowcasePanel";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-white font-sans text-slate-900 lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <ShowcasePanel />

      <main className="relative flex min-h-dvh flex-col px-4 py-6 sm:px-8 lg:px-12">
        {/* Faint brand glow so the form side isn't flat white */}
        <div aria-hidden className="pointer-events-none absolute right-0 top-0 h-72 w-72 rounded-full bg-orange-200/40 blur-[110px]" />

        <div className="relative lg:hidden">
          <Brand />
        </div>

        <div className="relative mx-auto flex w-full max-w-[400px] flex-1 flex-col justify-center py-10">{children}</div>

        <p className="relative text-center text-[12px] text-slate-400">
          Aroma AI can make mistakes. Verify important information.
        </p>
      </main>
    </div>
  );
}
