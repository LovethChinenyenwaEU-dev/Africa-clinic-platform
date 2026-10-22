"use client";

import { ArrowUpRight, Mail, Menu, Phone, WifiOff, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Logo } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { CONTACT, NAV } from "./content";
import { Wrap } from "./Eyebrow";

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <>
      <div className="bg-deep text-[13px] text-white/80">
        <Wrap className="flex h-10 items-center justify-between gap-4">
          <div className="flex gap-5">
            <a href={`mailto:${CONTACT.email}`} className="flex items-center gap-2 hover:text-white">
              <Mail aria-hidden className="size-3.5 text-[#7fd8b6]" />
              <span className="hidden sm:inline">{CONTACT.email}</span>
              <span className="sm:hidden">Email</span>
            </a>
            <a href={CONTACT.phoneHref} className="flex items-center gap-2 hover:text-white">
              <Phone aria-hidden className="size-3.5 text-[#7fd8b6]" />
              {CONTACT.phone}
            </a>
          </div>
          <span className="hidden items-center gap-2 md:flex">
            <WifiOff aria-hidden className="size-3.5 text-[#7fd8b6]" />
            Keeps working when the network doesn&apos;t
          </span>
        </Wrap>
      </div>

      <header className="sticky top-0 z-50 border-b border-line/70 bg-white/95 backdrop-blur">
        <Wrap className="relative flex h-[76px] items-center gap-6">
          <a href="#top" aria-label="Lafiya, back to the top" onClick={close}>
            <Logo tagline />
          </a>

          <nav
            id="site-menu"
            aria-label="Main"
            className={cn(
              "ml-auto text-[15px] font-bold text-muted",
              // phones: a panel under the bar, shown only when open
              "absolute inset-x-0 top-[76px] flex-col border-b border-line bg-white px-4 pb-4 shadow-lg",
              open ? "flex" : "hidden",
              // desktop: always a row
              "lg:static lg:flex lg:flex-row lg:items-center lg:gap-7 lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none",
            )}
          >
            {NAV.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={close}
                className="border-b border-line py-3 hover:text-accent last:border-0 lg:border-0 lg:py-0"
              >
                {item.label}
              </a>
            ))}
            <Link href="/login" className="py-3 text-accent lg:hidden">
              Staff sign in
            </Link>
          </nav>

          <div className="ml-auto flex items-center gap-2 lg:ml-0">
            <Button asChild variant="ghost" className="hidden lg:inline-flex">
              <Link href="/login">Staff sign in</Link>
            </Button>
            <Button asChild className="hidden sm:inline-flex">
              <a href="#demo">
                Request a demo <ArrowUpRight aria-hidden className="size-4" />
              </a>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              aria-expanded={open}
              aria-controls="site-menu"
              aria-label={open ? "Close the menu" : "Open the menu"}
              onClick={() => setOpen(!open)}
            >
              {open ? <X aria-hidden /> : <Menu aria-hidden />}
            </Button>
          </div>
        </Wrap>
      </header>
    </>
  );
}
