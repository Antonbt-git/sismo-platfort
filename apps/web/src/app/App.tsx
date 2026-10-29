import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./Layout";
import { useAuth } from "./AuthContext";
import LoginPage from "../modules/auth/LoginPage";
import DashboardPage from "../modules/dashboard/DashboardPage";
import EventosPage from "../modules/eventos/EventosPage";
import MapaPage from "../modules/mapa-sismico/MapaPage";
import AnalisisPage from "../modules/analisis/AnalisisPage";
import DatasetsPage from "../modules/preparacion-datos/DatasetsPage";
import ModelosPage from "../modules/modelos-ml/ModelosPage";
import EstimatesPage from "../modules/estimaciones/EstimatesPage";
import AlertasPage from "../modules/alertas/AlertasPage";
import FuentesPage from "../modules/fuentes-datos/FuentesPage";
import ReportesPage from "../modules/reportes/ReportesPage";
import UsuariosPage from "../modules/usuarios-roles/UsuariosPage";
import AuditoriaPage from "../modules/auditoria/AuditoriaPage";
import ConfiguracionPage from "../modules/configuracion/ConfiguracionPage";

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10 text-slate-500">Cargando sesion…</div>;

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route element={user ? <Layout /> : <Navigate to="/login" replace />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/eventos" element={<EventosPage />} />
        <Route path="/mapa" element={<MapaPage />} />
        <Route path="/analisis" element={<AnalisisPage />} />
        <Route path="/datasets" element={<DatasetsPage />} />
        <Route path="/modelos" element={<ModelosPage />} />
        <Route path="/estimaciones" element={<EstimatesPage />} />
        <Route path="/alertas" element={<AlertasPage />} />
        <Route path="/fuentes" element={<FuentesPage />} />
        <Route path="/reportes" element={<ReportesPage />} />
        <Route path="/usuarios" element={<UsuariosPage />} />
        <Route path="/auditoria" element={<AuditoriaPage />} />
        <Route path="/configuracion" element={<ConfiguracionPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
