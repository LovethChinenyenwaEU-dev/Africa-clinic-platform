import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** The small capital label above a section heading. */
export function Eyebrow({ children, light = false }: { children: ReactNode; light?: boolean }) {
  return (
    <p
      className={cn(
        "mb-4 flex items-center gap-3 text-xs font-bold uppercase tracking-[0.16em]",
        light ? "text-[#7fd8b6]" : "text-accent",
      )}
    >
      <span aria-hidden className={cn("h-0.5 w-7", light ? "bg-[#7fd8b6]" : "bg-indigo")} />
      {children}
    </p>
  );
}

/** The width every section shares, with a 16px gutter on phones. */
export function Wrap({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-[1160px] px-4 sm:px-6", className)}>{children}</div>;
}

/** A section heading: big, tight, in the display font. */
export function SectionTitle({
  children,
  light = false,
  className,
  id,
}: {
  children: ReactNode;
  light?: boolean;
  className?: string;
  id?: string;
}) {
  return (
    <h2
      id={id}
      className={cn(
        "mb-5 font-display text-[34px] font-bold leading-[1.12] tracking-[-0.03em] sm:text-[42px]",
        light ? "text-white" : "text-ink",
        className,
      )}
    >
      {children}
    </h2>
  );
}
