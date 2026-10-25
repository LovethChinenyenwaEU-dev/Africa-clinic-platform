"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { currentHref, type NavItem } from "./navigation";

export function StaffNav({ items }: { items: NavItem[] }) {
  const pathname = usePathname();
  const active = currentHref(pathname, items);

  return (
    <nav aria-label="Main">
      <ul className="flex flex-wrap gap-4">
        {items.map((item) => {
          const current = item.href === active;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={current ? "page" : undefined}
                className={current ? "font-semibold text-accent underline" : "hover:text-accent"}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
