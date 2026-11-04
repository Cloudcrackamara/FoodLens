"use client";

import { useState, type FormEvent } from "react";
import { EmptyPanel, ErrorPanel, InlineError, LoadingPanel } from "@/components/ui/Panels";
import { StatusPill } from "@/components/ui/StatusPill";
import { describeError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import {
  useAddKey,
  useAddTill,
  useCreatePartner,
  useLinkRetailer,
  usePartners,
  useRemoveTill,
  useRetailerOptions,
  useRevokeKey,
  useRevokeLink,
  useSetPartnerStatus,
  type Credentials,
  type Partner,
  type RetailerOption,
} from "@/lib/pos";
import { buttonClass, inputClass } from "@/lib/ui";

// Approved wording (30 Oct 2026).
const ONE_TIME =
  "Copy these now. FoodLens shows the API key and signing secret only once and can't show them again.";

const subheadingClass = "font-semibold text-ink";

/** The one-time reveal after creating a partner or a key. Kept only in this component's state. */
function OneTime({ credentials, onDone }: { credentials: Credentials; onDone: () => void }) {
  return (
    <div role="status" className="flex flex-col gap-2 rounded-[10px] border-2 border-pending bg-pending-bg p-4">
      <p className="m-0 font-semibold text-pending">{ONE_TIME}</p>
      <dl className="m-0 grid grid-cols-1 gap-1 text-sm">
        <dt className="font-medium">API key</dt>
        <dd className="m-0 break-all font-mono">{credentials.api_key}</dd>
        {credentials.signing_secret && (
          <>
            <dt className="font-medium">Signing secret</dt>
            <dd className="m-0 break-all font-mono">{credentials.signing_secret}</dd>
          </>
        )}
      </dl>
      <button type="button" onClick={onDone} className={`self-start ${buttonClass("secondary", "sm")}`}>
        Done
      </button>
    </div>
  );
}

function TillForm({ partner, retailers }: { partner: Partner; retailers: RetailerOption[] }) {
  const addTill = useAddTill();
  const linked = retailers.filter((r) => partner.links.some((l) => l.retailer_id === r.retailer_id && l.status === "ACTIVE"));
  const [retailerId, setRetailerId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [tillRef, setTillRef] = useState("");
  const locations = linked.find((r) => r.retailer_id === retailerId)?.locations ?? [];

  function submit(event: FormEvent) {
    event.preventDefault();
    addTill.mutate(
      { partnerId: partner.partner_id, retailer_id: retailerId, till_ref: tillRef.trim(), location_id: locationId },
      { onSuccess: () => setTillRef("") },
    );
  }

  if (linked.length === 0) return null;
  return (
    <form onSubmit={submit} aria-label={`Add till for ${partner.name}`} className="grid grid-cols-1 gap-2 sm:grid-cols-4 sm:items-end">
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Retailer</span>
        <select value={retailerId} onChange={(e) => { setRetailerId(e.target.value); setLocationId(""); }} className={inputClass}>
          <option value="" />
          {linked.map((r) => <option key={r.retailer_id} value={r.retailer_id}>{r.display_name}</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Location</span>
        <select value={locationId} onChange={(e) => setLocationId(e.target.value)} className={inputClass}>
          <option value="" />
          {locations.map((l) => <option key={l.location_id} value={l.location_id}>{l.name} ({l.area})</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Till</span>
        <input value={tillRef} onChange={(e) => setTillRef(e.target.value)} maxLength={64} className={inputClass} />
      </label>
      <button type="submit" disabled={!retailerId || !locationId || !tillRef.trim() || addTill.isPending} className={buttonClass("secondary", "sm")}>
        Add till
      </button>
      {addTill.isError && <InlineError className="text-sm sm:col-span-4">{describeError(addTill.error)}</InlineError>}
    </form>
  );
}

function PartnerRow({ partner, retailers }: { partner: Partner; retailers: RetailerOption[] }) {
  const [credentials, setCredentials] = useState<Credentials | null>(null);
  const [linkId, setLinkId] = useState("");
  const setStatus = useSetPartnerStatus();
  const addKey = useAddKey();
  const revokeKey = useRevokeKey();
  const link = useLinkRetailer();
  const revokeLink = useRevokeLink();
  const removeTill = useRemoveTill();
  const pid = partner.partner_id;
  const active = partner.status === "ACTIVE";
  const unlinked = retailers.filter((r) => !partner.links.some((l) => l.retailer_id === r.retailer_id && l.status === "ACTIVE"));
  const failed = [setStatus, addKey, revokeKey, link, revokeLink, removeTill].find((m) => m.isError);

  return (
    <li aria-label={partner.name} className="flex flex-col gap-4 rounded-[12px] bg-white p-6 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold">{partner.name}</h3>
          <p className="text-sm">{formatDate(partner.created_at.slice(0, 10))}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusPill tone={active ? "ok" : "bad"}>{active ? "Active" : "Suspended"}</StatusPill>
          <button
            type="button"
            disabled={setStatus.isPending}
            onClick={() => setStatus.mutate({ partnerId: pid, status: active ? "SUSPENDED" : "ACTIVE" })}
            className={buttonClass(active ? "danger" : "secondary", "sm")}
          >
            {active ? "Suspend" : "Reactivate"}
          </button>
        </div>
      </div>

      {credentials && <OneTime credentials={credentials} onDone={() => setCredentials(null)} />}
      {failed?.error && <InlineError className="text-sm">{describeError(failed.error)}</InlineError>}

      <div className="flex flex-col gap-2">
        <h4 className={subheadingClass}>API keys</h4>
        <ul className="flex flex-col gap-2">
          {partner.keys.map((key) => (
            <li key={key.key_id} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-mono">{key.key_prefix}…</span>
              <span>{formatDate(key.created_at.slice(0, 10))}</span>
              {key.revoked_at ? (
                <StatusPill tone="neutral">Revoked</StatusPill>
              ) : (
                <>
                  <StatusPill tone="ok">Active</StatusPill>
                  <button type="button" disabled={revokeKey.isPending} onClick={() => revokeKey.mutate({ partnerId: pid, keyId: key.key_id })} className={buttonClass("quiet", "sm")}>
                    Revoke key
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
        <button
          type="button"
          disabled={addKey.isPending}
          onClick={() => addKey.mutate(pid, { onSuccess: (created) => setCredentials(created.credentials) })}
          className={`self-start ${buttonClass("secondary", "sm")}`}
        >
          Add key
        </button>
      </div>

      <div className="flex flex-col gap-2">
        <h4 className={subheadingClass}>Retailers</h4>
        <ul className="flex flex-col gap-2">
          {partner.links.map((item) => (
            <li key={item.link_id} className="flex flex-wrap items-center gap-2 text-sm">
              <span>{item.retailer_name}</span>
              <span className="font-mono text-text-subtle">{item.retailer_id}</span>
              {item.status === "ACTIVE" ? (
                <>
                  <StatusPill tone="ok">Active</StatusPill>
                  <button type="button" disabled={revokeLink.isPending} onClick={() => revokeLink.mutate({ partnerId: pid, linkId: item.link_id })} className={buttonClass("quiet", "sm")}>
                    Revoke link
                  </button>
                </>
              ) : (
                <StatusPill tone="neutral">Revoked</StatusPill>
              )}
            </li>
          ))}
        </ul>
        {unlinked.length > 0 && (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <label className="flex flex-col gap-1 text-sm sm:w-72">
              <span className="font-medium">Retailer</span>
              <select value={linkId} onChange={(e) => setLinkId(e.target.value)} className={inputClass}>
                <option value="" />
                {unlinked.map((r) => <option key={r.retailer_id} value={r.retailer_id}>{r.display_name}</option>)}
              </select>
            </label>
            <button
              type="button"
              disabled={!linkId || link.isPending}
              onClick={() => link.mutate({ partnerId: pid, retailerId: linkId }, { onSuccess: () => setLinkId("") })}
              className={buttonClass("secondary", "sm")}
            >
              Link retailer
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <h4 className={subheadingClass}>Tills</h4>
        <ul className="flex flex-col gap-2">
          {partner.tills.map((till) => (
            <li key={till.till_id} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-mono">{till.till_ref}</span>
              <span>{till.retailer_name} · {till.location_name} ({till.area})</span>
              <button type="button" disabled={removeTill.isPending} onClick={() => removeTill.mutate({ partnerId: pid, tillId: till.till_id })} className={buttonClass("quiet", "sm")}>
                Remove till
              </button>
            </li>
          ))}
        </ul>
        <TillForm partner={partner} retailers={retailers} />
      </div>
    </li>
  );
}

/** /admin: POS partners, their keys, retailer links and tills (D121). The server checks admin. */
export function PosPartners() {
  const partners = usePartners();
  const retailers = useRetailerOptions();
  const create = useCreatePartner();
  const [name, setName] = useState("");
  const [created, setCreated] = useState<Credentials | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate(name.trim(), {
      onSuccess: (result) => {
        setCreated(result.credentials);
        setName("");
      },
    });
  }

  return (
    <section aria-labelledby="pos-heading" className="flex flex-col gap-3">
      <h2 id="pos-heading" className="font-heading text-[17px] font-semibold text-ink">POS partners</h2>
      <form onSubmit={submit} aria-label="Add partner" className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <label className="flex flex-col gap-1 text-sm sm:w-72">
          <span className="font-medium">Partner name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} className={inputClass} />
        </label>
        <button type="submit" disabled={!name.trim() || create.isPending} className={buttonClass("primary", "sm")}>
          Add partner
        </button>
      </form>
      {create.isError && <InlineError className="text-sm">{describeError(create.error)}</InlineError>}
      {created && <OneTime credentials={created} onDone={() => setCreated(null)} />}
      {partners.isPending && <LoadingPanel />}
      {partners.isError && <ErrorPanel>{describeError(partners.error)}</ErrorPanel>}
      {partners.data?.length === 0 && <EmptyPanel title="No POS partners yet. Add one to issue an API key." />}
      <ul className="flex flex-col gap-3">
        {partners.data?.map((partner) => (
          <PartnerRow key={partner.partner_id} partner={partner} retailers={retailers.data ?? []} />
        ))}
      </ul>
    </section>
  );
}
