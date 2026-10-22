import { ArrowUpRight, Mail, Phone } from "lucide-react";
import type { ReactNode } from "react";

import { CONTACT } from "./content";
import { Eyebrow, Wrap } from "./Eyebrow";

export function ContactBand() {
  return (
    <section
      id="contact"
      aria-labelledby="contact-title"
      className="relative overflow-hidden bg-[linear-gradient(110deg,#0b6e4f,#064431)] py-14 text-white"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 -top-52 size-[360px] rounded-full border border-white/10 shadow-[0_0_0_45px_rgba(255,255,255,0.03),0_0_0_90px_rgba(255,255,255,0.025)]"
      />
      <Wrap className="relative grid items-center gap-4 sm:grid-cols-2 lg:grid-cols-[1.2fr_1fr_1fr] lg:gap-8">
        <div className="mb-3 sm:col-span-2 lg:col-span-1 lg:mb-0">
          <Eyebrow light>Let&apos;s talk</Eyebrow>
          <h2 id="contact-title" className="mb-3 font-display text-[32px] font-bold leading-tight tracking-[-0.03em]">
            Questions before a demo?
          </h2>
          <p className="m-0 text-white/75">We answer clinic owners and clinicians directly.</p>
        </div>
        <ContactCard href={CONTACT.phoneHref} label="Call us" value={CONTACT.phone} icon={<Phone aria-hidden />} />
        <ContactCard href={`mailto:${CONTACT.email}`} label="Email us" value={CONTACT.email} icon={<Mail aria-hidden />} />
      </Wrap>
    </section>
  );
}

function ContactCard({ href, label, value, icon }: { href: string; label: string; value: string; icon: ReactNode }) {
  return (
    <a
      href={href}
      className="flex items-center gap-4 rounded-2xl border border-white/25 p-4 transition hover:-translate-y-0.5 hover:bg-white/10"
    >
      <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-white/15">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-xs font-bold uppercase tracking-[0.14em] text-white/65">{label}</span>
        <strong className="block truncate">{value}</strong>
      </span>
      <ArrowUpRight aria-hidden className="size-5 shrink-0 text-[#7fd8b6]" />
    </a>
  );
}
