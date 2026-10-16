"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { errorMessage } from "@/lib/api-client";

import { getBranches, getHours, publishHours, removeHours, type HoursForm } from "./api";
import { VISIT_TYPE_LABELS, WEEKDAY_LABELS, clockTime } from "./labels";

const SLOT_CHOICES = [10, 15, 20, 30, 45, 60];

/*
 * A clinician's own weekly hours: when they see patients in person, and when they
 * take remote consultations. Front desk books into the free slots these make;
 * patients booking themselves (later this week) may only take a free slot.
 */
export function MyHours({ meId }: { meId: string }) {
  const queryClient = useQueryClient();
  const key = ["hours", meId];
  const hours = useQuery({ queryKey: key, queryFn: () => getHours(meId) });
  const branches = useQuery({ queryKey: ["branches"], queryFn: getBranches });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: key });

  const [form, setForm] = useState<Omit<HoursForm, "branch_id"> & { branch_id: string }>({
    branch_id: "",
    weekday: 0,
    starts: "09:00",
    ends: "13:00",
    visit_type: "in_person",
    slot_minutes: 15,
  });
  const [problem, setProblem] = useState<string | null>(null);
  const add = useMutation({ mutationFn: publishHours, onSuccess: refresh });
  const remove = useMutation({ mutationFn: removeHours, onSuccess: refresh });

  const branchId = form.branch_id || branches.data?.[0]?.id || "";
  const branchName = (id: string) =>
    branches.data?.find((branch) => branch.id === id)?.name ?? "a branch";

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!branchId) return setProblem("Choose the branch.");
    if (form.starts >= form.ends) return setProblem("The end time must be after the start.");
    setProblem(null);
    add.mutate({ ...form, branch_id: branchId });
  }

  return (
    <section className="grid gap-6">
      <div>
        <h1 className="mb-1">My hours</h1>
        <p className="text-sm">
          The weekly hours you see patients, in Lagos time. Front desk books into the free
          slots. Removing hours does not cancel visits already booked in them.
        </p>
      </div>

      <section aria-labelledby="hours-heading" className="card">
        <h2 id="hours-heading" className="mb-0">
          Every week
        </h2>
        {hours.isPending && <p>Loading...</p>}
        {hours.isError && (
          <p role="alert" className="error">
            {errorMessage(hours.error)}
          </p>
        )}
        {hours.data?.length === 0 && <p>No hours yet. Add them below.</p>}
        {hours.data && hours.data.length > 0 && (
          <ul className="grid gap-2">
            {hours.data.map((row) => (
              <li
                key={row.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2"
              >
                <span className="w-28 font-semibold">{WEEKDAY_LABELS[row.weekday]}</span>
                <span className="font-mono">
                  {clockTime(row.starts)}-{clockTime(row.ends)}
                </span>
                <span className="badge bg-blue-100 text-blue-900">
                  {VISIT_TYPE_LABELS[row.visit_type] ?? row.visit_type}
                </span>
                <span className="text-sm">
                  {row.slot_minutes}-minute slots · {branchName(row.branch_id)}
                </span>
                <span className="ml-auto">
                  <ConfirmAction
                    label="Remove"
                    question="Stop offering these hours?"
                    pending={remove.isPending}
                    onConfirm={() => remove.mutate(row.id)}
                  />
                </span>
              </li>
            ))}
          </ul>
        )}
        {remove.isError && (
          <p role="alert" className="error">
            {errorMessage(remove.error)}
          </p>
        )}
      </section>

      <form
        className="card grid gap-3 sm:grid-cols-3"
        onSubmit={handleSubmit}
        noValidate
        aria-labelledby="add-hours-heading"
      >
        <h2 id="add-hours-heading" className="mb-0 sm:col-span-3">
          Add hours
        </h2>
        <div className="field">
          <label htmlFor="hours-day">Day</label>
          <select
            id="hours-day"
            value={form.weekday}
            onChange={(event) => setForm({ ...form, weekday: Number(event.target.value) })}
          >
            {WEEKDAY_LABELS.map((label, index) => (
              <option key={label} value={index}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="hours-from">From</label>
          <input
            id="hours-from"
            type="time"
            step={300}
            value={form.starts}
            onChange={(event) => setForm({ ...form, starts: event.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="hours-to">To</label>
          <input
            id="hours-to"
            type="time"
            step={300}
            value={form.ends}
            onChange={(event) => setForm({ ...form, ends: event.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="hours-type">Kind</label>
          <select
            id="hours-type"
            value={form.visit_type}
            onChange={(event) =>
              setForm({ ...form, visit_type: event.target.value as HoursForm["visit_type"] })
            }
          >
            {Object.entries(VISIT_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="hours-slot">Slot length</label>
          <select
            id="hours-slot"
            value={form.slot_minutes}
            onChange={(event) => setForm({ ...form, slot_minutes: Number(event.target.value) })}
          >
            {SLOT_CHOICES.map((minutes) => (
              <option key={minutes} value={minutes}>
                {minutes} minutes
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="hours-branch">Branch</label>
          <select
            id="hours-branch"
            value={branchId}
            onChange={(event) => setForm({ ...form, branch_id: event.target.value })}
          >
            {branches.data?.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
        </div>
        {(problem || add.isError) && (
          <p role="alert" className="error sm:col-span-3">
            {problem ?? errorMessage(add.error)}
          </p>
        )}
        <div className="sm:col-span-3">
          <button className="button" type="submit" disabled={add.isPending}>
            {add.isPending ? "Saving..." : "Add hours"}
          </button>
        </div>
      </form>
    </section>
  );
}
