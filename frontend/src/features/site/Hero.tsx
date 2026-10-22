import { ArrowRight, CloudUpload, ShieldCheck, Siren, Smartphone, WifiOff } from "lucide-react";
import Image from "next/image";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

import { PHOTOS } from "./content";
import { Eyebrow, Wrap } from "./Eyebrow";

export function Hero() {
  return (
    <section
      id="top"
      aria-labelledby="hero-title"
      className="relative overflow-hidden bg-[linear-gradient(115deg,#f5faf8_0%,#edf6f2_58%,#e2f1ea_100%)] pt-12 sm:pt-[72px]"
    >
      {/* Rings in the corner, like ripples from the doorway in the logo */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-52 -top-80 size-[800px] rounded-full border border-accent/10 shadow-[0_0_0_70px_rgba(11,110,79,0.025),0_0_0_140px_rgba(11,110,79,0.02)]"
      />

      <Wrap className="relative grid items-center gap-8 lg:min-h-[470px] lg:grid-cols-[1fr_1.03fr] lg:gap-16">
        <div>
          <Eyebrow>Clinic software for Africa</Eyebrow>
          <h1
            id="hero-title"
            className="mb-6 font-display text-[44px] font-bold leading-[1.05] tracking-[-0.04em] text-ink sm:text-[56px] lg:text-[64px]"
          >
            Care that <span className="text-accent">keeps going</span> when the network doesn&apos;t.
          </h1>
          <p className="mb-8 max-w-[480px] text-[17px] leading-[1.75] text-muted">
            Lafiya runs your front desk, triage, consultations and follow-ups. Work is saved on the
            device first and synced when the connection returns, so no patient waits on a loading
            screen.
          </p>
          <div className="flex flex-col items-start gap-5 sm:flex-row sm:items-center sm:gap-7">
            <Button asChild size="lg">
              <a href="#demo">
                Request a demo <ArrowRight aria-hidden className="size-[18px]" />
              </a>
            </Button>
            <Button asChild variant="link">
              <a href="#flow">
                See how a visit flows <ArrowRight aria-hidden className="size-4" />
              </a>
            </Button>
          </div>
          <div className="mt-10 flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-indigo-soft text-indigo">
              <ShieldCheck aria-hidden className="size-5" />
            </span>
            <p className="m-0 text-sm leading-snug">
              <strong className="block text-ink">Every change is recorded</strong>
              <span className="text-muted">Who, what, when, and on which device</span>
            </p>
          </div>
        </div>

        <div className="relative mx-auto h-[340px] w-full max-w-[540px] sm:h-[420px] lg:h-[450px] lg:max-w-none">
          <div className="absolute right-[6%] top-0 h-[92%] w-[82%] overflow-hidden rounded-[48%_48%_22px_22px] bg-accent-soft shadow-[0_25px_55px_rgba(10,42,33,0.16)]">
            <Image
              src={PHOTOS.hero.src}
              alt={PHOTOS.hero.alt}
              fill
              priority
              sizes="(min-width: 1024px) 480px, 80vw"
              className="object-cover"
            />
            <div aria-hidden className="absolute inset-0 bg-linear-to-t from-deep/25 to-transparent to-55%" />
          </div>

          <FloatingCard className="left-0 top-12 sm:-left-2 sm:top-16">
            <span className="grid size-10 place-items-center rounded-xl bg-[#fef0c7] text-[#93370d]">
              <WifiOff aria-hidden className="size-5" />
            </span>
            <span>
              <strong className="block text-ink">Saved on this device</strong>
              <span className="text-muted">2 entries sync when online</span>
            </span>
          </FloatingCard>

          <FloatingCard className="bottom-6 right-0 sm:-right-2 sm:bottom-10">
            <span className="grid size-10 place-items-center rounded-xl bg-[#fef3f2] text-danger">
              <Siren aria-hidden className="size-5" />
            </span>
            <span>
              <strong className="block text-ink">Emergency first</strong>
              <span className="text-muted">Triage sorts the queue</span>
            </span>
          </FloatingCard>

          <span aria-hidden className="absolute right-[3%] top-[7%] size-6 rounded-full border-[5px] border-[#7fd8b6]" />
          <span aria-hidden className="absolute bottom-[14%] left-[5%] size-3.5 rounded-full bg-indigo" />
        </div>
      </Wrap>

      <Wrap className="relative mt-10 flex flex-wrap justify-between gap-x-10 gap-y-3 border-t border-deep/10 py-6 sm:justify-start">
        <Assurance icon={<CloudUpload aria-hidden className="size-[18px]" />}>Syncs safely when back online</Assurance>
        <Assurance icon={<ShieldCheck aria-hidden className="size-[18px]" />}>Audit trail on every record</Assurance>
        <Assurance icon={<Smartphone aria-hidden className="size-[18px]" />}>Patients sign in by SMS code</Assurance>
      </Wrap>
    </section>
  );
}

function FloatingCard({ className, children }: { className: string; children: ReactNode }) {
  return (
    <div
      className={`absolute z-10 flex items-center gap-3 rounded-[14px] bg-white p-3 text-[13px] leading-snug shadow-[0_14px_40px_rgba(10,42,33,0.14)] sm:p-4 sm:text-sm ${className}`}
    >
      {children}
    </div>
  );
}

function Assurance({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <span className="flex items-center gap-2 text-sm font-bold text-muted">
      <span className="text-accent">{icon}</span>
      {children}
    </span>
  );
}
