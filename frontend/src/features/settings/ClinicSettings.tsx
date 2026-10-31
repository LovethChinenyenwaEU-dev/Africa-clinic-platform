"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { getCurrentWording } from "@/features/consent/api";
import { PURPOSE_LABELS } from "@/features/consent/labels";
import { PURPOSES, type Purpose, type Wording } from "@/features/consent/schemas";
import { getBranches } from "@/features/scheduling/api";
import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import {
  MAX_WORDING_LENGTH,
  addBranch,
  newBranchSchema,
  publishWording,
  wordingProblem,
  type NewBranch,
} from "./api";

/*
 * Clinic settings (Week 11), for admins: branches, and the consent wording patients
 * agree to. Wording is never edited: publishing makes a new version, and consents
 * already given keep pointing at the words the patient actually saw.
 */
export function ClinicSettings() {
  return (
    <section className="grid gap-6">
      <div>
        <p className="eyebrow">Admin</p>
        <h1 className="mb-1">Clinic settings</h1>
        <p className="m-0 text-sm">Your branches, and the consent wording patients agree to.</p>
      </div>
      <Branches />
      <section className="grid gap-4">
        <div>
          <h2 className="mb-1">Consent wording</h2>
          <p className="m-0 text-sm">
            Publishing new wording makes a new version for new agreements. Consents already
            given keep the version the patient agreed to; nothing is changed after the fact.
          </p>
        </div>
        {PURPOSES.map((purpose) => (
          <WordingCard key={purpose} purpose={purpose} />
        ))}
      </section>
    </section>
  );
}

const EMPTY_BRANCH: NewBranch = { name: "", city: "" };

function Branches() {
  const queryClient = useQueryClient();
  const branches = useQuery({ queryKey: ["branches"], queryFn: getBranches });
  const [form, setForm] = useState<NewBranch>(EMPTY_BRANCH);
  const [problem, setProblem] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: addBranch,
    onSuccess: () => {
      setForm(EMPTY_BRANCH);
      void queryClient.invalidateQueries({ queryKey: ["branches"] });
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const parsed = newBranchSchema.safeParse(form);
    if (!parsed.success) {
      setProblem(parsed.error.issues[0].message);
      return;
    }
    setProblem(null);
    add.mutate(parsed.data);
  }

  return (
    <section className="card gap-4">
      <h2 className="mb-0">Branches</h2>
      {branches.isPending && <p className="m-0">Loading...</p>}
      {branches.isError && (
        <p role="alert" className="error">
          {errorMessage(branches.error)}
        </p>
      )}
      {branches.data?.length === 0 && <p className="m-0">No branches yet.</p>}
      <ul className="m-0 grid gap-1">
        {branches.data?.map((branch) => (
          <li key={branch.id}>
            <span className="font-semibold">{branch.name}</span>
            {branch.city && <span className="text-sm">, {branch.city}</span>}
          </li>
        ))}
      </ul>
      <form
        className="grid items-end gap-3 border-t border-line pt-4 sm:grid-cols-[1fr_1fr_auto]"
        onSubmit={handleSubmit}
        noValidate
      >
        <div className="field">
          <label htmlFor="branch-name">New branch name</label>
          <input
            id="branch-name"
            autoComplete="off"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            aria-invalid={Boolean(problem)}
            aria-describedby={problem ? "branch-error" : undefined}
          />
        </div>
        <div className="field">
          <label htmlFor="branch-city">City (optional)</label>
          <input
            id="branch-city"
            autoComplete="off"
            value={form.city}
            onChange={(event) => setForm({ ...form, city: event.target.value })}
          />
        </div>
        <button type="submit" className="button" disabled={add.isPending}>
          {add.isPending ? "Adding..." : "Add branch"}
        </button>
      </form>
      {problem && (
        <p id="branch-error" role="alert" className="error">
          {problem}
        </p>
      )}
      {add.isError && (
        <p role="alert" className="error">
          {errorMessage(add.error)}
        </p>
      )}
    </section>
  );
}

function WordingCard({ purpose }: { purpose: Purpose }) {
  const key = ["consent-wording", purpose];
  const wording = useQuery({ queryKey: key, queryFn: () => getCurrentWording(purpose) });
  const [editing, setEditing] = useState(false);

  return (
    <section className="card gap-3">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h3 className="mb-0 text-base">{PURPOSE_LABELS[purpose]}</h3>
        {wording.data && (
          <span className="text-sm">
            Version {wording.data.version}, published {formatDateTime(wording.data.created_at)}
          </span>
        )}
      </div>
      {wording.isPending && <p className="m-0">Loading...</p>}
      {wording.isError && (
        <p role="alert" className="error">
          {errorMessage(wording.error)}
        </p>
      )}
      {wording.data === null && (
        <p className="notice m-0">
          No wording yet: staff cannot record this consent until you publish some.
        </p>
      )}
      {wording.data && !editing && (
        <blockquote className="m-0 border-l-4 border-accent-soft pl-3 whitespace-pre-line">
          {wording.data.body}
        </blockquote>
      )}
      {wording.isSuccess &&
        (editing ? (
          <WordingEditor
            purpose={purpose}
            current={wording.data}
            onDone={() => setEditing(false)}
          />
        ) : (
          <div>
            <button type="button" className="button-secondary" onClick={() => setEditing(true)}>
              {wording.data ? "Publish new wording" : "Write the wording"}
            </button>
          </div>
        ))}
    </section>
  );
}

function WordingEditor({
  purpose,
  current,
  onDone,
}: {
  purpose: Purpose;
  current: Wording | null;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [body, setBody] = useState(current?.body ?? "");
  const [problem, setProblem] = useState<string | null>(null);
  const publish = useMutation({
    mutationFn: () => publishWording(purpose, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["consent-wording", purpose] });
      onDone();
    },
  });
  const id = `wording-${purpose}`;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = wordingProblem(body, current);
    setProblem(found);
    if (!found) publish.mutate();
  }

  return (
    <form className="grid gap-3" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor={id}>
          {current ? `New wording (becomes version ${current.version + 1})` : "Wording"}
        </label>
        <textarea
          id={id}
          rows={6}
          maxLength={MAX_WORDING_LENGTH}
          value={body}
          onChange={(event) => setBody(event.target.value)}
          aria-invalid={Boolean(problem)}
          aria-describedby={problem ? `${id}-error` : undefined}
        />
        <p className="m-0 text-sm">
          Plain words a patient can understand. {body.trim().length} of {MAX_WORDING_LENGTH}{" "}
          characters.
        </p>
      </div>
      {problem && (
        <p id={`${id}-error`} role="alert" className="error">
          {problem}
        </p>
      )}
      {publish.isError && (
        <p role="alert" className="error">
          {errorMessage(publish.error)}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="button" disabled={publish.isPending}>
          {publish.isPending ? "Publishing..." : "Publish"}
        </button>
        <button type="button" className="button-secondary" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}
