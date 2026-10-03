import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
const BASE = process.env.BACKEND_URL;

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (!BASE) return NextResponse.json({ detail: "The audio service is not configured." }, { status: 503 });
  const { path } = await context.params;
  const url = `${BASE}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  for (const key of ["content-type", "cookie", "origin"]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  try {
    const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.text();
    if (body && body.length > 65536) return NextResponse.json({ detail: "Request too large." }, { status: 413 });
    const response = await fetch(url, { method: request.method, headers, body, cache: "no-store", signal: AbortSignal.timeout(30000), redirect: "manual" });
    const outgoing = new Headers({ "Cache-Control": "no-store", "Content-Type": response.headers.get("content-type") || "application/json" });
    for (const cookie of response.headers.getSetCookie()) outgoing.append("set-cookie", cookie);
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch {
    return NextResponse.json({ detail: "The audio service is temporarily unavailable. Your saved recordings are safe. Please try again." }, { status: 503 });
  }
}
export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };
