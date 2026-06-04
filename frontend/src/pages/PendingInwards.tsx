import { useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, PlayCircle, Eye, RefreshCw } from 'lucide-react';
import { transferOrdersApi, inwardApi } from '@/api/index';
import {
  Button, Card, Badge, Alert, FullPageSpinner, EmptyState,
} from '@/components/ui';
import {
  fmtDate, fmtQty, TO_STATUS_COLORS, TO_STATUS_LABELS,
} from '@/utils/formatters';
import type { TransferOrder } from '@/types';

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
];

export default function PendingInwards() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importMsg, setImportMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const status = searchParams.get('status') ?? '';
  const page = Number(searchParams.get('page') ?? 1);

  const { data, isLoading, error } = useQuery({
    queryKey: ['transfer-orders', status, page],
    queryFn: () => transferOrdersApi.list({ status: status || undefined, page, page_size: 25 }),
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => transferOrdersApi.importExcel(file),
    onSuccess: (result) => {
      setImportMsg({
        type: 'success',
        text: result.message,
      });
      queryClient.invalidateQueries({ queryKey: ['transfer-orders'] });
    },
    onError: (err: any) => {
      setImportMsg({
        type: 'error',
        text: err?.response?.data?.detail ?? 'Import failed.',
      });
    },
  });

  const startMutation = useMutation({
    mutationFn: (transferOrderId: string) => inwardApi.startSession(transferOrderId),
    onSuccess: (session) => navigate(`/inward/${session.id}`),
    onError: (err: any) => {
      alert(err?.response?.data?.detail ?? 'Failed to start session.');
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) importMutation.mutate(file);
    e.target.value = '';
  };

  if (isLoading) return <FullPageSpinner />;
  if (error) return <Alert variant="error">Failed to load transfer orders.</Alert>;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Transfer Orders</h1>
          <p className="text-sm text-gray-500">
            {data?.total ?? 0} orders total
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw className="h-4 w-4" />}
            onClick={() => queryClient.invalidateQueries({ queryKey: ['transfer-orders'] })}
          >
            Refresh
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            className="hidden"
            onChange={handleFileChange}
          />
          <Button
            variant="primary"
            size="sm"
            icon={<Upload className="h-4 w-4" />}
            loading={importMutation.isPending}
            onClick={() => fileInputRef.current?.click()}
          >
            Import Excel
          </Button>
        </div>
      </div>

      {/* Import result */}
      {importMsg && (
        <Alert variant={importMsg.type}>
          {importMsg.text}
          <button
            className="ml-2 text-xs underline"
            onClick={() => setImportMsg(null)}
          >
            Dismiss
          </button>
        </Alert>
      )}

      {/* Status filter tabs */}
      <div className="flex gap-1 rounded-lg border border-gray-200 bg-white p-1 w-fit">
        {STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => {
              setSearchParams(opt.value ? { status: opt.value } : {});
            }}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              status === opt.value
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <Card padding={false}>
        {data?.items.length === 0 ? (
          <EmptyState
            title="No transfer orders found"
            description={
              status
                ? `No ${status.replace('_', ' ')} transfer orders.`
                : 'Import an AExpert Excel export to get started.'
            }
            action={
              <Button
                icon={<Upload className="h-4 w-4" />}
                onClick={() => fileInputRef.current?.click()}
              >
                Import Excel
              </Button>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-5 py-3 text-left font-medium text-gray-600">Transfer No.</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Date</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Depot</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Store</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Items</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Total Qty</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((order: TransferOrder) => (
                  <tr key={order.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3">
                      <span className="font-mono text-xs font-medium text-gray-800">
                        {order.to_number}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{fmtDate(order.transfer_date)}</td>
                    <td className="px-4 py-3 text-gray-700">{order.depot.name}</td>
                    <td className="px-4 py-3 text-gray-700">{order.store.name}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{order.total_items}</td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {fmtQty(order.total_expected_qty)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${TO_STATUS_COLORS[order.status]}`}
                      >
                        {TO_STATUS_LABELS[order.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {order.status === 'pending' && (
                          <Button
                            size="sm"
                            variant="primary"
                            icon={<PlayCircle className="h-3.5 w-3.5" />}
                            loading={startMutation.isPending}
                            onClick={() => startMutation.mutate(order.id)}
                          >
                            Start
                          </Button>
                        )}
                        {order.status === 'in_progress' && (
                          <Button
                            size="sm"
                            variant="outline"
                            icon={<PlayCircle className="h-3.5 w-3.5" />}
                            onClick={() => navigate(`/inwards/${order.id}/session`)}
                          >
                            Continue
                          </Button>
                        )}
                        {order.status === 'completed' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={<Eye className="h-3.5 w-3.5" />}
                            onClick={() => navigate(`/inwards/${order.id}`)}
                          >
                            View
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Pagination */}
      {(data?.pages ?? 0) > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Page {data?.page} of {data?.pages} ({data?.total} total)
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={page <= 1}
              onClick={() => setSearchParams({ ...(status && { status }), page: String(page - 1) })}
            >
              Previous
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={page >= (data?.pages ?? 1)}
              onClick={() => setSearchParams({ ...(status && { status }), page: String(page + 1) })}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
