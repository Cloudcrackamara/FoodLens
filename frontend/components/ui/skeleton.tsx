import * as React from "react";
import { cn } from "@/lib/utils";

/** Loading placeholder. Pulses only when the phone allows motion. */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("rounded-lg bg-muted motion-safe:animate-pulse", className)}
      {...props}
    />
  );
}

export { Skeleton };
