import { cn } from "@/lib/utils";

/**
 * The Lafiya mark: a doorway (the clinic) with a person inside it.
 * "Lafiya" is Hausa for health and well-being.
 */
export function LogoMark({ className, inverted = false }: { className?: string; inverted?: boolean }) {
  const ground = inverted ? "#FFFFFF" : "#0B6E4F";
  const figure = inverted ? "#0B6E4F" : "#FFFFFF";
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className={cn("size-10 shrink-0", className)}>
      <rect width="48" height="48" rx="12" fill={ground} />
      <path
        d="M12 33 V22 a12 12 0 0 1 24 0 V33"
        fill="none"
        stroke={figure}
        strokeWidth="5"
        strokeLinecap="round"
      />
      <circle cx="24" cy="25" r="5" fill={figure} />
    </svg>
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
      <LogoMark inverted={tone === "light"} className={size === "sm" ? "size-8" : undefined} />
      <span className="grid leading-none">
        <span
          className={cn(
            "font-display font-bold tracking-tight",
            size === "sm" ? "text-[22px]" : "text-[26px]",
            tone === "light" ? "text-white" : "text-ink",
          )}
        >
          Lafiya
        </span>
        {tagline && (
          <span
            className={cn(
              "mt-1 text-[10px] font-bold uppercase tracking-[0.14em]",
              tone === "light" ? "text-white/60" : "text-muted",
            )}
          >
            Clinic care, online or not
          </span>
        )}
      </span>
    </span>
  );
}
