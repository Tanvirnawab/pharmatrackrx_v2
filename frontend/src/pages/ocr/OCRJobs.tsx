import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FileScan, Plus } from 'lucide-react';
import { ocrApi } from '@/api/index';
import { Badge, Button, Card, FullPageSpinner } from '@/components/ui';
import { fmtDate } from '@/utils/formatters';

const STATUS_VARIANT: Record<string, 'default' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'> = {
  queued: 'warning',
  processing: 'info',
  completed: 'success',
  approved: 'success',
  rejected: 'danger',
  failed: 'danger',
};

export default function OCRJobs() {
  const { data, isLoading } = useQuery({
    queryKey: ['ocr-jobs'],
    queryFn: () => ocrApi.listJobs({ page: 1, page_size: 50 }),
    refetchInterval: 10_000,
  });

  if (isLoading) return <FullPageSpinner />;
  const jobs = data?.items ?? [];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">OCR Jobs</h1>
          <p className="text-sm text-gray-500">Review document extraction and transfer-order matching.</p>
        </div>
        <Link to="/ocr/upload">
          <Button icon={<Plus className="h-4 w-4" />}>Upload Document</Button>
        </Link>
      </div>

      <Card padding={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-5 py-3 text-left font-medium text-gray-600">Job</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Type</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Engine</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Confidence</th>
                <th className="px-5 py-3 text-right font-medium text-gray-600">Created</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <Link to={`/ocr/jobs/${job.id}`} className="flex items-center gap-2 font-medium text-brand-700 hover:underline">
                      <FileScan className="h-4 w-4" />
                      {job.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={STATUS_VARIANT[job.status] ?? 'default'}>{job.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{job.document_type ?? '-'}</td>
                  <td className="px-4 py-3 text-gray-600">{job.engine ?? '-'}</td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {job.confidence_score !== null ? `${job.confidence_score}%` : '-'}
                  </td>
                  <td className="px-5 py-3 text-right text-gray-500">{fmtDate(job.created_at)}</td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-sm text-gray-400">
                    No OCR jobs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
