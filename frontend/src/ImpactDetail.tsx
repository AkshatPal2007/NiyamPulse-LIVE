import {useState} from 'react'
import type {components} from './generated/api'
type Models=components['schemas']
export function ImpactDetail({match}:{match:Models['RecipientMatch']}){
  if(match.before==null||match.after==null)return null
  const changed=match.before!==match.after
  return <section className={'impact-detail '+(changed?'changed':'')}><span className="eyebrow">DETERMINISTIC ASSESSMENT · AT PUBLICATION</span><div className="impact-transition"><span className={'decision '+match.before.toLowerCase()}>{match.before}</span><span aria-hidden="true">→</span><span className={'decision '+match.after.toLowerCase()}>{match.after}</span><strong>{changed?'Overall status changed':'Overall status unchanged'}</strong></div><p>These are historical rule checks for your opted-in profile at publication. They are decision support, not official eligibility.</p><div className="rule-comparison">{[['Before',match.before_checks??[]],['After',match.after_checks??[]]].map(([label,checks])=><div key={String(label)}><h4>{String(label)}</h4>{(checks as Models['RuleCheck'][]).length?(checks as Models['RuleCheck'][]).map((check,index)=><details className="rule-check" key={check.rule_id+index}><summary><span>{check.rule_type.replaceAll('_',' ')}</span><span className={'decision '+check.status.toLowerCase()}>{check.status}</span></summary><dl><dt>Observed</dt><dd>{check.observed_value??'Not supplied'}</dd><dt>Required</dt><dd>{check.expected_value}</dd><dt>Reason</dt><dd>{check.reason_code}</dd></dl>{(check.evidence??[]).map((proof,i)=><blockquote key={i}><small>Source page {proof.page_number}</small>{proof.literal_quote}</blockquote>)}</details>):<p className="muted">Per-rule checks were not recorded on this historical alert.</p>}</div>)}</div></section>
}

const names:Record<Models['Topic'],string>={ALL:'All updates',REGISTRATION:'Registration',ELIGIBILITY:'Supported eligibility changes',EXAM_SCHEDULE:'Exam schedule',ADMIT_CARD:'Admit cards',ANSWER_KEY:'Answer keys',RESULTS:'Results',SYLLABUS:'Syllabus',OTHER:'Other announcements'}
export function SubscriptionTopics({value,onSave}:{value:Models['Topic'][];onSave:(topics:Models['Topic'][])=>Promise<void>}){
  const [selected,setSelected]=useState(value),[busy,setBusy]=useState(false),[error,setError]=useState('')
  function toggle(topic:Models['Topic']){if(topic==='ALL'){setSelected(['ALL']);return}const list=selected.filter(t=>t!=='ALL'&&t!==topic);if(!selected.includes(topic))list.push(topic);setSelected(list.length?list:['ALL'])}
  async function save(){setBusy(true);setError('');try{await onSave(selected)}catch(reason){setError((reason as Error).message)}finally{setBusy(false)}}
  return <details className="subscription-topics"><summary>Edit topics</summary><fieldset><legend>Receive updates about</legend>{Object.entries(names).map(([key,label])=><label className="checkbox-label" key={key}><input type="checkbox" checked={selected.includes(key as Models['Topic'])} onChange={()=>toggle(key as Models['Topic'])}/>{label}</label>)}</fieldset><button className="button secondary small" disabled={busy} onClick={()=>void save()}>Save topics</button>{error&&<p role="alert">{error}</p>}</details>
}
