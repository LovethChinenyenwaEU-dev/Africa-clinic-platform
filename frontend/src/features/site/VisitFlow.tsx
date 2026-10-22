import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";

import { FLOW } from "./content";
import { Eyebrow, SectionTitle, Wrap } from "./Eyebrow";
import { ICONS } from "./icons";

export function VisitFlow() {
  return (
    <section
      id="flow"
      aria-labelledby="flow-title"
      className="relative overflow-hidden bg-deep py-16 text-white sm:py-24"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-72 -right-52 size-[480px] rounded-full border border-white/10 shadow-[0_0_0_55px_rgba(255,255,255,0.025),0_0_0_110px_rgba(255,255,255,0.02)]"
      />
      <Wrap className="relative grid items-center gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:gap-24">
        <div>
          <Eyebrow light>How a visit flows</Eyebrow>
          <SectionTitle id="flow-title" light>
            From the front desk to follow-up, in one record.
          </SectionTitle>
          <p className="mb-8 max-w-[400px] leading-[1.8] text-white/70">
            Each step is done by the person whose job it is, and each one is recorded, so the next
            person picks up exactly where the last one stopped.
          </p>
          <Button asChild variant="light" size="lg">
            <a href="#demo">
              Request a demo <ArrowRight aria-hidden className="size-4" />
            </a>
          </Button>
        </div>

        <ol className="border-t border-white/15">
          {FLOW.map(({ icon, step, who, text }, i) => {
            const Icon = ICONS[icon];
            return (
              <li key={step} className="flex items-center gap-4 border-b border-white/15 py-5">
                <span className="grid size-12 shrink-0 place-items-center rounded-[13px] bg-white/10 text-[#7fd8b6]">
                  <Icon aria-hidden className="size-6" />
                </span>
                <span className="flex-1">
                  <strong className="block text-base">
                    <span className="mr-2 font-mono text-sm font-medium text-[#7fd8b6]">{i + 1}.</span>
                    {step}
                  </strong>
                  <span className="mt-1 block text-sm text-white/65">{text}</span>
                </span>
                <span className="d-badge d-badge-outline hidden border-white/25 text-xs font-bold text-white/80 sm:inline-flex">
                  {who}
                </span>
              </li>
            );
          })}
        </ol>
      </Wrap>
    </section>
  );
}
