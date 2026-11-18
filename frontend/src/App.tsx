import { useState } from "react";
import { ArrowUpRight, BadgeCheck, FileText, Globe2, HelpCircle, LockKeyhole, ShieldCheck, Wallet } from "lucide-react";

type Language = "en" | "am";
const content = {
  en: { eyebrow: "YOUR DIGITAL SERVICE DESK", title: "Identity services,", accent: "made simpler.", description: "A secure place to access supported Fayda services, manage requests, and track your activity.", explore: "Explore services", notice: "Foundation preview", noticeText: "Official identity services will appear here after authorized integration is configured.", services: "Your services", names: ["Identity verification", "Document services", "Wallet & payments", "Help center"], details: ["Secure, authorized verification flow", "Available services and request history", "Transparent fees and transaction receipts", "Guides, support, and frequently asked questions"], privacy: "Privacy-first by design", privacyText: "Your data should only be processed for a clear, authorized purpose." },
  am: { eyebrow: "የዲጂታል አገልግሎት ማዕከልዎ", title: "የመታወቂያ አገልግሎቶች፣", accent: "በቀላሉ።", description: "የተፈቀዱ የፋይዳ አገልግሎቶችን ለማግኘት፣ ጥያቄዎችን ለማስተዳደር እና እንቅስቃሴዎን ለመከታተል የተዘጋጀ ደህንነቱ የተጠበቀ መድረክ።", explore: "አገልግሎቶችን ይመልከቱ", notice: "የመጀመሪያ ቅድመ እይታ", noticeText: "ይፋዊ የመታወቂያ አገልግሎቶች የሚታዩት የተፈቀደ ግንኙነት ከተዘጋጀ በኋላ ነው።", services: "አገልግሎቶችዎ", names: ["የመታወቂያ ማረጋገጫ", "የሰነድ አገልግሎቶች", "ቦርሳ እና ክፍያዎች", "የእገዛ ማዕከል"], details: ["ደህንነቱ የተጠበቀ እና የተፈቀደ ሂደት", "የሚገኙ አገልግሎቶች እና የጥያቄ ታሪክ", "ግልጽ ክፍያዎች እና ደረሰኞች", "መመሪያዎች፣ ድጋፍ እና ተደጋጋሚ ጥያቄዎች"], privacy: "ግላዊነትን በመጀመሪያ", privacyText: "መረጃዎ ለግልጽ እና ለተፈቀደ ዓላማ ብቻ መሰራት አለበት።" }
};
const icons = [BadgeCheck, FileText, Wallet, HelpCircle];

export default function App() {
  const [lang, setLang] = useState<Language>("en");
  const t = content[lang];
  return <main className="shell">
    <header className="topbar"><a className="brand" href="#"><span className="brand-icon"><ShieldCheck size={21}/></span>FAYDA<span className="brand-muted">.ID</span></a><button className="lang" onClick={() => setLang(lang === "en" ? "am" : "en")}><Globe2 size={16}/>{lang === "en" ? "አማ" : "EN"}</button></header>
    <section className="hero"><div><div className="eyebrow"><i/> {t.eyebrow}</div><h1>{t.title}<br/><span>{t.accent}</span></h1><p className="intro">{t.description}</p><a className="cta" href="#services">{t.explore}<ArrowUpRight size={18}/></a><div className="trust"><LockKeyhole size={14}/>{t.privacy}</div></div><div className="visual"><div className="ring ring-one"/><div className="ring ring-two"/><div className="core"><ShieldCheck size={55}/></div><span className="float-tag tag-top">✦ SECURE</span><span className="float-tag tag-bottom"><i/> DIGITAL SERVICES</span></div></section>
    <section className="notice"><span className="notice-icon"><LockKeyhole size={19}/></span><div><strong>{t.notice}</strong><p>{t.noticeText}</p></div></section>
    <section id="services" className="services"><div className="section-head"><div><small>FAYDA PLATFORM</small><h2>{t.services}</h2></div><span>04 MODULES</span></div><div className="grid">{t.names.map((name, i) => { const Icon = icons[i]; return <article className="service" key={name}><span className={`service-icon icon-${i}`}><Icon size={21}/></span><div><h3>{name}</h3><p>{t.details[i]}</p></div><ArrowUpRight className="arrow" size={16}/><b>0{i + 1}</b></article>; })}</div></section>
    <footer><span className="footer-icon"><ShieldCheck size={17}/></span><div><strong>{t.privacy}</strong><p>{t.privacyText}</p></div><small>V 0.1.0</small></footer>
  </main>;
}
