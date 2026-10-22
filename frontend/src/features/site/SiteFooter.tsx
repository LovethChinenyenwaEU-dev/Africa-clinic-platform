import { ArrowRight, HeartPulse } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/brand/Logo";

import { NAV } from "./content";
import { Wrap } from "./Eyebrow";

export function SiteFooter() {
  return (
    <footer className="bg-[#07211a] text-white/70">
      <Wrap className="grid grid-cols-2 gap-x-5 gap-y-9 py-12 lg:grid-cols-[1.4fr_0.7fr_0.9fr_1fr] lg:gap-14 lg:py-16">
        <div className="col-span-2 lg:col-span-1">
          <Logo tone="light" tagline />
          <p className="mt-5 max-w-[300px] text-sm leading-[1.8]">
            Clinic software that works on a bad day: offline-first records, triage and remote care,
            made for clinics in Africa.
          </p>
        </div>
        <FooterLinks title="Explore" links={NAV.slice(0, 3)} />
        <div>
          <h2 className="mb-4 mt-1 text-sm font-bold text-white">Get started</h2>
          <a href="#demo" className="my-3 block text-sm hover:text-[#7fd8b6]">
            Request a demo
          </a>
          <Link href="/login" className="my-3 block text-sm hover:text-[#7fd8b6]">
            Staff sign in
          </Link>
          <a href="#top" className="my-3 block text-sm hover:text-[#7fd8b6]">
            Back to the top
          </a>
        </div>
        <div className="col-span-2 rounded-2xl border border-white/15 p-5 lg:col-span-1">
          <HeartPulse aria-hidden className="size-5 text-[#7fd8b6]" />
          <strong className="mt-3 block text-white">Patients of a Lafiya clinic</strong>
          <p className="my-2 text-sm leading-relaxed">
            Your clinic gives you the address of your own page. Sign in there with your phone number.
          </p>
          <a href="#faq" className="flex items-center gap-2 text-sm font-bold text-[#7fd8b6]">
            How it works <ArrowRight aria-hidden className="size-4" />
          </a>
        </div>
      </Wrap>
      <Wrap className="flex flex-col justify-between gap-2 border-t border-white/10 py-5 text-xs text-white/50 sm:flex-row">
        <span>© {new Date().getFullYear()} Lafiya. All rights reserved.</span>
        <span>Contact details shown are placeholders.</span>
      </Wrap>
    </footer>
  );
}

function FooterLinks({ title, links }: { title: string; links: readonly { label: string; href: string }[] }) {
  return (
    <nav aria-label={title}>
      <h2 className="mb-4 mt-1 text-sm font-bold text-white">{title}</h2>
      {links.map((link) => (
        <a key={link.href} href={link.href} className="my-3 block text-sm hover:text-[#7fd8b6]">
          {link.label}
        </a>
      ))}
    </nav>
  );
}
