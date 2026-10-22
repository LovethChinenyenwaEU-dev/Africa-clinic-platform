import { Atkinson_Hyperlegible, Bricolage_Grotesque, IBM_Plex_Mono } from "next/font/google";
import type { ReactNode } from "react";

import "./globals.css";
import { Providers } from "./providers";

// The Lafiya fonts. Atkinson Hyperlegible was drawn for low vision readers,
// so it carries every word a person must read; Bricolage is only for headings.
const atkinson = Atkinson_Hyperlegible({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-atkinson",
  display: "swap",
});
const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  weight: ["500", "700"],
  variable: "--font-bricolage",
  display: "swap",
});
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata = {
  title: "Lafiya",
  description: "Offline-first clinic management and telemedicine",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      data-theme="lafiya"
      className={`${atkinson.variable} ${bricolage.variable} ${plexMono.variable}`}
    >
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
