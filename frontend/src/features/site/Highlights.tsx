import { HIGHLIGHTS } from "./content";
import { Wrap } from "./Eyebrow";
import { ICONS } from "./icons";

export function Highlights() {
  return (
    <section aria-label="At a glance" className="border-b border-line bg-white">
      <Wrap>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-6 py-7 lg:grid-cols-4">
          {HIGHLIGHTS.map(({ icon, title, text }) => {
            const Icon = ICONS[icon];
            return (
              <li
                key={title}
                className="flex items-center gap-3 lg:border-line lg:px-6 lg:first:pl-0 lg:[&:not(:last-child)]:border-r"
              >
                <span className="grid size-11 shrink-0 place-items-center rounded-[13px] bg-accent-soft text-accent">
                  <Icon aria-hidden className="size-[22px]" />
                </span>
                <span className="leading-snug">
                  <strong className="block text-[15px] text-ink">{title}</strong>
                  <span className="text-[13px] text-muted">{text}</span>
                </span>
              </li>
            );
          })}
        </ul>
      </Wrap>
    </section>
  );
}
