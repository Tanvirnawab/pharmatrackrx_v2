import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { UploadCloud } from 'lucide-react';
import { ocrApi } from '@/api/index';
import { Alert, Button, Card, Input } from '@/components/ui';

export default function OCRUpload() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [transferOrderId, setTransferOrderId] = useState('');
  const [documentType, setDocumentType] = useState('delivery_note');

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Select a document first.');
      return ocrApi.upload({
        file,
        transfer_order_id: transferOrderId || undefined,
        document_type: documentType || undefined,
      });
    },
    onSuccess: (job) => navigate(`/ocr/jobs/${job.id}`),
  });

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-900">OCR Upload</h1>
        <p className="text-sm text-gray-500">Upload delivery notes, GRNs, invoices, transfer sheets, photos, or scanned PDFs.</p>
      </div>

      {uploadMutation.error && (
        <Alert variant="error">
          {uploadMutation.error instanceof Error ? uploadMutation.error.message : 'Upload failed.'}
        </Alert>
      )}

      <Card>
        <div className="space-y-4">
          <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-brand-300 bg-brand-50 px-5 py-10 text-center hover:bg-brand-100">
            <UploadCloud className="mb-3 h-8 w-8 text-brand-600" />
            <span className="text-sm font-semibold text-brand-800">
              {file ? file.name : 'Choose document'}
            </span>
            <span className="mt-1 text-xs text-brand-600">PDF, JPG, PNG, WEBP, or TIFF up to 25 MB</span>
            <input
              type="file"
              accept="application/pdf,image/jpeg,image/png,image/webp,image/tiff"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Document type</label>
              <select
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="delivery_note">Delivery Note</option>
                <option value="supplier_invoice">Supplier Invoice</option>
                <option value="grn">Goods Received Note</option>
                <option value="transfer_sheet">Transfer Sheet</option>
                <option value="mobile_photo">Mobile Photo</option>
                <option value="scanned_pdf">Scanned PDF</option>
              </select>
            </div>
            <Input
              label="Transfer order ID"
              value={transferOrderId}
              onChange={(e) => setTransferOrderId(e.target.value)}
              placeholder="Optional UUID for matching"
              helperText="Leave blank to run OCR without matching."
            />
          </div>

          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => navigate('/ocr/jobs')}>
              View Jobs
            </Button>
            <Button
              icon={<UploadCloud className="h-4 w-4" />}
              loading={uploadMutation.isPending}
              disabled={!file}
              onClick={() => uploadMutation.mutate()}
            >
              Upload & Queue OCR
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
