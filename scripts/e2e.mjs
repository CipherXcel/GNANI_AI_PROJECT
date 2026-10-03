// Real provider integration check using synthetic, non-private test audio.
import fs from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const base=process.env.APP_URL||'http://localhost:3000';
let cookie='';
async function api(route,method='GET',body){
  const response=await fetch(base+'/api'+route,{method,headers:{'content-type':'application/json',cookie},body:body?JSON.stringify(body):undefined});
  const set=response.headers.get('set-cookie');if(set)cookie=set.split(';')[0];
  const data=response.status===204?null:await response.json();
  if(!response.ok)throw new Error(JSON.stringify({status:response.status,detail:data?.detail}));
  return data;
}
const config=await api('/config');
if(!config.worker_online)throw new Error('The background worker is offline');
console.log('Services online. Uploading synthetic test audio.');
let upload;
if(process.argv.includes('--resume')){
 const session=JSON.parse(await fs.readFile(path.join(root,'.runtime/e2e-session.json'),'utf8'));
 cookie=session.cookie;upload={id:session.noteId};
 const note=await api(`/notes/${upload.id}`);
 if(note.status==='failed')await api(`/notes/${upload.id}/retry`,'POST');
}else{
 const content=await fs.readFile(path.join(root,'.runtime/test-recording.wav'));
 upload=await api('/uploads','POST',{filename:'community-garden-test.wav',title:'Community garden — integration test',size:content.length,language:'en-IN',content_type:'audio/wav'});
 for(let part=1;part<=upload.part_count;part++){
   const {url}=await api(`/uploads/${upload.id}/parts/${part}`);
   const response=await fetch(url,{method:'PUT',body:content.subarray((part-1)*upload.part_size,part*upload.part_size)});
   if(!response.ok)throw new Error('Storage upload failed: '+response.status);
 }
 await api(`/uploads/${upload.id}/complete`,'POST');
 await fs.writeFile(path.join(root,'.runtime/e2e-session.json'),JSON.stringify({cookie,noteId:upload.id}));
}
let previous='';
for(let poll=0;poll<180;poll++){
  const note=await api(`/notes/${upload.id}`);
  const stage=`${note.status}: ${note.progress}% — ${note.stage_message}`;
  if(stage!==previous){console.log(stage);previous=stage;}
  if(note.status==='failed')throw new Error(note.error);
  if(note.status==='ready'){
    if(note.duration<120)throw new Error('Test audio should be at least two minutes');
    if(!note.transcript||!note.summary?.overview||note.segments.length<4)throw new Error('Missing transcript, summary, or chunks');
    const result={id:note.id,duration:note.duration,chunks:note.segments.length,transcriptCharacters:note.transcript.length,summary:note.summary};
    await fs.writeFile(path.join(root,'.runtime/e2e-result.json'),JSON.stringify(result,null,2));
    console.log('PASS: real audio → Gnani transcript → Gemini summary → saved history');
    console.log(JSON.stringify({duration:note.duration,chunks:note.segments.length,transcriptCharacters:note.transcript.length,summaryCharacters:note.summary.overview.length}));
    process.exit(0);
  }
  await new Promise(r=>setTimeout(r,5000));
}
throw new Error('Processing did not finish within the integration-test deadline');
