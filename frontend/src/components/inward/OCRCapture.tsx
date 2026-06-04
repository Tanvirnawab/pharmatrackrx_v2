/**
 * OCRCapture — camera or file-upload widget for OCR-assisted expiry capture.
 *
 * Flow:
 *   1. User taps the camera icon on an inward item
 *   2. This widget opens — user takes a photo or selects from gallery
 *   3. Image is sent to /scanning/ocr/extract-expiry
 *   4. Suggested dates appear as buttons — user taps one to confirm
 *   5. Confirmed date is passed back via onConfirm() — NOT auto-saved
 *
 * If OCR is unavailable on the server, the widget shows a friendly fallback
 * and lets the user type a date manually.
 */
import { useState, useRef, useCallback, useEffect } from 'react';
import { Camera, Upload, X, Check, RotateCcw, Calendar } from 'lucide-react';
import { clsx } from 'clsx';
import { scanningApi } from '@/api/index';

interface OCRCaptureProps {
  onConfirm: (date: string) => void;
  onClose: () => void;
}

type Step = 'capture' | 'processing' | 'results' | 'manual';

export function OCRCapture({ onConfirm, onClose }: OCRCaptureProps) {
  const [step, setStep] = useState<Step>('capture');
  const [preview, setPreview] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<string[]>([]);
  const [bestDate, setBestDate] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [manualDate, setManualDate] = useState('');
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    const stream = streamRef.current;
    if (!cameraActive || !video || !stream) return;

    video.srcObject = stream;
    video.muted = true;
    video.play().catch(() => undefined);
  }, [cameraActive]);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
    setCameraReady(false);
  }, []);

  const startCamera = async () => {
    setError('');
    setCameraReady(false);
    stopCamera();

    try {
      setCameraActive(true);

      await new Promise<void>((resolve) => {
        requestAnimationFrame(() => resolve());
      });

      const devices = await navigator.mediaDevices.enumerateDevices();
      const cameras = devices.filter((device) => device.kind === 'videoinput');
      const preferred =
        cameras.find((device) => {
          const label = device.label.toLowerCase();
          return label.includes('back') || label.includes('rear') || label.includes('environment');
        }) ?? cameras[0];

      const stream = await navigator.mediaDevices.getUserMedia({
        video: preferred?.deviceId
          ? { deviceId: { exact: preferred.deviceId }, width: { ideal: 1280 } }
          : { facingMode: 'environment', width: { ideal: 1280 } },
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.muted = true;
        await videoRef.current.play();
      }

      window.setTimeout(() => {
        const video = videoRef.current;
        if (streamRef.current && video && (video.videoWidth === 0 || video.readyState < 2)) {
          setError('Camera opened, but no video frames are visible. Reload the page after allowing camera access, or upload an image.');
        }
      }, 2500);
    } catch {
      stopCamera();
      setError('Camera not available or permission was denied. Use "Upload image" instead.');
    }
  };

  const captureFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;
    const v = videoRef.current;
    if (v.videoWidth === 0 || v.videoHeight === 0) {
      setError('Camera preview is not ready yet. Reload after allowing camera access, or upload an image.');
      return;
    }
    const c = canvasRef.current;
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    c.getContext('2d')!.drawImage(v, 0, 0);
    const b64 = c.toDataURL('image/jpeg', 0.85).split(',')[1];
    stopCamera();
    setPreview(c.toDataURL('image/jpeg', 0.5));
    processImage(b64);
  }, [stopCamera]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const full = reader.result as string;
      const b64 = full.split(',')[1];
      setPreview(full);
      processImage(b64);
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  const processImage = async (b64: string) => {
    setStep('processing');
    setError('');
    try {
      const result = await scanningApi.ocrExtractExpiry(b64);
      setMessage(result.message);
      setCandidates(result.candidates);
      setBestDate(result.best_date);

      if (!result.available || result.candidates.length === 0) {
        setStep('manual');
      } else {
        setStep('results');
      }
    } catch {
      setError('OCR request failed. Please enter the expiry date manually.');
      setStep('manual');
    }
  };

  const handleConfirmCandidate = (candidate: string) => {
    // Convert display string to ISO date if possible
    // If it's already a valid ISO date from best_date, use that
    if (bestDate && candidates[0] === candidate) {
      onConfirm(bestDate);
    } else {
      // Try to extract a date from the candidate label
      // Fallback: open manual with the text pre-filled
      setManualDate('');
      setStep('manual');
    }
  };

  const handleManualConfirm = () => {
    if (manualDate) onConfirm(manualDate);
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-lg p-4 w-full max-w-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Camera className="h-4 w-4 text-brand-600" />
          <span className="text-sm font-semibold text-gray-800">Capture Expiry Date</span>
        </div>
        <button onClick={() => { stopCamera(); onClose(); }} className="text-gray-400 hover:text-gray-600">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Step: Capture */}
      {step === 'capture' && (
        <div className="space-y-3">
          {!cameraActive ? (
            <div className="space-y-2">
              <button
                onClick={startCamera}
                className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-brand-300 bg-brand-50 py-6 text-sm font-medium text-brand-700 hover:bg-brand-100 transition-colors"
              >
                <Camera className="h-5 w-5" />
                Open camera
              </button>
              <button
                onClick={() => fileRef.current?.click()}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-300 py-3 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
              >
                <Upload className="h-4 w-4" />
                Upload image
              </button>
              <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFileUpload} />
              <button
                onClick={() => setStep('manual')}
                className="w-full text-xs text-brand-600 hover:underline py-1"
              >
                Skip — enter manually
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="relative rounded-lg overflow-hidden bg-gray-900 aspect-video">
                <video
                  ref={videoRef}
                  className="w-full h-full object-cover"
                  muted
                  autoPlay
                  playsInline
                  onLoadedMetadata={() => {
                    setCameraReady(true);
                    videoRef.current?.play().catch(() => undefined);
                  }}
                  onCanPlay={() => setCameraReady(true)}
                />
                {!cameraReady && (
                  <div className="absolute inset-0 flex items-center justify-center bg-gray-950 text-xs text-gray-300">
                    Waiting for camera...
                  </div>
                )}
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="border-2 border-yellow-400 rounded w-48 h-10 opacity-80" />
                </div>
              </div>
              <p className="text-xs text-center text-gray-500">Point at the expiry date printed on the label</p>
              {error && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
                  {error}
                </div>
              )}
              <button
                onClick={captureFrame}
                className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-medium text-white hover:bg-brand-700 transition-colors"
              >
                Capture
              </button>
              <div className="flex justify-between text-xs">
                <button onClick={startCamera} className="text-brand-600 hover:underline">
                  Retry camera
                </button>
                <button onClick={() => fileRef.current?.click()} className="text-brand-600 hover:underline">
                  Upload image
                </button>
              </div>
            </div>
          )}
          {error && !cameraActive && <p className="text-xs text-red-600 mt-1">{error}</p>}
        </div>
      )}

      {/* Step: Processing */}
      {step === 'processing' && (
        <div className="py-8 flex flex-col items-center gap-3">
          {preview && (
            <img src={preview} alt="Captured" className="h-24 w-full object-cover rounded-lg mb-1" />
          )}
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
          <p className="text-sm text-gray-500">Extracting date…</p>
        </div>
      )}

      {/* Step: Results */}
      {step === 'results' && (
        <div className="space-y-3">
          {preview && (
            <img src={preview} alt="Captured" className="h-20 w-full object-cover rounded-lg" />
          )}
          <p className="text-xs text-gray-500">{message}</p>
          <div className="space-y-1.5">
            {candidates.map((c, i) => (
              <button
                key={i}
                onClick={() => handleConfirmCandidate(c)}
                className={clsx(
                  'flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-sm text-left transition-colors',
                  i === 0
                    ? 'border-brand-400 bg-brand-50 text-brand-800 font-medium'
                    : 'border-gray-200 hover:bg-gray-50 text-gray-700'
                )}
              >
                <Check className="h-3.5 w-3.5 shrink-0" />
                {c}
                {i === 0 && <span className="ml-auto text-xs text-brand-500">Best match</span>}
              </button>
            ))}
          </div>
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => { setPreview(null); setStep('capture'); setCameraActive(false); }}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
            >
              <RotateCcw className="h-3 w-3" /> Retake
            </button>
            <button
              onClick={() => setStep('manual')}
              className="ml-auto text-xs text-brand-600 hover:underline"
            >
              Enter manually
            </button>
          </div>
        </div>
      )}

      {/* Step: Manual */}
      {step === 'manual' && (
        <div className="space-y-3">
          {message && <p className="text-xs text-amber-700 bg-amber-50 rounded p-2">{message}</p>}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">
              Expiry date (from label)
            </label>
            <input
              type="date"
              autoFocus
              value={manualDate}
              onChange={(e) => setManualDate(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <button
            disabled={!manualDate}
            onClick={handleManualConfirm}
            className="w-full rounded-lg bg-brand-600 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-40 transition-colors"
          >
            Confirm
          </button>
        </div>
      )}

      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}
