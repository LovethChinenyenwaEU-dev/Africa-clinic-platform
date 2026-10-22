import { ArrowRight } from "lucide-react";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";

import { FAQS } from "./content";
import { Eyebrow, SectionTitle, Wrap } from "./Eyebrow";

export function Faq() {
  return (
    <section id="faq" aria-labelledby="faq-title" className="bg-canvas py-16 sm:py-24">
      <Wrap className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:gap-24">
        <div>
          <Eyebrow>Good questions</Eyebrow>
          <SectionTitle id="faq-title">
            What clinics ask us <span className="text-accent">first.</span>
          </SectionTitle>
          <p className="mb-6 leading-[1.8] text-muted">
            The short answers to what clinic owners, doctors and nurses usually want to know.
          </p>
          <Button asChild variant="link">
            <a href="#contact">
              Another question? Contact us <ArrowRight aria-hidden className="size-4" />
            </a>
          </Button>
        </div>
        <Accordion type="single" collapsible defaultValue="faq-0" className="border-t border-line">
          {FAQS.map(({ question, answer }, i) => (
            <AccordionItem key={question} value={`faq-${i}`}>
              <AccordionTrigger className="text-base">{question}</AccordionTrigger>
              <AccordionContent>{answer}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </Wrap>
    </section>
  );
}
