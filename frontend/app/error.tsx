"use client";
export default function ErrorPage({reset}:{error:Error;reset:()=>void}){return <main className="empty-state" style={{minHeight:"100vh"}}><h1>Something interrupted this page.</h1><p>Your saved recordings are still in your workspace.</p><button className="button primary" onClick={reset}>Try again</button></main>;}
