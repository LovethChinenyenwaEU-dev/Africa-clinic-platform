"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { useSync } from "@/features/sync/SyncProvider";
import { API_MESSAGES, ApiError } from "@/lib/api-client";
import { errorsByField } from "@/lib/form-errors";
import { todayInLagos } from "@/lib/format";

import { offlineRegistrationWrite, registerPatient, type RegisterResult } from "./api";
import { DUPLICATE_REASON_LABELS, SEX_LABELS } from "./labels";
import { SEXES, registerFormSchema, type RegisterPayload } from "./schemas";

const FIELDS = ["full_name", "date_of_birth", "sex", "phone"] as const;
type Field = (typeof FIELDS)[number];

// What is in the boxes right now. Zod checks it all when the form is sent.
type FormState = Record<Field, string>;
const EMPTY: FormState = { full_name: "", date_of_birth: "", sex: "", phone: "" };

export function RegisterPatientForm() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  // The checked form waiting for the person's answer to "is this someone new?".
  const [pending, setPending] = useState<RegisterPayload | null>(null);
  // Registered with no network: kept on this device and sent when it returns.
  const [savedOnDevice, setSavedOnDevice] = useState(false);
  const { online, queue } = useSync();

  const register = useMutation({
    mutationFn: ({ payload, confirmed }: { payload: RegisterPayload; confirmed: boolean }) =>
      registerPatient(payload, confirmed),
    onSuccess: (result: RegisterResult) => {
      if (result.kind === "registered") {
        router.push(`/patients/${result.patient.id}`);
      }
    },
  });

  const duplicate = register.data?.kind === "possible_duplicate" ? register.data : null;

  function update(field: Field, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = registerFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(errorsByField(parsed.error, FIELDS));
      return;
    }
    setErrors({});
    setPending(parsed.data);
    if (!online) {
      void saveOnDevice(parsed.data);
      return;
    }
    register.mutate({ payload: parsed.data, confirmed: false });
  }

  async function saveOnDevice(payload: RegisterPayload) {
    await queue(offlineRegistrationWrite(payload));
    register.reset();
    setPending(null);
    setForm(EMPTY);
    setSavedOnDevice(true);
  }

  const networkFailed = register.error instanceof ApiError && register.error.kind === "unavailable";

  function confirmNewPerson() {
    if (pending) register.mutate({ payload: pending, confirmed: true });
  }

  const failure =
    register.error instanceof ApiError
      ? register.error.message
      : register.error
        ? API_MESSAGES.unavailable
        : null;

  return (
    <section className="grid max-w-xl gap-6">
      <h1 className="mb-0">Register a patient</h1>

      {!online && !savedOnDevice && (
        <p className="notice">
          Offline. The registration will be kept on this device and sent when the network
          returns. If the patient may already be registered, front desk will be asked to check.
        </p>
      )}
      {savedOnDevice && (
        <p role="status" className="notice">
          Saved on this device. The patient will be registered when the network returns (see the
          sync badge at the top). You can register another patient below.
        </p>
      )}

      <form className="card" onSubmit={handleSubmit} noValidate>
        {/* Locked while the duplicate question is open, so what is confirmed is what was checked. */}
        <fieldset disabled={Boolean(duplicate) || register.isPending} className="grid gap-4">
          <div className="field">
            <label htmlFor="full_name">Full name</label>
            <input
              id="full_name"
              autoComplete="off"
              value={form.full_name}
              onChange={(event) => update("full_name", event.target.value)}
              aria-invalid={Boolean(errors.full_name)}
              aria-describedby={errors.full_name ? "full_name-error" : undefined}
            />
            {errors.full_name && (
              <p id="full_name-error" className="error">
                {errors.full_name}
              </p>
            )}
          </div>

          <div className="field">
            <label htmlFor="date_of_birth">Date of birth</label>
            <input
              id="date_of_birth"
              type="date"
              min="1900-01-01"
              max={todayInLagos()}
              value={form.date_of_birth}
              onChange={(event) => update("date_of_birth", event.target.value)}
              aria-invalid={Boolean(errors.date_of_birth)}
              aria-describedby={errors.date_of_birth ? "date_of_birth-error" : undefined}
            />
            {errors.date_of_birth && (
              <p id="date_of_birth-error" className="error">
                {errors.date_of_birth}
              </p>
            )}
          </div>

          <div className="field">
            <label htmlFor="sex">Sex</label>
            <select
              id="sex"
              value={form.sex}
              onChange={(event) => update("sex", event.target.value)}
              aria-invalid={Boolean(errors.sex)}
              aria-describedby={errors.sex ? "sex-error" : undefined}
            >
              <option value="">Choose...</option>
              {SEXES.map((sex) => (
                <option key={sex} value={sex}>
                  {SEX_LABELS[sex]}
                </option>
              ))}
            </select>
            {errors.sex && (
              <p id="sex-error" className="error">
                {errors.sex}
              </p>
            )}
          </div>

          <div className="field">
            <label htmlFor="phone">Phone number (optional)</label>
            <input
              id="phone"
              type="tel"
              autoComplete="off"
              placeholder="0803 123 4567"
              value={form.phone}
              onChange={(event) => update("phone", event.target.value)}
              aria-invalid={Boolean(errors.phone)}
              aria-describedby={errors.phone ? "phone-error" : undefined}
            />
            {errors.phone && (
              <p id="phone-error" className="error">
                {errors.phone}
              </p>
            )}
          </div>
        </fieldset>

        {failure && (
          <p role="alert" className="error">
            {failure}
          </p>
        )}
        {networkFailed && pending && (
          <p>
            <button
              className="button-secondary"
              type="button"
              onClick={() => void saveOnDevice(pending)}
            >
              Save on this device instead
            </button>
          </p>
        )}

        {!duplicate && (
          <div className="flex gap-3">
            <button className="button" type="submit" disabled={register.isPending}>
              {register.isPending ? "Registering..." : "Register"}
            </button>
            <Link href="/patients" className="button-secondary">
              Cancel
            </Link>
          </div>
        )}
      </form>

      {duplicate && (
        <div role="alert" className="notice grid gap-3">
          <p className="font-semibold">This patient may already be registered.</p>
          <p>Open each match to check. Only register again if this is a different person.</p>
          <ul className="grid gap-1">
            {duplicate.matches.map((match) => (
              <li key={match.patient_id}>
                <Link
                  href={`/patients/${match.patient_id}`}
                  target="_blank"
                  className="text-accent underline"
                >
                  Possible match
                </Link>{" "}
                ({DUPLICATE_REASON_LABELS[match.reason]}, opens in a new tab)
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-3">
            <button
              className="button"
              type="button"
              onClick={confirmNewPerson}
              disabled={register.isPending}
            >
              {register.isPending ? "Registering..." : "This is a different person: register"}
            </button>
            <button
              className="button-secondary"
              type="button"
              onClick={() => register.reset()}
              disabled={register.isPending}
            >
              Go back and edit
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
