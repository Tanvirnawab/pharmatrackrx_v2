import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, MessageSquare, CheckCircle, XCircle,
  CornerDownRight, Send, AlertTriangle, TrendingUp,
} from 'lucide-react';
import { clsx } from 'clsx';
import { discrepanciesApi } from '@/api/index';
import { useAuthStore } from '@/store/authStore';
import { Button, Card, Alert, FullPageSpinner } from '@/components/ui';
import {
  fmtDate, fmtDateTime, fmtQty, fmtVariance,
  STATUS_COLORS, STATUS_LABELS,
} from '@/utils/formatters';
import type { DiscrepancyDetail } from '@/types';

function TimelineStep({
  label,
  date,
  by,
  active,
  done,
}: {
  label: string;
  date?: string | null;
  by?: string | null;
  active?: boolean;
  done?: boolean;
}) {
  return (
    <div className="flex items-start gap-3">
      <div
        className={clsx(
          'mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 text-xs',
          done
            ? 'border-emerald-500 bg-emerald-500 text-white'
            : active
            ? 'border-brand-500 bg-brand-50 text-brand-600'
            : 'border-gray-200 bg-white text-gray-400'
        )}
      >
        {done ? '✓' : ''}
      </div>
      <div className="pb-4">
        <p className={clsx('text-sm font-medium', done ? 'text-gray-800' : active ? 'text-brand-700' : 'text-gray-400')}>
          {label}
        </p>
        {date && <p className="text-xs text-gray-400">{fmtDateTime(date)}{by ? ` · ${by}` : ''}</p>}
      </div>
    </div>
  );
}

export default function DiscrepancyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();

  const [commentText, setCommentText] = useState('');
  const [depotResponseText, setDepotResponseText] = useState('');
  const [resolveNotes, setResolveNotes] = useState('');
  const [showResolvePanel, setShowResolvePanel] = useState(false);
  const [resolveAction, setResolveAction] = useState<'admin_resolved' | 'rejected' | 'closed'>('admin_resolved');

  const { data: disc, isLoading, error } = useQuery({
    queryKey: ['discrepancy', id],
    queryFn: () => discrepanciesApi.get(id!),
    enabled: !!id,
  });

  const commentMutation = useMutation({
    mutationFn: (body: string) => discrepanciesApi.addComment(id!, body),
    onSuccess: () => {
      setCommentText('');
      queryClient.invalidateQueries({ queryKey: ['discrepancy', id] });
    },
  });

  const depotResponseMutation = useMutation({
    mutationFn: (response: string) => discrepanciesApi.addDepotResponse(id!, response),
    onSuccess: () => {
      setDepotResponseText('');
      queryClient.invalidateQueries({ queryKey: ['discrepancy', id] });
      queryClient.invalidateQueries({ queryKey: ['discrepancies'] });
    },
  });

  const resolveMutation = useMutation({
    mutationFn: () => discrepanciesApi.resolve(id!, resolveAction, resolveNotes),
    onSuccess: () => {
      setShowResolvePanel(false);
      queryClient.invalidateQueries({ queryKey: ['discrepancy', id] });
      queryClient.invalidateQueries({ queryKey: ['discrepancies'] });
    },
  });

  if (isLoading) return <FullPageSpinner />;
  if (error || !disc) return <Alert variant="error">Discrepancy not found.</Alert>;

  const isAdmin = user?.role === 'admin';
  const isDepotStaff = user?.role === 'depot_staff';
  const canDepotRespond =
    (isAdmin || isDepotStaff) &&
    (disc.status === 'open' || disc.status === 'depot_responded');
  const canResolve = isAdmin && disc.status !== 'closed' && disc.status !== 'rejected';

  const typeIcon =
    disc.type === 'shortage' ? (
      <AlertTriangle className="h-5 w-5 text-red-500" />
    ) : (
      <TrendingUp className="h-5 w-5 text-amber-500" />
    );

  return (
    <div className="space-y-5">
      {/* Back + header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {typeIcon}
          <div>
            <h1 className="text-xl font-bold text-gray-900 leading-snug max-w-xl">
              {disc.item_name}
            </h1>
            <p className="text-sm text-gray-500">
              <span className="font-mono">{disc.to_number}</span>
              {' · '}
              {disc.depot.name} → {disc.store.name}
              {' · '}
              Raised {fmtDate(disc.created_at)}
              {disc.raised_by_name && ` by ${disc.raised_by_name}`}
            </p>
          </div>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-medium ${STATUS_COLORS[disc.status]}`}>
          {STATUS_LABELS[disc.status]}
        </span>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* Left column: details + comments */}
        <div className="lg:col-span-2 space-y-5">

          {/* Variance summary */}
          <Card>
            <h2 className="mb-4 text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Quantity Summary
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-lg bg-gray-50 p-3 text-center">
                <p className="text-xs text-gray-500 mb-1">Expected</p>
                <p className="text-xl font-bold text-gray-900 tabular-nums">
                  {fmtQty(disc.expected_qty)}
                </p>
              </div>
              <div className="rounded-lg bg-gray-50 p-3 text-center">
                <p className="text-xs text-gray-500 mb-1">Received</p>
                <p className="text-xl font-bold text-gray-900 tabular-nums">
                  {fmtQty(disc.received_qty)}
                </p>
              </div>
              <div
                className={clsx(
                  'rounded-lg p-3 text-center',
                  disc.variance_qty < 0 ? 'bg-red-50' : 'bg-amber-50'
                )}
              >
                <p className="text-xs text-gray-500 mb-1">Variance</p>
                <p
                  className={clsx(
                    'text-xl font-bold tabular-nums',
                    disc.variance_qty < 0 ? 'text-red-700' : 'text-amber-700'
                  )}
                >
                  {fmtVariance(disc.variance_qty)}
                </p>
              </div>
            </div>
          </Card>

          {/* Depot response */}
          {disc.depot_response && (
            <Card>
              <div className="flex items-center gap-2 mb-2">
                <CornerDownRight className="h-4 w-4 text-amber-500" />
                <h2 className="text-sm font-semibold text-gray-700">Depot Response</h2>
                {disc.depot_responded_at && (
                  <span className="text-xs text-gray-400">
                    {fmtDateTime(disc.depot_responded_at)}
                    {disc.depot_responded_by_name && ` · ${disc.depot_responded_by_name}`}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{disc.depot_response}</p>
            </Card>
          )}

          {/* Resolution */}
          {disc.resolution_notes && (
            <Card>
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="h-4 w-4 text-emerald-500" />
                <h2 className="text-sm font-semibold text-gray-700">Admin Resolution</h2>
                {disc.resolved_at && (
                  <span className="text-xs text-gray-400">
                    {fmtDateTime(disc.resolved_at)}
                    {disc.resolved_by_name && ` · ${disc.resolved_by_name}`}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{disc.resolution_notes}</p>
            </Card>
          )}

          {/* Comments thread */}
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <MessageSquare className="h-4 w-4 text-gray-400" />
              <h2 className="text-sm font-semibold text-gray-700">Comments</h2>
            </div>

            {disc.comments.length === 0 ? (
              <p className="text-sm text-gray-400 mb-4">No comments yet.</p>
            ) : (
              <div className="space-y-3 mb-4">
                {disc.comments.map((c) => (
                  <div key={c.id} className="flex gap-3">
                    <div className="h-7 w-7 shrink-0 rounded-full bg-brand-100 flex items-center justify-center text-xs font-semibold text-brand-700">
                      {(c.author_name ?? 'S').charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 rounded-lg bg-gray-50 px-3 py-2">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-semibold text-gray-700">
                          {c.author_name ?? 'System'}
                        </span>
                        <span className="text-xs text-gray-400">{fmtDateTime(c.created_at)}</span>
                      </div>
                      <p
                        className="text-sm text-gray-700 whitespace-pre-wrap"
                        dangerouslySetInnerHTML={{
                          __html: c.body.replace(
                            /\*\*(.*?)\*\*/g,
                            '<strong>$1</strong>'
                          ),
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Add comment */}
            <div className="flex gap-2">
              <textarea
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                rows={2}
                placeholder="Add a comment..."
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
              />
              <Button
                size="sm"
                variant="primary"
                icon={<Send className="h-3.5 w-3.5" />}
                loading={commentMutation.isPending}
                disabled={!commentText.trim()}
                onClick={() => commentMutation.mutate(commentText.trim())}
              >
                Post
              </Button>
            </div>
          </Card>
        </div>

        {/* Right column: timeline + actions */}
        <div className="space-y-5">
          {/* Status timeline */}
          <Card>
            <h2 className="mb-4 text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Resolution Timeline
            </h2>
            <div className="relative pl-2">
              <div className="absolute left-5 top-3 bottom-3 w-px bg-gray-200" />
              <TimelineStep
                label="Discrepancy raised"
                date={disc.created_at}
                by={disc.raised_by_name ?? undefined}
                done
              />
              <TimelineStep
                label="Depot response"
                date={disc.depot_responded_at ?? undefined}
                by={disc.depot_responded_by_name ?? undefined}
                done={!!disc.depot_response}
                active={disc.status === 'open'}
              />
              <TimelineStep
                label="Admin resolved"
                date={disc.resolved_at ?? undefined}
                by={disc.resolved_by_name ?? undefined}
                done={['admin_resolved', 'closed', 'rejected'].includes(disc.status)}
                active={disc.status === 'depot_responded'}
              />
              <TimelineStep
                label="Closed"
                done={disc.status === 'closed'}
                active={disc.status === 'admin_resolved'}
              />
            </div>
          </Card>

          {/* Action panels */}
          {canDepotRespond && !disc.depot_response && (
            <Card>
              <h2 className="mb-3 text-sm font-semibold text-gray-700">Add Depot Response</h2>
              <textarea
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                rows={3}
                placeholder="Explain what happened — wrong count, dispatch error, transit loss..."
                value={depotResponseText}
                onChange={(e) => setDepotResponseText(e.target.value)}
              />
              <Button
                className="mt-3 w-full justify-center"
                loading={depotResponseMutation.isPending}
                disabled={!depotResponseText.trim()}
                onClick={() => depotResponseMutation.mutate(depotResponseText.trim())}
              >
                Submit Response
              </Button>
            </Card>
          )}

          {canResolve && (
            <Card>
              <h2 className="mb-3 text-sm font-semibold text-gray-700">Admin Resolution</h2>
              {!showResolvePanel ? (
                <Button
                  variant="outline"
                  className="w-full justify-center"
                  onClick={() => setShowResolvePanel(true)}
                >
                  Resolve / Close
                </Button>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-col gap-1.5">
                    {[
                      { value: 'admin_resolved', label: 'Mark Resolved', color: 'text-emerald-700' },
                      { value: 'closed', label: 'Close', color: 'text-gray-700' },
                      { value: 'rejected', label: 'Reject', color: 'text-red-600' },
                    ].map((opt) => (
                      <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          name="resolve_action"
                          value={opt.value}
                          checked={resolveAction === opt.value}
                          onChange={() => setResolveAction(opt.value as any)}
                          className="text-brand-600"
                        />
                        <span className={clsx('text-sm font-medium', opt.color)}>{opt.label}</span>
                      </label>
                    ))}
                  </div>
                  <textarea
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                    rows={3}
                    placeholder="Resolution notes (required for rejection)..."
                    value={resolveNotes}
                    onChange={(e) => setResolveNotes(e.target.value)}
                  />
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      className="flex-1 justify-center"
                      onClick={() => setShowResolvePanel(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      className="flex-1 justify-center"
                      loading={resolveMutation.isPending}
                      onClick={() => resolveMutation.mutate()}
                    >
                      Confirm
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
