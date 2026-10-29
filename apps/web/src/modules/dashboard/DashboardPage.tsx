import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Card, ErrorBox, HeroStat, Spinner, StatCard, Tag } from "../../components/ui";
import { api, qs } from "../../lib/api";
import { useLiveRefresh } from "../../lib/realtime";
import type { DashboardSummary, SeismicEvent } from "../../types";

interface TsPoint {
  bucket: string;
  count: number;
}
interface Bin {
  label: string;
  count: number;
}

/** Rangos de analisis del dashboard (KPIs + graficas). */
const RANGES = [
  { key: "7", label: "Ultimos 7 dias", short: "7 dias" },
  { key: "30", label: "Ultimos 30 dias", short: "30 dias" },
  { key: "365", label: "Ultimo año", short: "1 año" },
];


/** Paleta de apoyo para graficas (indigo de marca + acentos). */
const CHART_COLORS = ["#6c63f5", "#20c4a3", "#ff9d6c", "#f06595", "#4cc3f7"];
const GRID = "#eceef7";
const AXIS = "#8b92ad";
const TOOLTIP_STYLE = {
  borderRadius: 12,
  border: "1px solid #e5e7f2",
  boxShadow: "0 10px 28px -14px rgba(27,42,94,.25)",
  fontSize: 12,
};

const ICONS = {
  clock: "M12 7v5l3 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  calendar: "M5 5h14v15H5zM5 10h14M9 3v4M15 3v4",
  pulse: "M3 12h4l2.5-7 4 14L16 9l1.5 3H21",
  depth: "M12 4v14M6 12l6 6 6-6",
  bell: "M6 16v-5a6 6 0 1 1 12 0v5l2 2H4l2-2zM10 21h4",
};

/** Chip de magnitud para la lista de eventos recientes. */
function magClass(m: number | null | undefined) {
  if (typeof m !== "number") return "bg-slate-100 text-slate-500";
  if (m >= 5) return "bg-red-100 text-red-700";
  if (m >= 4) return "bg-orange-100 text-orange-600";
  return "bg-brand-100 text-brand-700";
}

export default function DashboardPage() {
  const [range, setRange] = useState("7");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [series, setSeries] = useState<TsPoint[]>([]);
  const [bins, setBins] = useState<Bin[]>([]);
  const [latest, setLatest] = useState<SeismicEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  const active = RANGES.find((r) => r.key === range) ?? RANGES[0];

  const load = useCallback(() => {
    const dateFrom = new Date(Date.now() - Number(range) * 86400_000).toISOString();
    const dateTo = new Date().toISOString();
    const period = { date_from: dateFrom, date_to: dateTo };
    Promise.all([
      api<DashboardSummary>("/api/v1/dashboard/summary" + qs(period)),
      api<TsPoint[]>("/api/v1/analytics/timeseries" + qs({ ...period, granularity: "day" })),
      api<Bin[]>("/api/v1/analytics/magnitude-histogram" + qs(period)),
      api<{ items: SeismicEvent[] }>("/api/v1/events" + qs({ limit: 8 })),
    ])
      .then(([s, ts, h, ev]) => {
        setSummary(s);
        setSeries(ts);
        setBins(h);
        setLatest(ev.items);
        setUpdatedAt(new Date().toLocaleTimeString());
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, [range]);

  useEffect(load, [load]);
  // Actualizacion en vivo: cuando entran eventos, los KPIs y graficas se refrescan solos.
  useLiveRefresh(load);

  if (error) return <ErrorBox error={error} />;
  if (!summary) return <Spinner text="Cargando dashboard…" />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Dashboard</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-500">
            {updatedAt ? `Actualizado ${updatedAt}` : ""}
            {summary.period_start && summary.period_end
              ? ` · periodo ${new Date(summary.period_start).toLocaleDateString()} → ${new Date(summary.period_end).toLocaleDateString()}`
              : ""}
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-full border border-slate-200/70 bg-white p-1 text-sm shadow-soft">
          {RANGES.map((r) => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              aria-pressed={range === r.key}
              className={`rounded-full px-4 py-1.5 font-medium transition ${range === r.key
                ? "bg-brand-600 text-white shadow-sm"
                : "text-slate-600 hover:bg-brand-50 hover:text-brand-700"
                }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-7">
        <div className="col-span-2 md:col-span-3 xl:col-span-2">
          <HeroStat label={`Eventos · ${active.short}`} value={summary.total_events} note="Eventos observados en el periodo" />
        </div>
        <StatCard icon={ICONS.clock} tone="mint" label="Ultimas 24 h" value={summary.events_last_24h} />
        <StatCard icon={ICONS.calendar} tone="sky" label="Ultimos 7 dias" value={summary.events_last_7d} />
        <StatCard icon={ICONS.pulse} tone="orange" label={`Mag. max. · ${active.short}`} value={summary.period_max_magnitude ?? "—"} />
        <StatCard icon={ICONS.depth} tone="pink" label={`Profundidad media · ${active.short}`} value={summary.period_avg_depth ?? "—"} hint="km" />
        <StatCard icon={ICONS.bell} tone="brand" label="Alertas activas" value={summary.active_alerts} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-12">
        <div className="md:col-span-2 xl:col-span-7">
          <Card
            title="Eventos a lo largo del tiempo"
            subtitle={`Fuente: sismos observados · granularidad diaria · ${active.short}`}
          >
            {series.length === 0 ? (
              <p className="text-sm text-slate-500">Sin datos en el periodo seleccionado.</p>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={series} margin={{ left: -12, right: 8, top: 8 }}>
                  <defs>
                    <linearGradient id="eventsFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6c63f5" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#6c63f5" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke={GRID} />
                  <XAxis dataKey="bucket" fontSize={11} tickLine={false} axisLine={false} stroke={AXIS} />
                  <YAxis allowDecimals={false} fontSize={11} tickLine={false} axisLine={false} stroke={AXIS} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Area type="monotone" dataKey="count" stroke="#6c63f5" strokeWidth={2.5} fill="url(#eventsFill)" dot={false} activeDot={{ r: 5 }} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>
        </div>

        <div className="xl:col-span-5">
          <Card
            title="Distribucion por magnitud"
            subtitle={`Conteo por rango · ${active.short} · limites de la fuente`}
          >
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={bins} margin={{ left: -12, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} stroke={GRID} />
                <XAxis dataKey="label" fontSize={11} tickLine={false} axisLine={false} stroke={AXIS} />
                <YAxis allowDecimals={false} fontSize={11} tickLine={false} axisLine={false} stroke={AXIS} />
                <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "#f4f5fb" }} />
                <Bar dataKey="count" radius={[8, 8, 0, 0]} maxBarSize={34}>
                  {bins.map((b, i) => (
                    <Cell key={b.label} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
        <Card title="Estado de fuentes" subtitle="Conectores de ingesta">
          <ul className="divide-y divide-slate-100 text-sm">
            {summary.sources.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-2 py-2.5 first:pt-0 last:pb-0">
                <span className="font-medium text-slate-700">{s.name}</span>
                <span className="flex items-center gap-2">
                  <Tag value={s.status} />
                  <span className="text-xs text-slate-400">
                    {s.last_success_at ? new Date(s.last_success_at).toLocaleString() : "sin exito previo"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Ultima sincronizacion">
          <div className="rounded-xl bg-brand-50 px-4 py-3">
            <p className="text-2xl font-bold tracking-tight text-ink">
              {summary.last_sync_at ? new Date(summary.last_sync_at).toLocaleString() : "—"}
            </p>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-slate-500">
            Cada grafica muestra la fuente y el periodo; los valores provienen de eventos observados, no de estimaciones.
            El panel se refresca solo cuando llegan eventos nuevos.
          </p>
        </Card>
        </div>
        <Card title="Eventos recientes">
          <ul className="divide-y divide-slate-100 text-sm">
            {latest.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                <Link to="/eventos" className="flex min-w-0 items-center gap-3 text-slate-700 hover:text-brand-700">
                  <span className={`grid h-9 min-w-9 shrink-0 place-items-center rounded-full px-1 text-xs font-bold tabular-nums ${magClass(e.magnitude)}`}>
                    {e.magnitude ?? "s/m"}
                  </span>
                  <span className="truncate font-medium">{e.place ?? "sin lugar"}</span>
                </Link>
                <span className="shrink-0 text-xs text-slate-400">
                  {new Date(e.occurred_at).toLocaleDateString()}
                </span>
              </li>
            ))}
            {latest.length === 0 && <li className="italic text-slate-500">Sin eventos sincronizados.</li>}
          </ul>
        </Card>
      </div>
    </div>
  );
}
