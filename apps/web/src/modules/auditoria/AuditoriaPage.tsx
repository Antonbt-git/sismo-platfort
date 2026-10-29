import { useEffect, useState } from "react";
import { EmptyState, ErrorBox, Spinner, Tag } from "../../components/ui";
import { api, qs } from "../../lib/api";
import type { AuditLog } from "../../types";

export default function AuditoriaPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ action: "", entity_type: "" });

  useEffect(() => {
    setLoading(true);
    api<AuditLog[]>("/api/v1/audit-logs" + qs({ ...filters, limit: 200 }))
      .then(setLogs)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Auditoria</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          Bitacora inmutable de acciones criticas: accesos, sincronizaciones, cambios de reglas, aprobaciones y
          descargas. Sin secretos ni tokens.
        </p>
      </div>

      <div className="flex flex-wrap gap-3 text-sm">
        <label className="text-slate-600">Accion
          <input value={filters.action} placeholder="ej. alert.approve"
            onChange={(e) => setFilters({ ...filters, action: e.target.value })}
            className="ml-2 rounded border border-slate-300 px-2 py-1" />
        </label>
        <label className="text-slate-600">Entidad
          <input value={filters.entity_type} placeholder="ej. alert"
            onChange={(e) => setFilters({ ...filters, entity_type: e.target.value })}
            className="ml-2 rounded border border-slate-300 px-2 py-1" />
        </label>
      </div>

      {error && <ErrorBox error={error} />}
      {loading ? (
        <Spinner />
      ) : logs.length === 0 ? (
        <EmptyState text="Sin registros para estos filtros." />
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-left">
              <tr>
                <th className="px-3 py-2">Fecha (UTC)</th>
                <th className="px-3 py-2">Usuario</th>
                <th className="px-3 py-2">Accion</th>
                <th className="px-3 py-2">Entidad</th>
                <th className="px-3 py-2">Resultado</th>
                <th className="px-3 py-2">IP</th>
                <th className="px-3 py-2">Detalles</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-t border-slate-100">
                  <td className="px-3 py-1.5 text-xs">{new Date(l.occurred_at).toLocaleString()}</td>
                  <td className="px-3 py-1.5">{l.actor_email ?? "sistema"}</td>
                  <td className="px-3 py-1.5 font-mono text-xs">{l.action}</td>
                  <td className="px-3 py-1.5">{l.entity_type} {l.entity_id ? `#${l.entity_id.slice(0, 8)}` : ""}</td>
                  <td className="px-3 py-1.5"><Tag value={l.result === "success" ? "completed" : "failed"} /></td>
                  <td className="px-3 py-1.5 text-xs">{l.ip ?? "—"}</td>
                  <td className="px-3 py-1.5 text-xs">
                    {(l.before_json || l.after_json) ? (
                      <pre className="bg-slate-50 rounded p-1 overflow-auto max-w-xs">
                        {JSON.stringify({ before: l.before_json, after: l.after_json })}
                      </pre>
                    ) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
