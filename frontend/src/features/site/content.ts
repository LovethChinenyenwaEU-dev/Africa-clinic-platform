// Every word and picture on the public site, in one place, so it can be
// checked by tests and changed without touching the layout.

/**
 * A placeholder photo from Unsplash. The keywords are in the address only to
 * say what the photo should show; swap the ID for the real photo later.
 */
export function unsplash(id: string, keywords: string, width = 1200): string {
  const params = new URLSearchParams({
    auto: "format",
    fit: "crop",
    w: String(width),
    q: "80",
    keywords,
  });
  return `https://images.unsplash.com/photo-${id}?${params.toString()}`;
}

export type Photo = { src: string; alt: string };

export const PHOTOS = {
  hero: {
    src: unsplash("1576091160399-112ba8d25d1d", "african-doctor-stethoscope-phone", 1100),
    alt: "A clinician with a stethoscope checks a phone",
  },
  about: {
    src: unsplash("1631558554184-319c88f4f8a4", "doctor-listening-patient-clinic", 1000),
    alt: "A doctor listens to a patient's chest with a stethoscope",
  },
} satisfies Record<string, Photo>;

export const CONTACT = {
  // Placeholders until the real ones are chosen.
  email: "hello@lafiya.example",
  phone: "+234 800 000 0000",
  phoneHref: "tel:+2348000000000",
};

export const NAV = [
  { label: "Features", href: "#features" },
  { label: "How it works", href: "#flow" },
  { label: "Who it's for", href: "#roles" },
  { label: "Questions", href: "#faq" },
  { label: "Contact", href: "#contact" },
] as const;

/** Every section id on the page, in order. Nav links must point at one of these. */
export const SECTION_IDS = ["top", "about", "features", "flow", "demo", "roles", "faq", "contact"] as const;

export type IconName =
  | "wifi-off"
  | "siren"
  | "video"
  | "smartphone"
  | "user-plus"
  | "pill"
  | "send"
  | "file-check"
  | "clipboard"
  | "stethoscope"
  | "heart-pulse"
  | "calendar";

export const HIGHLIGHTS: { icon: IconName; title: string; text: string }[] = [
  { icon: "wifi-off", title: "Works offline", text: "Saves first, syncs later" },
  { icon: "siren", title: "Triage first", text: "Danger signs go to the top" },
  { icon: "video", title: "Remote care", text: "Video, audio or text" },
  { icon: "smartphone", title: "Patient page", text: "SMS code, no app to install" },
];

export const FEATURES: { icon: IconName; title: string; text: string }[] = [
  {
    icon: "user-plus",
    title: "Patient records",
    text: "Register patients, record allergies and problems, and catch a likely duplicate before it is created.",
  },
  {
    icon: "siren",
    title: "Triage queue",
    text: "Twelve danger signs move the sickest patients to the top, so they are seen first.",
  },
  {
    icon: "pill",
    title: "Prescriptions",
    text: "Doctors prescribe with a structured dose. Stopping a medicine keeps its history.",
  },
  {
    icon: "video",
    title: "Remote consultations",
    text: "Video, audio or text on the same record. Step down to audio when the connection drops.",
  },
  {
    icon: "send",
    title: "Referrals and follow-ups",
    text: "Print a referral letter in one click. The front desk sees who is due back.",
  },
  {
    icon: "file-check",
    title: "Visit summaries",
    text: "Written by the clinician, approved after sign-off, then shown on the patient's own page.",
  },
];

export const FLOW: { icon: IconName; step: string; who: string; text: string }[] = [
  { icon: "clipboard", step: "Register and book", who: "Front desk", text: "New or returning, in person or remote" },
  { icon: "heart-pulse", step: "Vitals and triage", who: "Nurse", text: "Danger signs push the patient up the queue" },
  { icon: "stethoscope", step: "Consult, in the room or remote", who: "Doctor", text: "Notes, prescriptions and referrals" },
  { icon: "calendar", step: "Summary and follow-up", who: "Doctor and front desk", text: "Approved summary, next visit booked" },
];

export const ROLES: { title: string; text: string; photo: Photo }[] = [
  {
    title: "Front desk",
    text: "Registers, books and checks in. Sees who is waiting and who is due back.",
    photo: {
      src: unsplash("1519494026892-80bbd2d6fd0d", "clinic-reception-front-desk", 700),
      alt: "A clinic reception desk",
    },
  },
  {
    title: "Nurses",
    text: "Take vitals and triage. Everything saves on the tablet, even offline.",
    photo: {
      src: unsplash("1666887360921-85952a86894f", "african-nurse-scrubs-stethoscope", 700),
      alt: "A nurse in blue scrubs with a stethoscope",
    },
  },
  {
    title: "Doctors",
    text: "Examine, prescribe and refer, in the room or by video, audio or text.",
    photo: {
      src: unsplash("1678695972687-033fa0bdbac9", "african-woman-doctor-white-coat", 700),
      alt: "A doctor in a white coat with a stethoscope",
    },
  },
  {
    title: "Patients",
    text: "Sign in with their phone and a code by SMS to see visits and book remote care.",
    photo: {
      src: unsplash("1686723726446-8b881f37ce62", "african-woman-talking-on-phone", 700),
      alt: "A woman talks on her mobile phone",
    },
  },
];

export const FAQS: { question: string; answer: string }[] = [
  {
    question: "What happens when the internet goes down?",
    answer:
      "Staff keep working. New entries are saved on the device and sent when the network returns. If two people changed the same record, Lafiya keeps both versions and asks a person to choose.",
  },
  {
    question: "Do patients need to install an app?",
    answer:
      "No. Each clinic has its own patient web page. Patients sign in with their phone number, date of birth and a code sent by SMS.",
  },
  {
    question: "What if a video call keeps dropping?",
    answer:
      "Switch the consultation to audio or to text chat. The change is recorded with the visit, so the record shows how the patient was seen.",
  },
  {
    question: "Who can see a patient's record?",
    answer:
      "Only the staff of that clinic, and only the parts their role needs. Every view and every change is written to the audit log.",
  },
  {
    question: "Can patients book their own remote visit?",
    answer:
      "Yes, once they agree to remote care on their page. If their answers show a danger sign, the remote visit stops and they are told to come in.",
  },
];

export const COUNTRIES = ["Nigeria", "Ghana", "Kenya", "Rwanda", "Uganda", "South Africa", "Other"];

export const CLINIC_SIZES = ["1 to 5 staff", "6 to 20 staff", "21 to 50 staff", "More than 50 staff"];
