"use client";

import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { extractNumber, type Extraction, type ScanKind } from "@/lib/ocr/extract";
import type { LookupQuery } from "@/lib/lookup";
import type { Rect } from "@/lib/ocr/preprocess";
import { ConfirmScan } from "./ConfirmScan";
import { Button } from "@/components/ui/button";

/** How images become text. The real one runs Tesseract.js on the phone; tests pass a fake. */
export type ScanReader = {
  prepare: (onProgress: (message: string) => void) => Promise<void>;
  fromVideo: (video: HTMLVideoElement, guide: Rect) => Promise<string>;
  fromFile: (file: File) => Promise<string>;
  release: () => Promise<void>;
};

async function defaultReader(): Promise<ScanReader> {
  const [{ loadOcr, releaseOcr }, { readFromVideo, readFromFile }] = await Promise.all([
    import("@/lib/ocr/engine"),
    import("@/lib/ocr/readImage"),
  ]);
  return {
    prepare: async (onProgress) => {
      await loadOcr(({ status, progress }) =>
        onProgress(status.includes("load") ? `Loading the reader… ${Math.round(progress * 100)}%` : "Getting ready…"),
      );
    },
    fromVideo: readFromVideo,
    fromFile: readFromFile,
    release: releaseOcr,
  };
}

type Step = ScanKind | "confirm";

const STEP_TEXT: Record<ScanKind, { title: string; hint: string }> = {
  registration: {
    title: "Scan the NAFDAC or SON number",
    hint: 'Fit the number and its label (for example "NAFDAC Reg No") inside the box. Hold steady, in good light.',
  },
  batch: {
    title: "Scan the batch number (optional)",
    hint: 'Fit the batch number and its label ("Batch", "BN" or "LOT") inside the box.',
  },
};

type Props = {
  onConfirm: (query: LookupQuery) => void;
  onCancel: () => void;
  reader?: ScanReader;
};

/**
 * Camera scanning of the printed registration and batch numbers (D88-D94). Images stay on the
 * phone: frames are read in memory and discarded; only the confirmed text leaves the scanner.
 */
export function ScanPack({ onConfirm, onCancel, reader: injectedReader }: Props) {
  const [step, setStep] = useState<Step>("registration");
  const [results, setResults] = useState<{ registration: Extraction | null; batch: Extraction | null }>({
    registration: null,
    batch: null,
  });
  const [cameraState, setCameraState] = useState<"starting" | "ready" | "unavailable">(() =>
    typeof navigator !== "undefined" && typeof navigator.mediaDevices?.getUserMedia === "function"
      ? "starting"
      : "unavailable",
  );
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const readerRef = useRef<Promise<ScanReader> | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const guideRef = useRef<HTMLDivElement>(null);

  function getReader(): Promise<ScanReader> {
    readerRef.current ??= injectedReader ? Promise.resolve(injectedReader) : defaultReader();
    return readerRef.current;
  }

  // Start loading the OCR engine while the person aims the camera; free it when done.
  useEffect(() => {
    let cancelled = false;
    getReader()
      .then((reader) => reader.prepare((message) => !cancelled && setStatus(message)))
      .then(() => !cancelled && setStatus(null))
      .catch(() => !cancelled && setStatus("The reader could not load. You can still type the numbers."));
    return () => {
      cancelled = true;
      void readerRef.current?.then((reader) => reader.release());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Camera on for the two capture steps only; every track is stopped afterwards.
  useEffect(() => {
    if (step === "confirm" || cameraState === "unavailable") return;
    const video = videoRef.current;
    let stream: MediaStream | null = null;
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 } }, audio: false })
      .then(async (media) => {
        if (cancelled) return media.getTracks().forEach((track) => track.stop());
        stream = media;
        if (video) {
          video.srcObject = media;
          await video.play().catch(() => undefined);
        }
        setCameraState("ready");
      })
      .catch(() => !cancelled && setCameraState("unavailable"));
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((track) => track.stop());
      if (video) video.srcObject = null;
    };
  }, [step, cameraState]);

  function finishStep(kind: ScanKind, text: string) {
    const extraction = extractNumber(text, kind);
    setResults((previous) => ({ ...previous, [kind]: extraction }));
    setStep(kind === "registration" ? "batch" : "confirm");
  }

  async function read(kind: ScanKind, readText: (reader: ScanReader) => Promise<string>) {
    setBusy(true);
    setProblem(null);
    try {
      const reader = await getReader();
      setStatus("Reading…");
      finishStep(kind, await readText(reader));
    } catch {
      setProblem("Could not read that. Try again in better light, or type the number instead.");
    } finally {
      setBusy(false);
      setStatus(null);
    }
  }

  function capture(kind: ScanKind) {
    const video = videoRef.current;
    const guide = guideRef.current;
    if (!video || !guide) return;
    const view = video.getBoundingClientRect();
    const box = guide.getBoundingClientRect();
    const rect = { x: box.left - view.left, y: box.top - view.top, width: box.width, height: box.height };
    void read(kind, (reader) => reader.fromVideo(video, rect));
  }

  function choosePhoto(kind: ScanKind, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // nothing kept in the form either
    if (file) void read(kind, (reader) => reader.fromFile(file));
  }

  if (step === "confirm") {
    return (
      <Overlay>
        <ConfirmScan
          registration={results.registration ?? { value: null, candidates: [] }}
          batch={results.batch}
          onConfirm={onConfirm}
          onRescan={() => {
            setResults({ registration: null, batch: null });
            setStep("registration");
          }}
          onCancel={onCancel}
        />
      </Overlay>
    );
  }

  const text = STEP_TEXT[step];
  return (
    <Overlay>
      <div className="flex flex-col gap-3">
        <h2 className="text-2xl font-bold">{text.title}</h2>
        <p className="text-sm">{text.hint}</p>
        <p className="text-xs text-muted-foreground">
          Photos are read on your phone and never uploaded or saved.
        </p>

        {cameraState !== "unavailable" ? (
          <div className="relative aspect-[3/4] w-full overflow-hidden rounded-xl bg-black">
            <video ref={videoRef} playsInline muted aria-label="Camera view" className="h-full w-full object-cover" />
            <div
              ref={guideRef}
              aria-hidden="true"
              className="absolute left-[7.5%] top-[39%] h-[22%] w-[85%] rounded-lg border-4 border-white shadow-[0_0_0_9999px_rgba(0,0,0,0.45)]"
            />
          </div>
        ) : (
          <label className="flex flex-col gap-2 rounded-xl border border-border bg-card p-4">
            <span className="font-medium">The camera is not available. Take or choose a photo instead:</span>
            <input type="file" accept="image/*" capture="environment" disabled={busy}
              onChange={(event) => choosePhoto(step, event)} aria-label="Photo of the number" />
          </label>
        )}

        {status && <p role="status" className="text-sm">{status}</p>}
        {problem && <p role="alert" className="text-destructive">{problem}</p>}

        <div className="flex flex-wrap gap-3">
          {cameraState !== "unavailable" && (
            <Button type="button" size="lg" disabled={busy || cameraState !== "ready"} onClick={() => capture(step)}>
              {busy ? "Reading…" : "Capture"}
            </Button>
          )}
          {step === "batch" && (
            <Button type="button" variant="outline" size="lg" disabled={busy} onClick={() => setStep("confirm")}>
              Skip batch number
            </Button>
          )}
          <Button type="button" variant="link" onClick={onCancel}>Type instead</Button>
        </div>
      </div>
    </Overlay>
  );
}

function Overlay({ children }: { children: React.ReactNode }) {
  return (
    <div role="dialog" aria-modal="true" aria-label="Scan pack" className="fixed inset-0 z-50 overflow-y-auto bg-background p-4">
      <div className="mx-auto w-full max-w-md">{children}</div>
    </div>
  );
}
