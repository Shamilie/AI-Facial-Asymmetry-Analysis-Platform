import React, { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClientProvider } from '@tanstack/react-query';
import { theme as appTheme } from './theme';
import { queryClient } from './queryClient';
import { useAuthStore } from '@/store/authStore';
import { AppLayout } from '@/layouts/AppLayout';
import { LoginPage } from '@/features/auth/LoginPage';
import { DashboardPage } from '@/features/dashboard/DashboardPage';
import {
  PatientListingPage,
  PatientProfilePage,
  PatientRegistrationPage,
} from '@/features/patients/PatientsPages';
import {
  ImageAcquisitionPage,
  VisitManagementPage,
} from '@/features/visits/VisitsAndImagesPages';
import {
  AIAnalysisWorkspacePage,
  LandmarkReviewWorkspacePage,
} from '@/features/analysis/AIAndLandmarksPages';
import {
  CalibrationWorkspacePage,
  ReconstructionWorkspacePage,
} from '@/features/reconstruction/ReconstructionAndCalibrationPages';
import {
  FollowUpComparisonPage,
  MeasurementResultsPage,
} from '@/features/measurements/MeasurementsAndFollowUpPages';
import {
  ReportsCenterPage,
  ResearchAnalyticsPage,
} from '@/features/reports/ReportsAndAnalyticsPages';
import {
  AIExecutionMonitorPage,
  AIModelConfigPage,
  AuditLogsPage,
  ProtocolConfigPage,
  SettingsPage,
  UserManagementPage,
} from '@/features/admin/AdminPages';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, refreshProfile } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated) {
      refreshProfile();
    }
  }, [isAuthenticated, refreshProfile]);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

const PermissionRoute: React.FC<{
  permissions?: string[];
  roles?: string[];
  children: React.ReactNode;
}> = ({ permissions, roles, children }) => {
  const { user } = useAuthStore();
  if (!user) return <Navigate to="/login" replace />;
  if (user.is_superuser) return <>{children}</>;

  const hasPerm = permissions ? permissions.some((p) => user.permissions?.includes(p)) : false;
  const hasRole = roles ? roles.some((r) => user.roles?.includes(r)) : false;

  if (permissions && roles) {
    if (!hasPerm && !hasRole) return <Navigate to="/" replace />;
  } else if (permissions) {
    if (!hasPerm) return <Navigate to="/" replace />;
  } else if (roles) {
    if (!hasRole) return <Navigate to="/" replace />;
  }
  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={appTheme}>
        <CssBaseline />
        <BrowserRouter>
          <Routes>
            {/* PAGE 1: Login */}
            <Route path="/login" element={<LoginPage />} />

            {/* Authenticated Clinical Research Shell */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              {/* PAGE 2: Dashboard */}
              <Route index element={<DashboardPage />} />

              {/* PAGE 3, 4, 5: Patients Listing, Registration Wizard, Patient Profile */}
              <Route path="patients" element={<PatientListingPage />} />
              <Route
                path="patients/new"
                element={
                  <PermissionRoute permissions={['patient:write']}>
                    <PatientRegistrationPage />
                  </PermissionRoute>
                }
              />
              <Route path="patients/:patientId" element={<PatientProfilePage />} />

              {/* PAGE 6 & 7: Visit Management & Image Acquisition */}
              <Route path="visits" element={<VisitManagementPage />} />
              <Route
                path="images"
                element={
                  <PermissionRoute permissions={['image:upload', 'image:review']}>
                    <ImageAcquisitionPage />
                  </PermissionRoute>
                }
              />
              <Route
                path="visits/:visitId/images"
                element={
                  <PermissionRoute permissions={['image:upload', 'image:review']}>
                    <ImageAcquisitionPage />
                  </PermissionRoute>
                }
              />

              {/* PAGE 8 & 9: AI Analysis Pipeline & Landmark Review */}
              <Route
                path="ai-analysis"
                element={
                  <PermissionRoute permissions={['ai:run', 'ai:manage']}>
                    <AIAnalysisWorkspacePage />
                  </PermissionRoute>
                }
              />
              <Route
                path="ai-analysis/:visitId"
                element={
                  <PermissionRoute permissions={['ai:run', 'ai:manage']}>
                    <AIAnalysisWorkspacePage />
                  </PermissionRoute>
                }
              />
              <Route
                path="landmarks"
                element={
                  <PermissionRoute permissions={['landmark:review', 'landmark:approve']}>
                    <LandmarkReviewWorkspacePage />
                  </PermissionRoute>
                }
              />
              <Route
                path="landmarks/:visitId"
                element={
                  <PermissionRoute permissions={['landmark:review', 'landmark:approve']}>
                    <LandmarkReviewWorkspacePage />
                  </PermissionRoute>
                }
              />

              {/* PAGE 10 & 11: 3D Reconstruction & Physical Calibration */}
              <Route
                path="reconstruction"
                element={
                  <PermissionRoute permissions={['ai:run']}>
                    <ReconstructionWorkspacePage />
                  </PermissionRoute>
                }
              />
              <Route
                path="reconstruction/:visitId"
                element={
                  <PermissionRoute permissions={['ai:run']}>
                    <ReconstructionWorkspacePage />
                  </PermissionRoute>
                }
              />
              <Route
                path="calibration"
                element={
                  <PermissionRoute permissions={['calibration:write']}>
                    <CalibrationWorkspacePage />
                  </PermissionRoute>
                }
              />
              <Route
                path="calibration/:visitId"
                element={
                  <PermissionRoute permissions={['calibration:write']}>
                    <CalibrationWorkspacePage />
                  </PermissionRoute>
                }
              />

              {/* PAGE 12 & 13: Measurements & Longitudinal Follow-Up Comparison */}
              <Route path="measurements" element={<MeasurementResultsPage />} />
              <Route path="measurements/:visitId" element={<MeasurementResultsPage />} />
              <Route path="follow-up" element={<FollowUpComparisonPage />} />
              <Route path="follow-up/:patientId" element={<FollowUpComparisonPage />} />

              {/* PAGE 16 & 17: Reports Center & Research Analytics */}
              <Route
                path="reports"
                element={
                  <PermissionRoute permissions={['report:generate', 'report:export']}>
                    <ReportsCenterPage />
                  </PermissionRoute>
                }
              />
              <Route path="analytics" element={<ResearchAnalyticsPage />} />

              {/* PAGE 14, 15, 18, 19, 20 & Settings: Governance & Administration */}
              <Route
                path="admin/ai-config"
                element={
                  <PermissionRoute permissions={['config:manage']}>
                    <AIModelConfigPage />
                  </PermissionRoute>
                }
              />
              <Route
                path="admin/ai-monitor"
                element={
                  <PermissionRoute permissions={['ai:manage', 'config:manage']}>
                    <AIExecutionMonitorPage />
                  </PermissionRoute>
                }
              />
              <Route
                path="admin/protocols"
                element={
                  <PermissionRoute permissions={['protocol:manage']}>
                    <ProtocolConfigPage />
                  </PermissionRoute>
                }
              />
              <Route
                path="admin/users"
                element={
                  <PermissionRoute permissions={['user:manage']}>
                    <UserManagementPage />
                  </PermissionRoute>
                }
              />
              <Route
                path="admin/audit-logs"
                element={
                  <PermissionRoute permissions={['audit:read']}>
                    <AuditLogsPage />
                  </PermissionRoute>
                }
              />
              <Route path="settings" element={<SettingsPage />} />

              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
};
