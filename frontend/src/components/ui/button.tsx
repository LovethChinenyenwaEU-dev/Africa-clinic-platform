import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

// shadcn/ui Button, coloured with the AfriPeak Health tokens instead of shadcn's own variables.
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-[10px] font-bold transition-[background-color,color,border-color,transform] disabled:pointer-events-none disabled:opacity-60 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-accent text-white hover:-translate-y-px hover:bg-accent-dark",
        indigo: "bg-indigo text-white hover:-translate-y-px hover:bg-[#2d31a6]",
        outline: "border border-accent bg-transparent text-accent hover:bg-accent-soft",
        light: "bg-white text-deep hover:-translate-y-px hover:bg-accent-soft",
        ghost: "text-ink hover:bg-accent-soft",
        link: "px-0 text-accent hover:gap-3",
      },
      size: {
        default: "min-h-11 px-[18px] text-[15px]",
        sm: "min-h-9 px-3.5 text-sm",
        lg: "min-h-[54px] px-6 text-base",
        icon: "size-11",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return <Comp data-slot="button" className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}

export { Button, buttonVariants };
