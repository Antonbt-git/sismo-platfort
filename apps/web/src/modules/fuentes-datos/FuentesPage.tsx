import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Card, EmptyState, ErrorBox, Tag } from "../../components/ui";
import { api } from "../../lib/api";
import type { DataSource } from "../../types";
import { useAuth } from "../../app/AuthContext";

interface Run {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  records_seen: number;
  records_inserted: number;
  records_updated: number;
  error_summary: string | null;
}

const EMPTY_FORM = {
  name: "",
  organization: "",
  base_url: "",
  source_type: "rest",
  license: "",
  contact: "",
  frequency_minutes: "5",
};

const SOURCE_TYPES = [
  { value: "rest", label: "REST / JSON (formato CENSIS-IGP)" },
  { value: "graphql", label: "GraphQL" },
  { value: "otro", label: "Otro formato" },
];

export default function FuentesPage() {
  const { hasRole } = useAuth();
  const [sources, setSources] = useState<DataSource[]>([]);
  const [runsBySource, setRunsBySource] = useState<Record<string, Run[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const load = useCallback(() => {
    api<DataSource[]>("/api/v1/sources")
      .then(setSources)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  async function createSource(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      await api("/api/v1/sources", {
        method: "POST",
        json: {
          name: form.name.trim(),
          organization: form.organization.trim(),
          base_url: form.base_url.trim(),
          source_type: form.source_type,
          license: form.license.trim(),
          contact: form.contact.trim(),
          frequency_minutes: Number(form.frequency_minutes) || 5,
        },
      });
      setMsg(
        `Fuente «${form.name.trim()}» creada. Se sincronizara sola en el proximo ciclo del daemon` +
          " (o pulse «Sincronizar ahora»). Queda registrada en auditoria.",
      );
      setForm(EMPTY_FORM);
      setShowForm(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear la fuente");
    } finally {
      setBusy(false);
    }
  }

  async function sync(id: string) {
    setError(null);
    setMsg(null);
    try {
      const run = await api<Run>(`/api/v1/sources/${id}/sync`, { method: "POST" });
      setMsg(`Sincronizacion encolada (ejecucion ${run.id.slice(0, 8)}…). Refresque en unos segundos.`);
      setTimeout(load, 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al sincronizar");
    }
  }

  async function remove(source: DataSource) {
    if (!window.confirm(
      `¿Eliminar la fuente «${source.name}»?\n\nSe eliminarán su bitácora de ejecuciones y los eventos observados asociados. Esta acción no se puede deshacer.`,
    )) {
      return;
    }
    setError(null);
    setMsg(null);
    try {
      await api(`/api/v1/sources/${source.id}`, { method: "DELETE" });
      setMsg(`Fuente «${source.name}» eliminada.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al eliminar la fuente");
    }
  }

  async function toggle(source: DataSource) {
    await api(`/api/v1/sources/${source.id}/status?enabled=${!source.enabled}`, { method: "PATCH" });
    load();
  }

  async function showRuns(id: string) {
    const runs = await api<Run[]>(`/api/v1/sources/${id}/runs?limit=10`);
    setRunsBySource((prev) => ({ ...prev, [id]: runs }));
  }

  const input = "mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Fuentes de datos</h1>
          <p className="text-xs text-slate-500 max-w-3xl">
            Conectores de ingesta con procedencia, licencia, latencia y bitacora de ejecuciones. Las fuentes
            habilitadas se sincronizan solas en cada ciclo del daemon. Los secretos se manejan por referencia
            (variables/secret manager), nunca en texto plano.
          </p>
        </div>
        {hasRole("analyst") && !showForm && (
          <button
            onClick={() => { setShowForm(true); setError(null); setMsg(null); }}
            className="rounded bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700"
          >
            Agregar fuente
          </button>
        )}
      </div>

      {error && <ErrorBox error={error} />}
      {msg && <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}

      {showForm && hasRole("analyst") && (
        <Card
          title="Nueva fuente de datos"
          subtitle="Alta auditada · sin credenciales en claro: referencie secretos por entorno"
        >
          <form onSubmit={createSource} className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <label className="block text-sm text-slate-700">
              Nombre *
              <input required minLength={3} maxLength={120} value={form.name} placeholder="IGP / CENSIS (estacion norte)"
                onChange={(e) => setForm({ ...form, name: e.target.value })} className={input} />
            </label>
            <label className="block text-sm text-slate-700">
              Organizacion *
              <input required minLength={2} maxLength={120} value={form.organization} placeholder="Instituto Geofisico del Peru"
                onChange={(e) => setForm({ ...form, organization: e.target.value })} className={input} />
            </label>
            <label className="block text-sm text-slate-700">
              Endpoint (URL) *
              <input required type="url" maxLength={500} value={form.base_url}
                placeholder="https://censis.igp.gob.pe/api/ultimo-sismo/sismos"
                onChange={(e) => setForm({ ...form, base_url: e.target.value })} className={input} />
            </label>
            <label className="block text-sm text-slate-700">
              Tipo de fuente
              <select value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value })} className={input}>
                {SOURCE_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
            <label className="block text-sm text-slate-700">
              Frecuencia (minutos)
              <input type="number" min={1} max={1440} value={form.frequency_minutes}
                onChange={(e) => setForm({ ...form, frequency_minutes: e.target.value })} className={input} />
            </label>
            <label className="block text-sm text-slate-700">
              Licencia / condiciones de uso
              <input maxLength={255} value={form.license} placeholder="Informacion oficial; citar fuente y enlace"
                onChange={(e) => setForm({ ...form, license: e.target.value })} className={input} />
            </label>
            <label className="block text-sm text-slate-700">
              Contacto / propietario
              <input maxLength={255} value={form.contact} placeholder="https://www.igp.gob.pe"
                onChange={(e) => setForm({ ...form, contact: e.target.value })} className={input} />
            </label>

            <div className="md:col-span-2 lg:col-span-3 text-xs text-slate-500">
              El conector implementado interpreta el formato del CENSIS/IGP (REST/JSON). Si la fuente usa otro
              formato, la ejecucion quedara registrada con error en la bitacora hasta que se incorpore su conector.
            </div>

            <div className="flex gap-2 lg:col-span-3">
              <button type="submit" disabled={busy}
                className="rounded bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50">
                {busy ? "Creando…" : "Crear fuente"}
              </button>
              <button type="button" onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}
                className="rounded border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50">
                Cancelar
              </button>
            </div>
          </form>
        </Card>
      )}

      {sources.length === 0 ? (
        <EmptyState text="Sin fuentes configuradas." />
      ) : (
        <div className="space-y-3">
          {sources.map((s) => (
            <Card key={s.id} title={s.name} subtitle={`${s.organization} · ${s.license}`}>
              <div className="flex flex-wrap items-center gap-4 text-sm">
                <span>Estado: <Tag value={s.status} /></span>
                <span>Habilitada: {s.enabled ? "si" : "no"}</span>
                <span>Frecuencia: cada {s.frequency_minutes} min</span>
                <span>Ultimo exito: {s.last_success_at ? new Date(s.last_success_at).toLocaleString() : "—"}</span>
                <span>Latencia: {s.last_latency_ms !== null ? `${s.last_latency_ms} ms` : "—"}</span>
                <a href={s.base_url} target="_blank" rel="noreferrer" className="text-brand-700 underline">Endpoint</a>
              </div>
              <div className="flex gap-2 mt-3">
                {hasRole("analyst") && (
                  <>
                    <button onClick={() => sync(s.id)}
                      className="rounded bg-brand-600 px-3 py-1 text-sm text-white hover:bg-brand-700">
                      Sincronizar ahora
                    </button>
                    <button onClick={() => toggle(s)}
                      className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50">
                      {s.enabled ? "Deshabilitar" : "Habilitar"}
                    </button>
                    <button onClick={() => remove(s)}
                      className="rounded border border-red-300 px-3 py-1 text-sm text-red-700 hover:bg-red-50">
                      Eliminar
                    </button>
                  </>
                )}
                <button onClick={() => showRuns(s.id)}
                  className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50">
                  Ver ejecuciones
                </button>
              </div>
              {runsBySource[s.id] && (
                <table className="w-full text-xs mt-3">
                  <thead className="bg-slate-50 text-slate-500 text-left">
                    <tr>
                      <th className="px-2 py-1">Inicio</th>
                      <th className="px-2 py-1">Estado</th>
                      <th className="px-2 py-1">Vistos</th>
                      <th className="px-2 py-1">Insertados</th>
                      <th className="px-2 py-1">Actualizados</th>
                      <th className="px-2 py-1">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runsBySource[s.id].map((r) => (
                      <tr key={r.id} className="border-t border-slate-100">
                        <td className="px-2 py-1">{new Date(r.started_at).toLocaleString()}</td>
                        <td className="px-2 py-1"><Tag value={r.status} /></td>
                        <td className="px-2 py-1">{r.records_seen}</td>
                        <td className="px-2 py-1">{r.records_inserted}</td>
                        <td className="px-2 py-1">{r.records_updated}</td>
                        <td className="px-2 py-1 text-red-600">{r.error_summary ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
