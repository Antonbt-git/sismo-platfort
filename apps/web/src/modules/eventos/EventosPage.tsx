import { useCallback, useEffect, useState } from "react";
import { Card, EmptyState, ErrorBox, Pagination, Spinner, Tag } from "../../components/ui";
import { api, qs } from "../../lib/api";
import { useLiveRefresh } from "../../lib/realtime";
import type { SeismicEvent } from "../../types";

const LIMIT = 25;

export default function EventosPage() {
  const [events, setEvents] = useState<SeismicEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<SeismicEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ date_from: "", date_to: "", min_magnitude: "", place: "" });

  // silent=true (actualizacion en vivo) no muestra spinner: la tabla permanece
  // visible mientras llegan los eventos nuevos.
  const load = useCallback(
    (silent = false) => {
      if (!silent) setLoading(true);
      api<{ items: SeismicEvent[]; total: number }>(
        "/api/v1/events" + qs({ ...filters, offset, limit: LIMIT }),
      )
        .then((page) => {
          setEvents(page.items);
          setTotal(page.total);
        })
        .catch((e) => setError(e.message))
        .finally(() => {
          if (!silent) setLoading(false);
        });
    },
    [filters, offset],
  );

  useEffect(() => load(), [load]);
  // En vivo: si entra un evento nuevo, la pagina actual se refresca sola.
  useLiveRefresh(() => load(true));

  const input = "rounded border border-slate-300 px-2 py-1 text-sm";

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold tracking-tight text-ink">Eventos sismicos observados</h1>

      <div className="flex flex-wrap gap-3 items-end bg-white rounded-lg border border-slate-200 p-3">
        <label className="text-sm text-slate-600">
          Desde
          <input type="date" className={`${input} ml-2`} value={filters.date_from}
            onChange={(e) => { setOffset(0); setFilters({ ...filters, date_from: e.target.value }); }} />
        </label>
        <label className="text-sm text-slate-600">
          Hasta
          <input type="date" className={`${input} ml-2`} value={filters.date_to}
            onChange={(e) => { setOffset(0); setFilters({ ...filters, date_to: e.target.value }); }} />
        </label>
        <label className="text-sm text-slate-600">
          Mag. min.
          <input type="number" step="0.1" min="0" max="10" className={`${input} ml-2 w-20`} value={filters.min_magnitude}
            onChange={(e) => { setOffset(0); setFilters({ ...filters, min_magnitude: e.target.value }); }} />
        </label>
        <label className="text-sm text-slate-600">
          Lugar
          <input type="text" placeholder="buscar" className={`${input} ml-2`} value={filters.place}
            onChange={(e) => { setOffset(0); setFilters({ ...filters, place: e.target.value }); }} />
        </label>
        <button
          className="text-sm text-brand-700 underline"
          onClick={() => { setOffset(0); setFilters({ date_from: "", date_to: "", min_magnitude: "", place: "" }); }}
        >
          Limpiar
        </button>
      </div>

      {error && <ErrorBox error={error} />}
      {loading ? (
        <Spinner />
      ) : events.length === 0 ? (
        <EmptyState text="No hay eventos con estos filtros. Sincronice la fuente desde 'Fuentes de datos'." />
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-left">
              <tr>
                <th className="px-3 py-2">Fecha (UTC)</th>
                <th className="px-3 py-2">Magnitud</th>
                <th className="px-3 py-2">Prof. (km)</th>
                <th className="px-3 py-2">Lugar</th>
                <th className="px-3 py-2">Estado</th>
                <th className="px-3 py-2">Procedencia</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                  onClick={() => setSelected(e)}>
                  <td className="px-3 py-1.5 whitespace-nowrap">{new Date(e.occurred_at).toLocaleString()}</td>
                  <td className="px-3 py-1.5">{e.magnitude ?? "s/m"} <span className="text-xs text-slate-400">{e.magnitude_type}</span></td>
                  <td className="px-3 py-1.5">{e.depth_km ?? "s/d"}</td>
                  <td className="px-3 py-1.5">{e.place ?? "—"}</td>
                  <td className="px-3 py-1.5"><Tag value={e.review_status} /></td>
                  <td className="px-3 py-1.5">
                    {e.source_url ? (
                      <a href={e.source_url} target="_blank" rel="noreferrer" className="text-brand-700 underline"
                        onClick={(ev) => ev.stopPropagation()}>
                        fuente
                      </a>
                    ) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination offset={offset} limit={LIMIT} total={total} onChange={setOffset} />

      {selected && (
        <Card title="Detalle del evento" subtitle="Ficha con procedencia verificable">
          <button className="text-sm text-slate-500 underline mb-2" onClick={() => setSelected(null)}>Cerrar</button>
          <dl className="grid md:grid-cols-2 gap-x-6 gap-y-1 text-sm">
            <div><dt className="text-slate-500 inline">ID externo: </dt><dd className="inline">{selected.external_id}</dd></div>
            <div><dt className="text-slate-500 inline">Ocurre (UTC): </dt><dd className="inline">{new Date(selected.occurred_at).toISOString()}</dd></div>
            <div><dt className="text-slate-500 inline">Lat/Lon: </dt><dd className="inline">{selected.latitude}, {selected.longitude}</dd></div>
            <div><dt className="text-slate-500 inline">Magnitud: </dt><dd className="inline">{selected.magnitude} ({selected.magnitude_type ?? "n/d"})</dd></div>
            <div><dt className="text-slate-500 inline">Profundidad: </dt><dd className="inline">{selected.depth_km ?? "n/d"} km</dd></div>
            <div><dt className="text-slate-500 inline">Region: </dt><dd className="inline">{selected.region ?? "—"}</dd></div>
            <div><dt className="text-slate-500 inline">Recibido: </dt><dd className="inline">{new Date(selected.received_at).toLocaleString()}</dd></div>
            <div><dt className="text-slate-500 inline">Enlace fuente: </dt>
              <dd className="inline">{selected.source_url
                ? <a className="text-brand-700 underline" href={selected.source_url} target="_blank" rel="noreferrer">ver original</a>
                : "sin enlace"}</dd></div>
          </dl>
          <p className="text-xs text-slate-400 mt-3">
            Evento observado reportado por el proveedor de datos. No representa una prediccion ni un aviso oficial.
          </p>
        </Card>
      )}
    </div>
  );
}
