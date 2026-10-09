"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { FormField } from "@/components/auth/FormField";
import { describeError } from "@/lib/api";
import { fieldErrors } from "@/lib/auth";
import {
  companyRegisterFormSchema,
  companyTypes,
  useRegisterCompany,
  type CompanyRegisterForm as Form,
} from "@/lib/companies";

const emptyForm: Form = {
  company_type: "MANUFACTURER",
  display_name: "",
  contact_email: "",
  contact_phone: "",
  claimed_legal_name: "",
  claimed_business_identifier: "",
  claimed_address: "",
};

export function CompanyRegisterForm() {
  const router = useRouter();
  const registerCompany = useRegisterCompany();
  const [form, setForm] = useState<Form>(emptyForm);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const set = (key: keyof Form) => (value: string) => setForm({ ...form, [key]: value });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = companyRegisterFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    registerCompany.mutate(parsed.data, { onSuccess: () => router.push("/company") });
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      <label className="flex flex-col gap-1">
        <span className="font-medium">Company type</span>
        <select
          value={form.company_type}
          onChange={(event) => set("company_type")(event.target.value)}
          className="rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900"
        >
          {Object.entries(companyTypes).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <FormField
        id="display_name"
        label="Company name (shown publicly)"
        value={form.display_name}
        error={errors.display_name}
        onChange={set("display_name")}
      />
      <FormField
        id="contact_email"
        label="Contact email (shown publicly)"
        type="email"
        value={form.contact_email}
        error={errors.contact_email}
        onChange={set("contact_email")}
      />
      <FormField
        id="contact_phone"
        label="Contact phone (optional, shown publicly)"
        type="tel"
        value={form.contact_phone}
        error={errors.contact_phone}
        onChange={set("contact_phone")}
      />
      <fieldset className="flex flex-col gap-4 rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
        <legend className="px-1 font-semibold">Business details you claim</legend>
        <p className="text-sm text-zinc-700 dark:text-zinc-300">
          FoodLens records these as claims. They are not verified and are not shown in the public
          directory.
        </p>
        <FormField
          id="claimed_legal_name"
          label="Registered legal name"
          value={form.claimed_legal_name}
          error={errors.claimed_legal_name}
          onChange={set("claimed_legal_name")}
        />
        <FormField
          id="claimed_business_identifier"
          label="Business registration number (optional)"
          value={form.claimed_business_identifier}
          error={errors.claimed_business_identifier}
          onChange={set("claimed_business_identifier")}
        />
        <FormField
          id="claimed_address"
          label="Registered address (optional)"
          value={form.claimed_address}
          error={errors.claimed_address}
          onChange={set("claimed_address")}
        />
      </fieldset>
      {registerCompany.isError && (
        <p role="alert" className="text-red-700 dark:text-red-400">
          {describeError(registerCompany.error)}
        </p>
      )}
      <button
        type="submit"
        disabled={registerCompany.isPending}
        className="rounded-md bg-zinc-900 px-4 py-2 font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {registerCompany.isPending ? "Submitting…" : "Submit for FoodLens review"}
      </button>
    </form>
  );
}
