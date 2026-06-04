import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { reportsApi } from '@/api/index';
import { StatCard, Card, FullPageSpinner, Alert } from '@/components/ui';
import { fmtPct, fmtDate } from '@/utils/formatters';

export default function Dashboard() {
  const navigate = useNavigate();

  const { data: summary, isLoading: loadingSummary, error } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: reportsApi.getDashboardSummary,
    refetchInterval: 60_000,
  });

  const { data: trends = [] } = useQuery({
    queryKey: ['discrepancy-trends', 30],
    queryFn: () => reportsApi.getDiscrepancyTrends({ days: 30 }),
  });

  const { data: topMeds = [] } = useQuery({
    queryKey: ['top-medicines', 30],
    queryFn: () => reportsApi.getTopMedicines({ days: 30, limit: 8 }),
  });

  const { data: depotPerf = [] } = useQuery({
    queryKey: ['depot-performance', 30],
    queryFn: () => reportsApi.getDepotPerformance({ days: 30 }),
  });

  if (loadingSummary) return <FullPageSpinner />;
  if (error) return <Alert variant="error">Failed to load dashboard data.</Alert>;

  // Process trends for chart — pivot shortage/excess by day
  const trendsByDay: Record<string, { day: string; shortage: number; excess: number }> = {};
  trends.forEach((pt) => {
    if (!trendsByDay[pt.day]) trendsByDay[pt.day] = { day: pt.day, shortage: 0, excess: 0 };
    if (pt.type === 'shortage') trendsByDay[pt.day].shortage += pt.count;
    if (pt.type === 'excess') trendsByDay[pt.day].excess += pt.count;
  });
  const trendData = Object.values(trendsByDay).sort((a, b) => a.day.localeCompare(b.day));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500">Operations overview — refreshed every minute</p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard
          label="Pending Inwards"
          value={summary!.pending_inwards}
          color={summary!.pending_inwards > 0 ? 'warning' : 'default'}
          onClick={() => navigate('/inwards?status=pending')}
        />
        <StatCard
          label="In Progress"
          value={summary!.in_progress_inwards}
          color={summary!.in_progress_inwards > 0 ? 'brand' : 'default'}
          onClick={() => navigate('/inwards?status=in_progress')}
        />
        <StatCard
          label="Open Discrepancies"
          value={summary!.open_discrepancies}
          color={summary!.open_discrepancies > 0 ? 'danger' : 'success'}
          onClick={() => navigate('/discrepancies?status=open')}
        />
        <StatCard
          label="Awaiting Depot"
          value={summary!.depot_pending_response}
          color={summary!.depot_pending_response > 0 ? 'warning' : 'default'}
          onClick={() => navigate('/discrepancies?status=open')}
        />
        <StatCard
          label="Resolved This Week"
          value={summary!.resolved_this_week}
          color="success"
          onClick={() => navigate('/discrepancies?status=admin_resolved')}
        />
        <StatCard
          label="Transfer Accuracy"
          value={fmtPct(summary!.transfer_accuracy_30d)}
          sub="last 30 days"
          color={
            summary!.transfer_accuracy_30d >= 95
              ? 'success'
              : summary!.transfer_accuracy_30d >= 85
              ? 'warning'
              : 'danger'
          }
        />
      </div>

      {/* Charts row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Discrepancy trends */}
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-gray-800">
            Discrepancy Trend — Last 30 Days
          </h2>
          {trendData.length === 0 ? (
            <div className="flex h-40 items-center justify-center text-sm text-gray-400">
              No discrepancy data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={trendData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => fmtDate(v).slice(0, 6)}
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
                  strokeWidth={2}
                  dot={false}
                  name="shortage"
                />
                <Line
                  type="monotone"
                  dataKey="excess"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                  name="excess"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>

        {/* Top medicines */}
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-gray-800">
            Top Discrepancy Medicines — Last 30 Days
          </h2>
          {topMeds.length === 0 ? (
            <div className="flex h-40 items-center justify-center text-sm text-gray-400">
              No data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={topMeds.slice(0, 6)}
                layout="vertical"
                margin={{ top: 4, right: 8, left: 8, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                <YAxis
                  dataKey="item_name"
                  type="category"
                  tick={{ fontSize: 10 }}
                  width={130}
                  tickFormatter={(v) => (v.length > 18 ? v.slice(0, 18) + '…' : v)}
                />
                <Tooltip formatter={(v, n) => [v, n === 'shortages' ? 'Shortages' : 'Excesses']} />
                <Legend iconType="square" iconSize={8} />
                <Bar dataKey="shortages" stackId="a" fill="#ef4444" name="shortages" />
                <Bar dataKey="excesses" stackId="a" fill="#f59e0b" name="excesses" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* Depot performance table */}
      {depotPerf.length > 0 && (
        <Card padding={false}>
          <div className="border-b border-gray-200 px-5 py-4">
            <h2 className="text-sm font-semibold text-gray-800">Depot Accuracy — Last 30 Days</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-5 py-3 text-left font-medium text-gray-600">Depot</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Transfers</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Items</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Shortages</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Excesses</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {depotPerf.map((d) => (
                  <tr key={d.depot_id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3 font-medium text-gray-800">{d.depot_name}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{d.total_transfers}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{d.total_items.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-red-600">{d.shortage_items.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-amber-600">{d.excess_items.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={`font-semibold ${d.accuracy_pct >= 95 ? 'text-emerald-700' : d.accuracy_pct >= 85 ? 'text-amber-700' : 'text-red-700'}`}>
                        {fmtPct(d.accuracy_pct)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
