import {useState,type FormEvent} from 'react'
import {CheckCircle2,KeyRound,LoaderCircle,LockKeyhole,LogOut,ShieldCheck} from 'lucide-react'
import type {components} from './generated/api'
type Models=components['schemas']
type Api=<T>(path:string,options?:RequestInit)=>Promise<T>

export function AccountSettings({session,profile,api,onSaved,onLogout}:{session:Models['AuthSession'];profile:Models['UserProfileV2'];api:Api;onSaved:(value:Models['UserProfileV2'])=>void;onLogout:()=>Promise<void>}) {
  const [name,setName]=useState(profile.display_name??'')
  const [language,setLanguage]=useState(profile.preferred_language)
  const [current,setCurrent]=useState('')
  const [next,setNext]=useState('')
  const [deletion,setDeletion]=useState(false)
  const [deletePassword,setDeletePassword]=useState('')
  const [confirmed,setConfirmed]=useState(false)
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState('')
  const [error,setError]=useState('')
  async function perform(action:()=>Promise<void>){setBusy(true);setError('');setMessage('');try{await action()}catch(reason){setError((reason as Error).message)}finally{setBusy(false)}}
  function save(event:FormEvent){event.preventDefault();void perform(async()=>{onSaved(await api<Models['UserProfileV2']>('/me/profile',{method:'PATCH',body:JSON.stringify({display_name:name,preferred_language:language})}));setMessage('Preferences saved.')})}
  function password(event:FormEvent){event.preventDefault();void perform(async()=>{await api('/auth/password',{method:'POST',body:JSON.stringify({current_password:current,new_password:next})});await onLogout()})}
  function remove(event:FormEvent){event.preventDefault();void perform(async()=>{await api('/me/account',{method:'DELETE',body:JSON.stringify({password:deletePassword})});await onLogout()})}
  return <div className="account-settings"><div className="verified-identity"><span className="account-avatar">{session.display_name.slice(0,2).toUpperCase()}</span><div><strong>{session.email}</strong><span><CheckCircle2 size={13}/>Email verified · {session.role==='ADMIN'?'Platform administrator':'Personal account'}</span></div></div><p className="muted"><LockKeyhole size={14}/> Your subscriptions need no marks, income or date of birth.</p>
    {error&&<div className="access-error" role="alert">{error}</div>}{message&&<div className="settings-success" role="status">{message}</div>}
    <form onSubmit={save}><h3>Your preferences</h3><label className="field-label">Display name<input value={name} required maxLength={80} autoComplete="name" onChange={e=>setName(e.target.value)}/></label><label className="field-label">Language for future alerts<select value={language} onChange={e=>setLanguage(e.target.value as Models['Language'])}><option value="en">English</option><option value="hi">हिंदी / Hindi</option></select></label><p className="muted">Hindi is used when a reviewed, source-backed summary is available. Previously delivered alerts stay unchanged.</p><button className="button primary small" disabled={busy}>{busy?<LoaderCircle className="spin" size={15}/>:<CheckCircle2 size={15}/>}Save preferences</button></form>
    <form onSubmit={password}><h3><KeyRound size={17}/>Change password</h3><label className="field-label">Current password<input type="password" value={current} autoComplete="current-password" required maxLength={128} onChange={e=>setCurrent(e.target.value)}/></label><label className="field-label">New password<input type="password" value={next} autoComplete="new-password" minLength={15} maxLength={128} required onChange={e=>setNext(e.target.value)}/></label><p className="muted">Use at least 15 characters. Saving signs out all sessions, including this one.</p><button className="button secondary small" disabled={busy}>Update password</button></form>
    {profile.personalization_opt_in&&<div className="settings-section"><h3>Personal information</h3><button className="button secondary small" disabled={busy} onClick={()=>void perform(async()=>{await api('/me/profile/personalization',{method:'DELETE'});onSaved(await api<Models['UserProfileV2']>('/me/profile'));setMessage('Personalization data removed.')})}>Remove personalization data</button></div>}
    <div className="settings-section"><button className="button secondary small" disabled={busy} onClick={()=>void perform(onLogout)}><LogOut size={15}/>Sign out</button></div>
    {session.role==='USER'&&<div className="account-danger"><h3>Delete account</h3><p>This permanently removes your subscriptions, private inbox and personal information. Published source evidence stays in the platform’s audit history.</p>{!deletion?<button className="danger-button" onClick={()=>setDeletion(true)}>Delete my account</button>:<form onSubmit={remove}><label className="field-label">Confirm your password<input type="password" autoComplete="current-password" required value={deletePassword} onChange={e=>setDeletePassword(e.target.value)}/></label><label className="checkbox-label consent-row"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} required/>I understand that my account and private data will be permanently deleted.</label><button className="danger-button" disabled={busy||!confirmed}>Permanently delete my account</button><button type="button" className="text-button" onClick={()=>setDeletion(false)}>Keep my account</button></form>}</div>}
    <p className="modal-disclaimer"><ShieldCheck size={14}/>Decision support only; not official eligibility or application confirmation.</p>
  </div>
}
