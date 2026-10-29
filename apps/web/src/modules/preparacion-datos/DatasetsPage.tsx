import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Card, EmptyState, ErrorBox, Spinner, Tag } from "../../components/ui";
import { api } from "../../lib/api";
import type { Dataset } from "../../types";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Dataset | null>(null);
  const [form, setForm] = useState({ name: "eventos-peru", date_from: "", date_to: "", min_magnitude: "" });

  const load = useCallback(() => {
    api<Dataset[]>("/api/v1/datasets")
      .then(setDatasets)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/api/v1/datasets", {
        method: "POST",
        json: {
          name: form.name,
          date_from: form.date_from ? new Date(form.date_from).toISOString() : null,
          date_to: form.date_to ? new Date(form.date_to).toISOString() : null,
          min_magnitude: form.min_magnitude ? Number(form.min_magnitude) : null,
        },
      });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear dataset");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Preparacion de datos</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          Datasets versionados e inmutables con informe de calidad; base reproducible del entrenamiento ML.
        </p>
      </div>

      <Card title="Crear dataset versionado" subtitle="Cada ejecucion genera una nueva version con su informe de calidad">
        <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3 text-sm">
          <label className="text-slate-600">Nombre
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="ml-2 rounded border border-slate-300 px-2 py-1" />
          </label>
          <label className="text-slate-600">Desde
            <input type="date" value={form.date_from}
              onChange={(e) => setForm({ ...form, date_from: e.target.value })}
              className="ml-2 rounded border border-slate-300 px-2 py-1" />
          </label>
          <label className="text-slate-600">Hasta
            <input type="date" value={form.date_to}
              onChange={(e) => setForm({ ...form, date_to: e.target.value })}
              className="ml-2 rounded border border-slate-300 px-2 py-1" />
          </label>
          <label className="text-slate-600">Mag. min.
            <input type="number" step="0.1" min="0" max="10" value={form.min_magnitude}
              onChange={(e) => setForm({ ...form, min_magnitude: e.target.value })}
              className="ml-2 w-20 rounded border border-slate-300 px-2 py-1" />
          </label>
          <button type="submit" disabled={busy}
            className="rounded bg-brand-600 px-3 py-1.5 text-white hover:bg-brand-700 disabled:opacity-50">
            {busy ? "Creando…" : "Crear version"}
          </button>
        </form>
      </Card>

      {error && <ErrorBox error={error} />}
      {datasets.length === 0 ? (
        <EmptyState text="Todavia no hay datasets publicados." />
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-left">
              <tr>
                <th className="px-3 py-2">Nombre</th>
                <th className="px-3 py-2">Version</th>
                <th className="px-3 py-2">Filas</th>
                <th className="px-3 py-2">Periodo</th>
                <th className="px-3 py-2">Creado</th>
                <th className="px-3 py-2">Calidad</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.id} className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                  onClick={() => setSelected(d)}>
                  <td className="px-3 py-1.5">{d.name}</td>
                  <td className="px-3 py-1.5">v{d.version}</td>
                  <td className="px-3 py-1.5">{d.row_count}</td>
                  <td className="px-3 py-1.5 text-xs">
                    {d.period_start ? new Date(d.period_start).toLocaleDateString() : "—"} —{" "}
                    {d.period_end ? new Date(d.period_end).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-3 py-1.5">{new Date(d.created_at).toLocaleString()}</td>
                  <td className="px-3 py-1.5"><Tag value="done" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <Card title={`Informe de calidad — ${selected.name} v${selected.version}`}>
          <button className="text-sm text-slate-500 underline mb-2" onClick={() => setSelected(null)}>Cerrar</button>
          <pre className="text-xs bg-slate-50 rounded p-3 overflow-auto">
            {JSON.stringify(selected.quality_report, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  );
}
