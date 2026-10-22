import { ArrowRight, BadgeCheck } from "lucide-react";
import Image from "next/image";

import { ROLES } from "./content";
import { Eyebrow, SectionTitle, Wrap } from "./Eyebrow";

export function Roles() {
  return (
    <section id="roles" aria-labelledby="roles-title" className="bg-white py-16 sm:py-24">
      <Wrap>
        <div className="mb-10 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between lg:gap-12">
          <div>
            <Eyebrow>One platform, every role</Eyebrow>
            <SectionTitle id="roles-title" className="mb-0">
              The right screen for <span className="text-accent">every person.</span>
            </SectionTitle>
          </div>
          <p className="m-0 max-w-[400px] leading-[1.8] text-muted">
            People only see what their job needs, which keeps screens simple and records private.
          </p>
        </div>

        <ul className="grid grid-cols-2 gap-3 sm:gap-5 lg:grid-cols-4">
          {ROLES.map(({ title, text, photo }) => (
            <li key={title} className="group overflow-hidden rounded-2xl border border-line bg-white">
              <div className="relative h-[180px] overflow-hidden bg-accent-soft sm:h-[260px]">
                <Image
                  src={photo.src}
                  alt={photo.alt}
                  fill
                  sizes="(min-width: 1024px) 270px, 50vw"
                  className="object-cover object-top transition-transform duration-300 group-hover:scale-[1.04]"
                />
                <span className="absolute bottom-3 right-3 grid size-9 place-items-center rounded-[10px] bg-white text-accent shadow-[0_5px_16px_rgba(10,42,33,0.1)]">
                  <BadgeCheck aria-hidden className="size-[18px]" />
                </span>
              </div>
              <div className="p-4 sm:p-5">
                <h3 className="mb-1.5 font-display text-lg font-bold text-ink">{title}</h3>
                <p className="mb-4 text-sm leading-relaxed text-muted">{text}</p>
                <span aria-hidden className="mb-4 block h-0.5 w-8 bg-accent" />
                <a href="#demo" className="flex items-center justify-between text-sm font-bold text-accent">
                  See it in a demo <ArrowRight aria-hidden className="size-4" />
                </a>
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-5 text-xs text-muted">Photos are placeholders and will be replaced.</p>
      </Wrap>
    </section>
  );
}
