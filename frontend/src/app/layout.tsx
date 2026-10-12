import type { ReactNode } from "react";

import "./globals.css";
import { Providers } from "./providers";

export const metadata = {
  title: "Clinic Platform",
  description: "Offline-first clinic management and telemedicine",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}