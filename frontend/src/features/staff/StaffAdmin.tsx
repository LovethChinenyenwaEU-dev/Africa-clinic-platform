"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { ROLE_LABELS } from "@/features/identity/roles";
import { roleSchema } from "@/features/identity/schemas";
import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import {
  MFA_LABELS,
  MIN_PASSWORD_LENGTH,
  addStaff,
  endStaffDevice,
  listStaff,
  newStaffSchema,
  resetApp,
  setActive,
  sortStaff,
  staffDevices,
  type NewStaff,
  type StaffListItem,
} from "./api";

const STAFF_KEY = ["staff-admin"];
const ACTIVE_BADGE = "bg-accent-soft text-accent";
const OFF_BADGE = "bg-gray-200 text-gray-800";

/*
 * Staff (Week 11), for admins: add people, switch them off and on, see and end their
 * signed-in devices, and reset an authenticator app after a lost phone.
 */
export function StaffAdmin({ meId }: { meId: string }) {
  const staff = useQuery({ queryKey: STAFF_KEY, queryFn: listStaff });

  return (
    <section className="grid gap-6">
      <div>
        <p className="eyebrow">Admin</p>
        <h1 className="mb-1">Staff</h1>
        <p className="m-0 text-sm">
          Who works at this clinic. Switching someone off signs them out everywhere at once;
          their records and audit lines are kept.
        </p>
      </div>
      <AddStaffForm />
      <section className="card" aria-live="polite">
        {staff.isPending && <p>Loading...</p>}
        {staff.isError && (
          <p role="alert" className="error">
            {errorMessage(staff.error)}
          </p>
        )}
        <ul className="grid gap-4">
          {sortStaff(staff.data ?? []).map((person) => (
            <StaffRow key={person.id} person={person} isMe={person.id === meId} />
          ))}
        </ul>
      </section>
    </section>
  );
}

type FormErrors = Partial<Record<keyof NewStaff, string>>;
const EMPTY: NewStaff = { full_name: "", email: "", role: "front_desk", password: "" };

function AddStaffForm() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<NewStaff>(EMPTY);
  const [errors, setErrors] = useState<FormErrors>({});
  const [added, setAdded] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: addStaff,
    onSuccess: (person) => {
      setAdded(person.full_name);
      setForm(EMPTY);
      void queryClient.invalidateQueries({ queryKey: STAFF_KEY });
    },
  });

  function update(field: keyof NewStaff, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setAdded(null);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const parsed = newStaffSchema.safeParse(form);
    if (!parsed.success) {
      const found: FormErrors = {};
      for (const issue of parsed.error.issues) {
        const field = issue.path[0] as keyof NewStaff;
        found[field] ??= issue.message;
      }
      setErrors(found);
      return;
    }
    setErrors({});
    add.mutate(parsed.data);
  }

  return (
    <details className="card">
      <summary className="cursor-pointer font-semibold">Add a staff member</summary>
      <form className="mt-4 grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit} noValidate>
        <TextField
          id="staff-name"
          label="Full name"
          value={form.full_name}
          error={errors.full_name}
          onChange={(value) => update("full_name", value)}
        />
        <TextField
          id="staff-email"
          label="Email"
          type="email"
          value={form.email}
          error={errors.email}
          onChange={(value) => update("email", value)}
        />
        <div className="field">
          <label htmlFor="staff-role">Role</label>
          <select
            id="staff-role"
            value={form.role}
            onChange={(event) => update("role", event.target.value)}
          >
            {roleSchema.options.map((role) => (
              <option key={role} value={role}>
                {ROLE_LABELS[role]}
              </option>
            ))}
          </select>
          {(form.role === "admin" || form.role === "billing") && (
            <p className="m-0 text-sm">They set up an authenticator app at their first sign-in.</p>
          )}
        </div>
        <TextField
          id="staff-password"
          label={`First password (at least ${MIN_PASSWORD_LENGTH} characters)`}
          type="password"
          value={form.password}
          error={errors.password}
          onChange={(value) => update("password", value)}
        />
        <div className="sm:col-span-2">
          <button type="submit" className="button" disabled={add.isPending}>
            {add.isPending ? "Adding..." : "Add staff member"}
          </button>
          <p className="mt-2 mb-0 text-sm">Give them the password in person, not by SMS.</p>
        </div>
        {add.isError && (
          <p role="alert" className="error sm:col-span-2">
            {errorMessage(add.error)}
          </p>
        )}
        {added && (
          <p role="status" className="m-0 sm:col-span-2">
            {added} was added and can sign in now.
          </p>
        )}
      </form>
    </details>
  );
}

function TextField({
  id,
  label,
  value,
  error,
  onChange,
  type = "text",
}: {
  id: string;
  label: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type={type}
        autoComplete={type === "password" ? "new-password" : "off"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
      />
      {error && (
        <p id={`${id}-error`} className="error">
          {error}
        </p>
      )}
    </div>
  );
}

function StaffRow({ person, isMe }: { person: StaffListItem; isMe: boolean }) {
  const queryClient = useQueryClient();
  const [showDevices, setShowDevices] = useState(false);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: STAFF_KEY });
  const toggle = useMutation({
    mutationFn: () => setActive(person.id, !person.is_active),
    onSuccess: refresh,
  });
  const reset = useMutation({ mutationFn: () => resetApp(person.id), onSuccess: refresh });

  return (
    <li className="grid gap-2 border-t border-line pt-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-semibold">{person.full_name}</span>
        {isMe && <span className="badge bg-accent-soft text-accent">You</span>}
        <span className="text-sm">{ROLE_LABELS[person.role]}</span>
        <span className="text-sm">{person.email}</span>
        <span className={`badge ${person.is_active ? ACTIVE_BADGE : OFF_BADGE}`}>
          {person.is_active ? "Active" : "Switched off"}
        </span>
      </div>
      <p className="m-0 text-sm">{MFA_LABELS[person.mfa]}</p>
      <div className="flex flex-wrap gap-2">
        {isMe ? (
          <Link href="/account" className="button-secondary">
            My devices
          </Link>
        ) : (
          <>
            <ConfirmAction
              label={person.is_active ? "Switch off" : "Switch back on"}
              question={
                person.is_active
                  ? `Switch ${person.full_name} off? They are signed out everywhere.`
                  : `Let ${person.full_name} sign in again?`
              }
              pending={toggle.isPending}
              onConfirm={() => toggle.mutate()}
            />
            {person.is_active && (
              <button
                type="button"
                className="button-secondary"
                aria-expanded={showDevices}
                onClick={() => setShowDevices((open) => !open)}
              >
                {showDevices ? "Hide devices" : "Devices"}
              </button>
            )}
            {person.mfa === "set_up" && (
              <ConfirmAction
                label="Reset authenticator app"
                question="Lost phone? They set up the app again at their next sign-in."
                pending={reset.isPending}
                onConfirm={() => reset.mutate()}
              />
            )}
          </>
        )}
      </div>
      {(toggle.isError || reset.isError) && (
        <p role="alert" className="error">
          {errorMessage(toggle.error ?? reset.error)}
        </p>
      )}
      {reset.isSuccess && person.mfa !== "set_up" && (
        <p role="status" className="m-0 text-sm">
          Reset. They will set up their app again at their next sign-in.
        </p>
      )}
      {showDevices && person.is_active && <StaffDevices person={person} />}
    </li>
  );
}

function StaffDevices({ person }: { person: StaffListItem }) {
  const queryClient = useQueryClient();
  const key = ["staff-devices", person.id];
  const devices = useQuery({ queryKey: key, queryFn: () => staffDevices(person.id) });
  const end = useMutation({
    mutationFn: (deviceId: string) => endStaffDevice(person.id, deviceId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: key }),
  });

  return (
    <div className="rounded-lg bg-accent-soft p-3 text-sm">
      {devices.isPending && <p className="m-0">Loading...</p>}
      {devices.isError && (
        <p role="alert" className="error m-0">
          {errorMessage(devices.error)}
        </p>
      )}
      {devices.data?.length === 0 && <p className="m-0">Not signed in anywhere.</p>}
      <ul className="m-0 grid gap-2">
        {devices.data?.map((device) => (
          <li key={device.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-semibold">{device.label}</span>
            <span>last used {formatDateTime(device.last_seen_at)}</span>
            <span className="ml-auto">
              <ConfirmAction
                label="Sign out this device"
                question="Sign it out now?"
                pending={end.isPending}
                onConfirm={() => end.mutate(device.id)}
              />
            </span>
          </li>
        ))}
      </ul>
      {end.isError && (
        <p role="alert" className="error m-0">
          {errorMessage(end.error)}
        </p>
      )}
    </div>
  );
}
