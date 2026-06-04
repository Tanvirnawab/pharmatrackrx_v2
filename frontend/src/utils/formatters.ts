import { format, formatDistanceToNow, parseISO } from 'date-fns';
import type { VarianceType, DiscrepancyStatus } from '@/types';

// ── Date formatting ───────────────────────────────────────────────────────────

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return format(parseISO(iso), 'dd MMM yyyy');
  } catch {
    return iso;
  }
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return format(parseISO(iso), 'dd MMM yyyy, HH:mm');
  } catch {
    return iso;
  }
}

export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return formatDistanceToNow(parseISO(iso), { addSuffix: true });
  } catch {
    return iso;
  }
}

// ── Number formatting ─────────────────────────────────────────────────────────

export function fmtQty(n: number | null | undefined): string {
  if (n == null) return '—';
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(n);
}

export function fmtVariance(v: number | null | undefined): string {
  if (v == null) return '—';
  const abs = Math.abs(v);
  const formatted = fmtQty(abs);
  if (v < 0) return `-${formatted}`;
  if (v > 0) return `+${formatted}`;
  return '0';
}

export function fmtPct(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${n.toFixed(1)}%`;
}

// ── Variance helpers ──────────────────────────────────────────────────────────

export const VARIANCE_COLORS: Record<string, string> = {
  match: 'text-emerald-700 bg-emerald-50',
  shortage: 'text-red-700 bg-red-50',
  excess: 'text-amber-700 bg-amber-50',
};

export const VARIANCE_BADGE_COLORS: Record<string, string> = {
  match: 'bg-emerald-100 text-emerald-800',
  shortage: 'bg-red-100 text-red-800',
  excess: 'bg-amber-100 text-amber-800',
};

export const VARIANCE_LABELS: Record<string, string> = {
  match: 'Match',
  shortage: 'Shortage',
  excess: 'Excess',
};

export function varianceLabel(type: VarianceType | null): string {
  if (!type) return 'Pending';
  return VARIANCE_LABELS[type] ?? type;
}

// ── Discrepancy status ────────────────────────────────────────────────────────

export const STATUS_COLORS: Record<DiscrepancyStatus, string> = {
  open: 'bg-red-100 text-red-800',
  depot_responded: 'bg-amber-100 text-amber-800',
  admin_resolved: 'bg-blue-100 text-blue-800',
  closed: 'bg-gray-100 text-gray-700',
  rejected: 'bg-gray-100 text-gray-500 line-through',
};

export const STATUS_LABELS: Record<DiscrepancyStatus, string> = {
  open: 'Open',
  depot_responded: 'Depot Responded',
  admin_resolved: 'Resolved',
  closed: 'Closed',
  rejected: 'Rejected',
};

// ── Transfer order status ─────────────────────────────────────────────────────

export const TO_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-amber-100 text-amber-800',
  completed: 'bg-emerald-100 text-emerald-800',
  cancelled: 'bg-gray-100 text-gray-600',
};

export const TO_STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  in_progress: 'In Progress',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

// ── Role labels ───────────────────────────────────────────────────────────────

export const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin',
  store_manager: 'Store Manager',
  store_staff: 'Store Staff',
  depot_staff: 'Depot Staff',
};
