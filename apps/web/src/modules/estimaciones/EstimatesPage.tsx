import { useCallback, useEffect, useState } from "react";
import { Badge, Card, EmptyState, ErrorBox, Tag } from "../../components/ui";
import { api } from "../../lib/api";
import type { Estimate, Experiment, Model } from "../../types";
import { useAuth } from "../../app/AuthContext";

/**
 * §6.7 Estimaciones experimentales: resultados de modelos con incertidumbre,
 * fecha de calculo y advertencia explicita. Nunca se difunden como alerta oficial
 * ni se confunden con los eventos observados.
 */
export default function EstimatesPage() {
  const { hasRole } = useAuth();
  const [estimates, setEstimates] = useState<Estimate[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([
      api<Estimate[]>("/api/v1/estimates"),
      api<Model[]>("/api/v1/ml/models"),
      api<Experiment[]>("/api/v1/ml/experiments"),
    ])
      .then(([est, m, exp]) => {
        setEstimates(est);
        setModels(m);
        setExperiments(exp);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  async function publish(modelId: string) {
    setError(null);
    setMsg(null);
    try {
      await api("/api/v1/ml/estimates", {
        method: "POST",
        json: { model_id: modelId, area_code: "PER", window_hours: 168 },
      });
      setMsg("Estimacion publicada con etiqueta experimental.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al publicar estimacion");
    }
  }

  const approved = models.filter((m) => m.status === "approved");
  const modelName = (id: string) => {
    const model = models.find((m) => m.id === id);
    const exp = model ? experiments.find((e) => e.id === model.experiment_id) : undefined;
    return exp?.name ?? (model ? `modelo ${model.version}` : id.slice(0, 8));
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Estimaciones experimentales</h1>
        <p className="text-xs text-slate-500 max-w-3xl">
          Salidas estadisticas y de Machine Learning con incertidumbre, version de modelo y fecha de calculo.
          Requieren validacion cientifica y <strong>no equivalen a una alerta sismica oficial</strong>: el sistema
          no predice fecha, hora, lugar ni magnitud de sismos futuros.
        </p>
      </div>

      <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 shadow-sm">
        <strong>Advertencia:</strong> toda fila de esta pagina es una estimacion experimental. No sustituye al IGP,
        al INDECI ni a los organismos de proteccion civil, y nunca se envia automaticamente como comunicado oficial.
      </div>

      {error && <ErrorBox error={error} />}
      {msg && <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}

      {hasRole("analyst") && (
        <Card title="Publicar desde un modelo aprobado" subtitle="Solo modelos con estado aprobado pueden generar estimaciones">
          {approved.length === 0 ? (
            <EmptyState text="No hay modelos aprobados aun." />
          ) : (
            <ul className="space-y-2 text-sm">
              {approved.map((m) => (
                <li key={m.id} className="flex flex-wrap items-center gap-3 border-b border-slate-100 pb-2">
                  <span className="font-medium">{modelName(m.id)}</span>
                  <span className="text-slate-500">v{m.version}</span>
                  <span className="text-xs text-slate-400">{m.limitations}</span>
                  <button
                    onClick={() => publish(m.id)}
                    className="rounded border border-purple-300 px-2 py-0.5 text-purple-700 hover:bg-purple-50"
                  >
                    Publicar estimacion
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <Card title="Estimaciones publicadas" subtitle="Metrica, valor, intervalo de incertidumbre, ventana y fecha de calculo">
        {estimates.length === 0 ? (
          <EmptyState text="Sin estimaciones publicadas." />
        ) : (
          <div className="space-y-3">
            {estimates.map((est) => {
              const isProb = est.metric_name.includes("prob");
              const displayValue = isProb
                ? `${(est.value * 100).toFixed(1)} %`
                : est.value;
              return (
                <div
                  key={est.id}
                  className="rounded-xl border border-slate-200 bg-slate-50/40 p-4 transition-shadow hover:shadow-sm"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2 border-b border-slate-200 pb-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge text="EXPERIMENTAL" />
                        <span className="font-semibold text-ink">{modelName(est.model_id)}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-400">
                        Calculada el {new Date(est.calculated_at).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-200">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Metrica</p>
                      <p className="mt-0.5 text-sm font-medium text-slate-700 break-words">{est.metric_name}</p>
                    </div>
                    <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-200">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                        {isProb ? "Probabilidad" : "Valor"}
                      </p>
                      <p className="mt-0.5 text-sm font-semibold tabular-nums text-ink">
                        {displayValue}
                        {(est.lower_bound !== null || est.upper_bound !== null) && (
                          <span className="ml-1 text-xs font-normal text-slate-400">
                            [{isProb ? `${(est.lower_bound! * 100).toFixed(1)} %` : est.lower_bound ?? "—"},{" "}
                            {isProb ? `${(est.upper_bound! * 100).toFixed(1)} %` : est.upper_bound ?? "—"}]
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-200">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Area</p>
                      <p className="mt-0.5 text-sm font-medium text-slate-700">{est.area_code}</p>
                    </div>
                    <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-200">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Ventana</p>
                      <p className="mt-0.5 text-sm font-medium text-slate-700">
                        {est.window_start ? new Date(est.window_start).toLocaleDateString() : "—"}{" "}
                        <span className="text-slate-400">→</span>{" "}
                        {est.window_end ? new Date(est.window_end).toLocaleDateString() : "—"}
                      </p>
                    </div>
                  </div>

                  <p className="mt-3 text-xs text-slate-500 leading-relaxed">{est.disclaimer}</p>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card title="Estado de los modelos fuente" subtitle="Trazabilidad: cada estimacion identifica modelo y version">
        {approved.length === 0 ? (
          <EmptyState text="Sin modelos aprobados." />
        ) : (
          <ul className="space-y-1 text-sm">
            {approved.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-3">
                <Tag value={m.status} />
                <span>{modelName(m.id)}</span>
                <span className="text-slate-500">v{m.version}</span>
                <span className="text-xs text-slate-400">aprobado {m.approved_at ? new Date(m.approved_at).toLocaleString() : "—"}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
