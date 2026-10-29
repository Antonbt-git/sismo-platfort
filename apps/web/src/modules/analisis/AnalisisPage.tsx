import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from "recharts";
import { Card, ErrorBox, StatCard, Spinner } from "../../components/ui";
import { api, qs } from "../../lib/api";

interface DepthPoint {
  depth_km: number;
  magnitude: number;
  place: string | null;
}
interface RegionCount {
  region: string;
  count: number;
}
interface Quality {
  sample_size: number;
  missing_magnitude: number;
  missing_depth: number;
  duplicate_external_ids: number;
}

export default function AnalisisPage() {
  const [points, setPoints] = useState<DepthPoint[]>([]);
  const [regions, setRegions] = useState<RegionCount[]>([]);
  const [quality, setQuality] = useState<Quality | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState("90");

  useEffect(() => {
    const dateFrom = new Date(Date.now() - Number(days) * 86400_000).toISOString();
    const params = { date_from: dateFrom };
    Promise.all([
      api<DepthPoint[]>("/api/v1/analytics/magnitude-depth" + qs({ ...params, limit: 2000 })),
      api<RegionCount[]>("/api/v1/analytics/regions" + qs(params)),
      api<Quality>("/api/v1/analytics/quality" + qs(params)),
    ])
      .then(([p, r, q]) => {
        setPoints(p);
        setRegions(r);
        setQuality(q);
      })
      .catch((e) => setError(e.message));
  }, [days]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Analisis estadistico descriptivo</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-500">
            Describe la historia de los eventos observados; no atribuye causalidad ni predice futuros sismos.
          </p>
        </div>
        <label className="text-sm text-slate-600">Periodo
          <select value={days} onChange={(e) => setDays(e.target.value)}
            className="ml-2 rounded border border-slate-300 px-2 py-1">
            <option value="30">30 dias</option>
            <option value="90">90 dias</option>
            <option value="365">1 año</option>
          </select>
        </label>
      </div>

      {error && <ErrorBox error={error} />}
      {!quality ? (
        <Spinner />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatCard label="Tamano de muestra" value={quality.sample_size} />
            <StatCard label="Sin magnitud" value={quality.missing_magnitude} />
            <StatCard label="Sin profundidad" value={quality.missing_depth} />
            <StatCard label="Duplicados" value={quality.duplicate_external_ids} />
            <StatCard label="Periodo" value={`${days} dias`} hint="corte: ahora" />
          </div>

          <div className="grid lg:grid-cols-2 gap-4">
            <Card title="Magnitud vs. profundidad" subtitle="Un punto por evento (sin atribuir causalidad)">
              <ResponsiveContainer width="100%" height={300}>
                <ScatterChart>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" dataKey="depth_km" name="Profundidad (km)" fontSize={11} />
                  <YAxis type="number" dataKey="magnitude" name="Magnitud" fontSize={11} domain={["auto", "auto"]} />
                  <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                  <Legend />
                  <Scatter data={points} fill="#1b2a5e" fillOpacity={0.45} name="Eventos" />
                </ScatterChart>
              </ResponsiveContainer>
            </Card>

            <Card title="Conteo por region" subtitle="Agrupacion del texto de lugar de la fuente">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={regions} layout="vertical" margin={{ left: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" allowDecimals={false} fontSize={11} />
                  <YAxis type="category" dataKey="region" width={140} fontSize={11} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#5b52e6" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <Card title="Calidad de los datos del periodo" subtitle="Frescura y completitud de lo mostrado">
            <ul className="text-sm text-slate-700 grid md:grid-cols-2 gap-1">
              <li>Muestras sin magnitud: {quality.missing_magnitude} ({((quality.missing_magnitude / Math.max(1, quality.sample_size)) * 100).toFixed(1)}%)</li>
              <li>Muestras sin profundidad: {quality.missing_depth} ({((quality.missing_depth / Math.max(1, quality.sample_size)) * 100).toFixed(1)}%)</li>
              <li>IDs externos duplicados: {quality.duplicate_external_ids}</li>
              <li>Fuente: IGP / CENSIS (eventos observados) · hora de corte: {new Date().toLocaleString()}</li>
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}
