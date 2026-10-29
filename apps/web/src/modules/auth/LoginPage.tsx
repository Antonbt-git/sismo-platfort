import { useState, type FormEvent } from "react";
import { useAuth } from "../../app/AuthContext";
import { ErrorBox } from "../../components/ui";
import heroUrl from "../../assets/login-hero.svg";

/** Sismografo decorativo del panel izquierdo (marca + aviso de alcance). */
function HeroPanel() {
  return (
    <div className="relative hidden lg:flex flex-1 overflow-hidden bg-ink">
      {/* Imagen tematica: registro sismografico con epicentro */}
      <img
        src={heroUrl}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-cover object-center opacity-95"
      />
      {/* Degradado para legibilidad del texto */}
      <div className="absolute inset-0 bg-gradient-to-t from-ink-deep via-ink-deep/35 to-transparent" />

      <div className="relative z-10 flex flex-col justify-between p-10 xl:p-14 w-full">
        <div className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-white/10 ring-1 ring-white/20 backdrop-blur">
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="#aaa5ff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 12h4l2.5-7 4 14L15 9l1.5 3H22" />
            </svg>
          </span>
          <div>
            <p className="text-white font-semibold leading-tight">Monitoreo Sismico</p>
            <p className="text-xs text-brand-300/90">Analitica y alertas · IGP / CENSIS</p>
          </div>
        </div>

        <div className="max-w-lg">
          <h2 className="text-3xl xl:text-4xl font-semibold text-white leading-tight">
            Eventos observados,
            <br />
            con procedencia verificable.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-slate-300">
            Consolidacion del catalogo del Centro Sismologico Nacional, analitica descriptiva y
            experimentos de Machine Learning claramente etiquetados, con trazabilidad completa de
            cada dato y cada accion.
          </p>

        </div>

        <p className="text-[11px] text-slate-400">
          Fuente unica: Instituto Geofisico del Peru (IGP) · CENSIS
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("admin@sismoplatform.pe");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error de autenticacion");
    } finally {
      setBusy(false);
    }
  }

  const input =
    "mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20";

  return (
    <div className="min-h-screen flex bg-ink">
      <HeroPanel />

      <div className="flex flex-1 items-center justify-center bg-surface px-6 py-12 lg:flex-none lg:w-[440px] xl:w-[500px]">
        <div className="w-full max-w-sm">
          {/* Marca compacta (visible en pantallas sin el panel lateral) */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-ink">
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="#aaa5ff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 12h4l2.5-7 4 14L15 9l1.5 3H22" />
              </svg>
            </span>
            <div>
              <p className="font-semibold text-ink leading-tight">Monitoreo Sismico</p>
              <p className="mt-1 max-w-3xl text-sm text-slate-500">Analitica y alertas</p>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/60 sm:p-7">
            <h1 className="text-xl font-semibold tracking-tight text-ink">Inicie sesion</h1>
            <p className="mt-1 text-sm text-slate-500">
              Acceso al panel de monitoreo, analitica y alertas
            </p>

            <form onSubmit={onSubmit} className="mt-6 space-y-4">
              {error && <ErrorBox error={error} />}

              <label className="block text-sm">
                <span className="font-medium text-slate-700">Correo</span>
                <input
                  type="email"
                  required
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={input}
                  placeholder="usuario@dominio.pe"
                />
              </label>

              <label className="block text-sm">
                <span className="font-medium text-slate-700">Contrasena</span>
                <input
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={input}
                  placeholder="••••••••"
                />
              </label>

              <button
                type="submit"
                disabled={busy}
                className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500/40 disabled:opacity-50"
              >
                {busy ? "Verificando…" : "Ingresar al panel"}
              </button>
            </form>
          </div>

          <p className="mt-6 text-center text-xs text-slate-500">
            Sistema interno · Uso sujeto a las politicas de la organizacion
          </p>
        </div>
      </div>
    </div>
  );
}
