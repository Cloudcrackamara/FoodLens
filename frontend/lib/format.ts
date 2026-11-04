/** "2026-10-22" -> "22 Oct 2026"; null -> "Not recorded". Dates are shown in UTC. */
export function formatDate(value: string | null): string {
  if (!value) return "Not recorded";
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
