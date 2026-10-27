"use client";

import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { codeFromQrText } from "@/lib/check";
import { createQrDecoder, type QrDecoder } from "@/lib/qr";

/** How often a camera frame is read, in milliseconds. */
const SCAN_INTERVAL_MS = 250;

type Props = {
  onCode: (code: string) => void;
  onCancel: () => void;
  onTypeInstead: () => void;
  decoder?: QrDecoder;
};

const CAMERA_UNAVAILABLE = "The camera is not available. Take or choose a photo of the QR instead.";
const CAMERA_DENIED =
  "We can't use the camera. If you blocked camera access, allow it in your browser settings, or take or choose a photo of the QR instead.";
const NOT_FOODLENS = "That QR code is not a FoodLens pack code. Aim at the QR on the pack label.";

/**
 * Camera QR scanning (D117; camera handling from D93). Back lens, no audio, and every track is
 * stopped as soon as a code is read or the scanner closes. Without a camera, or when permission
 * is refused, a photo picker reads the QR the same way. Images never leave the phone.
 */
export function ScanQr({ onCode, onCancel, onTypeInstead, decoder: injected }: Props) {
  const [cameraState, setCameraState] = useState<"starting" | "ready" | "unavailable">(() =>
    typeof navigator !== "undefined" && typeof navigator.mediaDevices?.getUserMedia === "function"
      ? "starting"
      : "unavailable",
  );
  const [problem, setProblem] = useState<string | null>(null);
  // The person (or the browser on their behalf) refused camera permission.
  const [denied, setDenied] = useState(false);
  const [busy, setBusy] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const decoderRef = useRef<QrDecoder | null>(null);
  const doneRef = useRef(false);
  const cameraOff = cameraState === "unavailable";

  function getDecoder(): QrDecoder {
    decoderRef.current ??= injected ?? createQrDecoder();
    return decoderRef.current;
  }

  function accept(text: string | null): boolean {
    if (text === null) return false;
    const code = codeFromQrText(text);
    if (!code) {
      setProblem(NOT_FOODLENS);
      return false;
    }
    doneRef.current = true;
    onCode(code);
    return true;
  }

  // Camera on while the scanner is open; every track is stopped on the way out.
  useEffect(() => {
    if (cameraOff) return;
    const video = videoRef.current;
    let stream: MediaStream | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const stop = () => {
      if (timer) clearTimeout(timer);
      stream?.getTracks().forEach((track) => track.stop());
      stream = null;
      if (video) video.srcObject = null;
    };

    const tick = async () => {
      if (cancelled || doneRef.current || !video) return;
      try {
        if (video.readyState >= 2 && accept(await getDecoder().fromVideo(video))) {
          stop();
          return;
        }
      } catch {
        // A frame that cannot be read is skipped.
      }
      if (!cancelled) timer = setTimeout(tick, SCAN_INTERVAL_MS);
    };

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false })
      .then(async (media) => {
        if (cancelled) return media.getTracks().forEach((track) => track.stop());
        stream = media;
        if (video) {
          video.srcObject = media;
          await video.play().catch(() => undefined);
        }
        setCameraState("ready");
        void tick();
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const name = error instanceof Error || error instanceof DOMException ? error.name : "";
        setDenied(name === "NotAllowedError" || name === "SecurityError");
        setCameraState("unavailable");
      });

    return () => {
      cancelled = true;
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraOff]);

  async function choosePhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // nothing kept in the form either
    if (!file) return;
    setBusy(true);
    setProblem(null);
    try {
      const text = await getDecoder().fromFile(file);
      if (text === null) setProblem("No QR code found in that photo. Try again closer, in good light.");
      else accept(text);
    } catch {
      setProblem("Could not read that photo. Try again, or type the code instead.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Scan QR"
      className="fixed inset-0 z-50 flex flex-col bg-ink text-white"
    >
      <div className="flex items-center justify-between px-4 py-3">
        <h2 className="font-heading text-[17px] font-semibold">Scan the QR on the pack</h2>
        <button
          type="button"
          onClick={onCancel}
          className="min-h-11 rounded-full px-3 text-sm font-semibold underline underline-offset-4"
        >
          Close
        </button>
      </div>

      {cameraState !== "unavailable" ? (
        <div className="relative mx-auto aspect-[3/4] w-full max-w-[440px] flex-1 overflow-hidden bg-black sm:rounded-[20px]">
          <video
            ref={videoRef}
            playsInline
            muted
            aria-label="Camera view"
            className="h-full w-full object-cover"
          />
          <div
            aria-hidden="true"
            className="absolute left-1/2 top-1/2 aspect-square w-3/5 -translate-x-1/2 -translate-y-1/2 rounded-2xl border-4 border-white/90 shadow-[0_0_0_9999px_rgba(0,0,0,0.5)]"
          />
          <p className="absolute inset-x-0 bottom-4 px-6 text-center text-sm text-white/90">
            {cameraState === "starting" ? "Starting the camera…" : "Hold the QR inside the square."}
          </p>
        </div>
      ) : (
        <p className="mx-auto w-full max-w-[440px] px-4 py-6 text-base">
          {denied ? CAMERA_DENIED : CAMERA_UNAVAILABLE}
        </p>
      )}

      <div className="mx-auto flex w-full max-w-[440px] flex-col gap-3 px-4 py-4">
        {problem && (
          <p role="alert" className="rounded-[10px] bg-sun px-3 py-2 text-sm font-semibold text-ink-2">
            {problem}
          </p>
        )}
        <label className="flex min-h-12 cursor-pointer items-center justify-center rounded-full border-2 border-white px-5 font-heading text-base font-semibold">
          {busy ? "Reading the photo…" : "Use a photo instead"}
          <input
            type="file"
            accept="image/*"
            capture="environment"
            disabled={busy}
            onChange={choosePhoto}
            aria-label="Photo of the QR"
            className="sr-only"
          />
        </label>
        <button
          type="button"
          onClick={onTypeInstead}
          className="min-h-12 rounded-full px-4 font-heading text-base font-semibold underline underline-offset-4"
        >
          Type the code instead
        </button>
        <p className="text-center text-xs text-white/70">
          Your photo is read on your phone and never uploaded. Only the pack code is sent to check it.
        </p>
      </div>
    </div>
  );
}
