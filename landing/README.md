# AfriPeak Health — Landing Page

A responsive, product-focused landing page for AfriPeak Health, an Africa-first clinic management, telemedicine and longitudinal health-record platform concept.

## Run locally

Requirements: Node.js 18.17+ and npm.

```bash
npm install
npm run dev
```

Open http://localhost:3000.

For a production build:

```bash
npm run build
npm start
```

## What's included

- Next.js App Router and TypeScript setup
- AfriPeak Health branding and metadata
- Responsive navigation and mobile menu
- Product-style hero with an illustrative clinic dashboard preview built from HTML/CSS
- Platform feature cards, clinic workflow preview, product principles, FAQs and early-access interest form
- Interactive FAQ accordion and client-side form confirmation
- Original image assets retained in `public/images` for future use

## Important before deployment

- The early-access form is a front-end demo. It does not send or store submissions. Connect it to a trusted backend or form service before collecting real information.
- Dashboard and patient examples are illustrative mock data, not live clinic records or proof that the represented features are already implemented.
- Review all privacy, consent, security, clinical and business claims before publishing. The landing page does not certify regulatory compliance or production readiness.
- Google Fonts are loaded remotely; system fallbacks are defined for environments where the font service is unavailable.
