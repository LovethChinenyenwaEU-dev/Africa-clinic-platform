import { ArrowUpRight } from "lucide-react";

import { cn } from "@/lib/utils";

import { FEATURES } from "./content";
import { Eyebrow, SectionTitle, Wrap } from "./Eyebrow";
import { ICONS } from "./icons";

export function Features() {
  return (
    <section id="features" aria-labelledby="features-title" className="bg-canvas py-16 sm:py-24">
      <Wrap>
        <div className="mb-10 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between lg:gap-12">
          <div>
            <Eyebrow>What it does</Eyebrow>
            <SectionTitle id="features-title" className="mb-0">
              Everything a visit needs. <span className="text-accent">Nothing it doesn&apos;t.</span>
            </SectionTitle>
          </div>
          <p className="m-0 max-w-[400px] leading-[1.8] text-muted">
            One record follows the patient from the front desk to follow-up, whether they are seen
            in the room or from home.
          </p>
        </div>

        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 lg:gap-5">
          {FEATURES.map(({ icon, title, text }, i) => {
            const Icon = ICONS[icon];
            const indigo = i % 2 === 1;
            return (
              <li
                key={title}
                className="d-card flex flex-col rounded-2xl border border-line bg-white p-6 transition-[transform,box-shadow] duration-200 hover:-translate-y-1 hover:shadow-[0_18px_40px_rgba(10,42,33,0.08)]"
              >
                <div className="mb-6 flex items-center justify-between">
                  <span
                    className={cn(
                      "grid size-[52px] place-items-center rounded-[15px]",
                      indigo ? "bg-indigo-soft text-indigo" : "bg-accent-soft text-accent",
                    )}
                  >
                    <Icon aria-hidden className="size-6" />
                  </span>
                  <span aria-hidden className="font-mono text-xs font-medium tracking-widest text-line">
                    0{i + 1}
                  </span>
                </div>
                <h3 className="mb-2.5 font-display text-xl font-bold text-ink">{title}</h3>
                <p className="mb-5 flex-1 text-[15px] leading-[1.7] text-muted">{text}</p>
                <a
                  href="#demo"
                  aria-label={`Ask about ${title.toLowerCase()}`}
                  className="flex items-center justify-between border-t border-line pt-4 text-sm font-bold text-accent hover:text-accent-dark"
                >
                  Ask about this <ArrowUpRight aria-hidden className="size-4" />
                </a>
              </li>
            );
          })}
        </ul>
      </Wrap>
    </section>
  );
}
