"use client";

import { useState } from "react";

/**
 * A button for something that cannot be undone. The first press asks the
 * question; only "Yes" does it.
 */
export function ConfirmAction({
  label,
  question,
  onConfirm,
  pending,
  quiet = true,
}: {
  label: string;
  question: string;
  onConfirm: () => void;
  pending: boolean;
  quiet?: boolean;
}) {
  const [asking, setAsking] = useState(false);

  if (!asking) {
    return (
      <button
        type="button"
        className={quiet ? "button-secondary" : "button"}
        onClick={() => setAsking(true)}
        disabled={pending}
      >
        {label}
      </button>
    );
  }

  return (
    <span role="group" className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-semibold">{question}</span>
      <button
        type="button"
        className="button"
        disabled={pending}
        onClick={() => {
          onConfirm();
          setAsking(false);
        }}
      >
        {pending ? "Saving..." : "Yes"}
      </button>
      <button
        type="button"
        className="button-secondary"
        disabled={pending}
        onClick={() => setAsking(false)}
      >
        No
      </button>
    </span>
  );
}
