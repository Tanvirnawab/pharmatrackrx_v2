// DiscrepancyList.tsx
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ChevronRight } from 'lucide-react';
import { discrepanciesApi } from '@/api/index';
import { Card, FullPageSpinner, Alert, EmptyState } from '@/components/ui';
import {
  fmtDate, fmtQty, fmtVariance, STATUS_COLORS, STATUS_LABELS,
} from '@/utils/formatters';
import type { Discrepancy } from '@/types';

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'open', label: 'Open' },
  { value: 'depot_responded', label: 'Depot Responded' },
  { value: 'admin_resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
];

const TYPE_LABELS: Record<string, string> = {
  shortage: 'Shortage',
  excess: 'Excess',
  wrong_medicine: 'Wrong Medicine',
};
const TYPE_COLORS: Record<string, string> = {
  shortage: 'bg-red-100 text-red-700',
  excess: 'bg-amber-100 text-amber-700',
  wrong_medicine: 'bg-purple-100 text-purple-700',
};

export default function DiscrepancyList() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get('status') ?? '';
  const page = Number(searchParams.get('page') ?? 1);

  const { data, isLoading, error } = useQuery({
    queryKey: ['discrepancies', status, page],
    queryFn: () =>
      discrepanciesApi.list({ status: status || undefined, page, page_size: 30 }),
    refetchInterval: 30_000,
  });

  if (isLoading) return <FullPageSpinner />;
  if (error) return <Alert variant="error">Failed to load discrepancies.</Alert>;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Discrepancies</h1>
        <p className="text-sm text-gray-500">{data?.total ?? 0} discrepancy records</p>
      </div>

      {/* Status filter */}
      <div className="flex flex-wrap gap-1 rounded-lg border border-gray-200 bg-white p-1 w-fit">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setSearchParams(tab.value ? { status: tab.value } : {})}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              status === tab.value
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <Card padding={false}>
        {data?.items.length === 0 ? (
          <EmptyState title="No discrepancies found" description="All transfers are matching." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-5 py-3 text-left font-medium text-gray-600">Medicine</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Transfer No.</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Depot → Store</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Expected</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Received</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Variance</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Type</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Raised</th>
                  <th className="px-3 py-3" />
                </tr>
              </thead>
              <tbody>
                {data?.items.map((disc: Discrepancy) => (
                  <tr
                    key={disc.id}
                    className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                    onClick={() => navigate(`/discrepancies/${disc.id}`)}
                  >
                    <td className="px-5 py-3">
                      <span className="font-medium text-gray-800 line-clamp-1 max-w-[240px] block">
                        {disc.item_name}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-gray-600">{disc.to_number}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {disc.depot.name} → {disc.store.name}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-gray-600">
                      {fmtQty(disc.expected_qty)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-gray-600">
                      {fmtQty(disc.received_qty)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <span className={disc.variance_qty < 0 ? 'text-red-600 font-semibold' : 'text-amber-600 font-semibold'}>
                        {fmtVariance(disc.variance_qty)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${TYPE_COLORS[disc.type] ?? ''}`}>
                        {TYPE_LABELS[disc.type] ?? disc.type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[disc.status]}`}>
                        {STATUS_LABELS[disc.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">{fmtDate(disc.created_at)}</td>
                    <td className="px-3 py-3">
                      <ChevronRight className="h-4 w-4 text-gray-400" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {(data?.pages ?? 0) > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">Page {data?.page} of {data?.pages}</p>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setSearchParams({ ...(status && { status }), page: String(page - 1) })}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              disabled={page >= (data?.pages ?? 1)}
              onClick={() => setSearchParams({ ...(status && { status }), page: String(page + 1) })}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
