import type { Metadata } from "next";
// The same fonts and icons as before (Poppins, Raleway, Roboto, Font Awesome 6.5.2), served
// from this app instead of Google Fonts and a CDN, so the page works offline and the build
// never depends on those sites.
import "@fontsource/poppins/400.css";
import "@fontsource/poppins/500.css";
import "@fontsource/poppins/600.css";
import "@fontsource/poppins/700.css";
import "@fontsource/poppins/800.css";
import "@fontsource/raleway/400.css";
import "@fontsource/raleway/500.css";
import "@fontsource/raleway/600.css";
import "@fontsource/raleway/700.css";
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto/700.css";
import "@fortawesome/fontawesome-free/css/all.min.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "AfriPeak Health | Connected care, built for Africa",
  description: "A thoughtfully designed clinic platform for connected workflows, patient records and remote care, starting in Nigeria.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-theme="light"><body>{children}</body></html>;
}
