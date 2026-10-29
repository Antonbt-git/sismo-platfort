import { useCallback, useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import type { LatLngExpression } from "leaflet";
import { Card, ErrorBox, Spinner } from "../../components/ui";
import { api, qs } from "../../lib/api";
import { useLiveRefresh } from "../../lib/realtime";

interface GeoProps {
  id: string;
  magnitude: number | null;
  depth_km: number | null;
  place: string | null;
  occurred_at: string;
  source_url: string | null;
}
interface Feature {
  geometry: { coordinates: [number, number] };
  properties: GeoProps;
}

const PERU_CENTER: LatLngExpression = [-9.2, -75.0];
/** Limite del endpoint geojson (Query le=5000). */
const MAX_LIMIT = 5000;

const PERIODS = [
  { value: "7", label: "7 dias" },
  { value: "30", label: "30 dias" },
  { value: "90", label: "90 dias" },
  { value: "all", label: "Todo" },
];

const DEPTH_BANDS = [
  { value: "all", label: "Toda la profundidad" },
  { value: "shallow", label: "Superficial (< 70 km)" },
  { value: "mid", label: "Intermedia (70 - 300 km)" },
  { value: "deep", label: "Profunda (> 300 km)" },
];

const MAG_PRESETS = [
  { label: "Todos", min: 0, max: 10 },
  { label: "M  4", min: 4, max: 10 },
  { label: "M  5", min: 5, max: 10 },
  { label: "M  6", min: 6, max: 10 },
];

function magColor(mag: number | null): string {
  if (mag === null) return "#94a3b8";
  if (mag < 4) return "#22c55e";
  if (mag < 5) return "#eab308";
  if (mag < 6) return "#f97316";
  return "#dc2626";
}

/** Busca sin distinguir mayusculas ni acentos ("piura" encuentra "Piura"). */
function normalize(text: string): string {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function depthInBand(depth: number | null, band: string): boolean {
  if (band === "all") return true;
  if (depth === null) return false;
  if (band === "shallow") return depth < 70;
  if (band === "mid") return depth >= 70 && depth <= 300;
  return depth > 300;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <span className="inline-flex items-baseline gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 shadow-sm">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">{label}</span>
      <span className="text-sm font-semibold tabular-nums text-ink">{value}</span>
    </span>
  );
}

export default function MapaPage() {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState("30");
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  // Filtros en el navegador: instantaneos mientras se arrastra la barra.
  const [magMin, setMagMin] = useState(0);
  const [magMax, setMagMax] = useState(10);
  const [depthBand, setDepthBand] = useState("all");
  const [placeQuery, setPlaceQuery] = useState("");

  // silent=true (actualizacion en vivo) no oculta el mapa: conserva centro y zoom.
  const load = useCallback(
    (silent = false) => {
      const dateFrom =
        days === "all" ? undefined : new Date(Date.now() - Number(days) * 86400_000).toISOString();
      if (!silent) setLoading(true);
      api<{ features: Feature[] }>(
        "/api/v1/events/geojson" + qs({ date_from: dateFrom, limit: MAX_LIMIT }),
      )
        .then((fc) => {
          setFeatures(fc.features);
          setError(null);
          setHasLoaded(true);
          setUpdatedAt(new Date().toLocaleTimeString());
        })
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    },
    [days],
  );

  useEffect(() => load(), [load]);
  // En vivo: los marcadores nuevos aparecen sin recargar la pagina.
  useLiveRefresh(() => load(true));

  const filtered = useMemo(() => {
    const q = placeQuery.trim() ? normalize(placeQuery) : null;
    return features.filter((f) => {
      const p = f.properties;
      // Sin magnitud registrada solo se muestra con el rango completo.
      if (p.magnitude === null) {
        if (magMin > 0 || magMax < 10) return false;
      } else if (p.magnitude < magMin || p.magnitude > magMax) {
        return false;
      }
      if (!depthInBand(p.depth_km, depthBand)) return false;
      if (q && !normalize(p.place ?? "").includes(q)) return false;
      return true;
    });
  }, [features, magMin, magMax, depthBand, placeQuery]);

  const stats = useMemo(() => {
    const mags = filtered
      .map((f) => f.properties.magnitude)
      .filter((m): m is number => m !== null);
    const depths = filtered
      .map((f) => f.properties.depth_km)
      .filter((d): d is number => d !== null);
    return {
      maxMag: mags.length ? Math.max(...mags) : null,
      avgDepth: depths.length
        ? Math.round(depths.reduce((a, b) => a + b, 0) / depths.length)
        : null,
    };
  }, [filtered]);

  const legend = useMemo(() => {
    const counts = { lt4: 0, b45: 0, b56: 0, ge6: 0, na: 0 };
    for (const f of filtered) {
      const m = f.properties.magnitude;
      if (m === null) counts.na++;
      else if (m < 4) counts.lt4++;
      else if (m < 5) counts.b45++;
      else if (m < 6) counts.b56++;
      else counts.ge6++;
    }
    return [
      { color: "#22c55e", label: "M < 4", count: counts.lt4 },
      { color: "#eab308", label: "4 - 5", count: counts.b45 },
      { color: "#f97316", label: "5 - 6", count: counts.b56 },
      { color: "#dc2626", label: "M >= 6", count: counts.ge6 },
      { color: "#94a3b8", label: "s/m", count: counts.na },
    ];
  }, [filtered]);

  function clearFilters() {
    setMagMin(0);
    setMagMax(10);
    setDepthBand("all");
    setPlaceQuery("");
  }

  const minPct = (magMin / 10) * 100;
  const maxPct = (magMax / 10) * 100;
  const filtersActive = magMin > 0 || magMax < 10 || depthBand !== "all" || placeQuery.trim() !== "";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Mapa sismico</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-500">
            Eventos observados · actualizado {updatedAt ?? "—"} · fuente: IGP / CENSIS
            {features.length >= MAX_LIMIT && " · limite de datos alcanzado, se muestran los mas recientes"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Stat label="En vista" value={filtered.length} />
          <Stat label="Mag. max" value={stats.maxMag !== null ? stats.maxMag.toFixed(1) : "—"} />
          <Stat label="Prof. media" value={stats.avgDepth !== null ? `${stats.avgDepth} km` : "—"} />
        </div>
      </div>

      {error && hasLoaded && <ErrorBox error={error} />}

      <div className="flex flex-col gap-4 lg:flex-row">
        {/* ---------- Panel de filtros ---------- */}
        <aside className="w-full shrink-0 space-y-4 lg:w-80">
          <Card title="Filtros" subtitle="Se aplican al instante sobre los datos del periodo">
            <div className="space-y-5">
              {/* Periodo (servidor) */}
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Periodo
                </label>
                <div className="mt-1.5 grid grid-cols-4 gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
                  {PERIODS.map((p) => (
                    <button
                      key={p.value}
                      type="button"
                      onClick={() => setDays(p.value)}
                      className={`rounded-md px-1 py-1.5 text-xs font-medium transition ${days === p.value
                        ? "bg-white text-ink shadow-sm ring-1 ring-slate-200"
                        : "text-slate-500 hover:text-slate-700"
                        }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Magnitud: barra dual ajustable */}
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Magnitud
                  </label>
                  <span className="text-xs text-slate-400">arrastrable</span>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs font-medium text-slate-600">
                  <span className="rounded-md bg-slate-100 px-2 py-1 tabular-nums">M {magMin.toFixed(1)}</span>
                  <span className="rounded-md bg-slate-100 px-2 py-1 tabular-nums">M {magMax.toFixed(1)}</span>
                </div>
                <div className="relative mt-2 h-6">
                  <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-slate-200" />
                  <div
                    className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full"
                    style={{
                      left: `${minPct}%`,
                      width: `${maxPct - minPct}%`,
                      background:
                        "linear-gradient(90deg,#22c55e 0%,#eab308 45%,#f97316 72%,#dc2626 100%)",
                    }}
                  />
                  <input
                    type="range"
                    min={0}
                    max={10}
                    step={0.1}
                    value={magMin}
                    aria-label="Magnitud minima"
                    onChange={(e) => setMagMin(Math.min(Number(e.target.value), magMax))}
                    className="mag-range"
                  />
                  <input
                    type="range"
                    min={0}
                    max={10}
                    step={0.1}
                    value={magMax}
                    aria-label="Magnitud maxima"
                    onChange={(e) => setMagMax(Math.max(Number(e.target.value), magMin))}
                    className="mag-range"
                  />
                </div>
                <div className="mt-3 grid grid-cols-4 gap-1.5">
                  {MAG_PRESETS.map((p) => {
                    const active = magMin === p.min && magMax === p.max;
                    return (
                      <button
                        key={p.label}
                        type="button"
                        onClick={() => {
                          setMagMin(p.min);
                          setMagMax(p.max);
                        }}
                        className={`rounded-md border px-1 py-1.5 text-xs font-medium transition ${active
                          ? "border-brand-600 bg-brand-50 text-brand-700"
                          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                          }`}
                      >
                        {p.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Profundidad */}
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Profundidad
                </label>
                <select
                  value={depthBand}
                  onChange={(e) => setDepthBand(e.target.value)}
                  className="mt-1.5 w-full px-3 py-2 text-sm"
                >
                  {DEPTH_BANDS.map((b) => (
                    <option key={b.value} value={b.value}>
                      {b.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Lugar */}
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Lugar
                </label>
                <div className="relative mt-1.5">
                  <svg
                    viewBox="0 0 24 24"
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  >
                    <circle cx="11" cy="11" r="7" />
                    <path d="m20 20-3.5-3.5" />
                  </svg>
                  <input
                    type="text"
                    value={placeQuery}
                    onChange={(e) => setPlaceQuery(e.target.value)}
                    placeholder="region, provincia, ciudad…"
                    className="w-full py-2 pl-9 pr-3 text-sm"
                  />
                </div>
              </div>
            </div>

            <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-500">
              <span>
                <strong className="text-ink">{filtered.length}</strong> de {features.length} eventos
              </span>
              <button
                type="button"
                onClick={clearFilters}
                disabled={!filtersActive}
                className="font-medium text-brand-700 transition hover:text-brand-800 disabled:cursor-not-allowed disabled:text-slate-300"
              >
                Limpiar filtros
              </button>
            </div>
          </Card>
        </aside>

        {/* ---------- Mapa ---------- */}
        <div className="relative min-w-0 flex-1">
          {!hasLoaded ? (
            <div className="grid min-h-[360px] place-items-center rounded-xl border border-slate-200 bg-white">
              {error ? (
                <div className="max-w-md px-4">
                  <ErrorBox error={error} />
                </div>
              ) : (
                <Spinner text="Cargando capa de eventos…" />
              )}
            </div>
          ) : (
            <>
              <MapContainer
                center={PERU_CENTER}
                zoom={5}
                scrollWheelZoom
                className="leaflet-container border border-slate-200"
              >
                <TileLayer
                  attribution="&copy; OpenStreetMap contributors"
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {filtered.map((f) => {
                  const [lon, lat] = f.geometry.coordinates;
                  const p = f.properties;
                  const radius = p.magnitude ? Math.max(4, p.magnitude * 2) : 4;
                  return (
                    <CircleMarker
                      key={p.id}
                      center={[lat, lon]}
                      radius={radius}
                      pathOptions={{
                        color: "#ffffff",
                        weight: 1.5,
                        fillColor: magColor(p.magnitude),
                        fillOpacity: 0.8,
                      }}
                    >
                      <Tooltip>{`${p.magnitude ?? "s/m"} — ${p.place ?? ""}`}</Tooltip>
                      <Popup minWidth={250}>
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-2">
                            <span
                              className="rounded px-1.5 py-0.5 text-xs font-bold text-white"
                              style={{ backgroundColor: magColor(p.magnitude) }}
                            >
                              {p.magnitude !== null ? `M ${p.magnitude}` : "s/m"}
                            </span>
                            <span className="text-xs text-slate-500">
                              {p.depth_km !== null ? `${p.depth_km} km` : "prof. n/d"}
                            </span>
                          </div>
                          <p className="font-semibold text-slate-800">{p.place ?? "Sin lugar"}</p>
                          <p className="text-xs text-slate-500">
                            {new Date(p.occurred_at).toLocaleString()}
                          </p>
                          {p.source_url && (
                            <a
                              href={p.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-block text-sm text-brand-700 underline"
                            >
                              Ver en la fuente
                            </a>
                          )}
                          <p className="border-t border-slate-100 pt-1.5 text-[11px] text-slate-400">
                            Evento observado; no es estimacion ni alerta oficial.
                          </p>
                        </div>
                      </Popup>
                    </CircleMarker>
                  );
                })}
              </MapContainer>

              {loading && (
                <span className="absolute right-3 top-3 z-[1000] inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/95 px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
                  Actualizando…
                </span>
              )}

              {!loading && filtered.length === 0 && (
                <div className="pointer-events-none absolute inset-0 z-[1000] grid place-items-center">
                  <div className="rounded-xl border border-slate-200 bg-white/95 px-5 py-4 text-center shadow-lg">
                    <p className="text-sm font-medium text-slate-700">
                      Sin eventos con estos filtros
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Amplie el rango de magnitud o limpie los filtros
                    </p>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ---------- Leyenda con conteos ---------- */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
        <span className="font-medium text-slate-700">Leyenda</span>
        {legend.map((l) => (
          <span key={l.label} className="flex items-center gap-1.5">
            <span
              className="h-3 w-3 rounded-full ring-1 ring-black/5"
              style={{ backgroundColor: l.color }}
            />
            <span className="text-slate-600">{l.label}</span>
            <span className="tabular-nums text-slate-400">({l.count})</span>
          </span>
        ))}
      </div>
    </div>
  );
}
