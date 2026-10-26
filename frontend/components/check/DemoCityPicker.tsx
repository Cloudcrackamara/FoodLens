"use client";

import { useDemoCities } from "@/lib/check";

type Props = { value: string; onChange: (city: string) => void };

/**
 * Demo only (SIMULATE_LOCATION_ENABLED): pretend the check comes from a chosen city, so the
 * demo scenario can show checks in different places. Hidden when the API has it switched off.
 */
export function DemoCityPicker({ value, onChange }: Props) {
  const cities = useDemoCities();
  if (!cities.data?.length) return null;
  return (
    <label className="flex flex-col gap-1 rounded-lg border border-dashed border-amber-500 p-3 text-sm">
      <span className="font-medium">Demo: check as if from</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-11 rounded-md border border-zinc-400 bg-transparent px-2 text-base"
      >
        <option value="">Use my real area</option>
        {cities.data.map((city) => (
          <option key={city.city} value={city.city}>
            {city.city}, {city.state}
          </option>
        ))}
      </select>
    </label>
  );
}
