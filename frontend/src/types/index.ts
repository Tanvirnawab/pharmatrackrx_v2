// ── Auth ──────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'store_manager' | 'store_staff' | 'depot_staff';
  store_id: string | null;
  depot_id: string | null;
  is_active: boolean;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

// ── Depots & Stores ───────────────────────────────────────────────────────────

export interface Depot {
  id: string;
  name: string;
  code: string | null;
  is_active: boolean;
}

export interface Store {
  id: string;
  name: string;
  code: string | null;
  is_active: boolean;
}

// ── Transfer Orders ───────────────────────────────────────────────────────────

export type TransferOrderStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled';

export interface TransferOrderItem {
  id: string;
  line_number: number;
  item_name: string;
  expected_qty: number;
  unit: string | null;
  unit_price: number | null;
  depot_stock: number | null;
}

export interface TransferOrder {
  id: string;
  to_number: string;
  transfer_date: string;
  status: TransferOrderStatus;
  total_items: number;
  total_expected_qty: number;
  depot: Depot;
  store: Store;
  imported_at: string | null;
  import_filename: string | null;
}

export interface TransferOrderDetail extends TransferOrder {
  items: TransferOrderItem[];
}

export interface ImportResult {
  transfers_created: number;
  transfers_skipped: number;
  items_created: number;
  transfer_numbers: string[];
  errors: string[];
  message: string;
}

// ── Inward Sessions ───────────────────────────────────────────────────────────

export type VarianceType = 'match' | 'shortage' | 'excess';
export type InwardSessionStatus = 'in_progress' | 'completed';

export interface InwardItem {
  id: string;
  session_id?: string;
  line_number: number;
  item_name: string;
  expected_qty: number;
  received_qty: number | null;
  expiry_date: string | null;
  batch_number?: string | null;
  barcode_value?: string | null;
  barcode_type?: string | null;
  ocr_suggested_expiry?: string | null;
  ocr_raw_text?: string | null;
  variance: number | null;
  variance_type: VarianceType | null;
  notes: string | null;
  verified_by_name: string | null;
  verified_at: string | null;
}

export interface SessionParticipant {
  user_id: string;
  full_name: string;
  last_active_at: string | null;
}

export interface InwardSession {
  id: string;
  status: InwardSessionStatus;
  started_at: string | null;
  completed_at: string | null;
  notes: string | null;
  total_items: number;
  verified_items: number;
  completion_pct: number;
  shortage_count: number;
  excess_count: number;
  transfer_order: TransferOrder | null;
  participants: SessionParticipant[];
}

export interface InwardSessionDetail extends InwardSession {
  items: InwardItem[];
}

// ── Discrepancies ─────────────────────────────────────────────────────────────

export type DiscrepancyType = 'shortage' | 'excess' | 'wrong_medicine';
export type DiscrepancyStatus =
  | 'open'
  | 'depot_responded'
  | 'admin_resolved'
  | 'closed'
  | 'rejected';

export interface DiscrepancyComment {
  id: string;
  body: string;
  author_name: string | null;
  created_at: string;
}

export interface DiscrepancyAttachment {
  id: string;
  label: string | null;
  filename: string;
  mime_type: string;
  size_bytes: number;
  url?: string;
}

export interface Discrepancy {
  id: string;
  type: DiscrepancyType;
  status: DiscrepancyStatus;
  item_name: string;
  expected_qty: number;
  received_qty: number;
  variance_qty: number;
  notes: string | null;
  depot: Depot;
  store: Store;
  to_number: string | null;
  raised_by_name: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface DiscrepancyDetail extends Discrepancy {
  depot_response: string | null;
  depot_responded_at: string | null;
  depot_responded_by_name: string | null;
  resolution_notes: string | null;
  resolved_by_name: string | null;
  comments: DiscrepancyComment[];
  attachments: DiscrepancyAttachment[];
}

// ── Reports & Dashboard ───────────────────────────────────────────────────────

export interface DashboardSummary {
  pending_inwards: number;
  in_progress_inwards: number;
  open_discrepancies: number;
  depot_pending_response: number;
  resolved_this_week: number;
  transfer_accuracy_30d: number;
}

export interface DiscrepancyTrendPoint {
  day: string;
  type: string;
  count: number;
  total_variance: number;
}

export interface TopDiscrepancyItem {
  item_name: string;
  discrepancy_count: number;
  shortages: number;
  excesses: number;
  total_variance_qty: number;
  avg_variance_qty: number;
}

export interface DepotPerformance {
  depot_id: string;
  depot_name: string;
  total_transfers: number;
  total_items: number;
  matched_items: number;
  shortage_items: number;
  excess_items: number;
  accuracy_pct: number;
}

// ── Notifications ─────────────────────────────────────────────────────────────

export interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  payload: Record<string, string> | null;
  read_at: string | null;
  created_at: string;
}

// OCR

export type OcrJobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'approved' | 'rejected';

export interface OcrJob {
  id: string;
  status: OcrJobStatus;
  document_type: string | null;
  transfer_order_id: string | null;
  file_upload_id: string;
  engine: string | null;
  confidence_score: number | null;
  error_message: string | null;
  review_notes: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  reviewed_at: string | null;
}

export interface OcrResult {
  id: string;
  job_id: string;
  line_number: number;
  medicine_name: string | null;
  sku: string | null;
  pack_size: string | null;
  batch_number: string | null;
  expiry_date: string | null;
  quantity: number | null;
  raw_text: string | null;
  confidence_score: number | null;
  corrected_data: Record<string, unknown> | null;
}

export interface OcrMatchResult {
  id: string;
  job_id: string;
  ocr_result_id: string;
  transfer_item_id: string | null;
  match_status: 'match' | 'mismatch' | 'unknown';
  confidence_score: number | null;
  mismatch_fields: Record<string, string> | null;
  notes: string | null;
}

export interface OcrJobDetail extends OcrJob {
  results: OcrResult[];
  match_results: OcrMatchResult[];
}

// ── Pagination ────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ── Form helpers ──────────────────────────────────────────────────────────────

export interface BatchItemUpdate {
  item_id: string;
  received_qty?: number;
  expiry_date?: string;
  notes?: string;
}
