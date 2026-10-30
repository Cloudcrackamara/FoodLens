"use client";

import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { codeFromQrText } from "@/lib/check";
import { createQrDecoder, type QrDecoder } from "@/lib/qr";
import { buttonClass } from "@/lib/ui";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { BottomSheet, PrivacyNote } from "@/components/ui/BottomSheet";
import { ScanFrame, Viewfinder } from "./ScanFrame";

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
    // Scan board layout (Scan.dc.html: reading, denied and unavailable states).
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Scan QR"
      className="fixed inset-0 z-50 flex flex-col overflow-y-auto bg-ink text-white"
    >
      <DemoDataBanner variant="compact" />
      <header className="flex items-center justify-between gap-3 px-3 py-2">
        <button
          type="button"
          onClick={onCancel}
          aria-label="Close"
          className="inline-flex size-11 flex-none items-center justify-center rounded-full text-white"
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M15 5l-7 7 7 7" />
          </svg>
        </button>
        <h2 className="m-0 font-heading text-[17px] font-semibold">Scan the QR on the pack</h2>
        <span aria-hidden="true" className="size-11 flex-none" />
      </header>

      <div className="flex flex-1 flex-col items-center gap-3.5 px-4 pt-1 pb-4">
        {cameraState !== "unavailable" ? (
          <>
            <p className="m-0 text-center font-heading text-[17px] font-semibold">
              {cameraState === "starting" ? "Starting the camera…" : "Hold the QR inside the square."}
            </p>
            <ScanFrame>
              <video
                ref={videoRef}
                playsInline
                muted
                aria-label="Camera view"
                className="absolute inset-0 size-full object-cover"
              />
              <Viewfinder className="w-3/5" />
            </ScanFrame>
          </>
        ) : (
          // Camera blocked / unavailable card (ScanDenied, ScanUnavailable).
          <section className="mt-3 box-border w-full max-w-[440px] rounded-[20px] bg-[#24215E] p-6">
            <span
              aria-hidden="true"
              className={`inline-flex size-14 items-center justify-center rounded-full ${denied ? "bg-sun" : "bg-white"}`}
            >
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#16143D"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                {denied ? (
                  <>
                    <path d="M3 3l18 18M9.5 5H15l1.5 2H19a2 2 0 0 1 2 2v8.5M17 19H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h1" />
                    <path d="M9.8 10.3a3 3 0 0 0 4 4" />
                  </>
                ) : (
                  <>
                    <path d="M9 5h6l1.5 2H19a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h2.5z" />
                    <path d="M12 10v3M12 16h.01" />
                  </>
                )}
              </svg>
            </span>
            <p className="mt-4 mb-0">{denied ? CAMERA_DENIED : CAMERA_UNAVAILABLE}</p>
          </section>
        )}
      </div>

      <BottomSheet>
        {problem && (
          <p role="alert" className="m-0 rounded-[10px] bg-sun px-3 py-2 text-sm font-semibold text-ink-2">
            {problem}
          </p>
        )}
        <label className={`cursor-pointer ${buttonClass("primary", "xl")}${busy ? " opacity-70" : ""}`}>
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
        <button type="button" onClick={onTypeInstead} className={buttonClass("secondary", "md")}>
          Type the code instead
        </button>
        <PrivacyNote>
          Your photo is read on your phone and never uploaded. Only the pack code is sent to check it.
        </PrivacyNote>
      </BottomSheet>
    </div>
  );
}
