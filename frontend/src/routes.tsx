import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { tokenStore } from '@/api/client';
import type { ReactNode } from 'react';

export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { isAuthenticated } = useAuthStore();
  const hasToken = !!tokenStore.getAccessToken();

  if (!isAuthenticated || !hasToken) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuthStore();
  if (user?.role !== 'admin') {
    return <Navigate to="/dashboard" replace />;
  }
  return <>{children}</>;
}

export function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const hasToken = !!tokenStore.getAccessToken();
  if (isAuthenticated && hasToken) {
    return <Navigate to="/dashboard" replace />;
  }
  return <>{children}</>;
}
