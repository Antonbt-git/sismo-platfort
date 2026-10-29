import type { ReactNode } from "react";

/** Cabecera de pagina estandar para los modulos (titulo + descripcion + acciones). */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 pb-1">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, subtitle, children, action }: { title?: string; subtitle?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200/60 bg-white shadow-soft">
      {title && (
        <div className="flex items-start justify-between gap-3 px-5 pt-5">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold tracking-tight text-ink">{title}</h2>
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div className={title ? "p-5 pt-4" : "p-5"}>{children}</div>
    </section>
  );
}

export type Tone = "brand" | "mint" | "sky" | "orange" | "pink";

const TONES: Record<Tone, string> = {
  brand: "bg-brand-100 text-brand-600",
  mint: "bg-emerald-100 text-emerald-600",
  sky: "bg-sky-100 text-sky-600",
  orange: "bg-orange-100 text-orange-500",
  pink: "bg-pink-100 text-pink-500",
};

/** Icono circular de color (kpis y listas). `d` es el trazo SVG de 24x24. */
export function IconChip({ d, tone = "brand", className = "h-10 w-10" }: { d: string; tone?: Tone; className?: string }) {
  return (
    <span className={`grid ${className} shrink-0 place-items-center rounded-full ${TONES[tone]}`}>
      <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d={d} />
      </svg>
    </span>
  );
}

export function StatCard({
  label, value, hint, icon, tone = "brand",
}: { label: string; value: ReactNode; hint?: string; icon?: string; tone?: Tone }) {
  return (
    <div className="rounded-2xl border border-slate-200/60 bg-white px-4 py-4 shadow-soft">
      {icon && <IconChip d={icon} tone={tone} />}
      <p className={`text-xs font-medium text-slate-500 ${icon ? "mt-3" : ""}`}>{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums tracking-tight text-ink">
        {value}
        {hint && <span className="ml-1 text-sm font-medium text-slate-400">{hint}</span>}
      </p>
    </div>
  );
}

/** Tarjeta destacada con degradado de marca: la cifra principal de la pantalla. */
export function HeroStat({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="relative flex h-full min-h-[8.5rem] flex-col justify-between overflow-hidden rounded-2xl bg-gradient-to-br from-brand-500 via-brand-600 to-ink p-5 text-white shadow-soft">
      {/* Ondas decorativas: referencia visual a la señal sismica */}
      <svg viewBox="0 0 200 80" className="pointer-events-none absolute -right-2 top-3 h-16 w-40 text-white/15" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M0 44h40l10-30 18 62 16-46 8 14h108" />
      </svg>
      <p className="text-sm font-medium text-white/80">{label}</p>
      <div>
        <p className="text-4xl font-bold tabular-nums tracking-tight">{value}</p>
        {note && <p className="mt-1 text-xs text-white/70">{note}</p>}
      </div>
    </div>
  );
}

const TAG_STYLES: Record<string, string> = {
  observed: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  pending_approval: "bg-amber-100 text-amber-800 ring-amber-600/20",
  approved: "bg-sky-100 text-sky-800 ring-sky-600/20",
  sent: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  failed: "bg-red-100 text-red-800 ring-red-600/20",
  cancelled: "bg-slate-100 text-slate-600 ring-slate-500/20",
  critical: "bg-red-100 text-red-800 ring-red-600/20",
  warning: "bg-amber-100 text-amber-800 ring-amber-600/20",
  info: "bg-sky-100 text-sky-800 ring-sky-600/20",
  ok: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  error: "bg-red-100 text-red-800 ring-red-600/20",
  unknown: "bg-slate-100 text-slate-600 ring-slate-500/20",
  candidate: "bg-amber-100 text-amber-800 ring-amber-600/20",
  approved_model: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  experimental: "bg-purple-100 text-purple-800 ring-purple-600/20",
  done: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  running: "bg-sky-100 text-sky-800 ring-sky-600/20",
  completed: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  success: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
};

const TAG_LABELS: Record<string, string> = {
  observed: "observado",
  pending_approval: "pendiente",
  approved: "aprobado",
  sent: "enviada",
  failed: "fallida",
  cancelled: "cancelada",
};

export function Tag({ value }: { value: string }) {
  const cls = TAG_STYLES[value] ?? "bg-slate-100 text-slate-700 ring-slate-500/20";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}`}>
      {TAG_LABELS[value] ?? value}
    </span>
  );
}

export function Badge({ text }: { text: string }) {
  return (
    <span className="inline-block rounded-md bg-purple-700 px-2 py-0.5 text-xs font-bold text-white">
      {text}
    </span>
  );
}

export function ErrorBox({ error }: { error: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700"
    >
      <svg viewBox="0 0 24 24" className="mt-0.5 h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7.5v5M12 16v.01" />
      </svg>
      <span>{error}</span>
    </div>
  );
}

export function Spinner({ text = "Cargando…" }: { text?: string }) {
  return (
    <div className="flex items-center gap-2.5 py-2 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
      {text}
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-slate-300 bg-brand-50/40 px-4 py-8 text-center">
      <svg viewBox="0 0 24 24" className="h-6 w-6 text-slate-400" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 12h4l2.5-7 4 14L16 9l1.5 3H21" />
      </svg>
      <p className="text-sm text-slate-500">{text}</p>
    </div>
  );
}

export function Pagination({
  offset, limit, total, onChange,
}: { offset: number; limit: number; total: number; onChange: (offset: number) => void }) {
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));
  const btn =
    "rounded-xl border border-slate-200 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-brand-50 hover:text-brand-700 disabled:opacity-40 disabled:hover:bg-white disabled:hover:text-slate-600";
  return (
    <div className="flex items-center gap-3 text-sm text-slate-600">
      <button disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))} className={btn}>
        Anterior
      </button>
      <span className="tabular-nums">
        Pagina {page} de {pages} — {total} registros
      </span>
      <button
        disabled={offset + limit >= total}
        onClick={() => onChange(offset + limit)}
        className={btn}
      >
        Siguiente
      </button>
    </div>
  );
}
