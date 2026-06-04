import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, XCircle } from 'lucide-react';
import { ocrApi } from '@/api/index';
import { Alert, Badge, Button, Card, FullPageSpinner } from '@/components/ui';

export default function OCRReview() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState('');
  const [rejectReason, setRejectReason] = useState('');

  const { data: job, isLoading, error } = useQuery({
    queryKey: ['ocr-job', id],
    queryFn: () => ocrApi.getJob(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'queued' || status === 'processing' ? 5000 : false;
    },
  });

  const approveMutation = useMutation({
    mutationFn: () => ocrApi.approveJob(id!, { notes }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ocr-job', id] }),
  });

  const rejectMutation = useMutation({
    mutationFn: () => ocrApi.rejectJob(id!, rejectReason || 'Rejected during review'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ocr-job', id] }),
  });

  if (isLoading) return <FullPageSpinner />;
  if (error || !job) return <Alert variant="error">OCR job not found.</Alert>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">OCR Review</h1>
          <p className="text-sm text-gray-500">
            Job {job.id.slice(0, 8)} · {job.document_type ?? 'document'} · {job.engine ?? 'queued'}
          </p>
        </div>
        <Link to="/ocr/jobs" className="text-sm font-medium text-brand-700 hover:underline">
          Back to jobs
        </Link>
      </div>

      {job.error_message && <Alert variant="error">{job.error_message}</Alert>}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <p className="text-xs font-medium text-gray-500">Status</p>
          <div className="mt-2"><Badge>{job.status}</Badge></div>
        </Card>
        <Card>
          <p className="text-xs font-medium text-gray-500">Confidence</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{job.confidence_score ?? 0}%</p>
        </Card>
        <Card>
          <p className="text-xs font-medium text-gray-500">Extracted lines</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{job.results.length}</p>
        </Card>
        <Card>
          <p className="text-xs font-medium text-gray-500">Mismatches</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">
            {job.match_results.filter((m) => m.match_status === 'mismatch').length}
          </p>
        </Card>
      </div>

      <Card padding={false}>
        <div className="border-b border-gray-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-gray-800">Match Review Table</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="px-5 py-3 text-left font-medium text-gray-600">Medicine</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Batch</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Expiry</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Qty</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Match</th>
                <th className="px-5 py-3 text-left font-medium text-gray-600">Raw text</th>
              </tr>
            </thead>
            <tbody>
              {job.results.map((result) => {
                const match = job.match_results.find((m) => m.ocr_result_id === result.id);
                return (
                  <tr key={result.id} className="border-b border-gray-50 align-top hover:bg-gray-50">
                    <td className="px-5 py-3 font-medium text-gray-800">{result.medicine_name ?? '-'}</td>
                    <td className="px-4 py-3 text-gray-600">{result.batch_number ?? '-'}</td>
                    <td className="px-4 py-3 text-gray-600">{result.expiry_date ?? '-'}</td>
                    <td className="px-4 py-3 text-right text-gray-700">{result.quantity ?? '-'}</td>
                    <td className="px-4 py-3">
                      <Badge variant={match?.match_status === 'match' ? 'success' : match?.match_status === 'mismatch' ? 'danger' : 'warning'}>
                        {match?.match_status ?? 'unknown'}
                      </Badge>
                    </td>
                    <td className="max-w-md px-5 py-3 text-xs text-gray-500">{result.raw_text ?? '-'}</td>
                  </tr>
                );
              })}
              {job.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-sm text-gray-400">
                    Results will appear after the worker processes this job.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-700">Review notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <div className="flex flex-wrap justify-end gap-3">
            <input
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Reject reason"
              className="min-w-64 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <Button
              variant="danger"
              icon={<XCircle className="h-4 w-4" />}
              loading={rejectMutation.isPending}
              onClick={() => rejectMutation.mutate()}
            >
              Reject
            </Button>
            <Button
              icon={<CheckCircle2 className="h-4 w-4" />}
              loading={approveMutation.isPending}
              disabled={job.status !== 'completed'}
              onClick={() => approveMutation.mutate()}
            >
              Approve
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
