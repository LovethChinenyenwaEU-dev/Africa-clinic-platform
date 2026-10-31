"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { errorMessage } from "@/lib/api-client";

import { mergeIntoOriginal } from "./api";

/*
 * "Move everything to the original" on a record the review found to be a duplicate
 * (Week 11). Visits, records, consents and invoices move; nothing is deleted. Afterwards
 * the person is taken to the original, which now holds the whole history.
 */
export function MergeButton({ duplicateId }: { duplicateId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const merge = useMutation({
    mutationFn: () => mergeIntoOriginal(duplicateId),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["patient"] });
      router.push(`/patients/${result.original.id}`);
    },
  });

  return (
    <div className="grid gap-1">
      <div>
        <ConfirmAction
          label="Move everything to the original"
          question="Move this record's visits, notes, consents and invoices to the original?"
          pending={merge.isPending}
          onConfirm={() => merge.mutate()}
          quiet={false}
        />
      </div>
      {merge.isError && (
        <p role="alert" className="error m-0">
          {errorMessage(merge.error)}
        </p>
      )}
    </div>
  );
}
