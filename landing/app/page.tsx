"use client";

import { useEffect, useState } from "react";
import { Activity, ArrowRight, ArrowUpRight, BadgeCheck, CalendarDays, Check, ChevronDown, Clock3, FlaskConical, HeartPulse, Hospital, Mail, MapPin, Menu, Microscope, Phone, Search, ShieldCheck, Stethoscope, Syringe, UsersRound, ClipboardCheck, CalendarCheck, X } from "lucide-react";

const services = [
  { icon: HeartPulse, title: "Connected care", desc: "Link patients, doctors, nurses and laboratory teams for more coordinated care." },
  { icon: Syringe, title: "Lab workflows", desc: "Support clearer diagnostic handoffs, result tracking and better-informed decisions." },
  { icon: Stethoscope, title: "Coordinated visits", desc: "Bring appointments, queues and follow-up into a simpler care journey." },
  { icon: CalendarCheck, title: "Appointment support", desc: "Make it easier to request visits and keep track of the next step in care." },
  { icon: FlaskConical, title: "Laboratory coordination", desc: "Help clinical and laboratory teams coordinate testing and communicate results." },
  { icon: ClipboardCheck, title: "Patient flow", desc: "Support clearer registration, triage and handoffs throughout a clinic visit." }
];
const doctors = [
  { name: "Clinic administrators", role: "Workflow and coordination", image: "/images/doctors/doctors-1.jpg" },
  { name: "Nurses and care teams", role: "Patient flow and triage", image: "/images/doctors/doctors-2.jpg" },
  { name: "Doctors and clinicians", role: "Clinical encounters", image: "/images/doctors/doctors-3.jpg" },
  { name: "Laboratory professionals", role: "Diagnostics and results", image: "/images/doctors/doctors-4.jpg" }
];
const faqs = [
  ["Is AfriPeak Health already connected to clinics?", "Not yet through this demo. The form is a frontend prototype and is not connected to a clinic booking system or backend."],
  ["Can it manage patient records and appointments?", "These are product goals. The prototype illustrates the intended direction; production workflows need to be implemented, tested and reviewed."],
  ["Will it work with unreliable internet?", "Low-connectivity support is a design priority, but offline behaviour must be implemented and tested before it can be promised."],
  ["How will patient information be protected?", "Privacy, consent and role-based access are important requirements. Do not enter real patient information into this demo."],
];
export default function Home() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("home");
  useEffect(() => {
    const sectionIds = ["home", "about", "services", "departments", "map-search", "contact"];
    const sections = sectionIds.map((id) => document.getElementById(id)).filter((section): section is HTMLElement => Boolean(section));
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) setActiveSection(visible.target.id);
    }, { rootMargin: "-18% 0px -62% 0px", threshold: [0, 0.1, 0.25, 0.5] });
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const [submitted, setSubmitted] = useState(false);
  const [mapQuery, setMapQuery] = useState("clinics and hospitals in Nigeria");
  const mapEmbedUrl = `https://www.google.com/maps?q=${encodeURIComponent(mapQuery || "clinics and hospitals in Nigeria")}&output=embed`;
  const mapSearchUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mapQuery || "clinics and hospitals in Nigeria")}`;
  return (
    <main>
      <div className="topbar"><div className="site-wrap topbar-inner"><div className="top-contact"><a href="mailto:hello@afripeak.health"><Mail size={14}/> hello@afripeak.health</a><a href="mailto:hello@afripeak.health"><Phone size={14}/> +234 800 000 0000</a></div><span className="top-note">Connected care, built for the realities of Africa</span></div></div>
      <header className="site-header"><div className="site-wrap nav-inner">
        <a className="brand" href="#home" aria-label="AfriPeak Health home"><span className="brand-mark"><Activity size={24}/></span><span>AfriPeak<span className="brand-dot"> Health</span><small>CONNECTED CARE, BUILT FOR AFRICA</small></span></a>
        <button className="menu-toggle btn btn-ghost btn-circle" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation">{menuOpen ? <X/> : <Menu/>}</button>
        <nav className={menuOpen ? "main-nav nav-open" : "main-nav"}>{[["Home","#home"],["About","#about"],["Services","#services"],["Workflows","#departments"],["Our clinics","#map-search"],["Contact","#contact"]].map(([label,href])=><a key={label} href={href} className={activeSection === href.slice(1) ? "nav-active" : ""} aria-current={activeSection === href.slice(1) ? "location" : undefined} onClick={()=>setMenuOpen(false)}>{label}</a>)}<a className="btn btn-primary mobile-appointment" href="#appointment" onClick={()=>setMenuOpen(false)}>Make an Appointment <CalendarDays size={17}/></a></nav>
        <a className="btn btn-primary nav-cta" href="#appointment">Make an Appointment <CalendarDays size={17}/></a>
      </div></header>
      <section id="home" className="hero-section hero-cover">
        <div className="hero-cover-overlay"></div>
        <div className="site-wrap hero-cover-inner">
          <div className="hero-copy hero-cover-copy">
            <h2 className="hero-title">Welcome to AfriPeak Health</h2>
            <p className="hero-lead">We make sure you stay connected for better healthcare.</p>
            <p className="hero-description">Connecting patients, clinicians and laboratory teams to make every step of care clearer, more coordinated and more accessible.</p>
          </div>
          <div className="hero-feature-row" aria-label="AfriPeak Health benefits">
            <article className="hero-feature-intro">
              <h2>Why Choose<br/>AfriPeak Health?</h2>
              <p>Care works better when patients, clinicians and laboratory teams can stay connected.</p>
              <a className="hero-feature-cta" href="#about">Learn More <ArrowRight size={17}/></a>
            </article>
            <article className="hero-feature-card">
              <span className="hero-feature-icon"><Activity size={34}/></span>
              <h3>Connected care</h3>
              <p>Keep the patient journey clearer across everyday care interactions.</p>
            </article>
            <article className="hero-feature-card">
              <span className="hero-feature-icon"><Microscope size={34}/></span>
              <h3>Lab workflows</h3>
              <p>Support better handoffs between clinical teams and diagnostics.</p>
            </article>
            <article className="hero-feature-card">
              <span className="hero-feature-icon"><CalendarDays size={34}/></span>
              <h3>Coordinated visits</h3>
              <p>Make appointments, queues and follow-up easier to navigate.</p>
            </article>
          </div>
        </div>
      </section>
      <section id="about" className="section-pad about-reference-section"><div className="site-wrap about-reference-grid"><div className="about-reference-image"><img src="/images/about.jpg" alt="A healthcare team of doctors and clinical professionals"/><a className="about-play" href="#about-details" aria-label="Explore AfriPeak Health"><span></span></a></div><div className="about-reference-copy" id="about-details"><h2>About Us</h2><p className="about-reference-intro">AfriPeak Health is being shaped around the people behind every visit. We want to help patients, clinicians and laboratory teams stay connected so care feels clearer and more coordinated.</p><div className="about-benefits"><article><span className="about-benefit-icon"><Syringe size={39}/><BadgeCheck size={20} className="benefit-check"/></span><div><h3>Connected information across every visit</h3><p>Help care teams keep relevant patient context easier to find and understand.</p></div></article><article><span className="about-benefit-icon"><Stethoscope size={43}/></span><div><h3>Workflows that support better coordination</h3><p>Bring appointments, queues and clinical handoffs into a clearer daily flow.</p></div></article><article><span className="about-benefit-icon"><HeartPulse size={43}/></span><div><h3>Patient-first care and follow-up</h3><p>Make next steps, follow-up and communication easier to navigate.</p></div></article></div></div></div></section>
      <section className="stats-strip"><div className="site-wrap stats-grid"><div><span className="stat-icon"><Activity/></span><strong>Clinics</strong><small>Care locations and teams</small></div><div><span className="stat-icon"><i className="fa-solid fa-user-doctor" aria-hidden="true"></i></span><strong>Doctors</strong><small>Clinicians supporting care</small></div><div><span className="stat-icon"><Hospital/></span><strong>Departments</strong><small>Connected care workflows</small></div><div><span className="stat-icon"><MapPin/></span><strong>Countries</strong><small>Built for African realities</small></div></div></section>
      <section id="services" className="section-pad services-section"><div className="site-wrap"><div className="services-heading"><h2>Services</h2><span className="services-heading-rule"><i></i></span><p>Explore the connected tools AfriPeak Health is designed to bring to everyday care.</p></div><div className="services-grid">{services.map(({icon:Icon,title,desc},i)=><article className={`service-card card ${i===2 ? "service-card-featured" : ""}`} key={title}><div className="service-icon-stack"><span className="service-icon-shadow"></span><span className="service-icon"><Icon size={30}/></span></div><h3>{title}</h3><p>{desc}</p><a href="#appointment" aria-label={`Ask about ${title}`} className="service-link">Learn more <ArrowUpRight size={17}/></a></article>)}</div></div></section>
      <section id="departments" className="department-section section-pad"><div className="site-wrap department-grid"><div><div className="eyebrow eyebrow-light">DESIGNED FOR REAL CLINIC DAYS</div><h2>One connected view<br/>of the care journey.</h2><p>From registration and triage to notes, results and follow-up, AfriPeak Health is designed to help teams see the next step more clearly.</p><a href="#appointment" className="btn btn-light">See how it works <ArrowRight size={17}/></a></div><div className="department-list">{["Clinical encounters","Remote consultations","General Medicine","Laboratory & Diagnostics"].map((d,i)=><a href="#appointment" key={d} className="department-row"><span className="dept-icon">{[<HeartPulse key="h"/>,<Activity key="a"/>,<Stethoscope key="s"/>,<Microscope key="m"/>][i]}</span><span><strong>{d}</strong><small>{["Connected patient information","Remote consultation workflows","Appointments and patient flow","Laboratory and diagnostic handoffs"][i]}</small></span><ArrowUpRight className="dept-arrow"/></a>)}</div></div></section>
      <section id="appointment" className="section-pad appointment-section"><div className="site-wrap appointment-grid"><div className="appointment-copy"><div className="eyebrow">LET’S CONNECT</div><h2>Let’s make room<br/>for <span>better care.</span></h2><p className="section-lead">Interested in shaping a more connected clinic workflow? Share your interest and help us understand what your team needs.</p><div className="appointment-points"><div><span><CalendarDays/></span><div><strong>Start a conversation</strong><small>Tell us about your clinic or care team.</small></div></div><div><span><Phone/></span><div><strong>Explore together</strong><small>Discuss the workflows that matter most.</small></div></div></div><div className="contact-mini"><MapPin size={18}/><span>Want to explore the idea? <a href="#contact">Contact the AfriPeak team</a></span></div></div><div className="appointment-card card"><div className="form-heading"><span className="form-icon"><CalendarDays/></span><div><h3>Register interest</h3><p>Tell us a little about your work.</p></div></div>{submitted ? <div className="success-state"><span><Check size={28}/></span><h3>Request ready!</h3><p>This demo form is working locally, but no request has been sent to a clinic. Connect it to your booking system or API to receive appointments.</p><button className="btn btn-primary" onClick={()=>setSubmitted(false)}>Submit another request</button></div> : <form onSubmit={(e)=>{e.preventDefault();setSubmitted(true)}} className="appointment-form"><div className="form-row"><label>Full name *<input className="input input-bordered" required placeholder="Your name"/></label><label>Work email *<input className="input input-bordered" required type="email" placeholder="you@yourclinic.com"/></label></div><div className="form-row"><label>Phone number<input className="input input-bordered" type="tel" placeholder="+1 (555) 000-0000"/></label><label>Clinic / organisation<input className="input input-bordered" type="text" placeholder="Clinic or organisation" required/></label></div><label>Your role *<select className="select select-bordered" required defaultValue=""><option value="" disabled>Choose your role</option><option>Clinical encounters</option><option>Remote consultations</option><option>General Medicine</option><option>Laboratory & Diagnostics</option><option>Connected care</option><option>Other / Not sure</option></select></label><label>What workflow would you improve?<textarea className="textarea textarea-bordered" rows={3} placeholder="Optional details about your clinic or team"/></label><button className="btn btn-primary submit-btn" type="submit">Register interest <ArrowRight size={18}/></button><p className="privacy-note"><ShieldCheck size={14}/> Demo form only. Connect a privacy-reviewed backend before collecting real details.</p></form>}</div></div></section>
      <section id="doctors" className="section-pad doctors-section"><div className="site-wrap"><div className="section-heading"><div><div className="eyebrow">PEOPLE AT THE CENTRE OF CARE</div><h2>Better tools. <span>More connected care.</span></h2></div><p>Technology should support the people doing the work. AfriPeak Health is being designed with clinic teams and patient needs in mind.</p></div><div className="doctors-grid">{doctors.map((d,i)=><article className="doctor-card card" key={d.name}><div className="doctor-image"><img src={d.image} alt={d.name}/><span className="doctor-badge"><BadgeCheck size={17}/></span></div><div className="doctor-info"><h3>{d.name}</h3><p>{d.role}</p><span className="doctor-rule"></span><a href="#appointment">Explore the platform <ArrowRight size={15}/></a></div></article>)}</div><p className="content-note">Illustrative audience groups, not customer or partner endorsements.</p></div></section>
      <section className="section-pad faq-section"><div className="site-wrap faq-grid"><div><div className="eyebrow">A FEW QUICK ANSWERS</div><h2>Questions? We’re<br/>glad you <span>asked.</span></h2><p>A few notes about the product direction and what the current demo represents.</p><a href="#contact" className="text-link">Still have a question? Contact us <ArrowRight size={16}/></a></div><div className="faq-list">{faqs.map(([q,a],i)=><div className={`faq-item ${openFaq===i?"faq-active":""}`} key={q}><button onClick={()=>setOpenFaq(openFaq===i?null:i)} aria-expanded={openFaq===i}><span>{q}</span><ChevronDown size={19}/></button>{openFaq===i&&<p>{a}</p>}</div>)}</div></div></section>
      <section id="contact" className="contact-section"><div className="site-wrap contact-grid"><div><div className="eyebrow eyebrow-light">LET’S BUILD WITH CARE TEAMS</div><h2>A more connected<br/>way to <span>care.</span></h2><p>Help us understand the everyday workflows AfriPeak Health should support first.</p></div><a className="contact-detail" href="mailto:hello@afripeak.health"><span><Phone/></span><small>CONTACT THE TEAM</small><strong>hello@afripeak.health</strong><ArrowUpRight/></a><a className="contact-detail" href="mailto:hello@afripeak.health"><span><Mail/></span><small>EMAIL THE TEAM</small><strong>hello@afripeak.health</strong><ArrowUpRight/></a></div></section>
      <section id="map-search" className="map-search-section section-pad"><div className="site-wrap"><div className="section-heading"><div><div className="eyebrow">FIND CARE NEAR YOU</div><h2>Search clinics and <span>health facilities.</span></h2></div><p>Search Google Maps for a clinic, hospital, laboratory or care facility. AfriPeak listings are not connected to this map demo yet.</p></div><form className="map-search-form" onSubmit={(e)=>{e.preventDefault(); window.open(mapSearchUrl, "_blank", "noopener,noreferrer");}}><Search size={20}/><input value={mapQuery} onChange={(e)=>setMapQuery(e.target.value)} aria-label="Search Google Maps" placeholder="Search a clinic, hospital, laboratory or location"/><button className="btn btn-primary" type="submit">Search map <ArrowUpRight size={17}/></button></form><div className="map-frame"><iframe title="Google Maps facility search" src={mapEmbedUrl} loading="lazy" referrerPolicy="no-referrer-when-downgrade" allowFullScreen/><a className="map-open-link" href={mapSearchUrl} target="_blank" rel="noreferrer">Open in Google Maps <ArrowUpRight size={15}/></a></div></div></section>
      <footer className="site-footer"><div className="site-wrap footer-main"><div className="footer-brand"><a className="brand brand-footer" href="#home"><span className="brand-mark"><Activity size={23}/></span><span>AfriPeak<span className="brand-dot"> Health</span><small>CONNECTED CARE, BUILT FOR AFRICA</small></span></a><p>Thoughtful technology for the people and teams who keep care moving.</p></div><div><h4>Explore</h4><a href="#about">About AfriPeak</a><a href="#services">The platform</a><a href="#departments">Workflows</a><a href="#doctors">For care teams</a><a href="#map-search">Find care on the map</a></div><div><h4>Get started</h4><a href="#appointment">Register interest</a><a href="#contact">Contact our team</a><a href="#home">Back to top ↑</a></div><div className="footer-note"><span><HeartPulse size={20}/></span><strong>Your health matters.</strong><p>Start with a question. We’ll help you find the next step.</p><a href="#appointment">Explore the platform <ArrowRight size={15}/></a></div></div><div className="site-wrap footer-bottom"><span>© {new Date().getFullYear()} AfriPeak Health. All rights reserved.</span><span>Product concept · Features subject to implementation and validation</span></div></footer>
    </main>
  );
}
