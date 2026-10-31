import {useEffect,useRef,useState} from 'react'
import {Mic,Square,Volume2,LoaderCircle,Search} from 'lucide-react'
import type {components} from './generated/api'
type Models=components['schemas']
type Api=<T>(path:string,options?:RequestInit)=>Promise<T>

function pcmWav(chunks:Float32Array[],rate:number){
  const input=new Float32Array(chunks.reduce((sum,c)=>sum+c.length,0));let at=0
  for(const chunk of chunks){input.set(chunk,at);at+=chunk.length}
  const count=Math.min(25*16000,Math.floor(input.length*16000/rate));const data=new ArrayBuffer(44+count*2);const view=new DataView(data)
  const word=(offset:number,value:string)=>[...value].forEach((char,i)=>view.setUint8(offset+i,char.charCodeAt(0)))
  word(0,'RIFF');view.setUint32(4,36+count*2,true);word(8,'WAVE');word(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);word(36,'data');view.setUint32(40,count*2,true)
  for(let i=0;i<count;i++){const position=i*rate/16000;const n=Math.floor(position);const sample=(input[n]??0)*(1-(position-n))+(input[n+1]??0)*(position-n);view.setInt16(44+i*2,Math.max(-1,Math.min(1,sample))*32767,true)}
  return new Blob([data],{type:'audio/wav'})
}

export function VoiceSearch({api,onSearch}:{api:Api;onSearch:(query:string,examId?:string)=>void}){
  const [recording,setRecording]=useState(false),[seconds,setSeconds]=useState(0),[clip,setClip]=useState<Blob|null>(null),[result,setResult]=useState<Models['VoiceSearchResult']|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  const stopRef=useRef<(()=>void)|null>(null),alive=useRef(true)
  const [preparing,setPreparing]=useState(false)
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;stopRef.current?.()}},[])
  async function record(){setError('');setResult(null);setClip(null);setPreparing(true)
    let stream:MediaStream|undefined,context:AudioContext|undefined
    const release=()=>{stream?.getTracks().forEach(track=>track.stop());void context?.close().catch(()=>{})}
    try{
      stream=await navigator.mediaDevices.getUserMedia({audio:true})
      if(!alive.current){release();return}
      const activeContext=new AudioContext();context=activeContext;await activeContext.resume()
      if(!alive.current){release();return}
      const source=activeContext.createMediaStreamSource(stream),processor=activeContext.createScriptProcessor(4096,1,1),chunks:Float32Array[]=[]
      processor.onaudioprocess=event=>chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)))
      source.connect(processor);processor.connect(activeContext.destination)
      let active=true;const started=performance.now();const timer=window.setInterval(()=>{if(alive.current)setSeconds(Math.floor((performance.now()-started)/1000))},250)
      const timeout=window.setTimeout(()=>stopRef.current?.(),15000)
      stopRef.current=()=>{if(!active)return;active=false;window.clearInterval(timer);window.clearTimeout(timeout);processor.disconnect();source.disconnect();release();if(alive.current){setRecording(false);setClip(pcmWav(chunks,activeContext.sampleRate))}stopRef.current=null}
      setSeconds(0);setRecording(true)
    }catch{release();if(alive.current)setError('Microphone unavailable or permission declined. You can still type your search.')}
    finally{if(alive.current)setPreparing(false)}
  }
  async function transcribe(){if(!clip)return;setBusy(true);setError('');try{const form=new FormData();form.append('file',clip,'query.wav');setResult(await api<Models['VoiceSearchResult']>('/me/voice-search',{method:'POST',body:form}))}catch(reason){setError((reason as Error).message)}finally{setBusy(false)}}
  return <section className="voice-search"><div><span className="eyebrow">ACCESSIBLE SEARCH</span><h3>Say the exam you’re looking for.</h3><p>Up to 15 seconds. Your clip is sent to Sarvam only when you select Transcribe; recordings are not saved by NiyamPulse. Voice never follows an exam automatically.</p></div><div className="voice-controls"><button className="button secondary small" disabled={busy||preparing} onClick={()=>recording?stopRef.current?.():void record()}>{recording?<Square size={15}/>:<Mic size={15}/>} {recording?`Stop · ${seconds}s`:'Record search'}</button>{clip&&<button className="button primary small" disabled={busy} onClick={()=>void transcribe()}>{busy?<LoaderCircle className="spin" size={15}/>:<Mic size={15}/>}Transcribe with Sarvam</button>}</div>{error&&<p role="alert" className="voice-error">{error}</p>}{result&&<div className="voice-transcript"><span className="eyebrow">CHECK YOUR TRANSCRIPT · {result.language_code}</span><p>{result.transcript}</p><button className="text-button" onClick={()=>onSearch(result.transcript,result.exam_ids?.[0])}><Search size={15}/>Use this search</button></div>}</section>
}

export function NoticeNarration({api,path}:{api:Api;path:string}){
  const [audio,setAudio]=useState<Models['NoticeAudio']|null>(null),[url,setUrl]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  useEffect(()=>()=>{if(url)URL.revokeObjectURL(url)},[url])
  async function generate(){setBusy(true);setError('');try{const result=await api<Models['NoticeAudio']>(path,{method:'POST'});const raw=Uint8Array.from(atob(result.audio_base64),c=>c.charCodeAt(0));setUrl(URL.createObjectURL(new Blob([raw],{type:'audio/wav'})));setAudio(result)}catch(reason){setError((reason as Error).message)}finally{setBusy(false)}}
  return <section className="narration"><div className="section-head"><h4>Listen to this source-backed update</h4><button className="button secondary small" disabled={busy} onClick={()=>void generate()}>{busy?<LoaderCircle className="spin" size={15}/>:<Volume2 size={15}/>} {audio?'Load audio again':'Generate audio · Sarvam'}</button></div><p className="muted">Audio reads the reviewed summary. Check dates and requirements against the written update and official notice.</p>{error&&<p role="alert" className="voice-error">{error} The written overview remains available.</p>}{audio&&<><audio controls src={url} aria-label="Reviewed notice narration"/><span className="eyebrow">{audio.cache_hit?'CACHED AUDIO':'BULBUL V4 FLASH · GENERATED AUDIO'}</span><details><summary>Exact text sent for speech</summary><p>{audio.text}</p></details></>}</section>
}
