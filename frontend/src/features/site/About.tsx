import { ArrowRight, Check, LockKeyhole } from "lucide-react";
import Image from "next/image";

import { Button } from "@/components/ui/button";

import { PHOTOS } from "./content";
import { Eyebrow, SectionTitle, Wrap } from "./Eyebrow";

const POINTS = [
  "Keeps working offline, then syncs safely",
  "Flags clashing edits instead of overwriting them",
  "Every view and change is in the audit log",
];

export function About() {
  return (
    <section id="about" aria-labelledby="about-title" className="py-16 sm:py-24">
      <Wrap className="grid items-center gap-12 lg:grid-cols-2 lg:gap-24">
        <div className="relative max-w-[540px] pb-6 pr-5 sm:pb-9 sm:pr-9">
          <div aria-hidden className="absolute bottom-0 left-5 h-[78%] w-[78%] rounded-2xl bg-accent-soft" />
          <div className="relative h-[300px] overflow-hidden rounded-2xl shadow-[0_15px_40px_rgba(10,42,33,0.1)] sm:h-[420px]">
            <Image
              src={PHOTOS.about.src}
              alt={PHOTOS.about.alt}
              fill
              sizes="(min-width: 1024px) 520px, 90vw"
              className="object-cover"
            />
          </div>
          <div className="absolute bottom-3 right-0 z-10 flex items-center gap-3 rounded-2xl bg-white p-3 shadow-[0_12px_35px_rgba(10,42,33,0.13)] sm:p-5">
            <span className="grid size-11 place-items-center rounded-xl bg-indigo-soft text-indigo">
              <LockKeyhole aria-hidden className="size-6" />
            </span>
            <strong className="text-sm leading-snug text-ink sm:text-[15px]">
              Each clinic&apos;s records
              <br />
              stay its own.
            </strong>
          </div>
        </div>

        <div className="max-w-[600px]">
          <Eyebrow>Why Lafiya</Eyebrow>
          <SectionTitle id="about-title">
            Built for the clinic you <span className="text-accent">actually run.</span>
          </SectionTitle>
          <p className="text-[17px] leading-[1.75] text-muted">
            Power cuts, patchy data and a full waiting room are normal days, not rare ones. Lafiya
            was designed around them.
          </p>
          <p className="leading-[1.8] text-muted">
            Each person sees the screens their job needs. The front desk registers and books,
            nurses take vitals and triage, doctors examine, prescribe and refer, and clinic admins
            review the audit log.
          </p>
          <ul className="my-7 grid gap-3 font-bold text-ink">
            {POINTS.map((point) => (
              <li key={point} className="flex items-center gap-3">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
                  <Check aria-hidden className="size-3.5" strokeWidth={3} />
                </span>
                {point}
              </li>
            ))}
          </ul>
          <Button asChild variant="outline">
            <a href="#features">
              See the features <ArrowRight aria-hidden className="size-4" />
            </a>
          </Button>
        </div>
      </Wrap>
    </section>
  );
}
