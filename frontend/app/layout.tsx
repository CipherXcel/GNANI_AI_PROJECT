import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "Suno — Audio, made useful",
  description: "Turn recordings into searchable transcripts, clear summaries, and useful takeaways with Gnani and Gemini.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}<Toaster richColors position="bottom-right" /></body></html>;
}
