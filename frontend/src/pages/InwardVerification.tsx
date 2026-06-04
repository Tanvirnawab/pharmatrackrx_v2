import { useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, AlertTriangle, TrendingUp, Search, Users, ScanLine, Camera } from 'lucide-react';
import { inwardApi, scanningApi } from '@/api/index';
import {
  Button, Card, Alert, FullPageSpinner, Spinner,
} from '@/components/ui';
import { BarcodeScanner } from '@/components/inward/BarcodeScanner';
import { OCRCapture } from '@/components/inward/OCRCapture';
import { fmtQty, fmtVariance, fmtDate } from '@/utils/formatters';
import { clsx } from 'clsx';
import type { InwardItem } from '@/types';

// ── Variance badge ────────────────────────────────────────────────────────────

function VarianceBadge({ type, variance }: { type: string | null; variance: number | null }) {
  if (type === null || variance === null) {
    return <span className="text-xs text-gray-400">—</span>;
  }
  const styles: Record<string, string> = {
    match: 'text-emerald-700 font-medium',
    shortage: 'text-red-600 font-semibold',
    excess: 'text-amber-600 font-semibold',
  };
  return (
    <span className={clsx('text-sm', styles[type] ?? 'text-gray-600')}>
      {fmtVariance(variance)}
    </span>
  );
}

// ── Row component ─────────────────────────────────────────────────────────────

interface RowProps {
  item: InwardItem;
  onSave: (itemId: string, qty: number | null, expiry: string | null, notes: string | null) => Promise<void>;
  saving: boolean;
  readOnly: boolean;
}

function InwardRow({ item, onSave, saving, readOnly }: RowProps) {
  const [qty, setQty] = useState(item.received_qty?.toString() ?? '');
  const [expiry, setExpiry] = useState(item.expiry_date ?? '');
  const [dirty, setDirty] = useState(false);
  const qtyRef = useRef<HTMLInputElement>(null);
  const [showScanner, setShowScanner] = useState(false);
  const [showOCR, setShowOCR] = useState(false);
  const [scanResult, setScanResult] = useState<any>(null);
  const [scanLoading, setScanLoading] = useState(false);

  const previewVariance =
    qty !== '' ? parseFloat(qty) - item.expected_qty : null;

  const rowBg = item.variance_type === 'shortage'
    ? 'bg-red-50/40'
    : item.variance_type === 'excess'
    ? 'bg-amber-50/40'
    : item.variance_type === 'match'
    ? ''
    : '';

  const handleQtyBlur = async () => {
    if (!dirty) return;
    const parsed = qty === '' ? null : parseFloat(qty);
    await onSave(item.id, parsed, expiry || null, null);
    setDirty(false);
  };

  const handleExpiryBlur = async () => {
    if (item.received_qty === null) return; // Don't save expiry without qty
    await onSave(item.id, item.received_qty, expiry || null, null);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.currentTarget.blur();
      // Focus next row qty input
      const rows = document.querySelectorAll<HTMLInputElement>('[data-qty-input]');
      const idx = Array.from(rows).indexOf(e.currentTarget);
      if (idx >= 0 && rows[idx + 1]) rows[idx + 1].focus();
    }
  };

  return (
    <tr className={clsx('border-b border-gray-100 hover:bg-gray-50/50 transition-colors', rowBg)}>
      <td className="px-3 py-2 text-xs text-gray-400 w-10 text-right">{item.line_number}</td>
      <td className="px-4 py-2">
        <span className="text-sm font-medium text-gray-800">{item.item_name}</span>
        {item.verified_by_name && (
          <div className="text-xs text-gray-400 mt-0.5">
            Verified by {item.verified_by_name}
          </div>
        )}
      </td>
      <td className="px-4 py-2 text-sm text-right text-gray-700 tabular-nums">
        {fmtQty(item.expected_qty)}
      </td>
      <td className="px-4 py-2 w-28">
        {readOnly ? (
          <span className="text-sm tabular-nums">
            {item.received_qty !== null ? fmtQty(item.received_qty) : '—'}
          </span>
        ) : (
          <input
            ref={qtyRef}
            data-qty-input
            type="number"
            step="1"
            min="0"
            value={qty}
            onChange={(e) => { setQty(e.target.value); setDirty(true); }}
            onBlur={handleQtyBlur}
            onKeyDown={handleKeyDown}
            placeholder={fmtQty(item.expected_qty)}
            className={clsx(
              'w-full rounded-md border px-2 py-1 text-sm text-right tabular-nums',
              'focus:outline-none focus:ring-2 focus:ring-brand-500',
              item.variance_type === 'shortage' && 'border-red-300 bg-red-50',
              item.variance_type === 'excess' && 'border-amber-300 bg-amber-50',
              item.variance_type === 'match' && 'border-emerald-300 bg-emerald-50',
              !item.variance_type && 'border-gray-300'
            )}
          />
        )}
      </td>
      <td className="px-4 py-2 text-right w-24">
        <VarianceBadge
          type={dirty && qty !== '' ? (previewVariance === 0 ? 'match' : previewVariance! < 0 ? 'shortage' : 'excess') : item.variance_type}
          variance={dirty && qty !== '' ? previewVariance : item.variance}
        />
      </td>
      <td className="px-4 py-2 w-36">
        {readOnly ? (
          <span className="text-sm text-gray-600">{item.expiry_date ? fmtDate(item.expiry_date) : '—'}</span>
        ) : (
          <div className="flex items-center gap-1">
            <input
              type="date"
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
              onBlur={handleExpiryBlur}
              className="flex-1 min-w-0 rounded-md border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <button
              title="Capture expiry with camera"
              onClick={() => { setShowOCR(true); setShowScanner(false); }}
              className="shrink-0 rounded p-1 text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
            >
              <Camera className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </td>
      {/* V2: scan icon in its own narrow cell */}
      {!readOnly && (
        <td className="px-2 py-2 w-8">
          <button
            title="Scan barcode"
            onClick={() => { setShowScanner(true); setShowOCR(false); }}
            className="rounded p-1 text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
          >
            <ScanLine className="h-3.5 w-3.5" />
          </button>
        </td>
      )}
      {/* V2: inline scanner/OCR panels */}
      {(showScanner || showOCR) && (
        <td className="w-0 p-0">
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
            <div className="w-full max-w-sm max-h-[calc(100vh-2rem)] overflow-y-auto rounded-xl shadow-2xl">
            {showScanner && (
              <BarcodeScanner
                onClose={() => { setShowScanner(false); setScanResult(null); }}
                apiResult={scanResult}
                loading={scanLoading}
                onScan={async (raw) => {
                  setScanLoading(true);
                  try {
                    const res = await scanningApi.scanItem(item.session_id ?? '', item.id, raw);
                    setScanResult(res);
                    if (res.batch_number && !item.batch_number) {
                      await onSave(item.id, item.received_qty ?? null, expiry || null, null);
                    }
                    if (res.expiry_date && !expiry) {
                      setExpiry(res.expiry_date);
                    }
                  } catch { setScanResult({ result: 'unknown', barcode_type: 'error', is_gs1: false, batch_number: null, expiry_date: null, confidence: 0, notes: 'Scan API error' }); }
                  finally { setScanLoading(false); }
                }}
              />
            )}
            {showOCR && (
              <OCRCapture
                onClose={() => setShowOCR(false)}
                onConfirm={(d) => {
                  setExpiry(d);
                  setShowOCR(false);
                  onSave(item.id, item.received_qty !== null ? item.received_qty : null, d, null);
                }}
              />
            )}
            </div>
          </div>
        </td>
      )}
      <td className="px-3 py-2 w-5">
        {saving && <Spinner size="sm" />}
        {!saving && item.variance_type === 'match' && (
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
        )}
        {!saving && item.variance_type === 'shortage' && (
          <AlertTriangle className="h-4 w-4 text-red-500" />
        )}
        {!saving && item.variance_type === 'excess' && (
          <TrendingUp className="h-4 w-4 text-amber-500" />
        )}
      </td>
    </tr>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function InwardVerification() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'pending' | 'shortage' | 'excess'>('all');
  const [savingItemIds, setSavingItemIds] = useState<Set<string>>(new Set());
  const [completeConfirm, setCompleteConfirm] = useState(false);
  const [completeNotes, setCompleteNotes] = useState('');

  // Poll every 15s for multi-user updates
  const { data: session, isLoading, error } = useQuery({
    queryKey: ['inward-session', sessionId],
    queryFn: () => inwardApi.getSession(sessionId!),
    refetchInterval: 15_000,
    enabled: !!sessionId,
  });

  const updateMutation = useMutation({
    mutationFn: async ({
      itemId,
      qty,
      expiry,
      notes,
    }: {
      itemId: string;
      qty: number | null;
      expiry: string | null;
      notes: string | null;
    }) => {
      return inwardApi.updateItem(sessionId!, itemId, {
        received_qty: qty ?? undefined,
        expiry_date: expiry ?? undefined,
        notes: notes ?? undefined,
      });
    },
    onSuccess: (updatedItem) => {
      queryClient.setQueryData(['inward-session', sessionId], (old: any) => {
        if (!old) return old;
        return {
          ...old,
          items: old.items.map((i: InwardItem) =>
            i.id === updatedItem.id ? updatedItem : i
          ),
          verified_items: old.items.filter((i: InwardItem) =>
            i.id === updatedItem.id ? updatedItem.received_qty !== null : i.received_qty !== null
          ).length,
        };
      });
    },
  });

  const completeMutation = useMutation({
    mutationFn: () => inwardApi.completeSession(sessionId!, completeNotes || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transfer-orders'] });
      navigate('/inwards', { state: { message: 'Inward session completed successfully.' } });
    },
  });

  const handleSaveItem = useCallback(
    async (itemId: string, qty: number | null, expiry: string | null, notes: string | null) => {
      setSavingItemIds((s) => new Set(s).add(itemId));
      try {
        await updateMutation.mutateAsync({ itemId, qty, expiry, notes });
      } finally {
        setSavingItemIds((s) => { const n = new Set(s); n.delete(itemId); return n; });
      }
    },
    [sessionId, updateMutation]
  );

  if (isLoading) return <FullPageSpinner />;
  if (error || !session) return <Alert variant="error">Session not found.</Alert>;

  const items = session.items ?? [];
  const isReadOnly = session.status === 'completed';

  // Filter items
  const filtered = items.filter((item) => {
    const matchSearch = !search || item.item_name.toLowerCase().includes(search.toLowerCase());
    const matchFilter =
      filter === 'all' ||
      (filter === 'pending' && item.received_qty === null) ||
      (filter === 'shortage' && item.variance_type === 'shortage') ||
      (filter === 'excess' && item.variance_type === 'excess');
    return matchSearch && matchFilter;
  });

  const pending = items.filter((i) => i.received_qty === null).length;
  const shortages = items.filter((i) => i.variance_type === 'shortage').length;
  const excesses = items.filter((i) => i.variance_type === 'excess').length;
  const pct = session.completion_pct;

  const transfer = session.transfer_order;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-gray-900">
              Inward Verification
            </h1>
            {isReadOnly && (
              <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800">
                Completed
              </span>
            )}
          </div>
          {transfer && (
            <p className="text-sm text-gray-500">
              <span className="font-mono font-medium">{transfer.to_number}</span>
              {' · '}
              {transfer.depot.name} → {transfer.store.name}
              {' · '}
              {fmtDate(transfer.transfer_date)}
            </p>
          )}
        </div>
        {!isReadOnly && (
          <Button
            variant="primary"
            size="md"
            icon={<CheckCircle2 className="h-4 w-4" />}
            onClick={() => setCompleteConfirm(true)}
          >
            Complete Inward
          </Button>
        )}
      </div>

      {/* Progress bar + stats */}
      <Card>
        <div className="mb-3 flex flex-wrap gap-6 text-sm">
          <div>
            <span className="text-gray-500">Progress </span>
            <span className="font-bold text-gray-900">{session.verified_items}/{session.total_items}</span>
          </div>
          <div>
            <span className="text-gray-500">Pending </span>
            <span className="font-semibold text-gray-700">{pending}</span>
          </div>
          <div>
            <span className="text-gray-500">Shortages </span>
            <span className="font-semibold text-red-600">{shortages}</span>
          </div>
          <div>
            <span className="text-gray-500">Excesses </span>
            <span className="font-semibold text-amber-600">{excesses}</span>
          </div>
          {session.participants.length > 0 && (
            <div className="flex items-center gap-1 text-gray-500">
              <Users className="h-3.5 w-3.5" />
              {session.participants.map((p) => p.full_name).join(', ')}
            </div>
          )}
        </div>
        {/* Progress bar */}
        <div className="h-2 w-full rounded-full bg-gray-100">
          <div
            className="h-2 rounded-full bg-brand-500 transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="mt-1 text-right text-xs text-gray-400">{pct}% verified</p>
      </Card>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search medicine..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-gray-300 pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div className="flex gap-1 rounded-lg border border-gray-200 bg-white p-1">
          {[
            { key: 'all', label: 'All' },
            { key: 'pending', label: `Pending (${pending})` },
            { key: 'shortage', label: `Shortage (${shortages})` },
            { key: 'excess', label: `Excess (${excesses})` },
          ].map((opt) => (
            <button
              key={opt.key}
              onClick={() => setFilter(opt.key as any)}
              className={clsx(
                'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                filter === opt.key
                  ? 'bg-brand-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-xs text-gray-400">{filtered.length} items shown</span>
      </div>

      {/* Items table */}
      <Card padding={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 w-10">#</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Medicine</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">Expected</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 w-28">
                  Received
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 w-24">
                  Variance
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 w-36">
                  Expiry Date
                </th>
                <th className="px-3 py-3 w-5" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <InwardRow
                  key={item.id}
                  item={item}
                  onSave={handleSaveItem}
                  saving={savingItemIds.has(item.id)}
                  readOnly={isReadOnly}
                />
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-5 py-12 text-center text-sm text-gray-400">
                    No items match the current filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Complete confirmation dialog */}
      {completeConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
            <h3 className="text-base font-semibold text-gray-900">Complete Inward Session?</h3>
            <p className="mt-2 text-sm text-gray-600">
              {pending > 0 && (
                <span className="font-medium text-red-600">
                  {pending} item(s) not yet verified will be recorded as received = 0 and flagged as shortages.{' '}
                </span>
              )}
              {shortages > 0 && (
                <span>
                  {shortages} shortage discrepancy(ies) will be auto-created and assigned to the depot.{' '}
                </span>
              )}
              {excesses > 0 && (
                <span>{excesses} excess discrepancy(ies) will be created. </span>
              )}
              This action cannot be undone.
            </p>
            <textarea
              className="mt-3 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              rows={2}
              placeholder="Optional notes..."
              value={completeNotes}
              onChange={(e) => setCompleteNotes(e.target.value)}
            />
            <div className="mt-4 flex justify-end gap-3">
              <Button variant="secondary" onClick={() => setCompleteConfirm(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                loading={completeMutation.isPending}
                onClick={() => completeMutation.mutate()}
              >
                Confirm & Complete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
