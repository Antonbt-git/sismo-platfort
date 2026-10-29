import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Card, EmptyState, ErrorBox } from "../../components/ui";
import { api } from "../../lib/api";
import type { ConfigDefinition, ConfigResponse } from "../../types";
import { useAuth } from "../../app/AuthContext";

const GROUP_LABELS: Record<string, string> = {
  ingesta: "Ingesta de datos (IGP / CENSIS)",
  reportes: "Reportes",
  alertas: "Alertas",
  auditoria: "Auditoria",
};

/**
 * §6.13 Auditoria y configuracion: parametros operativos con valores por defecto
 * visibles, rangos validados y cambios registrados en la bitacora.
 */
export default function ConfiguracionPage() {
  const { hasRole } = useAuth();
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api<ConfigResponse>("/api/v1/config")
      .then((c) => {
        setConfig(c);
        setDraft(Object.fromEntries(c.definitions.map((d) => [d.key, String(d.value)])));
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  const canEdit = hasRole("admin");

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!config) return;
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const changes: Record<string, number | string> = {};
      for (const def of config.definitions) {
        if (String(def.value) !== draft[def.key]) {
          changes[def.key] = def.kind === "str" ? draft[def.key] : Number(draft[def.key]);
        }
      }
      if (Object.keys(changes).length === 0) {
        setMsg("Sin cambios pendientes.");
        return;
      }
      const updated = await api<ConfigResponse>("/api/v1/config", { method: "PUT", json: { values: changes } });
      setConfig(updated);
      setDraft(Object.fromEntries(updated.definitions.map((d) => [d.key, String(d.value)])));
      setMsg(`Guardado. ${Object.keys(changes).length} parametro(s) actualizado(s) y registrado(s) en auditoria.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar la configuracion");
    } finally {
      setBusy(false);
    }
  }

  function reset(definitions: ConfigDefinition[]) {
    setDraft(Object.fromEntries(definitions.map((d) => [d.key, String(d.value)])));
    setMsg(null);
    setError(null);
  }

  const groups = config ? Array.from(new Set(config.definitions.map((d) => d.group))) : [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Configuracion del sistema</h1>
        <p className="text-xs text-slate-500 max-w-3xl">
          Parametros operativos con valor por defecto visible, validacion de rango y control de cambios.
          Cada modificacion queda en la bitacora de auditoria. Los secretos no se gestionan aqui: viven en
          variables de entorno o secret manager.
        </p>
      </div>

      {error && <ErrorBox error={error} />}
      {msg && <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{msg}</div>}

      {!config ? (
        <EmptyState text="Cargando configuracion…" />
      ) : (
        <form onSubmit={save} className="space-y-4">
          {groups.map((group) => (
            <Card key={group} title={GROUP_LABELS[group] ?? group}>
              <div className="grid gap-3 md:grid-cols-2">
                {config.definitions
                  .filter((d) => d.group === group)
                  .map((d) => (
                    <label key={d.key} className="block text-sm">
                      <span className="text-slate-700">
                        {d.description}
                        {d.modified && <span className="ml-1 text-xs text-amber-700">(modificado)</span>}
                      </span>
                      <input
                        type={d.kind === "str" ? "text" : "number"}
                        step={d.kind === "float" ? "0.1" : d.kind === "int" ? "1" : undefined}
                        min={d.minimum ?? undefined}
                        max={d.maximum ?? undefined}
                        value={draft[d.key] ?? ""}
                        disabled={!canEdit}
                        onChange={(e) => setDraft({ ...draft, [d.key]: e.target.value })}
                        className="mt-1 w-full rounded border border-slate-300 px-2 py-1 disabled:bg-slate-50 disabled:text-slate-500"
                      />
                      <span className="text-xs text-slate-400">
                        {d.key} · defecto: {String(d.default)}
                        {d.minimum !== null && d.maximum !== null ? ` · rango ${d.minimum}–${d.maximum}` : ""}
                      </span>
                    </label>
                  ))}
              </div>
            </Card>
          ))}

          {canEdit ? (
            <div className="flex gap-2">
              <button type="submit" disabled={busy}
                className="rounded bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50">
                {busy ? "Guardando…" : "Guardar cambios"}
              </button>
              <button type="button" onClick={() => reset(config.definitions)}
                className="rounded border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50">
                Descartar
              </button>
            </div>
          ) : (
            <p className="mt-1 max-w-3xl text-sm text-slate-500">Lectura sola: requiere rol administrador para modificar.</p>
          )}

          {config.last_updated_at && (
            <p className="mt-1 max-w-3xl text-sm text-slate-500">
              Ultima modificacion: {new Date(config.last_updated_at).toLocaleString()}
            </p>
          )}
        </form>
      )}
    </div>
  );
}
