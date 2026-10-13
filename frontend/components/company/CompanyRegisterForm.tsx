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
import { buttonVariants } from "@/components/ui/button";

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
    <form
      onSubmit={handleSubmit}
      noValidate
      className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 sm:p-6"
    >
      <label className="flex flex-col gap-1">
        <span className="font-medium">Company type</span>
        <select
          value={form.company_type}
          onChange={(event) => set("company_type")(event.target.value)}
          className="min-h-11 w-full rounded-lg border border-input bg-card px-3 py-2 text-base text-foreground outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40"
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
      <fieldset className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 sm:p-5">
        <legend className="px-1 font-semibold">Business details you claim</legend>
        <p className="text-sm text-muted-foreground">
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
        <p role="alert" className="text-destructive">
          {describeError(registerCompany.error)}
        </p>
      )}
      <button
        type="submit"
        disabled={registerCompany.isPending}
        className={buttonVariants()}
      >
        {registerCompany.isPending ? "Submitting…" : "Submit for FoodLens review"}
      </button>
    </form>
  );
}
