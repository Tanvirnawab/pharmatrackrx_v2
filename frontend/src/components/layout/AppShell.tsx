import { ReactNode, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { clsx } from 'clsx';
import {
  LayoutDashboard, Package, AlertCircle, BarChart2,
  FileText, Users, Bell, LogOut, Menu, X, Brain, ScanText,
} from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { authApi } from '@/api/auth';
import { useQuery } from '@tanstack/react-query';
import { notificationsApi } from '@/api/index';

interface NavItem {
  label: string;
  href: string;
  icon: ReactNode;
  roles?: string[];
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: <LayoutDashboard className="h-4 w-4" /> },
  { label: 'Transfer Orders', href: '/inwards', icon: <Package className="h-4 w-4" /> },
  { label: 'OCR Receiving', href: '/ocr/jobs', icon: <ScanText className="h-4 w-4" /> },
  { label: 'Discrepancies', href: '/discrepancies', icon: <AlertCircle className="h-4 w-4" /> },
  { label: 'Reports', href: '/reports', icon: <BarChart2 className="h-4 w-4" /> },
  { label: 'Intelligence', href: '/intelligence', icon: <Brain className="h-4 w-4" /> },
  { label: 'Audit Log', href: '/audit', icon: <FileText className="h-4 w-4" />, roles: ['admin'] },
  { label: 'Users', href: '/admin/users', icon: <Users className="h-4 w-4" />, roles: ['admin'] },
];

function SidebarNav({ mobile, onClose }: { mobile?: boolean; onClose?: () => void }) {
  const { user } = useAuthStore();

  return (
    <nav className="flex flex-1 flex-col gap-1 px-3 py-4">
      {NAV_ITEMS.filter(
        (item) => !item.roles || (user && item.roles.includes(user.role))
      ).map((item) => (
        <NavLink
          key={item.href}
          to={item.href}
          onClick={onClose}
          className={({ isActive }) =>
            clsx(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-brand-600 text-white'
                : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
            )
          }
        >
          {item.icon}
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

function SidebarContent({ onClose }: { onClose?: () => void }) {
  const { user, clearAuth } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    authApi.logout();
    clearAuth();
    navigate('/login');
  };

  return (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div className="flex h-16 shrink-0 items-center gap-2 border-b border-gray-200 px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white text-sm font-bold">
          Rx
        </div>
        <span className="text-sm font-bold text-gray-900">PharmaTrackRx</span>
      </div>

      <SidebarNav onClose={onClose} />

      {/* User footer */}
      <div className="border-t border-gray-200 p-4">
        <div className="mb-3 rounded-lg bg-gray-50 px-3 py-2">
          <p className="truncate text-sm font-medium text-gray-800">{user?.full_name}</p>
          <p className="truncate text-xs text-gray-500">{user?.email}</p>
          <span className="mt-1 inline-flex rounded-full bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700">
            {user?.role.replace('_', ' ')}
          </span>
        </div>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </div>
  );
}

function NotificationBell() {
  const { data: notifications = [] } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list(true),
    refetchInterval: 30_000,
  });
  const count = notifications.length;

  return (
    <NavLink
      to="/notifications"
      className="relative flex h-9 w-9 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
    >
      <Bell className="h-5 w-5" />
      {count > 0 && (
        <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
          {count > 9 ? '9+' : count}
        </span>
      )}
    </NavLink>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-gray-200 bg-white lg:flex lg:flex-col">
        <SidebarContent />
      </aside>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="fixed inset-0 bg-black/30"
            onClick={() => setSidebarOpen(false)}
          />
          <aside className="fixed left-0 top-0 h-full w-64 bg-white shadow-xl">
            <div className="flex h-16 items-center justify-between border-b border-gray-200 px-4">
              <span className="font-bold text-gray-900">PharmaTrackRx</span>
              <button onClick={() => setSidebarOpen(false)}>
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>
            <SidebarContent onClose={() => setSidebarOpen(false)} />
          </aside>
        </div>
      )}

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-4 lg:px-6">
          <button
            className="lg:hidden p-1 text-gray-500 hover:text-gray-900"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex-1" />
          <NotificationBell />
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
