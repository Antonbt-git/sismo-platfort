import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Card, EmptyState, ErrorBox, Tag } from "../../components/ui";
import { api } from "../../lib/api";
import type { Dataset, Experiment, Model } from "../../types";
import { useAuth } from "../../app/AuthContext";

export default function ModelosPage() {
  const { hasRole } = useAuth();
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expOpen, setExpOpen] = useState(true);
  const [form, setForm] = useState({ name: "", task_type: "classification", algorithm: "random_forest", days: "365", dataset_id: "" });

  const load = useCallback(() => {
    Promise.all([
      api<Experiment[]>("/api/v1/ml/experiments"),
      api<Model[]>("/api/v1/ml/models"),
      api<Dataset[]>("/api/v1/datasets"),
    ])
      .then(([e, m, d]) => {
        setExperiments(e);
        setModels(m);
        setDatasets(d);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  // Refresco simple para acompanar entrenamientos en segundo plano.
  useEffect(() => {
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [load]);

  async function train(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        name: form.name || `exp-${new Date().toISOString().slice(0, 10)}`,
        task_type: form.task_type,
        algorithm: form.algorithm,
      };
      if (form.dataset_id) {
        payload.dataset_id = form.dataset_id;
      } else {
        payload.date_from = new Date(Date.now() - Number(form.days) * 86400_000).toISOString();
      }
      await api("/api/v1/ml/experiments", {
        method: "POST",
        json: payload,
      });
      setForm({ name: "", task_type: form.task_type, algorithm: form.algorithm, days: form.days, dataset_id: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al entrenar");
    } finally {
      setBusy(false);
    }
  }

  async function approve(modelId: string, action: "approve" | "reject") {
    try {
      await api(`/api/v1/ml/models/${modelId}/${action}`, { method: "POST" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error en la operacion");
    }
  }

  const algos = form.task_type === "classification"
    ? ["random_forest", "logistic_regression", "baseline_dummy"]
    : ["random_forest", "linear_regression", "baseline_dummy"];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Modelos de Machine Learning</h1>
        <p className="text-xs text-slate-500 max-w-3xl">
          Experimentos supervisados reproducibles con particion temporal. Un modelo que clasifica registros existentes
          NO demuestra que pueda anticipar futuros terremotos.
        </p>
      </div>

      {error && <ErrorBox error={error} />}

      {hasRole("analyst") && (
        <Card title="Nuevo experimento">
          <form onSubmit={train} className="flex flex-wrap items-end gap-3 text-sm">
            <label className="text-slate-600">Nombre
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="clf-bandas-magnitud"
                className="ml-2 rounded border border-slate-300 px-2 py-1" />
            </label>
            <label className="text-slate-600">Tarea
              <select value={form.task_type}
                onChange={(e) => setForm({ ...form, task_type: e.target.value, algorithm: "random_forest" })}
                className="ml-2 rounded border border-slate-300 px-2 py-1">
                <option value="classification">Clasificacion (banda de magnitud)</option>
                <option value="regression">Regresion (profundidad estimada)</option>
              </select>
            </label>
            <label className="text-slate-600">Algoritmo
              <select value={form.algorithm} onChange={(e) => setForm({ ...form, algorithm: e.target.value })}
                className="ml-2 rounded border border-slate-300 px-2 py-1">
                {algos.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </label>
            <label className="text-slate-600">Datos
              <select value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })}
                disabled={!!form.dataset_id}
                className="ml-2 rounded border border-slate-300 px-2 py-1 disabled:opacity-50">
                <option value="180">180 dias</option>
                <option value="365">1 año</option>
                <option value="730">2 años</option>
              </select>
            </label>
            <label className="text-slate-600">Dataset preparado
              <select value={form.dataset_id}
                onChange={(e) => setForm({ ...form, dataset_id: e.target.value })}
                className="ml-2 rounded border border-slate-300 px-2 py-1">
                <option value="">Sin dataset (ventana temporal)</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} v{d.version} — {d.row_count} filas
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={busy}
              className="rounded bg-brand-600 px-3 py-1.5 text-white hover:bg-brand-700 disabled:opacity-50">
              {busy ? "Enviando…" : "Entrenar"}
            </button>
          </form>
        </Card>
      )}

      <Card
        title="Experimentos"
        subtitle="Metricas registradas con dataset, particion, semilla y librerias"
        action={
          <button
            type="button"
            onClick={() => setExpOpen((v) => !v)}
            className="rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            {expOpen ? "Minimizar ▲" : "Expandir ▼"}
          </button>
        }
      >
        {expOpen ? (
          experiments.length === 0 ? (
            <EmptyState text="Sin experimentos aun." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500 text-left">
                  <tr>
                    <th className="px-3 py-2">Nombre</th>
                    <th className="px-3 py-2">Tarea</th>
                    <th className="px-3 py-2">Algoritmo</th>
                    <th className="px-3 py-2">Dataset</th>
                    <th className="px-3 py-2">Metricas</th>
                    <th className="px-3 py-2">Estado</th>
                    <th className="px-3 py-2">Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {experiments.map((exp) => {
                    const ds = exp.dataset_id ? datasets.find((d) => d.id === exp.dataset_id) : undefined;
                    return (
                      <tr key={exp.id} className="border-t border-slate-100 align-top">
                        <td className="px-3 py-1.5">{exp.name}</td>
                        <td className="px-3 py-1.5">{exp.task_type === "classification" ? "clasificacion" : "regresion"}</td>
                        <td className="px-3 py-1.5">{exp.algorithm}</td>
                        <td className="px-3 py-1.5 text-xs">
                          {ds ? `${ds.name} v${ds.version}` : "ventana temporal"}
                        </td>
                        <td className="px-3 py-1.5 text-xs">
                          {exp.status === "completed" ? (
                            <div className="flex flex-wrap gap-1.5">
                              {Object.entries(exp.metrics ?? {})
                                .filter(([k]) => !["confusion_matrix", "classes", "baseline_dummy"].includes(k))
                                .map(([k, v]) => (
                                  <span key={k} className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700">
                                    <span className="text-slate-400">{k}</span>
                                    <span className="font-medium tabular-nums">{String(v)}</span>
                                  </span>
                                ))}
                            </div>
                          ) : "—"}
                          <p className="mt-1.5 text-slate-400 max-w-md">{exp.limitations}</p>
                        </td>
                        <td className="px-3 py-1.5"><Tag value={exp.status} /></td>
                        <td className="px-3 py-1.5 text-xs">{new Date(exp.created_at).toLocaleString()}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )
        ) : (
          <p className="text-xs text-slate-400">Seccion minimizada — {experiments.length} experimento(s).</p>
        )}
      </Card>

      <Card title="Registro de modelos" subtitle="Solo modelos aprobados pueden publicar estimaciones (ver modulo Estimaciones)">
        {models.length === 0 ? (
          <EmptyState text="Sin modelos registrados." />
        ) : (
          <ul className="space-y-2 text-sm">
            {models.map((m) => {
              const exp = experiments.find((e) => e.id === m.experiment_id);
              return (
                <li key={m.id} className="flex flex-wrap items-center gap-3 border-b border-slate-100 pb-2">
                  <span className="font-medium">{exp?.name ?? m.experiment_id}</span>
                  <span className="text-slate-500">v{m.version}</span>
                  <Tag value={m.status === "approved" ? "completed" : m.status} />
                  <span className="flex gap-2">
                    {hasRole("analyst") && m.status === "candidate" && (
                      <>
                        <button onClick={() => approve(m.id, "approve")}
                          className="rounded border border-emerald-300 px-2 py-0.5 text-emerald-700 hover:bg-emerald-50">
                          Aprobar
                        </button>
                        <button onClick={() => approve(m.id, "reject")}
                          className="rounded border border-red-300 px-2 py-0.5 text-red-700 hover:bg-red-50">
                          Rechazar
                        </button>
                      </>
                    )}
                  </span>
                  <span className="text-xs text-slate-400">{m.limitations}</span>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
