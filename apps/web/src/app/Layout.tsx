import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { useLiveConnection, useLiveState } from "../lib/realtime";

interface NavItem {
  to: string;
  label: string;
  roles?: string[];
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV: NavGroup[] = [
  {
    title: "Monitoreo",
    items: [
      { to: "/", label: "Dashboard" },
      { to: "/eventos", label: "Eventos" },
      { to: "/mapa", label: "Mapa sismico" },
      { to: "/analisis", label: "Analisis" },
    ],
  },
  {
    title: "Datos y modelos",
    items: [
      { to: "/datasets", label: "Preparacion de datos", roles: ["analyst", "admin"] },
      { to: "/modelos", label: "Modelos ML", roles: ["analyst", "admin", "auditor"] },
      { to: "/estimaciones", label: "Estimaciones", roles: ["analyst", "admin", "auditor"] },
      { to: "/alertas", label: "Alertas", roles: ["alert_operator", "admin", "auditor", "viewer"] },
      { to: "/fuentes", label: "Fuentes de datos", roles: ["analyst", "admin", "alert_operator"] },
    ],
  },
  {
    title: "Administracion",
    items: [
      { to: "/reportes", label: "Reportes" },
      { to: "/usuarios", label: "Usuarios", roles: ["admin"] },
      { to: "/auditoria", label: "Auditoria", roles: ["admin", "auditor", "analyst"] },
      { to: "/configuracion", label: "Configuracion", roles: ["admin", "auditor"] },
    ],
  },
];

/** Trazos SVG (24x24) de cada seccion del menu. */
const NAV_ICONS: Record<string, string> = {
  "/": "M4 4h6v8H4zM14 4h6v4h-6zM14 12h6v8h-6zM4 16h6v4H4z",
  "/eventos": "M3 12h4l2.5-7 4 14L16 9l1.5 3H21",
  "/mapa": "M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21zM12 7a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z",
  "/analisis": "M5 20v-9M12 20V4M19 20v-6",
  "/datasets": "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6",
  "/modelos": "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5",
  "/estimaciones": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
  "/alertas": "M6 16v-5a6 6 0 1 1 12 0v5l2 2H4l2-2zM10 21h4",
  "/fuentes": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18",
  "/reportes": "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
  "/usuarios": "M9 4.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5M17 5a3 3 0 0 1 0 6M19 20c-.3-2.4-1.4-4-3-4.8",
  "/auditoria": "M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6l8-3zM8.5 12l2.5 2.5 4.5-5",
  "/configuracion": "M4 7h10M18 7h2M4 17h2M10 17h10M16 5a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM8 15a2 2 0 1 0 0 4 2 2 0 0 0 0-4z",
};

function NavIcon({ to }: { to: string }) {
  return (
    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={NAV_ICONS[to] ?? NAV_ICONS["/"]} />
    </svg>
  );
}

function LogoMark({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <span className={`grid ${className} shrink-0 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 shadow-lg shadow-brand-900/40`}>
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 12h4l2.5-7 4 14L15 9l1.5 3H22" />
      </svg>
    </span>
  );
}

function LiveBadge() {
  const { status, received, lastAt } = useLiveState();
  const dot =
    status === "en vivo"
      ? "bg-emerald-500 animate-pulse"
      : status === "detenido"
        ? "bg-slate-400"
        : "bg-amber-400 animate-pulse";
  const label =
    status === "en vivo"
      ? "EN VIVO"
      : status === "conectando"
        ? "CONECTANDO"
        : status === "reconectando"
          ? "RECONECTANDO"
          : "SIN CANAL";

  return (
    <span
      title={
        lastAt
          ? `Ultimo evento recibido: ${new Date(lastAt).toLocaleTimeString()}`
          : "Canal de eventos en vivo: la informacion se actualiza sola"
      }
      className="inline-flex items-center gap-1.5 rounded-full border border-slate-200/70 bg-brand-50/60 px-3 py-1.5 text-xs font-semibold text-slate-600"
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {label}
      {received > 0 && <span className="text-slate-400">· {received} nuevos</span>}
    </span>
  );
}

function UserChip({ name, roles }: { name: string; roles: string[] }) {
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-brand-500 to-ink text-xs font-semibold text-white">
        {initials}
      </span>
      <span className="leading-tight hidden sm:block">
        <span className="block text-sm font-medium text-slate-700">{name}</span>
        <span className="block text-[11px] text-slate-400">
          {roles.join(", ")}
        </span>
      </span>
    </span>
  );
}

export default function Layout() {
  const { user, logout, hasRole } = useAuth();
  useLiveConnection(); // el canal vive mientras haya sesion iniciada

  return (
    <div className="flex min-h-screen gap-4 bg-surface p-3">
      <aside className="sticky top-3 flex h-[calc(100vh-1.5rem)] w-60 shrink-0 flex-col rounded-2xl bg-ink text-slate-200 shadow-soft">
        {/* Marca */}
        <div className="flex items-center gap-3 px-5 py-5">
          <LogoMark />
          <div className="min-w-0">
            <h1 className="truncate text-sm font-bold leading-tight text-white">
              Monitoreo Sismico
            </h1>
            <p className="text-[11px] text-brand-300/90">Analitica y alertas</p>
          </div>
        </div>

        {/* Navegacion agrupada */}
        <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-2">
          {NAV.map((group) => {
            const visible = group.items.filter((i) => !i.roles || hasRole(...i.roles));
            if (visible.length === 0) return null;
            return (
              <div key={group.title}>
                <p className="px-3 pb-2 text-xs font-medium text-slate-400/80">
                  {group.title}
                </p>
                <ul className="space-y-0.5">
                  {visible.map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        end={item.to === "/"}
                        className={({ isActive }) =>
                          `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition focus-visible:outline-2 focus-visible:outline-brand-300 ${
                            isActive
                              ? "bg-gradient-to-r from-brand-500 to-brand-600 font-semibold text-white shadow-lg shadow-ink-deep/40"
                              : "text-slate-300 hover:bg-white/8 hover:text-white"
                          }`
                        }
                      >
                        <NavIcon to={item.to} />
                        {item.label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>

        {/* Pie */}
        <div className="m-3 rounded-xl bg-white/5 px-4 py-3">
          <p className="text-[11px] leading-relaxed text-slate-300">
            Fuente unica IGP / CENSIS
            <br />
            <span className="text-slate-400">No predice terremotos</span>
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <header className="sticky top-3 z-20 flex items-center justify-between gap-4 rounded-2xl border border-slate-200/60 bg-white/90 px-5 py-3 shadow-soft backdrop-blur">
          <p className="hidden text-xs leading-relaxed text-slate-500 md:block">
            Eventos observados ≠ estimaciones experimentales ≠ comunicados oficiales.{" "}
            <span className="font-semibold text-slate-600">Este sistema no predice terremotos.</span>
          </p>
          <div className="flex items-center gap-3">
            <LiveBadge />
            {user && <UserChip name={user.full_name} roles={user.roles} />}
            <button
              onClick={logout}
              className="rounded-xl border border-slate-200 px-3.5 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-brand-50 hover:text-brand-700"
            >
              Salir
            </button>
          </div>
        </header>

        <main className="min-w-0 flex-1 overflow-auto px-1 pb-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
