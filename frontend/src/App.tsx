// PATH: src/App.tsx

import { Routes, Route, Navigate } from 'react-router-dom';
import { SessionTimeoutProvider } from './components/auth/SessionTimeoutProvider';
import { AppLayout } from './components/layout/AppLayout';
import LoginPage from './components/auth/LoginPage';
import { Dashboard } from './components/dashboard/Dashboard';
import { SensorsPage } from './components/sensors/SensorsPage';
import { JobsPage } from './components/jobs/JobsPage';
import { JobAnalysis } from './components/jobs/JobAnalysis';
import { AdminPage } from './components/admin/AdminPage';
import { NetworkPage } from './components/network/NetworkPage';
import { PreferencesPage } from './components/preferences/PreferencesPage';

function App() {
  return (
    <SessionTimeoutProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sensors"
          element={
            <ProtectedRoute>
              <SensorsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/jobs"
          element={
            <ProtectedRoute>
              <JobsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/jobs/:jobId/analysis"
          element={
            <ProtectedRoute>
              <JobAnalysis />
            </ProtectedRoute>
          }
        />
        <Route
          path="/network"
          element={
            <ProtectedRoute>
              <NetworkPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <AdminPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/preferences"
          element={
            <ProtectedRoute>
              <PreferencesPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </SessionTimeoutProvider>
  );
}

// Protected route wrapper
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <AppLayout>{children}</AppLayout>;
};

export default App; 