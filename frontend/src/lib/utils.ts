import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Join class names, letting a later Tailwind class beat an earlier one
 * ("px-4" then "px-6" gives "px-6"). The shadcn/ui components rely on it.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
