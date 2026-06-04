import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, TrendingDown, Package, BarChart3, Layers } from 'lucide-react';
import { intelligenceApi } from '@/api/index';
import { Card, FullPageSpinner, EmptyState } from '@/components/ui';
import { fmtDate, fmtQty } from '@/utils/formatters';
import { clsx } from 'clsx';

type TabKey = 'expiry-risk' | 'patterns' | 'high-freq' | 'batches';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'expiry-risk',  label: 'Expiry Risk',          icon: <AlertTriangle className="h-3.5 w-3.5" /> },
  { key: 'patterns',    label: 'Expiry Patterns',       icon: <TrendingDown className="h-3.5 w-3.5" /> },
  { key: 'high-freq',   label: 'Recurring Discrepancies', icon: <BarChart3 className="h-3.5 w-3.5" /> },
  { key: 'batches',     label: 'Batch Traceability',    icon: <Layers className="h-3.5 w-3.5" /> },
];

const DAY_OPTIONS = [
  { value: 30,  label: 'Last 30 days' },
  { value: 90,  label: 'Last 90 days' },
  { value: 180, label: 'Last 6 months' },
  { value: 365, label: 'Last year' },
];

function RiskBadge({ days }: { days: number }) {
  const cls =
    days <= 30 ? 'bg-red-100 text-red-700' :
    days <= 60 ? 'bg-amber-100 text-amber-700' :
                 'bg-yellow-100 text-yellow-700';
  return (
    <span className={clsx('rounded-full px-2 py-0.5 text-xs font-medium', cls)}>
      {days}d
    </span>
  );
}

export default function Intelligence() {
  const [tab, setTab] = useState<TabKey>('expiry-risk');
  const [days, setDays] = useState(90);
  const [threshold, setThreshold] = useState(90);

  const { data: riskItems = [], isLoading: lr } = useQuery({
    queryKey: ['expiry-risk', threshold],
    queryFn: () => intelligenceApi.getExpiryRisk({ days_threshold: threshold, limit: 50 }),
    enabled: tab === 'expiry-risk',
  });

  const { data: patterns = [], isLoading: lp } = useQuery({
    queryKey: ['expiry-patterns', days],
    queryFn: () => intelligenceApi.getExpiryPatterns({ days, limit: 30 }),
    enabled: tab === 'patterns',
  });

  const { data: highFreq = [], isLoading: lf } = useQuery({
    queryKey: ['high-freq-discs', days],
    queryFn: () => intelligenceApi.getHighFrequencyDiscrepancies({ days, min_occurrences: 2 }),
    enabled: tab === 'high-freq',
  });

  const { data: batches = [], isLoading: lb } = useQuery({
    queryKey: ['batch-patterns', days],
    queryFn: () => intelligenceApi.getBatchPatterns({ days }),
    enabled: tab === 'batches',
  });

  const isLoading = lr || lp || lf || lb;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Inventory Intelligence</h1>
          <p className="text-sm text-gray-500">Expiry patterns, recurring discrepancies, and batch traceability</p>
        </div>
        <div className="flex items-center gap-2">
          {tab === 'expiry-risk' ? (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <span>Within</span>
              <select
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                {[30, 60, 90, 120, 180].map((d) => (
                  <option key={d} value={d}>{d} days</option>
                ))}
              </select>
            </div>
          ) : (
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {DAY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex flex-wrap gap-1 rounded-xl border border-gray-200 bg-white p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={clsx(
              'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
              tab === t.key
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-gray-600 hover:bg-gray-100'
            )}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <FullPageSpinner />
      ) : (
        <>
          {/* ── Expiry Risk ───────────────────────────────────────────────── */}
          {tab === 'expiry-risk' && (
            <Card padding={false}>
              <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-gray-800">
                    Items expiring within {threshold} days
                  </h2>
                  <p className="text-xs text-gray-500 mt-0.5">Based on expiry dates recorded during inward verification</p>
                </div>
                <span className="text-2xl font-bold text-red-600">{riskItems.length}</span>
              </div>
              {riskItems.length === 0 ? (
                <EmptyState title="No items at risk" description="No received stock expires within the selected window." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100 bg-gray-50">
                        <th className="px-5 py-3 text-left font-medium text-gray-600">Medicine</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Expiry</th>
                        <th className="px-4 py-3 text-center font-medium text-gray-600">Days left</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Qty</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Store</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">From</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Transfer</th>
                      </tr>
                    </thead>
                    <tbody>
                      {riskItems.map((item, i) => (
                        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                          <td className="px-5 py-2.5 font-medium text-gray-800 max-w-[220px] truncate">
                            {item.item_name}
                          </td>
                          <td className="px-4 py-2.5 text-gray-600">{fmtDate(item.expiry_date)}</td>
                          <td className="px-4 py-2.5 text-center">
                            <RiskBadge days={item.days_until_expiry} />
                          </td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-gray-600">
                            {fmtQty(item.received_qty)}
                          </td>
                          <td className="px-4 py-2.5 text-gray-600">{item.store_name}</td>
                          <td className="px-4 py-2.5 text-gray-600">{item.depot_name}</td>
                          <td className="px-4 py-2.5">
                            <span className="font-mono text-xs text-gray-500">{item.to_number}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {/* ── Expiry Patterns ───────────────────────────────────────────── */}
          {tab === 'patterns' && (
            <Card padding={false}>
              <div className="px-5 py-4 border-b border-gray-100">
                <h2 className="text-sm font-semibold text-gray-800">Repeated expiry dates</h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  Same medicine arriving with the same expiry across multiple inwards — may indicate slow movement or single-batch supplier
                </p>
              </div>
              {patterns.length === 0 ? (
                <EmptyState title="No patterns found" description="Not enough data in this period." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100 bg-gray-50">
                        <th className="px-5 py-3 text-left font-medium text-gray-600">Medicine</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Expiry</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Times seen</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">First seen</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Last seen</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Depots</th>
                      </tr>
                    </thead>
                    <tbody>
                      {patterns.map((p, i) => (
                        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                          <td className="px-5 py-2.5 font-medium text-gray-800 max-w-[220px] truncate">{p.item_name}</td>
                          <td className="px-4 py-2.5 text-gray-600">{fmtDate(p.expiry_date)}</td>
                          <td className="px-4 py-2.5 text-right">
                            <span className="font-bold text-brand-700">{p.occurrences}×</span>
                          </td>
                          <td className="px-4 py-2.5 text-gray-500 text-xs">{fmtDate(p.first_seen)}</td>
                          <td className="px-4 py-2.5 text-gray-500 text-xs">{fmtDate(p.last_seen)}</td>
                          <td className="px-4 py-2.5 text-gray-500 text-xs max-w-[200px] truncate">{p.depots}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {/* ── High-frequency Discrepancies ─────────────────────────────── */}
          {tab === 'high-freq' && (
            <Card padding={false}>
              <div className="px-5 py-4 border-b border-gray-100">
                <h2 className="text-sm font-semibold text-gray-800">Medicines with repeated discrepancies</h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  These products consistently have counting or dispatch problems — worth investigating at the source
                </p>
              </div>
              {highFreq.length === 0 ? (
                <EmptyState title="No recurring patterns" description="No medicine has 2+ discrepancies in this period." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100 bg-gray-50">
                        <th className="px-5 py-3 text-left font-medium text-gray-600">Medicine</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Total</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Shortages</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Excesses</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Avg Δ</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Unresolved</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-600">Depots</th>
                      </tr>
                    </thead>
                    <tbody>
                      {highFreq.map((h, i) => (
                        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                          <td className="px-5 py-2.5 font-medium text-gray-800 max-w-[220px] truncate">{h.item_name}</td>
                          <td className="px-4 py-2.5 text-right font-bold text-red-600">{h.total_discrepancies}</td>
                          <td className="px-4 py-2.5 text-right text-red-500">{h.shortage_count}</td>
                          <td className="px-4 py-2.5 text-right text-amber-500">{h.excess_count}</td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-gray-600">
                            {fmtQty(h.avg_variance)}
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            {h.unresolved > 0 ? (
                              <span className="font-semibold text-red-600">{h.unresolved}</span>
                            ) : (
                              <span className="text-emerald-600">—</span>
                            )}
                          </td>
                          <td className="px-4 py-2.5 text-gray-500 text-xs max-w-[200px] truncate">{h.depots_involved}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {/* ── Batch Traceability ────────────────────────────────────────── */}
          {tab === 'batches' && (
            <div className="space-y-4">
              <Card>
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-blue-50 p-2">
                    <Layers className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-800">Batch registry — V2 foundation</h3>
                    <p className="text-sm text-gray-500 mt-0.5">
                      Batch numbers are recorded when staff scan a barcode or manually add batch detail during inward verification.
                      This table shows batches appearing across multiple transfers — the foundation for recall traceability in V3.
                    </p>
                  </div>
                </div>
              </Card>
              {batches.length === 0 ? (
                <Card>
                  <EmptyState
                    title="No batch data yet"
                    description="Batch records are created when staff scan barcodes or add batch detail during inward verification. Start scanning to build traceability data."
                  />
                </Card>
              ) : (
                <Card padding={false}>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-100 bg-gray-50">
                          <th className="px-5 py-3 text-left font-medium text-gray-600">Batch No.</th>
                          <th className="px-4 py-3 text-left font-medium text-gray-600">Medicine</th>
                          <th className="px-4 py-3 text-right font-medium text-gray-600">Transfers</th>
                          <th className="px-4 py-3 text-right font-medium text-gray-600">Stores</th>
                          <th className="px-4 py-3 text-left font-medium text-gray-600">Earliest expiry</th>
                          <th className="px-4 py-3 text-left font-medium text-gray-600">Latest expiry</th>
                          <th className="px-4 py-3 text-right font-medium text-gray-600">Total qty</th>
                        </tr>
                      </thead>
                      <tbody>
                        {batches.map((b, i) => (
                          <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                            <td className="px-5 py-2.5">
                              <span className="font-mono text-xs font-medium text-gray-800 bg-gray-100 px-2 py-0.5 rounded">
                                {b.batch_number}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-gray-700 max-w-[200px] truncate">{b.item_name}</td>
                            <td className="px-4 py-2.5 text-right text-gray-600">{b.transfer_count}</td>
                            <td className="px-4 py-2.5 text-right text-gray-600">{b.store_count}</td>
                            <td className="px-4 py-2.5 text-gray-500">
                              {b.earliest_expiry ? fmtDate(b.earliest_expiry) : '—'}
                            </td>
                            <td className="px-4 py-2.5 text-gray-500">
                              {b.latest_expiry ? fmtDate(b.latest_expiry) : '—'}
                            </td>
                            <td className="px-4 py-2.5 text-right tabular-nums text-gray-600">
                              {fmtQty(b.total_qty)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
