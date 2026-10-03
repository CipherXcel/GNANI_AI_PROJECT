"use client";
import Link from "next/link";
import {usePathname} from "next/navigation";
import { AudioLines, Library, Workflow, Headphones, Plus, ShieldCheck } from "lucide-react";

export function Shell({ children, onUpload }: { children: React.ReactNode; onUpload?: () => void }) {
  const pathname = usePathname();
  return <div className="app-shell">
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="Suno home"><span className="brand-icon"><AudioLines size={23}/></span><span>suno<span className="brand-period">.</span></span></Link>
      <span className="workspace-label">YOUR WORKSPACE</span>
      <nav aria-label="Main navigation">
        <Link className={`nav-item ${pathname === "/" || pathname.startsWith("/notes/") ? "active" : ""}`} href="/"><Library size={19}/>Audio library</Link>
        <Link className={`nav-item ${pathname === "/architecture" ? "active" : ""}`} href="/architecture"><Workflow size={19}/>Architecture</Link>
      </nav>
      {onUpload ? <button className="sidebar-upload" onClick={onUpload}><Plus size={18}/>New recording</button> : <Link className="sidebar-upload" href="/?upload=1"><Plus size={18}/>New recording</Link>}
      <div className="sidebar-bottom"><div className="sidebar-note"><Headphones size={22}/><strong>A little less listening.<br/>A lot more clarity.</strong><p>Your recordings, with the useful bits pulled out.</p></div><div className="workspace-person"><span className="avatar">Y</span><div><strong>Personal workspace</strong><span><ShieldCheck size={12}/>Private to this browser</span></div></div></div>
    </aside>
    <div className="main-area"><header className="topbar"><div><span className="topbar-home">Workspace</span><span className="slash">/</span><span>{pathname === "/architecture" ? "Architecture" : pathname.startsWith("/notes/") ? "Recording" : "Audio library"}</span></div><span className="powered"><AudioLines size={15}/>Powered by Gnani</span></header>{children}</div>
  </div>;
}
