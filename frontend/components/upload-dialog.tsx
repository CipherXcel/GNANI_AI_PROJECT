"use client";
import { useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { AudioLines, Check, FileAudio, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";
import { api, bytes, Config, LANGUAGES } from "@/lib/api";

function putPart(url: string, blob: Blob, signal: AbortSignal, progress: (bytes: number) => void) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    signal.addEventListener("abort", abort, {once:true});
    xhr.open("PUT", url);
    xhr.timeout = 180000;
    xhr.upload.onprogress = event => progress(event.loaded);
    xhr.onload = () => {signal.removeEventListener("abort",abort); if(xhr.status >= 200 && xhr.status < 300)resolve();else reject(new Error("The audio storage service rejected this part. Please retry."));};
    xhr.onerror = () => {signal.removeEventListener("abort",abort); reject(new Error("The upload connection was interrupted. Check your internet connection."));};
    xhr.ontimeout = () => {signal.removeEventListener("abort",abort); reject(new Error("The audio upload timed out. Please try again."));};
    xhr.onabort = () => {signal.removeEventListener("abort",abort); reject(new DOMException("Upload cancelled","AbortError"));};
    if (signal.aborted) {reject(new DOMException("Upload cancelled","AbortError")); return;}
    xhr.send(blob);
  });
}

export function UploadDialog({open, onOpenChange, onUploaded, config}: {open:boolean; onOpenChange:(open:boolean)=>void; onUploaded:(id:string)=>void; config:Config|null}) {
  const [file,setFile]=useState<File|null>(null), [title,setTitle]=useState(""), [language,setLanguage]=useState("en-IN");
  const [busy,setBusy]=useState(false), [percent,setPercent]=useState(0), [error,setError]=useState(""), [dragging,setDragging]=useState(false);
  const fileInput=useRef<HTMLInputElement>(null), controller=useRef<AbortController|null>(null), activeId=useRef<string|null>(null);
  const selectFile=(candidate?:File)=>{
    if(!candidate)return;
    setError("");
    if(!/\.(wav|mp3|m4a|aac|flac|ogg|webm|opus|mp4|aiff)$/i.test(candidate.name)){setError("Choose a supported audio file such as MP3, WAV or M4A.");return;}
    if(!candidate.size){setError("This file is empty. Please choose a recording with audio.");return;}
    if(candidate.size>(config?.max_upload_bytes || 50*1024**3)){setError("This recording exceeds the configured upload limit.");return;}
    setFile(candidate);setTitle(candidate.name.replace(/\.[^.]+$/,"").slice(0,200));
  };
  async function upload(){
    if(!file || busy)return;
    setBusy(true);setError("");setPercent(0);
    const aborter=new AbortController();controller.current=aborter;
    let completed=false;
    try{
      const session=await api<{id:string;part_size:number;part_count:number}>("/uploads",{method:"POST",body:JSON.stringify({filename:file.name,size:file.size,title,language,content_type:file.type || "application/octet-stream"})});
      activeId.current=session.id;
      const loaded=new Array(session.part_count).fill(0);let next=0;
      const runners=Array.from({length:Math.min(3,session.part_count)},async()=>{
        while(next<session.part_count){
          const index=next++;
          const blob=file.slice(index*session.part_size,Math.min(file.size,(index+1)*session.part_size));
          for(let attempt=0;attempt<3;attempt++){
            if(aborter.signal.aborted)throw new DOMException("Upload cancelled","AbortError");
            try{
              const {url}=await api<{url:string}>(`/uploads/${session.id}/parts/${index+1}`,{signal:aborter.signal});
              await putPart(url,blob,aborter.signal,value=>{loaded[index]=value;setPercent(Math.min(99,Math.floor(loaded.reduce((a,b)=>a+b,0)/file.size*100)));});
              break;
            }catch(e){if(aborter.signal.aborted || attempt===2)throw e; await new Promise(r=>setTimeout(r,1000*(attempt+1)));}
          }
        }
      });
      // Settle every upload before cleanup, so no in-flight part races an abort.
      const results=await Promise.allSettled(runners);
      const failure=results.find(r=>r.status==="rejected");
      if(failure?.status==="rejected")throw failure.reason;
      // Completion is idempotent; retry once after a dropped response.
      try {await api(`/uploads/${session.id}/complete`,{method:"POST"});}
      catch {await api(`/uploads/${session.id}/complete`,{method:"POST"});}
      completed=true;setPercent(100);toast.success("Recording uploaded. We’re preparing your notes.");
      setFile(null);setTitle("");onOpenChange(false);onUploaded(session.id);
    }catch(e){
      if(e instanceof Error && e.name!=="AbortError")setError(e.message);
      else setError("Upload cancelled. You can choose a file and try again.");
    }finally{
      if(!completed && activeId.current)await api(`/notes/${activeId.current}`,{method:"DELETE"}).catch(()=>{});
      activeId.current=null;controller.current=null;setBusy(false);
    }
  }
  return <Dialog.Root open={open} onOpenChange={value=>{if(!busy){setError("");onOpenChange(value);}}}><Dialog.Portal><Dialog.Overlay className="modal-overlay"/><Dialog.Content className="upload-modal" aria-describedby="upload-description">
    <div className="modal-heading"><span className="upload-symbol"><AudioLines size={24}/></span><Dialog.Close className="icon-button" aria-label="Close upload"><X size={20}/></Dialog.Close></div>
    <Dialog.Title className="modal-title">Make something of your audio.</Dialog.Title><Dialog.Description id="upload-description">Upload a recording. Get the words, the highlights, and what matters.</Dialog.Description>
    <input ref={fileInput} type="file" className="sr-only" accept=".wav,.mp3,.m4a,.aac,.flac,.ogg,.webm,.opus,.mp4,.aiff" aria-label="Audio file" onChange={e=>selectFile(e.target.files?.[0])} disabled={busy}/>
    <button type="button" className={`dropzone ${dragging?"dragging":""} ${file?"has-file":""}`} disabled={busy} onClick={()=>fileInput.current?.click()} onDragOver={e=>{e.preventDefault();setDragging(true);}} onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();setDragging(false);if(!busy)selectFile(e.dataTransfer.files[0]);}}>
      {file?<><FileAudio size={30}/><strong>{file.name}</strong><span>{bytes(file.size)} · Click to change file</span></>:<><UploadCloud size={32}/><strong>Drop your audio here</strong><span>or click to browse your files</span><small>MP3, WAV, M4A, FLAC, OGG & more</small></>}
    </button>
    <div className="form-fields"><label>Recording title<input placeholder="Give your recording a name" value={title} onChange={e=>setTitle(e.target.value)} maxLength={200} disabled={busy}/></label><label>Spoken language<select value={language} onChange={e=>setLanguage(e.target.value)} disabled={busy}>{Object.entries(config?.languages || LANGUAGES).map(([code,name])=><option key={code} value={code}>{name}</option>)}</select></label></div>
    <p className="form-hint">Choose the main language in the audio. Long recordings are processed in the background.</p>
    {error&&<div role="alert" className="error-banner">{error}</div>}
    {busy&&<div className="upload-progress" aria-live="polite"><div><span>{percent<99?"Uploading audio…":"Saving your recording…"}</span><strong>{percent}%</strong></div><progress max={100} value={percent}/><p>Keep this tab open until the upload finishes.</p></div>}
    <div className="modal-footer"><span><Check size={15}/>Only visible in your workspace</span><button className="button primary" onClick={busy?()=>controller.current?.abort():upload} disabled={!file}>{busy?<><X size={16}/>Cancel upload</>:<><UploadCloud size={17}/>Upload & transcribe</>}</button></div>
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
