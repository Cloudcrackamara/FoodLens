"use client";

import { useState } from "react";
import { describeError } from "@/lib/api";
import { companyTypes, useSuppliers, type Supplier } from "@/lib/companies";
import { formatDate } from "@/lib/lookup";

export function SupplierCard({ supplier }: { supplier: Supplier }) {
  return (
    <li
      aria-label={supplier.display_name}
      className="flex flex-col gap-3 rounded-md border border-zinc-300 p-4 dark:border-zinc-700"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{supplier.display_name}</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {companyTypes[supplier.company_type]}
          </p>
        </div>
        <span className="rounded-full border border-zinc-500 px-3 py-1 text-xs font-semibold">
          {supplier.badge}
        </span>
      </div>
      <p className="text-sm text-zinc-700 dark:text-zinc-300">{supplier.badge_note}</p>

      <div>
        <h3 className="font-medium">Demo-reviewed locations</h3>
        <ul className="mt-1 flex flex-col gap-1">
          {supplier.locations.map((location) => (
            <li key={location.name}>
              <span className="font-medium">{location.name}</span>: {location.address},{" "}
              {location.area}
              {location.reviewed_at && (
                <span className="text-sm text-zinc-600 dark:text-zinc-400">
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
        <span className="font-medium">Search by name or area</span>
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900"
        />
      </label>

      {suppliers.isError && (
        <p role="alert" className="text-red-700 dark:text-red-400">
          {describeError(suppliers.error)}
        </p>
      )}
      {suppliers.isSuccess && suppliers.data.length === 0 && (
        <p>No demo-reviewed suppliers match.</p>
      )}
      {suppliers.isSuccess && suppliers.data.length > 0 && (
        <ul className="flex flex-col gap-4">
          {suppliers.data.map((supplier) => (
            <SupplierCard key={supplier.company_id} supplier={supplier} />
          ))}
        </ul>
      )}
    </div>
  );
}
