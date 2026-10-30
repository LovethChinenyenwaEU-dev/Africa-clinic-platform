import { Activity } from "lucide-react";

import { cn } from "@/lib/utils";

/*
 * The AfriPeak Health brand, as on the landing page (landing/app/page.tsx): a pulse
 * line in a soft green rounded square, the name in Poppins with "Health" in teal,
 * and a line of small capitals under it.
 */
export function LogoMark({ className, inverted = false }: { className?: string; inverted?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid size-11 shrink-0 place-items-center rounded-[14px]",
        inverted ? "bg-white/10 text-[#9bd3b7]" : "bg-accent-soft text-accent",
        className,
      )}
    >
      <Activity className="size-6" />
    </span>
  );
}

export function Logo({
  className,
  tone = "dark",
  tagline = false,
  size = "md",
}: {
  className?: string;
  tone?: "dark" | "light";
  tagline?: boolean;
  size?: "sm" | "md";
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark inverted={tone === "light"} className={size === "sm" ? "size-9 [&_svg]:size-5" : undefined} />
      <span className="grid leading-none">
        <span
          className={cn(
            "font-display font-extrabold tracking-[-0.045em]",
            size === "sm" ? "text-[21px]" : "text-[26px]",
            tone === "light" ? "text-white" : "text-accent-dark",
          )}
        >
          AfriPeak<span className="text-teal"> Health</span>
        </span>
        {tagline && (
          <span
            className={cn(
              "mt-1.5 text-[8px] font-bold uppercase tracking-[0.14em]",
              tone === "light" ? "text-white/60" : "text-[#8196a5]",
            )}
          >
            Connected care, built for Africa
          </span>
        )}
      </span>
    </span>
  );
}
