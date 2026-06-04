import api from './client';
import type {
  TransferOrder, TransferOrderDetail, ImportResult, PaginatedResponse,
  InwardSession, InwardSessionDetail, InwardItem, BatchItemUpdate,
  Discrepancy, DiscrepancyDetail, DiscrepancyComment,
  DashboardSummary, DiscrepancyTrendPoint, TopDiscrepancyItem, DepotPerformance,
  Notification, Depot, Store, User,
  OcrJob, OcrJobDetail,
} from '@/types';

// ── Transfer Orders ───────────────────────────────────────────────────────────

export const transferOrdersApi = {
  async list(params: {
    page?: number;
    page_size?: number;
    status?: string;
    store_id?: string;
    depot_id?: string;
  }): Promise<PaginatedResponse<TransferOrder>> {
    const { data } = await api.get('/transfer-orders', { params });
    return data;
  },

  async get(id: string): Promise<TransferOrderDetail> {
    const { data } = await api.get(`/transfer-orders/${id}`);
    return data;
  },

  async importExcel(file: File): Promise<ImportResult> {
    const form = new FormData();
    form.append('file', file);
    const { data } = await api.post('/transfer-orders/import', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
};

// ── Inward Sessions ───────────────────────────────────────────────────────────

export const inwardApi = {
  async startSession(transferOrderId: string): Promise<InwardSession> {
    const { data } = await api.post(`/inward/start/${transferOrderId}`);
    return data;
  },

  async getActiveSessions(): Promise<InwardSession[]> {
    const { data } = await api.get('/inward/active');
    return data;
  },

  async getSession(sessionId: string): Promise<InwardSessionDetail> {
    const { data } = await api.get(`/inward/${sessionId}`);
    return data;
  },

  async getSessionByTransferOrder(transferOrderId: string): Promise<InwardSessionDetail> {
    const { data } = await api.get(`/inward/by-transfer/${transferOrderId}`);
    return data;
  },

  async updateItem(
    sessionId: string,
    itemId: string,
    payload: { received_qty?: number; expiry_date?: string; notes?: string }
  ): Promise<InwardItem> {
    const { data } = await api.put(`/inward/${sessionId}/items/${itemId}`, payload);
    return data;
  },

  async batchUpdateItems(
    sessionId: string,
    updates: BatchItemUpdate[]
  ): Promise<InwardItem[]> {
    const { data } = await api.put(`/inward/${sessionId}/items`, { updates });
    return data;
  },

  async completeSession(sessionId: string, notes?: string): Promise<InwardSessionDetail> {
    const { data } = await api.post(`/inward/${sessionId}/complete`, { notes });
    return data;
  },
};

// ── Discrepancies ─────────────────────────────────────────────────────────────

export const discrepanciesApi = {
  async list(params: {
    page?: number;
    page_size?: number;
    status?: string;
    type?: string;
    depot_id?: string;
    store_id?: string;
  }): Promise<PaginatedResponse<Discrepancy>> {
    const { data } = await api.get('/discrepancies', { params });
    return data;
  },

  async get(id: string): Promise<DiscrepancyDetail> {
    const { data } = await api.get(`/discrepancies/${id}`);
    return data;
  },

  async addDepotResponse(id: string, response: string): Promise<DiscrepancyDetail> {
    const { data } = await api.post(`/discrepancies/${id}/depot-response`, { response });
    return data;
  },

  async resolve(
    id: string,
    new_status: string,
    resolution_notes?: string
  ): Promise<DiscrepancyDetail> {
    const { data } = await api.post(`/discrepancies/${id}/resolve`, {
      new_status,
      resolution_notes,
    });
    return data;
  },

  async addComment(id: string, body: string): Promise<DiscrepancyComment> {
    const { data } = await api.post(`/discrepancies/${id}/comments`, { body });
    return data;
  },
};

// ── Reports & Dashboard ───────────────────────────────────────────────────────

export const reportsApi = {
  async getDashboardSummary(): Promise<DashboardSummary> {
    const { data } = await api.get('/dashboard/summary');
    return data;
  },

  async getDiscrepancyTrends(params: {
    days?: number;
    store_id?: string;
    depot_id?: string;
  }): Promise<DiscrepancyTrendPoint[]> {
    const { data } = await api.get('/reports/discrepancy-trends', { params });
    return data;
  },

  async getTopMedicines(params: { days?: number; limit?: number }): Promise<TopDiscrepancyItem[]> {
    const { data } = await api.get('/reports/top-medicines', { params });
    return data;
  },

  async getDepotPerformance(params: { days?: number }): Promise<DepotPerformance[]> {
    const { data } = await api.get('/reports/depot-performance', { params });
    return data;
  },
};

// ── Notifications ─────────────────────────────────────────────────────────────

export const notificationsApi = {
  async list(unreadOnly = true): Promise<Notification[]> {
    const { data } = await api.get('/notifications', { params: { unread_only: unreadOnly } });
    return data;
  },

  async markAllRead(): Promise<void> {
    await api.post('/notifications/read-all');
  },
};

// ── Admin ─────────────────────────────────────────────────────────────────────

export const adminApi = {
  async listUsers(params: { page?: number; page_size?: number }): Promise<PaginatedResponse<User>> {
    const { data } = await api.get('/admin/users', { params });
    return data;
  },

  async createUser(payload: {
    email: string;
    full_name: string;
    password: string;
    role: string;
    store_id?: string;
    depot_id?: string;
  }): Promise<User> {
    const { data } = await api.post('/admin/users', payload);
    return data;
  },

  async updateUser(
    id: string,
    payload: Partial<{ full_name: string; role: string; store_id: string; depot_id: string; is_active: boolean }>
  ): Promise<User> {
    const { data } = await api.patch(`/admin/users/${id}`, payload);
    return data;
  },

  async listDepots(): Promise<Depot[]> {
    const { data } = await api.get('/admin/depots');
    return data;
  },

  async listStores(): Promise<Store[]> {
    const { data } = await api.get('/admin/stores');
    return data;
  },

  async getAuditLogs(params: { page?: number; entity_type?: string }) {
    const { data } = await api.get('/admin/audit-logs', { params });
    return data;
  },
};

// ── V2: Scanning & OCR ────────────────────────────────────────────────────────

export const scanningApi = {
  async scanItem(
    sessionId: string,
    itemId: string,
    rawBarcode: string
  ): Promise<{
    result: 'match' | 'mismatch' | 'unknown';
    barcode_type: string;
    is_gs1: boolean;
    gtin: string | null;
    batch_number: string | null;
    expiry_date: string | null;
    confidence: number;
    notes: string;
  }> {
    const { data } = await api.post(
      `/scanning/inward/${sessionId}/items/${itemId}/scan`,
      { raw_barcode: rawBarcode }
    );
    return data;
  },

  async ocrExtractExpiry(imageB64: string): Promise<{
    available: boolean;
    candidates: string[];
    best_date: string | null;
    confidence: number;
    raw_text: string;
    message: string;
  }> {
    const { data } = await api.post('/scanning/ocr/extract-expiry', {
      image_b64: imageB64,
    });
    return data;
  },

  async addBatchRecord(
    sessionId: string,
    itemId: string,
    payload: {
      batch_number?: string;
      expiry_date?: string;
      quantity?: number;
      barcode_value?: string;
      source?: string;
      notes?: string;
    }
  ) {
    const { data } = await api.post(
      `/scanning/inward/${sessionId}/items/${itemId}/batches`,
      payload
    );
    return data;
  },

  async listBatchRecords(sessionId: string, itemId: string) {
    const { data } = await api.get(
      `/scanning/inward/${sessionId}/items/${itemId}/batches`
    );
    return data;
  },
};

// ── V2: Intelligence ──────────────────────────────────────────────────────────

export const intelligenceApi = {
  async getExpiryPatterns(params: { days?: number; limit?: number; store_id?: string }) {
    const { data } = await api.get('/intelligence/expiry-patterns', { params });
    return data as Array<{
      item_name: string;
      expiry_date: string;
      occurrences: number;
      first_seen: string;
      last_seen: string;
      depots: string;
    }>;
  },

  async getHighFrequencyDiscrepancies(params: {
    days?: number;
    min_occurrences?: number;
    limit?: number;
    store_id?: string;
  }) {
    const { data } = await api.get('/intelligence/high-frequency-discrepancies', { params });
    return data as Array<{
      item_name: string;
      total_discrepancies: number;
      shortage_count: number;
      excess_count: number;
      avg_variance: number;
      total_variance: number;
      unresolved: number;
      depots_involved: string;
    }>;
  },

  async getBatchPatterns(params: { days?: number; limit?: number }) {
    const { data } = await api.get('/intelligence/batch-patterns', { params });
    return data as Array<{
      batch_number: string;
      item_name: string;
      transfer_count: number;
      store_count: number;
      earliest_expiry: string | null;
      latest_expiry: string | null;
      total_qty: number;
    }>;
  },

  async getExpiryRisk(params: { days_threshold?: number; limit?: number; store_id?: string }) {
    const { data } = await api.get('/intelligence/expiry-risk', { params });
    return data as Array<{
      item_name: string;
      expiry_date: string;
      received_qty: number;
      store_name: string;
      depot_name: string;
      to_number: string;
      days_until_expiry: number;
    }>;
  },
};

// OCR document receiving

export const ocrApi = {
  async upload(payload: {
    file: File;
    transfer_order_id?: string;
    document_type?: string;
  }): Promise<OcrJob> {
    const form = new FormData();
    form.append('file', payload.file);
    if (payload.transfer_order_id) form.append('transfer_order_id', payload.transfer_order_id);
    if (payload.document_type) form.append('document_type', payload.document_type);
    const { data } = await api.post('/ocr/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  async listJobs(params: { page?: number; page_size?: number; status?: string }) {
    const { data } = await api.get('/ocr/jobs', { params });
    return data as PaginatedResponse<OcrJob>;
  },

  async getJob(id: string): Promise<OcrJobDetail> {
    const { data } = await api.get(`/ocr/job/${id}`);
    return data;
  },

  async approveJob(id: string, payload: { notes?: string; corrections?: Array<Record<string, unknown>> }): Promise<OcrJobDetail> {
    const { data } = await api.post(`/ocr/job/${id}/approve`, {
      notes: payload.notes,
      corrections: payload.corrections ?? [],
    });
    return data;
  },

  async rejectJob(id: string, reason: string): Promise<OcrJob> {
    const { data } = await api.post(`/ocr/job/${id}/reject`, { reason });
    return data;
  },
};
