/**
 * BarcodeScanner — inline barcode scan widget for the inward verification row.
 *
 * Two modes:
 *   1. Manual: paste/type a barcode string (always works)
 *   2. Camera: uses @zxing/library to decode from device camera (mobile-first)
 *
 * The parent receives the raw barcode string; it calls the API and handles the result.
 * This component is purely presentation + capture.
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { Camera, CameraOff, ScanLine, X, CheckCircle, AlertTriangle, HelpCircle } from 'lucide-react';
import { clsx } from 'clsx';

interface BarcodeScannerProps {
  onScan: (rawBarcode: string) => void;
  onClose: () => void;
  /** Result from the API after the parent submits the scan */
  apiResult?: {
    result: 'match' | 'mismatch' | 'unknown';
    barcode_type: string;
    is_gs1: boolean;
    batch_number: string | null;
    expiry_date: string | null;
    notes: string;
  } | null;
  loading?: boolean;
}

const RESULT_STYLES = {
  match: { icon: CheckCircle, bg: 'bg-emerald-50 border-emerald-300', text: 'text-emerald-700', label: 'Match' },
  mismatch: { icon: AlertTriangle, bg: 'bg-red-50 border-red-300', text: 'text-red-700', label: 'Mismatch' },
  unknown: { icon: HelpCircle, bg: 'bg-amber-50 border-amber-300', text: 'text-amber-700', label: 'Unknown' },
};

export function BarcodeScanner({ onScan, onClose, apiResult, loading }: BarcodeScannerProps) {
  const [mode, setMode] = useState<'manual' | 'camera'>('manual');
  const [manualValue, setManualValue] = useState('');
  const [cameraError, setCameraError] = useState('');
  const [scanning, setScanning] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const codeReaderRef = useRef<any>(null);

  // ── Camera scanning via @zxing/library ────────────────────────────────────
  const startCamera = useCallback(async () => {
    setCameraError('');
    setScanning(true);
    try {
      const { BrowserMultiFormatReader } = await import('@zxing/library');
      const reader = new BrowserMultiFormatReader();
      codeReaderRef.current = reader;

      const devices = await reader.listVideoInputDevices();
      if (!devices.length) throw new Error('No camera found on this device.');

      // Prefer rear camera on mobile
      const preferred = devices.find(
        (d) => d.label.toLowerCase().includes('back') || d.label.toLowerCase().includes('rear')
      ) ?? devices[0];

      await reader.decodeFromVideoDevice(
        preferred.deviceId,
        videoRef.current!,
        (result, err) => {
          if (result) {
            const text = result.getText();
            reader.reset();
            setScanning(false);
            onScan(text);
          }
        }
      );
    } catch (e: any) {
      setCameraError(e?.message ?? 'Camera unavailable. Use manual entry.');
      setScanning(false);
    }
  }, [onScan]);

  const stopCamera = useCallback(() => {
    if (codeReaderRef.current) {
      codeReaderRef.current.reset();
      codeReaderRef.current = null;
    }
    setScanning(false);
  }, []);

  useEffect(() => {
    if (mode === 'camera') startCamera();
    return () => stopCamera();
  }, [mode]);

  useEffect(() => {
    return () => stopCamera();
  }, []);

  const handleManualSubmit = () => {
    if (manualValue.trim()) {
      onScan(manualValue.trim());
    }
  };

  const resultConfig = apiResult ? RESULT_STYLES[apiResult.result] : null;

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-lg p-4 w-full max-w-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <ScanLine className="h-4 w-4 text-brand-600" />
          <span className="text-sm font-semibold text-gray-800">Scan Barcode</span>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-1 rounded-lg border border-gray-200 bg-gray-50 p-1 mb-3">
        {([['manual', 'Manual entry'], ['camera', 'Camera']] as const).map(([m, label]) => (
          <button
            key={m}
            onClick={() => { stopCamera(); setMode(m); setCameraError(''); }}
            className={clsx(
              'flex-1 rounded-md py-1.5 text-xs font-medium transition-colors',
              mode === m ? 'bg-white text-brand-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Manual mode */}
      {mode === 'manual' && (
        <div className="space-y-2">
          <input
            type="text"
            autoFocus
            placeholder="Type or paste barcode…"
            value={manualValue}
            onChange={(e) => setManualValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleManualSubmit()}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <button
            disabled={!manualValue.trim() || loading}
            onClick={handleManualSubmit}
            className="w-full rounded-lg bg-brand-600 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-40 transition-colors"
          >
            {loading ? 'Verifying…' : 'Submit'}
          </button>
        </div>
      )}

      {/* Camera mode */}
      {mode === 'camera' && (
        <div className="space-y-2">
          {cameraError ? (
            <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-xs text-red-700">
              <p className="font-medium mb-1">Camera unavailable</p>
              <p>{cameraError}</p>
              <button
                className="mt-2 text-brand-600 underline text-xs"
                onClick={() => setMode('manual')}
              >
                Switch to manual entry
              </button>
            </div>
          ) : (
            <div className="relative rounded-lg overflow-hidden bg-gray-900 aspect-video">
              <video
                ref={videoRef}
                className="w-full h-full object-cover"
                muted
                playsInline
              />
              {/* Scanning indicator overlay */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="border-2 border-brand-400 rounded-lg w-48 h-24 opacity-70" />
              </div>
              {scanning && (
                <div className="absolute top-2 right-2 bg-brand-600 text-white text-xs px-2 py-1 rounded-full animate-pulse">
                  Scanning…
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* API result display */}
      {apiResult && resultConfig && (
        <div className={clsx('mt-3 rounded-lg border p-3', resultConfig.bg)}>
          <div className="flex items-center gap-2 mb-1">
            <resultConfig.icon className={clsx('h-4 w-4', resultConfig.text)} />
            <span className={clsx('text-sm font-semibold', resultConfig.text)}>
              {resultConfig.label}
            </span>
            <span className="text-xs text-gray-500 ml-auto">{apiResult.barcode_type}</span>
          </div>
          {apiResult.batch_number && (
            <p className="text-xs text-gray-600">Batch: <span className="font-mono font-medium">{apiResult.batch_number}</span></p>
          )}
          {apiResult.expiry_date && (
            <p className="text-xs text-gray-600">Expiry: <span className="font-medium">{apiResult.expiry_date}</span></p>
          )}
          <p className="text-xs text-gray-500 mt-1 italic">{apiResult.notes}</p>
        </div>
      )}
    </div>
  );
}
