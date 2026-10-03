import Link from "next/link";
export default function NotFound(){return <main className="empty-state" style={{minHeight:"100vh"}}><h1>This page isn’t here.</h1><p>Head back to your library to find a recording.</p><Link href="/" className="button primary">Open audio library</Link></main>;}
