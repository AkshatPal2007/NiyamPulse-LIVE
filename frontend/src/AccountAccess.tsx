import {useState,type FormEvent} from 'react'
import {ArrowLeft,ArrowRight,CheckCircle2,Eye,EyeOff,LoaderCircle,LockKeyhole,Mail,ShieldCheck,X} from 'lucide-react'
import type {components} from './generated/api'
import {requestApi} from './api'
import {PrivacyNotice} from './PrivacyNotice'

type Models=components['schemas']
export type AccessMode='login'|'register'|'forgot'|'verify'|'reset'|'resend'

export function AccountAccess({mode:initial,token,available,onClose,onSession}:{mode:AccessMode;token?:string;available:boolean;onClose:()=>void;onSession:(value:Models['AuthSession'])=>void}) {
  const [mode,setMode]=useState(initial)
  const [email,setEmail]=useState('')
  const [name,setName]=useState('')
  const [password,setPassword]=useState('')
  const [adult,setAdult]=useState(false)
  const [visible,setVisible]=useState(false)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [sent,setSent]=useState(false)
  const [privacy,setPrivacy]=useState(false)
  const finishing=mode==='verify'||mode==='reset'
  const title=sent?'Check your inbox':mode==='register'?'A clearer path starts here.':mode==='forgot'?'Let’s get you back in.':mode==='resend'?'Get a fresh verification link.':mode==='verify'?'Make this account yours.':mode==='reset'?'Choose a new password.':'Good to see you again.'
  async function submit(event:FormEvent) {
    event.preventDefault();setBusy(true);setError('')
    try {
      if(mode==='login')onSession(await requestApi<Models['AuthSession']>('/auth/login',undefined,{method:'POST',body:JSON.stringify({email,password})}))
      else if(finishing)onSession(await requestApi<Models['AuthSession']>('/auth/'+(mode==='verify'?'verify':'reset-password'),undefined,{method:'POST',body:JSON.stringify({token,password})}))
      else {
        await requestApi('/auth/'+(mode==='register'?'register':mode==='resend'?'resend-verification':'forgot-password'),undefined,{method:'POST',body:JSON.stringify(mode==='register'?{email,display_name:name,adult_confirmed:adult}:{email})})
        setSent(true)
      }
    }catch(reason){setError((reason as Error).message)}finally{setBusy(false)}
  }
  function change(next:AccessMode){setMode(next);setError('');setSent(false);setPassword('')}
  return <div className="access-screen"><a className="public-brand" href="/" onClick={e=>{e.preventDefault();onClose()}}><span className="brand-mark">≈</span>Niyam<span>Pulse</span></a><button className="access-close icon-button" aria-label="Back to NiyamPulse" onClick={onClose}><X size={20}/></button><main className="access-layout" id="main-content" tabIndex={-1}><aside className="access-story"><span className="eyebrow">YOUR NEXT CHAPTER</span><h2>A little less searching.<br/>A lot more clarity.</h2><p>Follow the exams that matter to you. Find reviewed updates, original sources and a calm place to plan what comes next.</p><div className="access-points"><span><ShieldCheck size={18}/>Every alert starts with a reviewed source</span><span><LockKeyhole size={18}/>Your inbox belongs to you</span><span><Mail size={18}/>Email verification keeps your account yours</span></div><div className="access-orbit" aria-hidden="true"><i/><i/><i/><span>NP</span></div></aside><section className="access-card"><span className="eyebrow">{sent?'ONE MORE STEP':finishing?'SECURE ACCOUNT SETUP':mode==='register'?'CREATE YOUR ACCOUNT':'YOUR NIYAMPULSE ACCOUNT'}</span><h1 className="access-title">{title}</h1>{sent?<><div className="email-success"><CheckCircle2 size={31}/><p>If this address can receive the request, an email will arrive with a secure link. Open it on the device where you use NiyamPulse.</p></div><p className="muted">Check spam too. Links expire and work once. If nothing arrives, contact the person operating this instance.</p><button className="button primary full" onClick={()=>change('login')}>Back to sign in<ArrowRight size={16}/></button></>:<><p className="muted">{mode==='register'?'Start with your email. You’ll choose your password after verifying it.':mode==='forgot'?'Enter your account email to request a password reset.':mode==='resend'?'Use the email address you started your account with.':finishing?'Use a unique passphrase of at least 15 characters. Spaces are welcome.':'Sign in to your exam watchlist and private inbox.'}</p>{!available&&['register','forgot','resend'].includes(mode)?<div className="access-notice">Account email is currently unavailable. You can still browse reviewed updates and the exam catalog.<button className="text-button" onClick={onClose}>Browse NiyamPulse<ArrowRight size={16}/></button></div>:<form onSubmit={submit}>
      {mode==='register'&&<label className="field-label">Your name<input autoComplete="name" maxLength={80} value={name} onChange={e=>setName(e.target.value)} required placeholder="How should we address you?"/></label>}
      {!finishing&&<label className="field-label">Email address<input type="email" autoComplete="email" required value={email} maxLength={254} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com"/></label>}
      {(mode==='login'||finishing)&&<label className="field-label">{finishing?'Choose your password':'Password'}<span className="password-control"><input type={visible?'text':'password'} autoComplete={finishing?'new-password':'current-password'} required minLength={finishing?15:1} maxLength={128} value={password} onChange={e=>setPassword(e.target.value)}/><button type="button" aria-label={visible?'Hide password':'Show password'} onClick={()=>setVisible(!visible)}>{visible?<EyeOff size={18}/>:<Eye size={18}/>}</button></span></label>}
      {mode==='register'&&<label className="checkbox-label consent-row"><input type="checkbox" checked={adult} onChange={e=>setAdult(e.target.checked)} required/><span>I am 18 or older, registering for myself or as a guardian. I can follow exams without adding a child’s personal details.</span></label>}
      {mode==='register'&&<button className="privacy-link" type="button" onClick={()=>setPrivacy(true)}>How your account data is used</button>}
      {error&&<div className="access-error" role="alert">{error}{finishing&&<button type="button" className="access-link" onClick={()=>change(mode==='verify'?'resend':'forgot')}>Request a new email link</button>}</div>}
      <button className="button primary full" disabled={busy||mode==='register'&&!adult}>{busy?<LoaderCircle size={17} className="spin"/>:null}{mode==='login'?'Sign in':mode==='register'?'Continue with email':mode==='forgot'?'Request reset link':mode==='resend'?'Request verification link':mode==='verify'?'Verify & open my account':'Save password & sign in'}{!busy&&<ArrowRight size={17}/>}</button>
      </form>}{mode==='login'&&<><button className="access-link" onClick={()=>change('forgot')}>Forgot your password?</button><button className="access-link" onClick={()=>change('resend')}>Need a verification email?</button><p className="access-switch">New here? <button onClick={()=>change('register')}>Create an account</button></p></>}{mode!=='login'&&!finishing&&<button className="access-link" onClick={()=>change('login')}><ArrowLeft size={14}/>Back to sign in</button>}</>}<p className="access-footnote">Decision support only; not official eligibility or application confirmation.</p></section></main>{privacy&&<PrivacyNotice onClose={()=>setPrivacy(false)}/>}</div>
}
