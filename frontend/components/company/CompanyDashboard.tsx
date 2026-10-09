"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { FormField } from "@/components/auth/FormField";
import { Catalogue } from "./Catalogue";
import { describeError } from "@/lib/api";
import { fieldErrors, useCurrentUser } from "@/lib/auth";
import {
  companyStatusLabels,
  companyTypes,
  locationFormSchema,
  locationStatusLabels,
  useAddLocation,
  useMyCompany,
  type Company,
  type LocationForm,
} from "@/lib/companies";

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
        <p role="alert" className="text-red-700 dark:text-red-400">
          {describeError(addLocation.error)}
        </p>
      )}
      <button
        type="submit"
        disabled={addLocation.isPending}
        className="self-start rounded-md bg-zinc-900 px-4 py-2 font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
      >
        Submit location for review
      </button>
    </form>
  );
}

export function CompanyView({ company }: { company: Company }) {
  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="company-status" className="rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
        <h2 id="company-status" className="text-xl font-bold">{company.display_name}</h2>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">{companyTypes[company.company_type]}</p>
        <p className="mt-2 font-medium">Status: {companyStatusLabels[company.review_status]}</p>
        <p>{statusExplanations[company.review_status]}</p>
        {company.review_note && <p className="mt-1 text-sm">Reviewer note: {company.review_note}</p>}
      </section>

      <section aria-labelledby="locations-heading" className="flex flex-col gap-3">
        <h2 id="locations-heading" className="text-lg font-semibold">Supplier locations</h2>
        {company.locations.length === 0 ? (
          <p>No locations yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {company.locations.map((location) => (
              <li key={location.location_id} className="rounded-md border border-zinc-200 p-3 dark:border-zinc-800">
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
    </div>
  );
}

export function CompanyDashboard() {
  const { data: user, isPending } = useCurrentUser();
  const company = useMyCompany(user?.membership?.company_id);

  if (isPending) return <p>Loading…</p>;
  if (!user) {
    return (
      <p>
        <Link href="/login" className="underline">Sign in</Link> to manage your company.
      </p>
    );
  }
  if (!user.membership) {
    return (
      <p>
        Your account is not linked to a company yet.{" "}
        <Link href="/company/register" className="underline">Register your company</Link>.
      </p>
    );
  }
  if (company.isError) {
    return <p role="alert">{describeError(company.error)}</p>;
  }
  if (!company.data) return <p>Loading…</p>;
  return <CompanyView company={company.data} />;
}
