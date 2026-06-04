import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AppShell } from '@/components/layout/AppShell';
import { RequireAuth, RequireAdmin, RedirectIfAuthenticated } from '@/routes';
import { inwardApi } from '@/api/index';
import { Alert, FullPageSpinner } from '@/components/ui';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import PendingInwards from '@/pages/PendingInwards';
import InwardVerification from '@/pages/InwardVerification';
import DiscrepancyList from '@/pages/DiscrepancyList';
import DiscrepancyDetailPage from '@/pages/DiscrepancyDetail';
import Reports from '@/pages/Reports';
import AuditLog from '@/pages/AuditLog';
import UserManagement from '@/pages/admin/UserManagement';
import Intelligence from '@/pages/Intelligence';
import OCRUpload from '@/pages/ocr/OCRUpload';
import OCRJobs from '@/pages/ocr/OCRJobs';
import OCRReview from '@/pages/ocr/OCRReview';

function AppLayout() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/inwards" element={<PendingInwards />} />
        <Route path="/inward/:sessionId" element={<InwardVerification />} />
        {/* Support both URL patterns for navigating to a session */}
        <Route path="/inwards/:transferOrderId/session" element={<InwardVerificationRedirect />} />
        <Route path="/ocr/upload" element={<OCRUpload />} />
        <Route path="/ocr/jobs" element={<OCRJobs />} />
        <Route path="/ocr/jobs/:id" element={<OCRReview />} />
        <Route path="/discrepancies" element={<DiscrepancyList />} />
        <Route path="/discrepancies/:id" element={<DiscrepancyDetailPage />} />
        <Route path="/reports" element={<Reports />} />
        <Route
          path="/audit"
          element={
            <RequireAdmin>
              <AuditLog />
            </RequireAdmin>
          }
        />
        <Route
          path="/admin/users"
          element={
            <RequireAdmin>
              <UserManagement />
            </RequireAdmin>
          }
        />
        <Route path="/intelligence" element={<Intelligence />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AppShell>
  );
}

function InwardVerificationRedirect() {
  const { transferOrderId } = useParams<{ transferOrderId: string }>();
  const { data: session, isLoading, error } = useQuery({
    queryKey: ['inward-session-by-transfer', transferOrderId],
    queryFn: () => inwardApi.getSessionByTransferOrder(transferOrderId!),
    enabled: !!transferOrderId,
    retry: false,
  });

  if (isLoading) return <FullPageSpinner />;
  if (error || !session) {
    return <Alert variant="error">No inward session found for this transfer order.</Alert>;
  }
  return <Navigate to={`/inward/${session.id}`} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            <RedirectIfAuthenticated>
              <Login />
            </RedirectIfAuthenticated>
          }
        />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
