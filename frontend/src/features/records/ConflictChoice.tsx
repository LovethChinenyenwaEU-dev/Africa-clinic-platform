"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { errorMessage } from "@/lib/api-client";

import { resolveConflict, type ConflictKind, type Keep } from "./api";

/*
 * Shown on a version in conflict: it was changed on another device at the same time
 * as the version now in use (Week 8, FR-O4). Neither is lost; a person chooses.
 */
export function ConflictChoice({
  kind,
  id,
  allowed,
  queryKey,
  whoMayChoose = "Whoever recorded it, or the clinician who opened the encounter, can choose.",
}: {
  kind: ConflictKind;
  id: string;
  allowed: boolean; // the server checks again; this only hides buttons that would be refused
  queryKey: readonly unknown[];
  whoMayChoose?: string;
}) {
  const queryClient = useQueryClient();
  const choose = useMutation({
    mutationFn: (keep: Keep) => resolveConflict(kind, id, keep),
    onSettled: () => void queryClient.invalidateQueries({ queryKey }),
  });

  return (
    <div className="grid w-full gap-2 rounded border border-red-200 bg-red-50 p-2 text-sm">
      <p>
        <span className="badge mr-2 bg-red-100 text-red-900">Conflict</span>
        Changed on two devices at once. This version waits beside the one in use until someone
        chooses. The other is kept in the history.
      </p>
      {allowed ? (
        <div className="flex flex-wrap gap-2">
          <ConfirmAction
            label="Keep this version"
            question="Use this version, and move the current one to history?"
            pending={choose.isPending}
            onConfirm={() => choose.mutate("this")}
          />
          <ConfirmAction
            label="Keep the current one"
            question="Keep the current one, and move this version to history?"
            pending={choose.isPending}
            onConfirm={() => choose.mutate("current")}
          />
        </div>
      ) : (
        <p>{whoMayChoose}</p>
      )}
      {choose.isError && (
        <p role="alert" className="error">
          {errorMessage(choose.error)}
        </p>
      )}
    </div>
  );
}
