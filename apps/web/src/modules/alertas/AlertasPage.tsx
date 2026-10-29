import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Card, EmptyState, ErrorBox, Tag } from "../../components/ui";
import { api } from "../../lib/api";
import type { Alert, AlertRule, Delivery } from "../../types";
import { useAuth } from "../../app/AuthContext";

const SEVERITIES = ["info", "warning", "critical"] as const;

export default function AlertasPage() {
  const { hasRole } = useAuth();
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [deliveries, setDeliveries] = useState<Record<string, Delivery[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "", min_magnitude: "4.5", severity: "warning", channel: "console", requires_approval: true,
  });

  const load = useCallback(() => {
    Promise.all([
      api<AlertRule[]>("/api/v1/alert-rules"),
      api<Alert[]>("/api/v1/alerts"),
    ])
      .then(([r, a]) => {
        setRules(r);
        setAlerts(a);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  async function createRule(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/api/v1/alert-rules", {
        method: "POST",
        json: {
          name: form.name,
          min_magnitude: Number(form.min_magnitude),
          severity: form.severity,
          channels: [form.channel],
          requires_approval: form.requires_approval,
          enabled: false,
        },
      });
      setForm({ ...form, name: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear regla");
    }
  }

  async function toggle(rule: AlertRule) {
    await api(`/api/v1/alert-rules/${rule.id}/enabled?enabled=${!rule.enabled}`, { method: "PATCH" });
    load();
  }

  async function act(alertId: string, action: "approve" | "cancel") {
    try {
      await api(`/api/v1/alerts/${alertId}/${action}`, { method: "POST" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error en la operacion");
    }
  }

  async function showDeliveries(alertId: string) {
    const d = await api<Delivery[]>(`/api/v1/alerts/${alertId}/deliveries`);
    setDeliveries((prev) => ({ ...prev, [alertId]: d }));
  }

  const canWrite = hasRole("alert_operator");

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Reglas y centro de alertas</h1>
        <p className="text-xs text-slate-500 max-w-3xl">
          Avisos operativos basados en eventos OBSERVADOS por fuentes verificadas, con deduplicacion, aprobacion
          humana y registro de entrega. No sustituyen a INDECI, IGP ni proteccion civil.
        </p>
      </div>

      {error && <ErrorBox error={error} />}

      {canWrite && (
        <Card title="Nueva regla">
          <form onSubmit={createRule} className="flex flex-wrap items-end gap-3 text-sm">
            <label className="text-slate-600">Nombre
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="sismo >= 4.5"
                className="ml-2 rounded border border-slate-300 px-2 py-1" />
            </label>
            <label className="text-slate-600">Mag. minima
              <input type="number" step="0.1" min="0" max="10" value={form.min_magnitude}
                onChange={(e) => setForm({ ...form, min_magnitude: e.target.value })}
                className="ml-2 w-20 rounded border border-slate-300 px-2 py-1" />
            </label>
            <label className="text-slate-600">Severidad
              <select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}
                className="ml-2 rounded border border-slate-300 px-2 py-1">
                {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="text-slate-600">Canal
              <select value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}
                className="ml-2 rounded border border-slate-300 px-2 py-1">
                <option value="console">consola (bandeja interna)</option>
                <option value="email">correo (stub)</option>
              </select>
            </label>
            <label className="flex items-center gap-1 text-slate-600">
              <input type="checkbox" checked={form.requires_approval}
                onChange={(e) => setForm({ ...form, requires_approval: e.target.checked })} />
              Requiere aprobacion
            </label>
            <button type="submit"
              className="rounded bg-brand-600 px-3 py-1.5 text-white hover:bg-brand-700">
              Crear (inactiva)
            </button>
          </form>
        </Card>
      )}

      <Card title="Reglas configuradas">
        {rules.length === 0 ? (
          <EmptyState text="Sin reglas." />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-left">
              <tr>
                <th className="px-3 py-2">Nombre</th>
                <th className="px-3 py-2">Condicion</th>
                <th className="px-3 py-2">Severidad</th>
                <th className="px-3 py-2">Canales</th>
                <th className="px-3 py-2">Cooldown</th>
                <th className="px-3 py-2">Estado</th>
                {canWrite && <th className="px-3 py-2">Accion</th>}
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className="border-t border-slate-100">
                  <td className="px-3 py-1.5">{r.name}</td>
                  <td className="px-3 py-1.5 text-xs">{JSON.stringify(r.condition_json)}</td>
                  <td className="px-3 py-1.5"><Tag value={r.severity} /></td>
                  <td className="px-3 py-1.5">{r.channels.join(", ")}</td>
                  <td className="px-3 py-1.5">{r.cooldown_seconds}s</td>
                  <td className="px-3 py-1.5">{r.enabled ? <Tag value="completed" /> : <Tag value="cancelled" />}</td>
                  {canWrite && (
                    <td className="px-3 py-1.5">
                      <button onClick={() => toggle(r)}
                        className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-50">
                        {r.enabled ? "Desactivar" : "Activar"}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="Bandeja de alertas" subtitle="Estados: pendiente de aprobacion, enviada, fallida, cancelada">
        {alerts.length === 0 ? (
          <EmptyState text="Sin alertas generadas." />
        ) : (
          <ul className="space-y-3">
            {alerts.map((a) => (
              <li key={a.id} className="rounded border border-slate-200 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Tag value={a.severity} />
                  <span className="font-medium">{a.title}</span>
                  <Tag value={a.status} />
                  <span className="text-xs text-slate-400">{new Date(a.created_at).toLocaleString()}</span>
                </div>
                <p className="text-slate-600 mt-1">{a.message}</p>
                {a.source_url && (
                  <a href={a.source_url} target="_blank" rel="noreferrer" className="text-brand-700 underline text-xs">
                    Fuente del evento
                  </a>
                )}
                <div className="flex gap-2 mt-2">
                  {a.status === "pending_approval" && canWrite && (
                    <>
                      <button onClick={() => act(a.id, "approve")}
                        className="rounded border border-emerald-300 px-2 py-0.5 text-emerald-700 hover:bg-emerald-50">
                        Aprobar y enviar
                      </button>
                      <button onClick={() => act(a.id, "cancel")}
                        className="rounded border border-red-300 px-2 py-0.5 text-red-700 hover:bg-red-50">
                        Cancelar
                      </button>
                    </>
                  )}
                  <button onClick={() => showDeliveries(a.id)}
                    className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-50">
                    Ver entregas
                  </button>
                </div>
                {deliveries[a.id] && (
                  <ul className="mt-2 text-xs text-slate-600 space-y-1">
                    {deliveries[a.id].map((d) => (
                      <li key={d.id}>
                        canal {d.channel} — {d.status} · intentos {d.attempts}
                        {d.error_code ? ` · error: ${d.error_code}` : ""}
                        {d.delivered_at ? ` · entregado ${new Date(d.delivered_at).toLocaleString()}` : ""}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
