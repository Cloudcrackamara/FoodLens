"use client";

import { useState, type FormEvent } from "react";
import { Card } from "@/components/ui/Card";
import { ErrorPanel, InlineError, LoadingPanel } from "@/components/ui/Panels";
import { StatusPill } from "@/components/ui/StatusPill";
import { describeError } from "@/lib/api";
import { useAddStaff, useDeactivateStaff, useMembers } from "@/lib/merchant";
import { buttonClass, inputClass } from "@/lib/ui";

/**
 * /merchant/team: the owner adds staff by email and deactivates them (D106). The person must
 * already have a FoodLens account and no company. The server allows this for the owner only.
 */
export function TeamPage({ companyId }: { companyId: string }) {
  const members = useMembers(companyId);
  const add = useAddStaff(companyId);
  const deactivate = useDeactivateStaff(companyId);
  const [email, setEmail] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!email.trim()) return;
    add.mutate(email.trim(), { onSuccess: () => setEmail("") });
  }

  return (
    <div className="flex flex-col gap-5">
      <Card variant="workspace" aria-label="Add staff" className="flex flex-col gap-3">
        <h2 className="m-0 font-heading text-lg font-semibold text-ink">Add a staff member</h2>
        <p className="m-0 text-text-subtle">
          They need a FoodLens account that is not part of a company yet. Staff can record stock events.
          Only you can manage the team.
        </p>
        <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="flex flex-1 flex-col gap-1.5">
            <label htmlFor="staff-email" className="font-semibold text-ink">
              Their account email
            </label>
            <input
              id="staff-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="off"
              className={inputClass}
            />
          </div>
          <button type="submit" disabled={add.isPending || !email.trim()} className={buttonClass("primary", "sm")}>
            Add staff member
          </button>
        </form>
        {add.isError && <InlineError className="text-sm">{describeError(add.error)}</InlineError>}
      </Card>

      {members.isPending ? (
        <LoadingPanel label="Loading the team" />
      ) : members.isError ? (
        <ErrorPanel onRetry={() => members.refetch()}>{describeError(members.error)}</ErrorPanel>
      ) : (
        <Card variant="workspace" aria-label="Team" className="flex flex-col gap-2">
          <h2 className="m-0 font-heading text-lg font-semibold text-ink">Team</h2>
          <ul className="m-0 flex list-none flex-col p-0">
            {members.data.map((member) => (
              <li
                key={member.member_id}
                className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-divider py-3 first:border-t-0"
              >
                <span className="min-w-0 flex-1">
                  <b className="block text-ink">{member.display_name}</b>
                  <span className="break-all text-sm text-text-subtle">{member.email}</span>
                </span>
                <StatusPill tone={member.role === "OWNER" ? "info" : "neutral"}>
                  {member.role === "OWNER" ? "Owner" : "Staff"}
                </StatusPill>
                <StatusPill tone={member.membership_status === "ACTIVE" ? "ok" : "neutral"}>
                  {member.membership_status === "ACTIVE" ? "Active" : "Deactivated"}
                </StatusPill>
                {member.role === "STAFF" && member.membership_status === "ACTIVE" && (
                  <button
                    type="button"
                    disabled={deactivate.isPending}
                    onClick={() => deactivate.mutate(member.member_id)}
                    aria-label={`Deactivate ${member.display_name}`}
                    className={buttonClass("quiet", "sm")}
                  >
                    Deactivate
                  </button>
                )}
              </li>
            ))}
          </ul>
          {deactivate.isError && <InlineError className="text-sm">{describeError(deactivate.error)}</InlineError>}
        </Card>
      )}
    </div>
  );
}
