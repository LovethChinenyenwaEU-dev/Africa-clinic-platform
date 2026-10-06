import type { ReactNode } from "react";

export const metadata = {
  title: "Clinic Platform",
  description: "Offline-first clinic management and telemedicine",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
