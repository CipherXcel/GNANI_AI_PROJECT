import {NoteReader} from "@/components/note-reader";
export default async function RecordingPage({params}:{params:Promise<{id:string}>}){const {id}=await params;return <NoteReader id={id}/>;}
