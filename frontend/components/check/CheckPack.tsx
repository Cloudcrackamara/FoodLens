"use client";

import { useState, type FormEvent } from "react";
import { describeError } from "@/lib/api";
import {
  CODE_LENGTH,
  groupCode,
  isWellFormedCode,
  normaliseCode,
  useCheck,
  type IdentifierType,
} from "@/lib/check";
import type { QrDecoder } from "@/lib/qr";
import { CheckResultView } from "./CheckResultView";
import { DemoCityPicker } from "./DemoCityPicker";
import { ScanQr } from "./ScanQr";

type Mode = "scan" | "type";

/** /check: Scan QR or Type code (D141). Only the code text is ever sent. */
export function CheckPack({ decoder }: { decoder?: QrDecoder }) {
  const [mode, setMode] = useState<Mode>("scan");
  const [scanning, setScanning] = useState(false);
  const [typed, setTyped] = useState("");
  const [typedProblem, setTypedProblem] = useState<string | null>(null);
  const [city, setCity] = useState("");
  const [checked, setChecked] = useState<string | null>(null);
  const check = useCheck();

  function run(code: string, identifierType: IdentifierType) {
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
    check.reset();
    setChecked(null);
    setTyped("");
  }

  if (check.isSuccess) {
    return (
      <CheckResultView result={check.data} code={checked} simulatedCity={city} onCheckAnother={reset} />
    );
  }

  const normalised = normaliseCode(typed);

  return (
    <div className="flex flex-col gap-5">
      <div role="tablist" aria-label="How to check" className="grid grid-cols-2 gap-1 rounded-xl bg-zinc-200 p-1 dark:bg-zinc-800">
        {(
          [
            ["scan", "Scan QR"],
            ["type", "Type code"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={mode === value}
            onClick={() => setMode(value)}
            className={`min-h-12 rounded-lg text-base font-semibold ${
              mode === value ? "bg-white shadow dark:bg-zinc-950" : "text-zinc-700 dark:text-zinc-300"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === "scan" ? (
        <div role="tabpanel" aria-label="Scan QR" className="flex flex-col gap-3">
          <p>Point your camera at the QR code on the pack. You can also use a photo of it.</p>
          <button
            type="button"
            onClick={() => setScanning(true)}
            disabled={check.isPending}
            className="min-h-14 rounded-xl bg-zinc-900 px-5 text-lg font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {check.isPending ? "Checking…" : "Open the camera"}
          </button>
          <p className="text-xs text-zinc-600 dark:text-zinc-400">
            Your photo is read on your phone and never uploaded. Only the pack code is sent to check it.
          </p>
        </div>
      ) : (
        <form role="tabpanel" aria-label="Type code" onSubmit={submitTyped} className="flex flex-col gap-3">
          <label htmlFor="typed-code" className="font-medium">
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
            aria-describedby="typed-code-help"
            className="min-h-14 rounded-xl border border-zinc-400 bg-transparent px-4 font-mono text-lg uppercase tracking-wider"
          />
          <p id="typed-code-help" className="text-xs text-zinc-600 dark:text-zinc-400">
            Spaces and dashes are fine, and O, I and L are read as 0, 1 and 1.
            {normalised && (
              <>
                {" "}
                Reading: <span className="font-mono">{groupCode(normalised)}</span> ({normalised.length}/
                {CODE_LENGTH})
              </>
            )}
          </p>
          {typedProblem && (
            <p role="alert" className="text-sm text-red-700 dark:text-red-400">
              {typedProblem}
            </p>
          )}
          <button
            type="submit"
            disabled={check.isPending || !typed.trim()}
            className="min-h-14 rounded-xl bg-zinc-900 px-5 text-lg font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {check.isPending ? "Checking…" : "Check this code"}
          </button>
        </form>
      )}

      <DemoCityPicker value={city} onChange={setCity} />

      {check.isError && (
        <p role="alert" className="text-red-700 dark:text-red-400">
          {describeError(check.error)}
        </p>
      )}

      {scanning && (
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
      )}
    </div>
  );
}
