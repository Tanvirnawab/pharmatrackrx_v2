import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell,
} from 'recharts';
import { reportsApi } from '@/api/index';
import { Card, FullPageSpinner, Alert } from '@/components/ui';
import { fmtPct, fmtDate, fmtQty } from '@/utils/formatters';

type TabKey = 'trends' | 'medicines' | 'depots';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'trends', label: 'Discrepancy Trends' },
  { key: 'medicines', label: 'Top Medicines' },
  { key: 'depots', label: 'Depot Performance' },
];

const DAY_OPTIONS = [
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
];

export default function Reports() {
  const [tab, setTab] = useState<TabKey>('trends');
  const [days, setDays] = useState(30);

  const { data: trends = [], isLoading: lt } = useQuery({
    queryKey: ['discrepancy-trends', days],
    queryFn: () => reportsApi.getDiscrepancyTrends({ days }),
    enabled: tab === 'trends',
  });

  const { data: topMeds = [], isLoading: lm } = useQuery({
    queryKey: ['top-medicines', days],
    queryFn: () => reportsApi.getTopMedicines({ days, limit: 15 }),
    enabled: tab === 'medicines',
  });

  const { data: depotPerf = [], isLoading: ld } = useQuery({
    queryKey: ['depot-performance', days],
    queryFn: () => reportsApi.getDepotPerformance({ days }),
    enabled: tab === 'depots',
  });

  const isLoading = lt || lm || ld;

  // Pivot trend data
  const trendByDay: Record<string, { day: string; shortage: number; excess: number }> = {};
  trends.forEach((pt) => {
    if (!trendByDay[pt.day]) trendByDay[pt.day] = { day: pt.day, shortage: 0, excess: 0 };
    if (pt.type === 'shortage') trendByDay[pt.day].shortage += pt.count;
    if (pt.type === 'excess') trendByDay[pt.day].excess += pt.count;
  });
  const trendData = Object.values(trendByDay).sort((a, b) => a.day.localeCompare(b.day));

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Reports & Analytics</h1>
          <p className="text-sm text-gray-500">Operational intelligence for transfer verification</p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          {DAY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-gray-200 bg-white p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === t.key
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <FullPageSpinner />
      ) : (
        <>
          {/* ── Trends ── */}
          {tab === 'trends' && (
            <Card>
              <h2 className="mb-4 text-sm font-semibold text-gray-800">
                Daily Discrepancy Count — Last {days} Days
              </h2>
              {trendData.length === 0 ? (
                <p className="py-12 text-center text-sm text-gray-400">No discrepancy data for this period.</p>
              ) : (
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart data={trendData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis
                      dataKey="day"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v) => fmtDate(v).slice(0, 6)}
                      interval="preserveStartEnd"
                    />
                    <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                    <Tooltip
                      labelFormatter={(v) => fmtDate(String(v))}
                      formatter={(v, name) => [v, name === 'shortage' ? 'Shortages' : 'Excesses']}
                    />
                    <Legend iconType="circle" iconSize={8} />
                    <Line
                      type="monotone"
                      dataKey="shortage"
                      stroke="#ef4444"
                      strokeWidth={2.5}
                      dot={false}
                      activeDot={{ r: 4 }}
                      name="shortage"
                    />
                    <Line
                      type="monotone"
                      dataKey="excess"
                      stroke="#f59e0b"
                      strokeWidth={2.5}
                      dot={false}
                      activeDot={{ r: 4 }}
                      name="excess"
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </Card>
          )}

          {/* ── Top medicines ── */}
          {tab === 'medicines' && (
            <div className="space-y-4">
              <Card>
                <h2 className="mb-4 text-sm font-semibold text-gray-800">
                  Top {topMeds.length} Medicines by Discrepancy Count
                </h2>
                {topMeds.length === 0 ? (
                  <p className="py-8 text-center text-sm text-gray-400">No data for this period.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={Math.max(260, topMeds.length * 32)}>
                    <BarChart
                      data={topMeds}
                      layout="vertical"
                      margin={{ top: 4, right: 20, left: 8, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                      <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                      <YAxis
                        dataKey="item_name"
                        type="category"
                        tick={{ fontSize: 10 }}
                        width={180}
                        tickFormatter={(v) => (v.length > 24 ? v.slice(0, 24) + '…' : v)}
                      />
                      <Tooltip
                        formatter={(v, name) => [v, name === 'shortages' ? 'Shortages' : 'Excesses']}
                      />
                      <Legend iconType="square" iconSize={8} />
                      <Bar dataKey="shortages" stackId="a" fill="#ef4444" name="shortages" />
                      <Bar dataKey="excesses" stackId="a" fill="#f59e0b" name="excesses" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </Card>

              {/* Table view */}
              <Card padding={false}>
                <div className="border-b border-gray-100 px-5 py-3">
                  <h2 className="text-sm font-semibold text-gray-800">Detailed Breakdown</h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100 bg-gray-50">
                        <th className="px-5 py-3 text-left font-medium text-gray-600">Medicine</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Discrepancies</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Shortages</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Excesses</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Total Variance</th>
                        <th className="px-4 py-3 text-right font-medium text-gray-600">Avg Variance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topMeds.map((med, i) => (
                        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                          <td className="px-5 py-2.5 font-medium text-gray-800">{med.item_name}</td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-gray-600">{med.discrepancy_count}</td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-red-600">{med.shortages}</td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-amber-600">{med.excesses}</td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-gray-600">
                            {fmtQty(med.total_variance_qty)}
                          </td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-gray-600">
                            {fmtQty(med.avg_variance_qty)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}

          {/* ── Depot performance ── */}
          {tab === 'depots' && (
            <div className="space-y-4">
              {depotPerf.length === 0 ? (
                <Card>
                  <p className="py-8 text-center text-sm text-gray-400">
                    No completed inward sessions in this period.
                  </p>
                </Card>
              ) : (
                <>
                  {/* Accuracy chart */}
                  <Card>
                    <h2 className="mb-4 text-sm font-semibold text-gray-800">Transfer Accuracy by Depot</h2>
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={depotPerf} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis
                          dataKey="depot_name"
                          tick={{ fontSize: 11 }}
                          tickFormatter={(v) => (v.length > 12 ? v.slice(0, 12) + '…' : v)}
                        />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                        <Tooltip formatter={(v) => [`${v}%`, 'Accuracy']} />
                        <Bar dataKey="accuracy_pct" name="Accuracy" radius={[4, 4, 0, 0]}>
                          {depotPerf.map((d, i) => (
                            <Cell
                              key={i}
                              fill={d.accuracy_pct >= 95 ? '#10b981' : d.accuracy_pct >= 85 ? '#f59e0b' : '#ef4444'}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>

                  {/* Performance table */}
                  <Card padding={false}>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-100 bg-gray-50">
                            <th className="px-5 py-3 text-left font-medium text-gray-600">Depot</th>
                            <th className="px-4 py-3 text-right font-medium text-gray-600">Transfers</th>
                            <th className="px-4 py-3 text-right font-medium text-gray-600">Total Items</th>
                            <th className="px-4 py-3 text-right font-medium text-gray-600">Matched</th>
                            <th className="px-4 py-3 text-right font-medium text-gray-600">Shortages</th>
                            <th className="px-4 py-3 text-right font-medium text-gray-600">Excesses</th>
                            <th className="px-4 py-3 text-right font-medium text-gray-600">Accuracy</th>
                          </tr>
                        </thead>
                        <tbody>
                          {depotPerf
                            .slice()
                            .sort((a, b) => b.accuracy_pct - a.accuracy_pct)
                            .map((d) => (
                              <tr key={d.depot_id} className="border-b border-gray-50 hover:bg-gray-50">
                                <td className="px-5 py-3 font-medium text-gray-800">{d.depot_name}</td>
                                <td className="px-4 py-3 text-right tabular-nums text-gray-600">{d.total_transfers}</td>
                                <td className="px-4 py-3 text-right tabular-nums text-gray-600">
                                  {d.total_items.toLocaleString()}
                                </td>
                                <td className="px-4 py-3 text-right tabular-nums text-emerald-600">
                                  {d.matched_items.toLocaleString()}
                                </td>
                                <td className="px-4 py-3 text-right tabular-nums text-red-600">
                                  {d.shortage_items.toLocaleString()}
                                </td>
                                <td className="px-4 py-3 text-right tabular-nums text-amber-600">
                                  {d.excess_items.toLocaleString()}
                                </td>
                                <td className="px-4 py-3 text-right">
                                  <span
                                    className={`font-bold ${
                                      d.accuracy_pct >= 95
                                        ? 'text-emerald-700'
                                        : d.accuracy_pct >= 85
                                        ? 'text-amber-700'
                                        : 'text-red-700'
                                    }`}
                                  >
                                    {fmtPct(d.accuracy_pct)}
                                  </span>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
