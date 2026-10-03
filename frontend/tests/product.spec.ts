import { test, expect, Page } from "@playwright/test";
import type { Note } from "../lib/api";

function fixture(id="ready", status="ready"):Note {
  return {id,title:id==="ready"?"Community garden planning":"Recording "+id,filename:"meeting-"+"long-file-name-".repeat(12)+".wav",language:"en-IN",size:32044,status,progress:status==="ready"?100:50,stage_message:"Transcribing section 2 of 3",duration:65,total_chunks:3,completed_chunks:3,error:status==="failed"?"Summary service unavailable. Your transcript is saved.":null,error_stage:status==="failed"?"summarizing":null,created_at:"2026-10-01T10:00:00Z",updated_at:"2026-10-01T10:01:00Z",has_summary:status==="ready",transcript:"We are planning a community garden. Maya will prepare the seed list by Friday.",summary:status==="ready"?{overview:"A calm and practical discussion about building the community garden. ".repeat(14),key_points:["Start with tomatoes, spinach and basil.","Keep the path accessible to everyone."],action_items:["Maya will prepare a seed list by Friday."],topics:["Community","Planning","Accessibility"]}:null,segments:[{position:0,start:0,end:30,text:"We are planning a community garden. ".repeat(15)},{position:1,start:29,end:59,text:"Maya will prepare the seed list by Friday."},{position:2,start:58,end:65,text:"Everyone will meet on Saturday."}]};
}
async function setup(page:Page, options:{failLibrary?:boolean;empty?:boolean}={}) {
  let notes=options.empty?[]:[fixture(),fixture("failed","failed"),fixture("queued","queued")];
  const wave=Buffer.alloc(32044);wave.write("RIFF");wave.writeUInt32LE(32036,4);wave.write("WAVEfmt ",8);wave.writeUInt32LE(16,16);wave.writeUInt16LE(1,20);wave.writeUInt16LE(1,22);wave.writeUInt32LE(16000,24);wave.writeUInt32LE(32000,28);wave.writeUInt16LE(2,32);wave.writeUInt16LE(16,34);wave.write("data",36);wave.writeUInt32LE(32000,40);
  await page.route("**/test-audio.wav",route=>route.fulfill({status:200,contentType:"audio/wav",body:wave}));
  await page.route("**/test-storage/**",route=>route.fulfill({status:200,headers:{ETag:'"fixture-etag"'},body:""}));
  await page.route("**/api/**",async route=>{
    const request=route.request(), url=new URL(request.url()), path=url.pathname, method=request.method();
    const send=(body:unknown,status=200)=>route.fulfill({status,contentType:"application/json",body:JSON.stringify(body)});
    if(path==="/api/config")return send({languages:{"en-IN":"English","hi-IN":"Hindi"},max_upload_bytes:53687091200,worker_online:true,gnani_configured:true,gemini_configured:true,github_repo_url:""});
    if(path==="/api/notes"){
      if(options.failLibrary)return send({detail:"The recording database is temporarily unavailable. Please try again."},503);
      const q=url.searchParams.get("q")||"", status=url.searchParams.get("status");
      const filtered=notes.filter(n=>n.title.toLowerCase().includes(q.toLowerCase())&&(!status||n.status===status));
      return send({notes:filtered,total:filtered.length,stats:{total:notes.length,ready:1,processing:1,duration:195}});
    }
    if(path==="/api/uploads"&&method==="POST"){
      const body=request.postDataJSON();notes.push({...fixture("uploaded"),title:body.title,filename:body.filename});
      return send({id:"uploaded",part_size:16777216,part_count:1},201);
    }
    if(path.includes("/parts/"))return send({url:new URL("/test-storage/part",url).href});
    if(path.endsWith("/complete"))return send({status:"queued"},202);
    const id=path.split("/")[3];const note=notes.find(n=>n.id===id);
    if(!note)return send({detail:"This recording was not found in your workspace."},404);
    if(path.endsWith("/audio"))return send({url:new URL("/test-audio.wav",url).href});
    if(path.endsWith("/retry")){note.status="queued";note.error_stage=null;return send(note,202);}
    if(method==="PATCH"){note.title=request.postDataJSON().title;return send(note);}
    if(method==="DELETE"){notes=notes.filter(n=>n.id!==id);return route.fulfill({status:204});}
    return send(note);
  });
}
async function noOverflow(page:Page) {
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
}

test("library search, filters, grid, responsive theme and upload dialog",async({page},testInfo)=>{
  const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));
  await setup(page);await page.goto("/");
  await expect(page.getByRole("heading",{name:"Community garden planning"})).toBeVisible();
  await page.screenshot({path:`../.runtime/library-${testInfo.project.name}.png`,fullPage:true});
  await expect(page.locator("body")).toHaveCSS("background-color","rgb(236, 250, 252)");
  await page.getByLabel("Search recordings").fill("not present");
  await expect(page.getByRole("heading",{name:"No recordings found"})).toBeVisible();
  await page.getByRole("button",{name:"Clear filters",exact:true}).click();
  await page.getByRole("button",{name:"Needs attention",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Recording failed"})).toBeVisible();
  await page.getByRole("button",{name:"All recordings",exact:true}).click();
  await page.getByRole("button",{name:"Grid view"}).click();
  await noOverflow(page);
  await page.getByRole("button",{name:"Upload audio",exact:true}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByLabel("Audio file",{exact:true}).setInputFiles({name:"empty.wav",mimeType:"audio/wav",buffer:Buffer.alloc(0)});
  await expect(page.locator(".error-banner[role=alert]")).toContainText("empty");
  await page.getByLabel("Audio file",{exact:true}).setInputFiles({name:"long-filename-".repeat(10)+".wav",mimeType:"audio/wav",buffer:Buffer.alloc(100)});
  await page.getByLabel("Spoken language").selectOption("hi-IN");
  await noOverflow(page);
  await page.keyboard.press("Escape");await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(errors).toEqual([]);
});

test("completed recording playback, transcript search, copy, export, rename and delete",async({page,context},testInfo)=>{
  await context.grantPermissions(["clipboard-read","clipboard-write"]);
  await setup(page);await page.goto("/notes/ready");
  await expect(page.getByText("The big picture",{exact:true})).toBeVisible();
  await expect(page.getByText("Maya will prepare a seed list by Friday.",{exact:true})).toBeVisible();
  await page.screenshot({path:`../.runtime/detail-${testInfo.project.name}.png`,fullPage:true});
  await page.getByLabel("Playback speed").selectOption("1.5");
  await page.getByRole("button",{name:"Play audio",exact:true}).click();
  await expect(page.locator("audio")).toHaveJSProperty("playbackRate",1.5);
  await page.getByRole("button",{name:"Copy summary"}).click();
  await expect(page.getByText("Copied to clipboard",{exact:true})).toBeVisible();
  await page.getByRole("tab",{name:/Transcript/}).click();
  await page.getByLabel("Find in transcript").fill("Maya");
  await expect(page.locator(".transcript-entry")).toHaveCount(1);
  await expect(page.locator("mark")).toHaveText("Maya");
  await page.getByRole("button",{name:"Copy transcript"}).click();
  const download=page.waitForEvent("download");
  await page.getByLabel("Download recording notes").selectOption("srt");
  expect((await download).suggestedFilename()).toContain(".srt");
  await page.getByRole("button",{name:"Rename",exact:true}).click();
  await page.getByLabel("Recording title",{exact:true}).fill("Garden " + "longtitle".repeat(18));
  await page.getByRole("button",{name:"Save title"}).click();
  await expect(page.getByRole("heading",{level:1})).toContainText("Garden longtitle");
  await noOverflow(page);
  await page.getByRole("button",{name:"Delete recording",exact:true}).click();
  await page.getByRole("button",{name:"Keep recording"}).click();
  await page.getByRole("button",{name:"Delete recording",exact:true}).click();
  await page.getByRole("alertdialog").getByRole("button",{name:"Delete recording",exact:true}).click();
  await expect(page).toHaveURL("/");
});

test("partial transcript and retry preserve useful output",async({page})=>{
  await setup(page);await page.goto("/notes/failed");
  await expect(page.getByText("Transcript saved. Summary needs another try.")).toBeVisible();
  await expect(page.getByRole("tab",{name:/Transcript/})).toHaveAttribute("data-state","active");
  await expect(page.locator(".transcript-entry")).toHaveCount(3);
  await noOverflow(page);
  await page.getByRole("button",{name:"Retry from saved progress"}).click();
  await expect(page.getByText("You can leave this page. Your recording keeps processing in the background.")).toBeVisible();
});

test("upload completes through the existing multipart UI",async({page})=>{
  await setup(page);await page.goto("/");await page.getByRole("button",{name:"Upload audio",exact:true}).click();
  await page.getByLabel("Audio file",{exact:true}).setInputFiles({name:"sample.wav",mimeType:"audio/wav",buffer:Buffer.alloc(100)});
  await page.getByRole("button",{name:"Upload & transcribe"}).click();
  await expect(page).toHaveURL("/notes/uploaded");await expect(page.getByRole("heading",{level:1})).toHaveText("sample");
});

test("empty, unavailable and architecture pages remain usable",async({page})=>{
  await setup(page,{empty:true});await page.goto("/");
  await expect(page.getByRole("heading",{name:"Your next idea belongs here."})).toBeVisible();
  await page.getByRole("link",{name:"Architecture",exact:true}).click();
  await expect(page.getByRole("heading",{level:1})).toHaveText("From sound to something useful.");
  await expect(page.getByText(/private AWS S3 bucket in both/)).toBeVisible();await noOverflow(page);
});

test("temporary backend failure and missing workspace record",async({page})=>{
  await setup(page,{failLibrary:true});await page.goto("/");
  await expect(page.locator(".error-banner[role=alert]")).toContainText("temporarily unavailable");
  await page.goto("/notes/missing");await expect(page.locator(".error-banner[role=alert]")).toContainText("not found in your workspace");
  await noOverflow(page);
});
