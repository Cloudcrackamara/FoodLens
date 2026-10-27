"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { FormField } from "@/components/auth/FormField";
import { Catalogue } from "./Catalogue";
import { Announcements } from "./Announcements";
import { ChangeNotices } from "./ChangeNotices";
import { ordersEnabled } from "@/lib/features";
import { IncomingOrders } from "./IncomingOrders";
import { describeError } from "@/lib/api";
import { fieldErrors, useCurrentUser } from "@/lib/auth";
import { buttonClass } from "@/lib/ui";
import {
  companyStatusLabels,
  companyTypeLabel,
  contactFormSchema,
  locationFormSchema,
  locationStatusLabels,
  useAddLocation,
  useMyCompany,
  useUpdateContact,
  type Company,
  type ContactForm,
  type LocationForm,
} from "@/lib/companies";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/Panels";

const statusExplanations: Record<Company["review_status"], string> = {
  PENDING_REVIEW:
    "A FoodLens admin will review your profile for the demo directory. You can add supplier " +
    "locations once it is approved.",
  APPROVED:
    "Your profile is approved for the FoodLens demo directory. Locations appear there once an " +
    "admin has reviewed them. This is not a NAFDAC or SON approval.",
  REJECTED: "Your profile was not approved for the FoodLens demo directory.",
  SUSPENDED: "Your profile is suspended and hidden from the FoodLens demo directory.",
};

function AddLocationForm({ companyId }: { companyId: string }) {
  const addLocation = useAddLocation(companyId);
  const [form, setForm] = useState<LocationForm>({ name: "", address: "", area: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (key: keyof LocationForm) => (value: string) => setForm({ ...form, [key]: value });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = locationFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    addLocation.mutate(parsed.data, {
      onSuccess: () => setForm({ name: "", address: "", area: "" }),
    });
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-3">
      <h3 className="font-semibold">Add a supplier location</h3>
      <FormField id="location_name" label="Location name" value={form.name}
        error={errors.name} onChange={set("name")} />
      <FormField id="location_address" label="Address" value={form.address}
        error={errors.address} onChange={set("address")} />
      <FormField id="location_area" label="Area or city" value={form.area}
        error={errors.area} onChange={set("area")} />
      {addLocation.isError && (
        <p role="alert" className="font-semibold text-bad">
          {describeError(addLocation.error)}
        </p>
      )}
      <button
        type="submit"
        disabled={addLocation.isPending}
        className={`self-start ${buttonClass("primary", "sm")}`}
      >
        Submit location for review
      </button>
    </form>
  );
}

function ContactDetails({ company, isOwner }: { company: Company; isOwner: boolean }) {
  const update = useUpdateContact(company.company_id);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<ContactForm>({
    contact_email: company.contact_email,
    contact_phone: company.contact_phone ?? "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = contactFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    update.mutate(parsed.data, { onSuccess: () => setEditing(false) });
  }

  return (
    <section aria-labelledby="contact-heading" className="flex flex-col gap-2">
      <h2 id="contact-heading" className="font-heading text-[17px] font-semibold text-ink">Contact details</h2>
      {!editing ? (
        <>
          <p className="break-words">
            {company.contact_email}
            {company.contact_phone && ` · ${company.contact_phone}`}
          </p>
          {isOwner && (
            <button type="button" onClick={() => setEditing(true)} className="self-start font-semibold text-brand-dark underline">
              Edit contact details
            </button>
          )}
          {update.isSuccess && <p role="status" className="text-sm">Contact details saved.</p>}
        </>
      ) : (
        <form onSubmit={handleSubmit} noValidate aria-label="Edit contact details" className="flex flex-col gap-3">
          <p className="text-sm text-text-muted">
            Changes are saved straight away and recorded with your name and the time. They are shown in
            the partner directory.
          </p>
          <FormField id="contact_email" label="Contact email" type="email" value={form.contact_email}
            error={errors.contact_email} onChange={(value) => setForm({ ...form, contact_email: value })} />
          <FormField id="contact_phone" label="Contact phone (optional)" value={form.contact_phone}
            error={errors.contact_phone} onChange={(value) => setForm({ ...form, contact_phone: value })} />
          {update.isError && (
            <p role="alert" className="font-semibold text-bad">{describeError(update.error)}</p>
          )}
          <div className="flex gap-3">
            <button type="submit" disabled={update.isPending}
              className={buttonClass("primary", "sm")}>
              Save contact details
            </button>
            <button type="button" onClick={() => setEditing(false)} className="font-semibold text-brand-dark underline">Cancel</button>
          </div>
        </form>
      )}
    </section>
  );
}

export function CompanyView({ company, isOwner = false }: { company: Company; isOwner?: boolean }) {
  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="company-status" className="rounded-[12px] bg-white p-6 shadow-card">
        <h2 id="company-status" className="font-heading text-[17px] font-semibold text-ink">{company.display_name}</h2>
        <p className="text-sm text-text-subtle">{companyTypeLabel(company)}</p>
        <p className="mt-2 font-medium">Status: {companyStatusLabels[company.review_status]}</p>
        <p>{statusExplanations[company.review_status]}</p>
        {company.review_note && <p className="mt-1 text-sm">Reviewer note: {company.review_note}</p>}
      </section>

      <ContactDetails company={company} isOwner={isOwner} />

      <section aria-labelledby="locations-heading" className="flex flex-col gap-3">
        <h2 id="locations-heading" className="font-heading text-[17px] font-semibold text-ink">Locations</h2>
        {company.locations.length === 0 ? (
          <EmptyPanel title="No locations yet." />
        ) : (
          <ul className="flex flex-col gap-2">
            {company.locations.map((location) => (
              <li key={location.location_id} className="rounded-[10px] border border-line bg-white p-3.5">
                <p className="font-medium">{location.name}</p>
                <p>{location.address}, {location.area}</p>
                <p className="text-sm">{locationStatusLabels[location.review_status]}</p>
              </li>
            ))}
          </ul>
        )}
        {company.review_status === "APPROVED" && <AddLocationForm companyId={company.company_id} />}
      </section>

      {company.review_status === "APPROVED" && <Catalogue companyId={company.company_id} />}
      {company.review_status === "APPROVED" && <ChangeNotices companyId={company.company_id} />}
      {company.review_status === "APPROVED" && <Announcements companyId={company.company_id} />}
      {ordersEnabled && company.review_status === "APPROVED" && <IncomingOrders companyId={company.company_id} />}
    </div>
  );
}

export function CompanyDashboard() {
  const { data: user, isPending } = useCurrentUser();
  const company = useMyCompany(user?.membership?.company_id);

  if (isPending) return <LoadingPanel />;
  if (!user) {
    return (
      <p>
        <Link href="/login" className="font-semibold text-brand-dark underline">Sign in</Link> to manage your company.
      </p>
    );
  }
  if (!user.membership) {
    return (
      <p>
        Your account is not linked to a company yet.{" "}
        <Link href="/company/register" className="font-semibold text-brand-dark underline">Register your company</Link>.
      </p>
    );
  }
  if (company.isError) {
    return <ErrorPanel>{describeError(company.error)}</ErrorPanel>;
  }
  if (!company.data) return <LoadingPanel />;
  return <CompanyView company={company.data} isOwner={user.membership.role === "OWNER"} />;
}
