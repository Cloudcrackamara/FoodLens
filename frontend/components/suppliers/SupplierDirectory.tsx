"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Mail, MapPin, Search, UserRound } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { describeError } from "@/lib/api";
import { companyTypes, useSuppliers, type Supplier } from "@/lib/companies";
import { formatDate } from "@/lib/lookup";

export function SupplierCard({ supplier, linked = false }: { supplier: Supplier; linked?: boolean }) {
  return (
    <li
      aria-label={supplier.display_name}
      className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 sm:p-5"
    >
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="font-heading text-xl font-bold leading-tight text-primary">
              {linked ? (
                <Link href={`/suppliers/${supplier.company_id}`} className="hover:underline">
                  {supplier.display_name}
                </Link>
              ) : (
                supplier.display_name
              )}
            </h2>
            <p className="text-sm text-muted-foreground">{companyTypes[supplier.company_type]}</p>
          </div>
          <Badge variant="secondary">{supplier.badge}</Badge>
        </div>
        <p className="text-sm text-muted-foreground">{supplier.badge_note}</p>
      </div>

      <div>
        <h3 className="mb-1.5 flex items-center gap-2 text-sm font-semibold">
          <MapPin aria-hidden="true" className="size-4 text-coral" />
          Demo-reviewed locations
        </h3>
        <ul className="flex flex-col gap-1.5">
          {supplier.locations.map((location) => (
            <li key={location.location_id} className="text-sm">
              <span className="font-medium">{location.name}</span>: {location.address},{" "}
              {location.area}
              {location.reviewed_at && (
                <span className="text-muted-foreground">
                  {" "}
                  · reviewed {formatDate(location.reviewed_at.slice(0, 10))}
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h3 className="mb-1.5 flex items-center gap-2 text-sm font-semibold">
          <Mail aria-hidden="true" className="size-4 text-coral" />
          Contact
        </h3>
        <p className="break-words text-sm">
          {supplier.contact_email}
          {supplier.contact_phone && ` · ${supplier.contact_phone}`}
        </p>
        {supplier.contacts.length > 0 && (
          <ul className="mt-1.5 flex flex-col gap-1 text-sm">
            {supplier.contacts.map((contact) => (
              <li key={`${contact.display_name}-${contact.email ?? ""}`} className="flex gap-2 break-words">
                <UserRound aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <span>
                  {contact.display_name}
                  {contact.title && `, ${contact.title}`}
                  {contact.email && ` · ${contact.email}`}
                  {contact.phone && ` · ${contact.phone}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {linked && (
        <Button asChild variant="outline" size="sm" className="self-start">
          <Link href={`/suppliers/${supplier.company_id}`}>
            Products and order requests
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        </Button>
      )}
    </li>
  );
}

export function SupplierCardSkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  );
}

export function SupplierDirectory() {
  const [search, setSearch] = useState("");
  const suppliers = useSuppliers(search);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="supplier-search">Search by name, area, or product</Label>
        <div className="relative">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            id="supplier-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="e.g. Ikeja, palm oil"
            className="pl-10"
          />
        </div>
      </div>

      {suppliers.isPending && (
        <div role="status" aria-label="Loading suppliers" className="grid gap-4 md:grid-cols-2">
          <SupplierCardSkeleton />
          <SupplierCardSkeleton />
        </div>
      )}
      {suppliers.isError && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{describeError(suppliers.error)}</AlertDescription>
        </Alert>
      )}
      {suppliers.isSuccess && suppliers.data.length === 0 && (
        <p className="rounded-xl border border-dashed border-input p-6 text-center text-muted-foreground">
          No demo-reviewed suppliers match.
        </p>
      )}
      {suppliers.isSuccess && suppliers.data.length > 0 && (
        <ul className="grid gap-4 md:grid-cols-2">
          {suppliers.data.map((supplier) => (
            <SupplierCard key={supplier.company_id} supplier={supplier} linked />
          ))}
        </ul>
      )}
    </div>
  );
}
