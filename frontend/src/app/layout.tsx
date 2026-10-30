import type { ReactNode } from "react";

// The AfriPeak Health fonts, the same as the landing page (landing/): Poppins for
// headings, Roboto for text, Raleway for the menu. Served from our own app (Fontsource
// packages), never fetched from Google: the build needs no network, and no browser
// contacts Google to show a page. IBM Plex Mono lines up amounts and numbers.
import "@fontsource/poppins/500.css";
import "@fontsource/poppins/600.css";
import "@fontsource/poppins/700.css";
import "@fontsource/poppins/800.css";
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto/700.css";
import "@fontsource/raleway/600.css";
import "@fontsource/raleway/700.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";

import "./globals.css";
import { Providers } from "./providers";

export const metadata = {
  title: "AfriPeak Health",
  description: "Connected clinic care, records and remote consultations, built for Africa",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="afripeak">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
