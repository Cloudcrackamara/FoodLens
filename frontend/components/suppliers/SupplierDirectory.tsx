"use client";

import Link from "next/link";
import { useState } from "react";
import { describeError } from "@/lib/api";
import { companyTypeLabel, useSuppliers, type Supplier } from "@/lib/companies";
import { formatDate } from "@/lib/format";

export function SupplierCard({ supplier, linked = false }: { supplier: Supplier; linked?: boolean }) {
  return (
    <li
      aria-label={supplier.display_name}
      className="flex flex-col gap-3 rounded-[12px] bg-white p-6 shadow-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-heading text-[17px] font-semibold text-ink">
            {linked ? (
              <Link href={`/suppliers/${supplier.company_id}`} className="font-semibold text-brand-dark underline">
                {supplier.display_name}
              </Link>
            ) : (
              supplier.display_name
            )}
          </h2>
          <p className="text-sm text-text-subtle">
            {companyTypeLabel(supplier)}
          </p>
        </div>
        <span className="inline-flex items-center rounded-full bg-neutral-bg px-2.5 py-0.5 text-sm font-bold text-neutral">
          {supplier.badge}
        </span>
      </div>
      <p className="text-sm text-text-muted">{supplier.badge_note}</p>

      <div>
        <h3 className="font-medium">Demo-reviewed locations</h3>
        <ul className="mt-1 flex flex-col gap-1">
          {supplier.locations.map((location) => (
            <li key={location.location_id}>
              <span className="font-medium">{location.name}</span>: {location.address},{" "}
              {location.area}
              {location.reviewed_at && (
                <span className="text-sm text-text-subtle">
                  {" "}
                  · reviewed {formatDate(location.reviewed_at.slice(0, 10))}
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h3 className="font-medium">Contact</h3>
        <p className="break-words">
          {supplier.contact_email}
          {supplier.contact_phone && ` · ${supplier.contact_phone}`}
        </p>
        {supplier.contacts.length > 0 && (
          <ul className="mt-1 flex flex-col gap-1 text-sm">
            {supplier.contacts.map((contact) => (
              <li key={`${contact.display_name}-${contact.email ?? ""}`}>
                {contact.display_name}
                {contact.title && `, ${contact.title}`}
                {contact.email && ` · ${contact.email}`}
                {contact.phone && ` · ${contact.phone}`}
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

export function SupplierDirectory() {
  const [search, setSearch] = useState("");
  const suppliers = useSuppliers(search);

  return (
    <div className="flex flex-col gap-4">
      <label className="flex flex-col gap-1">
        <span className="font-medium">Search by name, area, or product</span>
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="min-h-[46px] rounded-[10px] border border-line-input bg-white px-3 text-base text-ink"
        />
      </label>

      {suppliers.isError && (
        <p role="alert" className="font-semibold text-bad">
          {describeError(suppliers.error)}
        </p>
      )}
      {suppliers.isSuccess && suppliers.data.length === 0 && (
        <p>No demo-reviewed suppliers match.</p>
      )}
      {suppliers.isSuccess && suppliers.data.length > 0 && (
        <ul className="flex flex-col gap-4">
          {suppliers.data.map((supplier) => (
            <SupplierCard key={supplier.company_id} supplier={supplier} linked />
          ))}
        </ul>
      )}
    </div>
  );
}
