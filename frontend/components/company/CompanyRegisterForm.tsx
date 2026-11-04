"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { FormField } from "@/components/auth/FormField";
import { describeError } from "@/lib/api";
import { fieldErrors } from "@/lib/auth";
import { buttonClass } from "@/lib/ui";
import {
  companyRegisterFormSchema,
  companyTypeFlags,
  useRegisterCompany,
  type CompanyTypeFlag,
  type CompanyRegisterForm as Form,
} from "@/lib/companies";

const emptyForm: Form = {
  is_manufacturer: false,
  is_distributor: false,
  is_retailer: false,
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
  const toggle = (flag: CompanyTypeFlag) => setForm({ ...form, [flag]: !form[flag] });

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
      <fieldset
        aria-describedby={errors.company_types ? "company_types-error" : undefined}
        className="flex flex-col gap-2"
      >
        <legend className="font-medium">What does your company do? Choose all that apply.</legend>
        {(Object.keys(companyTypeFlags) as CompanyTypeFlag[]).map((flag) => (
          <label key={flag} className="flex items-center gap-2">
            <input type="checkbox" checked={form[flag]} onChange={() => toggle(flag)} />
            {companyTypeFlags[flag]}
          </label>
        ))}
        {errors.company_types && (
          <p id="company_types-error" className="text-sm font-semibold text-bad">
            {errors.company_types}
          </p>
        )}
      </fieldset>
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
      <fieldset className="flex flex-col gap-4 rounded-[12px] bg-white p-6 shadow-card">
        <legend className="px-1 font-semibold">Business details you claim</legend>
        <p className="text-sm text-text-muted">
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
        <p role="alert" className="font-semibold text-bad">
          {describeError(registerCompany.error)}
        </p>
      )}
      <button
        type="submit"
        disabled={registerCompany.isPending}
        className={buttonClass("primary", "sm")}
      >
        {registerCompany.isPending ? "Submitting…" : "Submit for FoodLens review"}
      </button>
    </form>
  );
}
