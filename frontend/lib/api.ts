export type Note = {
  id: string; title: string; filename: string; language: string; size: number;
  status: string; progress: number; stage_message: string; duration: number | null;
  total_chunks: number; completed_chunks: number; error: string | null; error_stage: string | null;
  created_at: string; updated_at: string; has_summary: boolean;
  transcript?: string | null; summary?: {overview: string; key_points: string[]; action_items: string[]; topics: string[]} | null;
  segments?: {start: number; end: number; text: string; position: number}[];
};
export type Config = {languages: Record<string,string>; max_upload_bytes: number; gnani_configured: boolean; gemini_configured: boolean; worker_online: boolean; github_repo_url: string};
export const ACTIVE = ["queued", "preparing", "transcribing", "summarizing"];
export const LANGUAGES: Record<string,string> = {"en-IN":"English","hi-IN":"Hindi","bn-IN":"Bengali","gu-IN":"Gujarati","kn-IN":"Kannada","ml-IN":"Malayalam","mr-IN":"Marathi","pa-IN":"Punjabi","ta-IN":"Tamil","te-IN":"Telugu"};
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {credentials:"same-origin", cache:"no-store", ...options,
    headers: {"Content-Type":"application/json", ...options?.headers}});
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : "The request could not be completed. Please try again.");
  }
  return response.status === 204 ? undefined as T : response.json();
}
export function duration(seconds: number | null) {
  if (seconds === null) return "—";
  const mins = Math.floor(seconds / 60), secs = Math.floor(seconds % 60);
  return mins >= 60 ? `${Math.floor(mins/60)}:${String(mins%60).padStart(2,"0")}:${String(secs).padStart(2,"0")}` : `${mins}:${String(secs).padStart(2,"0")}`;
}
export function bytes(size: number) {return size >= 1024**3 ? `${(size/1024**3).toFixed(1)} GB` : size >= 1024**2 ? `${(size/1024**2).toFixed(1)} MB` : `${Math.max(1,Math.round(size/1024))} KB`;}
