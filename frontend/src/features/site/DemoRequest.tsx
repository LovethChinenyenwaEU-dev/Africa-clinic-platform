"use client";

import { ArrowRight, Building2, CalendarCheck, Check, Info, MessagesSquare, UsersRound } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

import { CLINIC_SIZES, CONTACT, COUNTRIES } from "./content";
import { Eyebrow, SectionTitle, Wrap } from "./Eyebrow";

const FIELD = "d-input w-full bg-[#fbfdfc]";

export function DemoRequest() {
  const [noted, setNoted] = useState(false);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Not connected yet: nothing is sent anywhere. The thank-you says so.
    setNoted(true);
  }

  return (
    <section id="demo" aria-labelledby="demo-title" className="bg-canvas py-16 sm:py-24">
      <Wrap className="grid items-center gap-12 lg:grid-cols-[0.85fr_1.15fr] lg:gap-20">
        <div className="max-w-[560px]">
          <Eyebrow>Bring Lafiya to your clinic</Eyebrow>
          <SectionTitle id="demo-title">
            Let&apos;s set up <span className="text-accent">your clinic.</span>
          </SectionTitle>
          <p className="text-[17px] leading-[1.75] text-muted">
            Tell us about your clinic and the people who work there. We will walk your team through
            the screens each of them will use.
          </p>
          <ul className="my-8 grid gap-5">
            <Point icon={<UsersRound aria-hidden className="size-5" />} title="A walk-through with your team">
              Front desk, nurses and doctors each see their own screens.
            </Point>
            <Point icon={<Building2 aria-hidden className="size-5" />} title="Your clinic, your records">
              Each clinic&apos;s patients are kept apart from every other clinic.
            </Point>
          </ul>
          <p className="m-0 flex items-center gap-2 border-t border-line pt-5 text-sm text-muted">
            <MessagesSquare aria-hidden className="size-[18px] text-accent" />
            <span>
              Rather talk first? <a href="#contact" className="font-bold text-accent">Contact us</a>
            </span>
          </p>
        </div>

        <div className="rounded-[20px] border border-line bg-white p-5 shadow-[0_20px_60px_rgba(10,42,33,0.08)] sm:p-8">
          <div className="mb-6 flex items-center gap-4 border-b border-line pb-6">
            <span className="grid size-12 place-items-center rounded-[13px] bg-accent-soft text-accent">
              <CalendarCheck aria-hidden className="size-6" />
            </span>
            <div>
              <h3 className="m-0 font-display text-xl font-bold text-ink">Request a demo</h3>
              <p className="m-0 text-sm text-muted">Fields marked * are needed.</p>
            </div>
          </div>

          {noted ? (
            <div role="status" className="grid justify-items-center gap-3 px-2 py-8 text-center">
              <span className="grid size-14 place-items-center rounded-full bg-[#ecfdf3] text-[#067647]">
                <Check aria-hidden className="size-7" />
              </span>
              <h3 className="m-0 font-display text-2xl font-bold text-ink">Thank you</h3>
              <p className="m-0 max-w-[420px] leading-[1.8] text-muted">
                This form is not connected yet, so nothing has been sent. Please email{" "}
                <a href={`mailto:${CONTACT.email}`} className="font-bold text-accent">
                  {CONTACT.email}
                </a>{" "}
                and we will reply.
              </p>
              <Button variant="outline" onClick={() => setNoted(false)}>
                Back to the form
              </Button>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="grid gap-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Your name *">
                  <input name="name" required autoComplete="name" className={FIELD} />
                </Field>
                <Field label="Work email *">
                  <input name="email" type="email" required autoComplete="email" className={FIELD} />
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Clinic name *">
                  <input name="clinic" required autoComplete="organization" className={FIELD} />
                </Field>
                <Field label="Phone">
                  <input name="phone" type="tel" autoComplete="tel" placeholder="+234 ..." className={FIELD} />
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Country *">
                  <select name="country" required defaultValue="" className="d-select w-full bg-[#fbfdfc]">
                    <option value="" disabled>
                      Choose a country
                    </option>
                    {COUNTRIES.map((country) => (
                      <option key={country}>{country}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Clinic size">
                  <select name="size" defaultValue="" className="d-select w-full bg-[#fbfdfc]">
                    <option value="">Choose a size</option>
                    {CLINIC_SIZES.map((size) => (
                      <option key={size}>{size}</option>
                    ))}
                  </select>
                </Field>
              </div>
              <Field label="Anything we should know?">
                <textarea name="message" rows={3} className="d-textarea w-full bg-[#fbfdfc]" />
              </Field>
              <Button type="submit" size="lg" className="mt-1">
                Request a demo <ArrowRight aria-hidden className="size-[18px]" />
              </Button>
              <p className="m-0 flex items-center justify-center gap-2 text-center text-xs text-muted">
                <Info aria-hidden className="size-3.5 shrink-0 text-accent" />
                We only use these details to arrange the demo.
              </p>
            </form>
          )}
        </div>
      </Wrap>
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-2 text-sm font-bold text-ink">
      {label}
      {children}
    </label>
  );
}

function Point({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <li className="flex items-center gap-4">
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-indigo-soft text-indigo">{icon}</span>
      <span>
        <strong className="block text-ink">{title}</strong>
        <span className="text-sm text-muted">{children}</span>
      </span>
    </li>
  );
}
