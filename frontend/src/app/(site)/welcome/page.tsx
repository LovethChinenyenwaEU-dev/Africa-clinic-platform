import { About } from "@/features/site/About";
import { ContactBand } from "@/features/site/ContactBand";
import { DemoRequest } from "@/features/site/DemoRequest";
import { Faq } from "@/features/site/Faq";
import { Features } from "@/features/site/Features";
import { Hero } from "@/features/site/Hero";
import { Highlights } from "@/features/site/Highlights";
import { Roles } from "@/features/site/Roles";
import { SiteFooter } from "@/features/site/SiteFooter";
import { SiteHeader } from "@/features/site/SiteHeader";
import { VisitFlow } from "@/features/site/VisitFlow";

export const metadata = {
  title: "Lafiya | Clinic care that keeps going when the network doesn't",
  description:
    "Offline-first clinic software for Africa: patient records, triage, prescriptions, remote consultations and a patient web page.",
};

// The public page about Lafiya. Nobody needs to be signed in to see it.
export default function WelcomePage() {
  return (
    <div className="bg-white">
      <SiteHeader />
      <main>
        <Hero />
        <Highlights />
        <About />
        <Features />
        <VisitFlow />
        <DemoRequest />
        <Roles />
        <Faq />
        <ContactBand />
      </main>
      <SiteFooter />
    </div>
  );
}
