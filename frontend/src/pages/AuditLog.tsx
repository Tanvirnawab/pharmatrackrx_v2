import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { adminApi } from '@/api/index';
import { Card, FullPageSpinner, Alert, EmptyState } from '@/components/ui';
import { fmtDateTime } from '@/utils/formatters';
import { clsx } from 'clsx';

const ENTITY_COLORS: Record<string, string> = {
  inward_session: 'bg-brand-100 text-brand-700',
  inward_item: 'bg-blue-100 text-blue-700',
  discrepancy: 'bg-red-100 text-red-700',
  transfer_order: 'bg-amber-100 text-amber-700',
  user: 'bg-gray-100 text-gray-700',
};

export default function AuditLog() {
  const [page, setPage] = useState(1);
  const [entityType, setEntityType] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['audit-logs', page, entityType],
    queryFn: () => adminApi.getAuditLogs({ page, entity_type: entityType || undefined }),
  });

  if (isLoading) return <FullPageSpinner />;
  if (error) return <Alert variant="error">Failed to load audit logs.</Alert>;

  const logs = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = Math.ceil(total / (data?.page_size ?? 50));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Audit Log</h1>
          <p className="text-sm text-gray-500">{total.toLocaleString()} entries — append-only record</p>
        </div>
        <select
          value={entityType}
          onChange={(e) => { setEntityType(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All entities</option>
          <option value="inward_session">Inward sessions</option>
          <option value="inward_item">Inward items</option>
          <option value="discrepancy">Discrepancies</option>
          <option value="transfer_order">Transfer orders</option>
          <option value="user">Users</option>
        </select>
      </div>

      <Card padding={false}>
        {logs.length === 0 ? (
          <EmptyState title="No audit entries found" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-5 py-3 text-left font-medium text-gray-600">Timestamp</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Actor</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Entity</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Label</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Action</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log: any) => (
                  <tr key={log.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-2.5 text-xs tabular-nums text-gray-500 whitespace-nowrap">
                      {fmtDateTime(log.created_at)}
                    </td>
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-gray-800">{log.actor_name ?? 'System'}</p>
                      {log.actor_role && (
                        <p className="text-xs text-gray-400">{log.actor_role}</p>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={clsx(
                          'rounded-full px-2 py-0.5 text-xs font-medium',
                          ENTITY_COLORS[log.entity_type] ?? 'bg-gray-100 text-gray-600'
                        )}
                      >
                        {log.entity_type.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-600 max-w-[200px] truncate">
                      {log.entity_label ?? log.entity_id?.slice(0, 8)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs text-gray-700">
                        {log.action}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">Page {page} of {pages}</p>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              disabled={page >= pages}
              onClick={() => setPage((p) => p + 1)}
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
