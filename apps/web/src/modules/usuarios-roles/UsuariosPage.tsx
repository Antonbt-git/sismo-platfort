import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Card, EmptyState, ErrorBox, Tag } from "../../components/ui";
import { api } from "../../lib/api";
import type { User } from "../../types";

const ROLES = ["admin", "analyst", "alert_operator", "auditor", "viewer"];

export default function UsuariosPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "viewer" });

  const load = useCallback(() => {
    api<User[]>("/api/v1/users")
      .then(setUsers)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/api/v1/users", {
        method: "POST",
        json: { full_name: form.full_name, email: form.email, password: form.password, roles: [form.role] },
      });
      setForm({ full_name: "", email: "", password: "", role: "viewer" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear usuario");
    }
  }

  async function setRoles(user: User, roles: string[]) {
    try {
      await api(`/api/v1/users/${user.id}/roles`, { method: "PATCH", json: { roles } });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al actualizar roles");
    }
  }

  async function toggleStatus(user: User) {
    const next = user.status === "active" ? "disabled" : "active";
    try {
      await api(`/api/v1/users/${user.id}/status?status=${next}`, { method: "PATCH" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cambiar estado");
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Usuarios y roles</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          Politica de minimo privilegio: los roles bloquean funciones tanto en la interfaz como en la API.
        </p>
      </div>

      {error && <ErrorBox error={error} />}

      <Card title="Crear usuario">
        <form onSubmit={create} className="flex flex-wrap items-end gap-3 text-sm">
          <label className="text-slate-600">Nombre
            <input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              className="ml-2 rounded border border-slate-300 px-2 py-1" />
          </label>
          <label className="text-slate-600">Correo
            <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="ml-2 rounded border border-slate-300 px-2 py-1" />
          </label>
          <label className="text-slate-600">Contrasena
            <input required type="password" minLength={8} value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="ml-2 rounded border border-slate-300 px-2 py-1" />
          </label>
          <label className="text-slate-600">Rol
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
              className="ml-2 rounded border border-slate-300 px-2 py-1">
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
          <button type="submit" className="rounded bg-brand-600 px-3 py-1.5 text-white hover:bg-brand-700">
            Crear
          </button>
        </form>
      </Card>

      {users.length === 0 ? (
        <EmptyState text="Sin usuarios." />
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-left">
              <tr>
                <th className="px-3 py-2">Nombre</th>
                <th className="px-3 py-2">Correo</th>
                <th className="px-3 py-2">Roles</th>
                <th className="px-3 py-2">Estado</th>
                <th className="px-3 py-2">Ultimo acceso</th>
                <th className="px-3 py-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-slate-100">
                  <td className="px-3 py-1.5">{u.full_name}</td>
                  <td className="px-3 py-1.5">{u.email}</td>
                  <td className="px-3 py-1.5">
                    <select multiple value={u.roles}
                      onChange={(e) => setRoles(u, Array.from(e.target.selectedOptions, (o) => o.value))}
                      className="rounded border border-slate-300 px-2 py-1 text-xs" size={Math.min(3, ROLES.length)}>
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td className="px-3 py-1.5"><Tag value={u.status === "active" ? "completed" : "cancelled"} /></td>
                  <td className="px-3 py-1.5 text-xs">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "nunca"}
                  </td>
                  <td className="px-3 py-1.5">
                    <button onClick={() => toggleStatus(u)}
                      className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-50">
                      {u.status === "active" ? "Deshabilitar" : "Habilitar"}
                    </button>
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
