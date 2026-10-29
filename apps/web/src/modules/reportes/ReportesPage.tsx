import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Card, EmptyState, ErrorBox, Tag } from "../../components/ui";
import { api } from "../../lib/api";
import type { ReportJob } from "../../types";
import { useAuth } from "../../app/AuthContext";
import { getToken } from "../../lib/api";

const TYPES = [
  { value: "events", label: "Eventos observados" },
  { value: "alerts", label: "Alertas y entregas" },
  { value: "quality", label: "Calidad de datasets" },
  { value: "models", label: "Experimentos y modelos" },
];

const FORMATS = [
  { value: "csv", label: "CSV" },
  { value: "xlsx", label: "XLSX" },
  { value: "pdf", label: "PDF" },
];

const EXT_LABEL: Record<string, string> = { csv: "CSV", xlsx: "XLSX", pdf: "PDF" };

export default function ReportesPage() {
  const { hasRole } = useAuth();
  const [reports, setReports] = useState<ReportJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ report_type: "events", date_from: "", date_to: "", min_magnitude: "", format: "csv" });

  const load = useCallback(() => {
    api<ReportJob[]>("/api/v1/reports")
      .then(setReports)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);
  useEffect(() => {
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/api/v1/reports", {
        method: "POST",
        json: {
          report_type: form.report_type,
          date_from: form.date_from ? new Date(form.date_from).toISOString() : null,
          date_to: form.date_to ? new Date(form.date_to).toISOString() : null,
          min_magnitude: form.min_magnitude ? Number(form.min_magnitude) : null,
          format: form.format,
        },
      });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al solicitar reporte");
    }
  }

  async function download(r: ReportJob) {
    const res = await fetch(`/api/v1/reports/${r.id}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) {
      setError("No se pudo descargar el reporte (revise permisos y expiracion)");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const ext = String(r.filters_json?.format ?? "csv");
    a.href = url;
    a.download = `${r.report_type}_${r.id}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Reportes</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          Exportaciones CSV/XLSX/PDF con fecha de corte, filtros, fuente y solicitante. Enlaces temporales
          (la vigencia la define el parametro de configuracion).
        </p>
      </div>

      {error && <ErrorBox error={error} />}

      {hasRole("analyst", "alert_operator") && (
        <Card title="Solicitar reporte">
          <form onSubmit={create} className="flex flex-wrap items-end gap-3 text-sm">
            <label className="text-slate-600">Tipo
              <select value={form.report_type} onChange={(e) => setForm({ ...form, report_type: e.target.value })}
                className="ml-2 rounded border border-slate-300 px-2 py-1">
                {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
            <label className="text-slate-600">Desde
              <input type="date" value={form.date_from} onChange={(e) => setForm({ ...form, date_from: e.target.value })}
                className="ml-2 rounded border border-slate-300 px-2 py-1" />
            </label>
            <label className="text-slate-600">Hasta
              <input type="date" value={form.date_to} onChange={(e) => setForm({ ...form, date_to: e.target.value })}
                className="ml-2 rounded border border-slate-300 px-2 py-1" />
            </label>
            <label className="text-slate-600">Mag. min.
              <input type="number" step="0.1" min="0" max="10" value={form.min_magnitude}
                onChange={(e) => setForm({ ...form, min_magnitude: e.target.value })}
                className="ml-2 w-20 rounded border border-slate-300 px-2 py-1" />
            </label>
            <label className="text-slate-600">Formato
              <select value={form.format} onChange={(e) => setForm({ ...form, format: e.target.value })}
                className="ml-2 rounded border border-slate-300 px-2 py-1">
                {FORMATS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
              </select>
            </label>
            <button type="submit" className="rounded bg-brand-600 px-3 py-1.5 text-white hover:bg-brand-700">
              Generar
            </button>
          </form>
        </Card>
      )}

      {reports.length === 0 ? (
        <EmptyState text="Sin reportes solicitados." />
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-left">
              <tr>
                <th className="px-3 py-2">Tipo</th>
                <th className="px-3 py-2">Filtros</th>
                <th className="px-3 py-2">Estado</th>
                <th className="px-3 py-2">Creado</th>
                <th className="px-3 py-2">Expira</th>
                <th className="px-3 py-2">Descarga</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id} className="border-t border-slate-100">
                  <td className="px-3 py-1.5">{r.report_type}</td>
                  <td className="px-3 py-1.5 text-xs">{JSON.stringify(r.filters_json)}</td>
                  <td className="px-3 py-1.5"><Tag value={r.status} /></td>
                  <td className="px-3 py-1.5">{new Date(r.created_at).toLocaleString()}</td>
                  <td className="px-3 py-1.5 text-xs">{r.expires_at ? new Date(r.expires_at).toLocaleString() : "—"}</td>
                  <td className="px-3 py-1.5">
                    {r.status === "done" ? (
                      <button onClick={() => download(r)} className="text-brand-700 underline">
                        {EXT_LABEL[String(r.filters_json?.format ?? "csv")] ?? "CSV"}
                      </button>
                    ) : r.error_summary ?? "—"}
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
