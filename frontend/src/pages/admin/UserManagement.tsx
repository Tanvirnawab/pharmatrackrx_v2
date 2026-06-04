import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { UserPlus, Pencil, ToggleLeft, ToggleRight } from 'lucide-react';
import { adminApi } from '@/api/index';
import { Button, Card, Input, Alert, FullPageSpinner, EmptyState } from '@/components/ui';
import { ROLE_LABELS } from '@/utils/formatters';
import type { User, Store, Depot } from '@/types';

function UserModal({
  onClose,
  onSave,
  stores,
  depots,
  saving,
  error,
}: {
  onClose: () => void;
  onSave: (data: any) => void;
  stores: Store[];
  depots: Depot[];
  saving: boolean;
  error?: string;
}) {
  const [form, setForm] = useState({
    email: '',
    full_name: '',
    password: '',
    role: 'store_staff',
    store_id: '',
    depot_id: '',
  });

  const update = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const needsStore = ['store_manager', 'store_staff'].includes(form.role);
  const needsDepot = form.role === 'depot_staff';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
        <h3 className="mb-5 text-base font-semibold text-gray-900">Create New User</h3>

        {error && <Alert variant="error" className="mb-4">{error}</Alert>}

        <div className="space-y-3">
          <Input label="Full name" value={form.full_name} onChange={(e) => update('full_name', e.target.value)} />
          <Input label="Email" type="email" value={form.email} onChange={(e) => update('email', e.target.value)} />
          <Input label="Password" type="password" value={form.password} onChange={(e) => update('password', e.target.value)} />

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Role</label>
            <select
              value={form.role}
              onChange={(e) => update('role', e.target.value)}
              className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {Object.entries(ROLE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>

          {needsStore && (
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Assigned Store</label>
              <select
                value={form.store_id}
                onChange={(e) => update('store_id', e.target.value)}
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">Select store…</option>
                {stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          )}

          {needsDepot && (
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Assigned Depot</label>
              <select
                value={form.depot_id}
                onChange={(e) => update('depot_id', e.target.value)}
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">Select depot…</option>
                {depots.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
          )}
        </div>

        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={saving}
            onClick={() =>
              onSave({
                ...form,
                store_id: needsStore && form.store_id ? form.store_id : undefined,
                depot_id: needsDepot && form.depot_id ? form.depot_id : undefined,
              })
            }
          >
            Create User
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function UserManagement() {
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [createError, setCreateError] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => adminApi.listUsers({ page: 1, page_size: 100 }),
  });

  const { data: stores = [] } = useQuery({
    queryKey: ['stores'],
    queryFn: adminApi.listStores,
  });

  const { data: depots = [] } = useQuery({
    queryKey: ['depots'],
    queryFn: adminApi.listDepots,
  });

  const createMutation = useMutation({
    mutationFn: adminApi.createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setShowModal(false);
      setCreateError('');
    },
    onError: (err: any) => {
      setCreateError(err?.response?.data?.detail ?? 'Failed to create user.');
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      adminApi.updateUser(id, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });

  if (isLoading) return <FullPageSpinner />;

  const users = data?.items ?? [];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">User Management</h1>
          <p className="text-sm text-gray-500">{users.length} users</p>
        </div>
        <Button icon={<UserPlus className="h-4 w-4" />} onClick={() => setShowModal(true)}>
          Add User
        </Button>
      </div>

      <Card padding={false}>
        {users.length === 0 ? (
          <EmptyState title="No users found" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-5 py-3 text-left font-medium text-gray-600">Name</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Email</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Role</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Assigned To</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {users.map((user: User) => {
                  const assignedStore = stores.find((s) => s.id === user.store_id);
                  const assignedDepot = depots.find((d) => d.id === user.depot_id);
                  return (
                    <tr key={user.id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-5 py-3 font-medium text-gray-800">{user.full_name}</td>
                      <td className="px-4 py-3 text-gray-600">{user.email}</td>
                      <td className="px-4 py-3">
                        <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700">
                          {ROLE_LABELS[user.role] ?? user.role}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {assignedStore?.name ?? assignedDepot?.name ?? (user.role === 'admin' ? 'All stores' : '—')}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                            user.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'
                          }`}
                        >
                          {user.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          title={user.is_active ? 'Deactivate user' : 'Activate user'}
                          onClick={() => toggleMutation.mutate({ id: user.id, is_active: !user.is_active })}
                          className="text-gray-400 hover:text-gray-700 transition-colors"
                        >
                          {user.is_active ? (
                            <ToggleRight className="h-5 w-5 text-emerald-500" />
                          ) : (
                            <ToggleLeft className="h-5 w-5" />
                          )}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {showModal && (
        <UserModal
          onClose={() => { setShowModal(false); setCreateError(''); }}
          onSave={(data) => createMutation.mutate(data)}
          stores={stores}
          depots={depots}
          saving={createMutation.isPending}
          error={createError}
        />
      )}
    </div>
  );
}
