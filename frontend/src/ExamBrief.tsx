import {useEffect,useState} from 'react'
import type {components} from './generated/api'
type Models=components['schemas']
type Api=<T>(path:string,options?:RequestInit)=>Promise<T>
export function ExamBrief({api,cycle,query}:{api:Api;cycle?:string;query?:string}){
 const [data,setData]=useState<Models['PublicUpdatesResponse']|null>(null),[error,setError]=useState('')
 useEffect(()=>{let active=true;setData(null);setError('');api<Models['PublicUpdatesResponse']>('/me/notice-search?'+new URLSearchParams({...(cycle?{cycle_id:cycle}:{}),...(query?{q:query}:{})})).then(value=>{if(active)setData(value)}).catch(reason=>{if(active)setError((reason as Error).message)});return()=>{active=false}},[api,cycle,query])
 const updates=data?.updates??[]
 return <section className="panel exam-brief" aria-label={cycle?'Exam brief':'Notice search results'}>
  <header className="brief-heading"><div><span className="eyebrow">{cycle?'YOUR EXAM BRIEF':'FROM THE SOURCE DESK'}</span><h3>{cycle?'Dates & latest notices':'Your notice results'}</h3></div>{data&&<span className="brief-count">{data.total} {data.total===1?'notice':'notices'}</span>}</header>
  <p className="brief-caution">Reviewed sources, including notices published before you followed. Dates may have passed or been superseded.</p>
  {error?<p role="alert">{error}</p>:!data?<p className="muted">Finding reviewed notices…</p>:!updates.length?<div className="brief-empty"><h4>No verified match yet</h4><p>Try the exam name, year and session. We’ll show a deadline only when a reviewed official notice supports it.</p></div>:updates.map(item=><article className="brief-notice" key={item.update_id}>
   <div className="brief-meta"><span>{item.publisher}</span><span>Reviewed {new Date(item.published_at).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</span></div>
   <h4>{item.title}</h4>
   <div className="brief-summary">{item.summary_en.replace(/\n[ \t]*\n+/g,'\n')}</div>
   <div className="brief-notice-actions"><a href={item.source_url} target="_blank" rel="noopener noreferrer">Read official notice <span aria-hidden="true">↗</span></a></div>
   {!!item.evidence.length&&<details className="brief-evidence"><summary>View source excerpts <span>{item.evidence.length}</span></summary><div>{item.evidence.map((e,i)=><blockquote key={i}><small>PAGE {e.page_number}</small><pre>{e.literal_quote}</pre></blockquote>)}</div></details>}
  </article>)}
 </section>
}
