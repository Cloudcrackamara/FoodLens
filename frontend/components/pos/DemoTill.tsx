"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { ScanQr } from "@/components/check/ScanQr";
import { Card } from "@/components/ui/Card";
import { EmptyPanel, ErrorPanel, InlineError, LoadingPanel } from "@/components/ui/Panels";
import { StatusPill, type Tone } from "@/components/ui/StatusPill";
import { Spinner } from "@/components/ui/Spinner";
import { WorkspaceShell } from "@/components/ui/WorkspaceShell";
import { describeError } from "@/lib/api";
import { useCurrentUser, useLogout } from "@/lib/auth";
import { groupCode, normaliseCode } from "@/lib/check";
import {
  REASON_MAX,
  useDemoTills,
  useTillAction,
  useTillLookup,
  type DemoTill as Till,
  type PosLookup,
  type TillAction,
} from "@/lib/pos";
import type { QrDecoder } from "@/lib/qr";
import { unitStatusLabels } from "@/lib/units";
import {
  busyButtonClass,
  buttonClass,
  codeInputClass,
  detailListClass,
  detailTermClass,
  detailValueClass,
  inputClass,
  noteClass,
  textareaClass,
} from "@/lib/ui";

// Approved wording (30 Oct 2026).
const TITLE = "Demo till";
const SUBTITLE = "A simulated shop till. Sales go through the same signed POS API a real till uses.";
const PAYMENT_NOTE =
  "No payment happens here. FoodLens records the sale only after the till confirms payment, and stores no amount or card details.";
const SIGN_IN = "Sign in as a member of a retailer linked to the demo till.";
const NO_TILL = "No demo till is registered for your company.";

const STATUS_TONES: Record<string, Tone> = {
  ISSUED: "pending",
  RELEASED: "info",
  IN_TRANSIT: "new",
  IN_STOCK: "ok",
  SOLD: "neutral",
  RECALLED: "alert",
  VOIDED: "bad",
};

function done(action: TillAction, retailerName: string): string {
  switch (action) {
    case "sales":
      return `Sale recorded. A buyer who checks this pack now sees "Just sold by ${retailerName}".`;
    case "refunds":
      return "Refund recorded. The pack is back in stock, and the sale stays in the history.";
    case "voids":
      return "Sale voided. The earlier sale stays in the history.";
  }
}

type Outcome = { ok: boolean; message: string };

function Details({ lookup }: { lookup: PosLookup }) {
  return (
    <dl className={`m-0 ${detailListClass}`}>
      <dt className={detailTermClass}>Product</dt>
      <dd className={`m-0 ${detailValueClass}`}>
        {lookup.product_name}
        {lookup.size ? ` · ${lookup.size}` : ""}
      </dd>
      <dt className={detailTermClass}>Batch</dt>
      <dd className={`m-0 font-mono ${detailValueClass}`}>{lookup.batch_number}</dd>
      {lookup.expiry_date && (
        <>
          <dt className={detailTermClass}>Expiry</dt>
          <dd className={`m-0 ${detailValueClass}`}>{lookup.expiry_date}</dd>
        </>
      )}
      <dt className={detailTermClass}>Status</dt>
      <dd className={`m-0 ${detailValueClass}`}>
        <StatusPill tone={STATUS_TONES[lookup.status] ?? "neutral"}>{unitStatusLabels[lookup.status]}</StatusPill>
      </dd>
      <dt className={detailTermClass}>Code ending</dt>
      <dd className={`m-0 font-mono ${detailValueClass}`}>{lookup.code_last4}</dd>
    </dl>
  );
}

/**
 * The simulated till: choose a till, scan or type a pack code, see the lookup and any warning,
 * then Confirm payment, Refund or Void sale. Every action goes to /api/demo/pos/*, where the
 * server signs it and runs the real POS checks; the browser never holds a key or secret.
 * Composed from the merchant page parts (no board in design/).
 */
export function DemoTill({ tills, retailerName, decoder }: { tills: Till[]; retailerName: string; decoder?: QrDecoder }) {
  const [tillRef, setTillRef] = useState(tills[0]?.till_ref ?? "");
  const [typed, setTyped] = useState("");
  const [scanning, setScanning] = useState(false);
  const [current, setCurrent] = useState<{ code: string; lookup: PosLookup } | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [voiding, setVoiding] = useState(false);
  const [reason, setReason] = useState("");
  const lookup = useTillLookup();
  const action = useTillAction();
  const busy = lookup.isPending || action.isPending;

  function find(code: string, keepOutcome = false) {
    const normalised = normaliseCode(code);
    if (!normalised) return;
    lookup.mutate(
      { till_ref: tillRef, code: normalised },
      {
        onSuccess: (found) => {
          setCurrent({ code: normalised, lookup: found });
          if (!keepOutcome) setOutcome(null);
        },
      },
    );
  }

  function run(kind: TillAction) {
    if (!current) return;
    const request = { till_ref: tillRef, code: current.code, ...(kind === "voids" ? { reason: reason.trim() } : {}) };
    action.mutate(
      { action: kind, request },
      {
        onSuccess: (result) => {
          const unit = result.units[0];
          setOutcome(
            unit?.result === "RECORDED"
              ? { ok: true, message: done(kind, retailerName) }
              : { ok: false, message: unit?.error?.message ?? "" },
          );
          setVoiding(false);
          setReason("");
          find(current.code, true);
        },
      },
    );
  }

  function submit(submitted: FormEvent) {
    submitted.preventDefault();
    find(typed);
  }

  if (scanning) {
    return (
      <ScanQr
        decoder={decoder}
        onCancel={() => setScanning(false)}
        onTypeInstead={() => setScanning(false)}
        onCode={(code) => {
          setScanning(false);
          setTyped(code);
          find(code);
        }}
      />
    );
  }

  const normalised = normaliseCode(typed);
  const found = current?.lookup;
  return (
    <div className="flex flex-col gap-4">
      <Card variant="workspace" aria-label="Find a pack" className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="till-ref" className="font-semibold text-ink">
            Till
          </label>
          <select id="till-ref" value={tillRef} onChange={(changed) => setTillRef(changed.target.value)} className={inputClass}>
            {tills.map((till) => (
              <option key={till.till_ref} value={till.till_ref}>
                {till.till_ref} · {till.location_name}, {till.area}
              </option>
            ))}
          </select>
        </div>
        <form onSubmit={submit} aria-label="Look up a pack" className="flex flex-col gap-2">
          <label htmlFor="till-code" className="font-semibold text-ink">
            Scan or type the pack code
          </label>
          <input
            id="till-code"
            value={typed}
            onChange={(changed) => setTyped(changed.target.value)}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={40}
            placeholder="7Q2M 8KD3 XH4N …"
            className={`${codeInputClass("default", lookup.isPending)} uppercase`}
          />
          {normalised && (
            <p className="m-0 text-sm text-text-subtle">
              <span className="font-mono">{groupCode(normalised)}</span>
            </p>
          )}
          {lookup.isError && <InlineError className="text-sm">{describeError(lookup.error)}</InlineError>}
          <div className="flex flex-col gap-2.5 sm:flex-row">
            <button type="button" onClick={() => setScanning(true)} disabled={busy} className={`flex-1 ${buttonClass("primary", "md")}`}>
              Scan QR
            </button>
            {lookup.isPending ? (
              <button type="submit" disabled aria-busy="true" className={`flex-1 ${busyButtonClass}`}>
                <Spinner />
                Look up
              </button>
            ) : (
              <button type="submit" disabled={!normalised || busy} className={`flex-1 ${buttonClass("secondary", "md")}`}>
                Look up
              </button>
            )}
          </div>
        </form>
      </Card>

      {found && (
        <Card variant="workspace" aria-label="Pack details" className="flex flex-col gap-4">
          <Details lookup={found} />
          {/* After this till's own sale, the refreshed lookup warns "already sold"; the success
              message says it better, so the warning waits for the next lookup. */}
          {found.warning && !outcome?.ok && (
            <p role="alert" className="m-0 rounded-[10px] border-2 border-bad-line bg-bad-bg px-3.5 py-3 font-semibold text-bad">
              {found.warning.message}
            </p>
          )}
          {outcome && (
            <p
              role={outcome.ok ? "status" : "alert"}
              className={`m-0 rounded-[10px] px-3.5 py-3 font-semibold ${outcome.ok ? "bg-ok-bg text-ok" : "bg-bad-bg text-bad"}`}
            >
              {outcome.message}
            </p>
          )}
          {action.isError && <InlineError className="text-sm">{describeError(action.error)}</InlineError>}
          {found.subject === "UNIT" && !voiding && (
            <div className="flex flex-col gap-2.5">
              {action.isPending ? (
                <button type="button" disabled aria-busy="true" className={busyButtonClass}>
                  <Spinner />
                  Confirm payment
                </button>
              ) : (
                <button type="button" onClick={() => run("sales")} disabled={busy} className={buttonClass("primary", "lg")}>
                  Confirm payment
                </button>
              )}
              <p className={`m-0 ${noteClass}`}>{PAYMENT_NOTE}</p>
              {found.status === "SOLD" && (
                <div className="flex flex-col gap-2.5 sm:flex-row">
                  <button type="button" onClick={() => run("refunds")} disabled={busy} className={`flex-1 ${buttonClass("secondary", "md")}`}>
                    Refund
                  </button>
                  <button type="button" onClick={() => setVoiding(true)} disabled={busy} className={`flex-1 ${buttonClass("danger", "md")}`}>
                    Void sale
                  </button>
                </div>
              )}
            </div>
          )}
          {voiding && (
            <form
              aria-label="Void sale"
              onSubmit={(submitted) => {
                submitted.preventDefault();
                run("voids");
              }}
              className="flex flex-col gap-2"
            >
              <label htmlFor="void-reason" className="font-semibold text-ink">
                Reason for the void
              </label>
              <textarea
                id="void-reason"
                value={reason}
                onChange={(changed) => setReason(changed.target.value)}
                maxLength={REASON_MAX}
                rows={3}
                className={textareaClass}
              />
              <span className="text-right text-[13px] text-text-subtle">
                {reason.length}/{REASON_MAX}
              </span>
              <div className="flex flex-col gap-2.5 sm:flex-row">
                <button type="submit" disabled={busy || reason.trim() === ""} className={`flex-1 ${buttonClass("danger", "md")}`}>
                  Void sale
                </button>
                <button type="button" onClick={() => setVoiding(false)} disabled={busy} className={`flex-1 ${buttonClass("quiet", "md")}`}>
                  Go back
                </button>
              </div>
            </form>
          )}
        </Card>
      )}
    </div>
  );
}

function Centered({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-cream">
      <DemoDataBanner />
      <main className="mx-auto box-border flex w-full max-w-[520px] flex-1 flex-col gap-5 px-4 py-10">{children}</main>
    </div>
  );
}

/**
 * /demo/pos: sign-in gate, then the till in the workspace shell. Only members of a retailer linked
 * to the demo partner get tills; the server checks this on every call (CLAUDE.md rule 8).
 */
export function DemoTillScreen({ decoder }: { decoder?: QrDecoder }) {
  const router = useRouter();
  const { data: user, isPending } = useCurrentUser();
  const logout = useLogout();
  const tills = useDemoTills(Boolean(user));

  if (isPending || (user && tills.isPending)) {
    return (
      <Centered>
        <LoadingPanel />
      </Centered>
    );
  }
  if (!user) {
    return (
      <Centered>
        <EmptyPanel
          title={TITLE}
          action={
            <Link href="/login" className={buttonClass("primary", "sm")}>
              Sign in
            </Link>
          }
        >
          {SIGN_IN}
        </EmptyPanel>
      </Centered>
    );
  }
  if (tills.isError) {
    return (
      <Centered>
        <ErrorPanel>{describeError(tills.error)}</ErrorPanel>
      </Centered>
    );
  }
  if (!tills.data?.length || !user.membership) {
    return (
      <Centered>
        <EmptyPanel title={TITLE}>{NO_TILL}</EmptyPanel>
      </Centered>
    );
  }

  return (
    <WorkspaceShell
      companyName={user.membership.company_display_name}
      roleLabel="Retailer"
      accountName={user.display_name}
      nav={[{ href: "/demo/pos", label: TITLE }]}
      currentHref="/demo/pos"
      pageTitle={TITLE}
      onLogout={() => logout.mutate(undefined, { onSuccess: () => router.push("/login") })}
    >
      <div className="mx-auto flex w-full max-w-[560px] flex-col gap-4">
        <p className="m-0 text-text-subtle">{SUBTITLE}</p>
        <DemoTill tills={tills.data} retailerName={tills.data[0].retailer_name} decoder={decoder} />
      </div>
    </WorkspaceShell>
  );
}
