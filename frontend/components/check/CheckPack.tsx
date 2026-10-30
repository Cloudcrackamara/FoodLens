"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { describeError } from "@/lib/api";
import {
  CODE_LENGTH,
  groupCode,
  isWellFormedCode,
  normaliseCode,
  useCheck,
  type IdentifierType,
} from "@/lib/check";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { BottomSheet, PrivacyNote } from "@/components/ui/BottomSheet";
import { ConsumerHeader } from "@/components/ui/ConsumerHeader";
import { InlineError } from "@/components/ui/Panels";
import { Spinner } from "@/components/ui/Spinner";
import type { QrDecoder } from "@/lib/qr";
import { busyButtonClass, buttonClass, codeInputClass } from "@/lib/ui";
import { CheckResultView } from "./CheckResultView";
import { DemoCityPicker } from "./DemoCityPicker";
import { ScanHero, ScanReadingHero } from "./ScanFrame";
import { ScanQr } from "./ScanQr";

type Mode = "scan" | "type";

const PRIVACY = "Your photo is read on your phone and never uploaded. Only the pack code is sent to check it.";

/**
 * The reading step holds until the last card of the board's 6.5s cycle has landed: fl-batch is
 * fully in at 62%, so 4.03s. Under reduced motion there is no hold (D149).
 */
const READING_HOLD_MS = 4030;

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

const HEADER = { title: "Check a pack", backHref: "/", backLabel: "Back to home" } as const;

/** Scan icon of the board's primary button (Scan.dc.html). */
function ScanIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M4 12h16" />
    </svg>
  );
}

/**
 * /check: Scan QR or Type code (D141). Only the code text is ever sent. Screens follow the Scan,
 * ConfirmTyped and Result boards; each draws its own demo banner and consumer header.
 */
export function CheckPack({ decoder }: { decoder?: QrDecoder }) {
  const [mode, setMode] = useState<Mode>("scan");
  const [scanning, setScanning] = useState(false);
  const [typed, setTyped] = useState("");
  const [typedProblem, setTypedProblem] = useState<string | null>(null);
  const [city, setCity] = useState("");
  const [checked, setChecked] = useState<string | null>(null);
  // After a QR is read: the last 4 characters for the reading cards, and whether the hold is over.
  const [reading, setReading] = useState<{ last4: string } | null>(null);
  const [holdOver, setHoldOver] = useState(false);
  const holdTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const check = useCheck();

  useEffect(() => () => {
    if (holdTimer.current) clearTimeout(holdTimer.current);
  }, []);

  function startReading(code: string) {
    if (holdTimer.current) clearTimeout(holdTimer.current);
    setReading({ last4: code.slice(-4) });
    if (prefersReducedMotion()) {
      setHoldOver(true);
      return;
    }
    setHoldOver(false);
    holdTimer.current = setTimeout(() => setHoldOver(true), READING_HOLD_MS);
  }

  function run(code: string, identifierType: IdentifierType) {
    if (identifierType === "QR") startReading(code);
    setChecked(code);
    check.mutate({ code, identifier_type: identifierType, simulated_city: city });
  }

  function submitTyped(event: FormEvent) {
    event.preventDefault();
    const code = normaliseCode(typed);
    if (!isWellFormedCode(code)) {
      setTypedProblem(
        code.length === CODE_LENGTH
          ? "That code has a character that is not used in FoodLens codes. Check it against the pack."
          : `The code under the QR has ${CODE_LENGTH} letters and numbers. You typed ${code.length}.`,
      );
      return;
    }
    setTypedProblem(null);
    run(code, "TYPED");
  }

  function reset() {
    if (holdTimer.current) clearTimeout(holdTimer.current);
    setReading(null);
    check.reset();
    setChecked(null);
    setTyped("");
  }

  const scanner = scanning && (
    <ScanQr
      decoder={decoder}
      onCancel={() => setScanning(false)}
      onTypeInstead={() => {
        setScanning(false);
        setMode("type");
      }}
      onCode={(code) => {
        setScanning(false);
        run(code, "QR");
      }}
    />
  );

  // The result waits for the cards to land and for the check to return, whichever is later.
  const showReading = reading !== null && !check.isError && !(holdOver && check.isSuccess);

  if (showReading) {
    return (
      // Reading step (Scan.dc.html, reading state): dark page, the picture with the three cards.
      <div className="flex flex-1 flex-col bg-ink text-white">
        <DemoDataBanner variant="compact" />
        <ConsumerHeader {...HEADER} tone="dark" titleAs="h1" />
        <main className="flex flex-1 flex-col items-center gap-3.5 px-4 pt-1 pb-4">
          <ScanReadingHero last4={reading.last4} />
        </main>
      </div>
    );
  }

  // The camera screen draws its own demo banner, so the page under it draws none.
  if (scanner) return scanner;

  if (check.isSuccess) {
    return (
      <div className="flex flex-1 flex-col">
        <ConsumerHeader {...HEADER} />
        <main className="flex flex-1 flex-col">
          <CheckResultView result={check.data} code={checked} simulatedCity={city} onCheckAnother={reset} />
        </main>
      </div>
    );
  }

  const error = check.isError && <InlineError className="text-sm">{describeError(check.error)}</InlineError>;

  if (mode === "type") {
    const normalised = normaliseCode(typed);
    return (
      // Typed-code screen (ConfirmTyped.dc.html): one code field, no batch field.
      <div className="flex flex-1 flex-col bg-white">
        <DemoDataBanner variant="compact" />
        <ConsumerHeader {...HEADER} />
        <main className="flex flex-1 flex-col">
          <form aria-label="Type code" onSubmit={submitTyped} className="flex flex-1 flex-col">
            <div className="mx-auto box-border flex w-full max-w-[520px] flex-1 flex-col gap-5 px-5 pt-5 pb-2">
              <h1 className="m-0 font-heading text-2xl font-bold leading-[1.25]">Type code</h1>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="typed-code" className="font-semibold">
                  The code printed under the QR
                </label>
                <input
                  id="typed-code"
                  value={typed}
                  onChange={(event) => setTyped(event.target.value)}
                  autoComplete="off"
                  autoCapitalize="characters"
                  spellCheck={false}
                  inputMode="text"
                  maxLength={40}
                  placeholder="7Q2M 8KD3 XH4N …"
                  aria-invalid={typedProblem ? true : undefined}
                  aria-describedby="typed-code-help"
                  className={`${codeInputClass(
                    typedProblem ? "error" : "default",
                    check.isPending,
                  )} uppercase`}
                />
                {typedProblem && (
                  // Correction box (Confirm.dc.html, error state).
                  <div role="alert" className="flex gap-2 rounded-[10px] bg-bad-bg p-3 text-sm text-bad">
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="#B42318"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                      aria-hidden="true"
                      className="mt-0.5 flex-none"
                    >
                      <circle cx="12" cy="12" r="9" />
                      <path d="M12 7v6M12 16.5h.01" />
                    </svg>
                    <span>{typedProblem}</span>
                  </div>
                )}
                <p id="typed-code-help" className="m-0 text-sm text-[#4B4F5C]">
                  Spaces and dashes are fine, and O, I and L are read as 0, 1 and 1.
                  {normalised && (
                    <>
                      {" "}
                      Reading: <span className="font-mono">{groupCode(normalised)}</span> ({normalised.length}/
                      {CODE_LENGTH})
                    </>
                  )}
                </p>
              </div>
              <DemoCityPicker value={city} onChange={setCity} />
              {error}
            </div>
            <div className="mx-auto box-border flex w-full max-w-[520px] flex-col gap-2.5 bg-white px-5 pt-3 pb-6">
              {check.isPending ? (
                <button type="submit" disabled aria-busy="true" className={busyButtonClass}>
                  <Spinner />
                  Checking…
                </button>
              ) : (
                <button type="submit" disabled={!typed.trim()} className={buttonClass("primary", "xl")}>
                  Check this code
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  setMode("scan");
                  setScanning(true);
                }}
                disabled={check.isPending}
                className={buttonClass("secondary", "md")}
              >
                Scan QR
              </button>
            </div>
          </form>
        </main>
      </div>
    );
  }

  return (
    // Scan screen (Scan.dc.html, ready state): dark page, picture, white bottom sheet.
    <div className="flex flex-1 flex-col bg-ink text-white">
      <DemoDataBanner variant="compact" />
      <ConsumerHeader {...HEADER} tone="dark" titleAs="h1" />
      <main className="flex flex-1 flex-col items-center gap-3.5 px-4 pt-1 pb-4">
        <p className="m-0 max-w-[440px] text-center font-heading text-[17px] font-semibold">
          Point your camera at the QR code on the pack. You can also use a photo of it.
        </p>
        <ScanHero />
        <p className="m-0 max-w-[440px] text-center text-[#DCDAF0]">
          See what has been recorded for the code on your pack: who issued it, whether it is in
          circulation or sold, and any recall. Free, with no account.
        </p>
      </main>
      <BottomSheet>
        <button
          type="button"
          onClick={() => setScanning(true)}
          disabled={check.isPending}
          className={buttonClass("primary", "xl")}
        >
          <ScanIcon />
          {check.isPending ? "Checking…" : "Open the camera"}
        </button>
        <button type="button" onClick={() => setMode("type")} className={buttonClass("secondary", "md")}>
          Type code
        </button>
        <PrivacyNote>{PRIVACY}</PrivacyNote>
        {error}
        <DemoCityPicker value={city} onChange={setCity} />
        <p className="m-0 text-center text-[13px] text-[#4B4F5C]">
          A copied QR carries the same code. FoodLens spots copies by whether the code was sold,
          where it is checked, how often, and where the stock was sent, not by the QR alone. No QR
          system catches every copied code.
        </p>
      </BottomSheet>
    </div>
  );
}
