import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './app/AuthContext';
import { ProtectedRoute } from './app/RouteGuard';
import { AppShell } from './components/layout/AppShell';

import { Homepage } from './pages/Homepage';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { Overview } from './pages/Overview';
import { Services } from './pages/Services';
import { ServiceDetail } from './pages/ServiceDetail';
import { Incidents } from './pages/Incidents';
import { Alerts } from './pages/Alerts';
import { Metrics } from './pages/Metrics';
import { Logs } from './pages/Logs';
import { AIAssistant } from './pages/AIAssistant';
import { Reports } from './pages/Reports';
import { Settings } from './pages/Settings';

const RegistrationRoute = () => import.meta.env.DEV || import.meta.env.VITE_PUBLIC_REGISTRATION_ENABLED === 'true'
  ? <Register />
  : <Navigate to="/login" replace />;

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Landing & Authentication Routes */}
          <Route path="/" element={<Homepage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<RegistrationRoute />} />

          {/* Authenticated Dashboard Workspace */}
          <Route path="/app" element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route index element={<Navigate to="/app/overview" replace />} />
              <Route path="overview" element={<Overview />} />
              <Route path="services" element={<Services />} />
              <Route path="services/:serviceId" element={<ServiceDetail />} />
              <Route path="incidents" element={<Incidents />} />
              <Route path="incidents/:incidentId" element={<Incidents />} />
              <Route path="alerts" element={<Alerts />} />
              <Route path="metrics" element={<Metrics />} />
              <Route path="logs" element={<Logs />} />
              <Route path="ai" element={<AIAssistant />} />
              <Route path="reports" element={<Reports />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Route>

          {/* Catch-all Redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}


