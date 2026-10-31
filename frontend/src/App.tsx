import {VoiceSearch,NoticeNarration} from './VoiceTools'
import {EvidenceViewer} from './EvidenceViewer'
import {ImpactDetail,SubscriptionTopics} from './ImpactDetail'
import {EvaluationPanel} from './EvaluationPanel'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Activity, ArrowDownLeft, ArrowRight, ArrowUpRight, Bell, BellRing, BookOpen, Check, CheckCheck, ChevronDown, ChevronRight, CircleHelp, ExternalLink, FileText, GraduationCap, LayoutDashboard, ListChecks, LoaderCircle, LockKeyhole, Menu, Radio, Search, Settings2, ShieldCheck, SlidersHorizontal, Sparkles, Users, Waves, X } from 'lucide-react'
import type { components } from './generated/api'
import {AccountAccess,type AccessMode} from './AccountAccess'
import {PublicHome} from './PublicHome'
import {AccountSettings} from './AccountSettings'
import {ApiFailure,requestApi} from './api'
import {LogOut,RefreshCw} from 'lucide-react'

type Models = components['schemas']
type Catalog = Models['CatalogResponse']
type Subscription = Models['ExamSubscription']
type Notification = Models['InAppNotification']
type Notice = Models['DetectedNotice']
type Dashboard = Models['AdminDashboardResponse']
type Source = Models['OfficialSource']
type Session = Models['AuthSession']
type Detail = Models['NoticeDetail']
type InboxItem = Models['InboxItem']
type Topic = Models['Topic']
type View = 'overview' | 'explore' | 'following' | 'inbox' | 'review' | 'sources' | 'delivery'
const DISCLAIMER = 'Decision support only; not official eligibility or application confirmation.'
const topicLabels: Record<Topic,string> = { ALL:'All updates',REGISTRATION:'Registration',ELIGIBILITY:'Eligibility',EXAM_SCHEDULE:'Exam schedule',ADMIT_CARD:'Admit cards',ANSWER_KEY:'Answer keys',RESULTS:'Results',SYLLABUS:'Syllabus',OTHER:'Announcements' }
const topics: Topic[] = ['ALL','REGISTRATION','ELIGIBILITY','EXAM_SCHEDULE','ADMIT_CARD','ANSWER_KEY','RESULTS','SYLLABUS','OTHER']
const date = (value?:string|null) => value ? new Date(value).toLocaleString('en-IN',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}) : 'Not checked yet'
const titleCase = (text:string) => text.replaceAll('_',' ').toLowerCase().replace(/^./,s=>s.toUpperCase())

const fetchApi=requestApi

export default function App() {
  const [session,setSession]=useState<Session|null>(null)
  const [booting,setBooting]=useState(true)
  const [config,setConfig]=useState<Models['AuthConfig']|null>(null)
  const [intent,setIntent]=useState<string|undefined>()
  const [link,setLink]=useState<{mode:'verify'|'reset';token:string}|null>(()=>{
    const match=/^#(verify|reset)=([A-Za-z0-9_-]{32,128})$/.exec(window.location.hash)
    if(!match)return null
    return {mode:match[1] as 'verify'|'reset',token:match[2]}
  })
  const [access,setAccess]=useState<AccessMode|null>(link?.mode??null)
  useEffect(()=>{if(link)window.history.replaceState(null,'',window.location.pathname+window.location.search)},[link])
  useEffect(()=>{let active=true
    Promise.all([fetchApi<Models['AuthConfig']>('/auth/config'),fetchApi<Session>('/auth/session').catch(reason=>{if(reason instanceof ApiFailure&&reason.status===401)return null;throw reason})]).then(([settings,user])=>{if(active){setConfig(settings);setSession(user)}}).catch(()=>{if(active)setSession(null)}).finally(()=>{if(active)setBooting(false)})
    return()=>{active=false}
  },[])
  function signedIn(value:Session){setSession(value);setLink(null);setAccess(null)}
  async function logout(){await fetchApi('/auth/logout',session?.csrf_token,{method:'POST'});setSession(null);setAccess(null)}
  if(access)return <AccountAccess mode={access} token={link?.token} available={config?.registration_available??false} onClose={()=>{setAccess(null);setLink(null)}} onSession={signedIn}/>
  if(booting)return <div className="account-boot"><span className="brand-mark">≈</span><strong>NiyamPulse</strong><LoaderCircle className="spin" size={20}/><span>Opening your workspace…</span></div>
  if(session)return <Workspace session={session} onLogout={logout} onExpired={()=>setSession(null)} initialCycle={intent}/>
  return <PublicHome onAccess={(mode,cycle)=>{setIntent(cycle);setAccess(mode)}}/>
}

function Modal({title,children,onClose,wide=false}:{title:string;children:ReactNode;onClose:()=>void;wide?:boolean}) {
  const ref=useRef<HTMLDialogElement>(null)
  useEffect(()=>{const dialog=ref.current;dialog?.showModal();return()=>dialog?.close()},[])
  return <dialog ref={ref} className={'modal '+(wide?'wide':'')} onCancel={onClose} onClick={e=>{if(e.target===e.currentTarget)onClose()}}>
    <div className="modal-head"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={20}/></button></div>{children}
  </dialog>
}

function Empty({icon,heading,body,action}:{icon:ReactNode;heading:string;body:string;action?:ReactNode}) {
  return <div className="empty"><div className="empty-icon">{icon}</div><h3>{heading}</h3><p>{body}</p>{action}</div>
}

function Workspace({session,onLogout,onExpired,initialCycle}:{session:Session;onLogout:()=>Promise<void>;onExpired:()=>void;initialCycle?:string}) {
  const [view,setView]=useState<View>('overview')
  const [catalog,setCatalog]=useState<Catalog|null>(null)
  const [subscriptions,setSubscriptions]=useState<Subscription[]>([])
  const [inbox,setInbox]=useState<Models['NotificationsResponse']>({schema_version:'2.0.0',notifications:[],next_cursor:null,unread_count:0})
  const [dashboard,setDashboard]=useState<Dashboard|null>(null)
  const [sources,setSources]=useState<Source[]>([])
  const [notices,setNotices]=useState<Notice[]>([])
  const [sarvam,setSarvam]=useState<Models['SarvamHealth']|null>(null)
  const [processing,setProcessing]=useState<Models['ProcessingQueue']|null>(null)
  const [creditBalance,setCreditBalance]=useState('')
  const [loaded,setLoaded]=useState(false)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [toast,setToast]=useState('')
  const [search,setSearch]=useState('')
  const [audience,setAudience]=useState('ALL')
  const [selectedCycle,setSelectedCycle]=useState<Record<string,string>>({})
  const [selectedTopic,setSelectedTopic]=useState<Record<string,Topic>>({})
  const [detail,setDetail]=useState<Detail|null>(null)
  const [inboxItem,setInboxItem]=useState<InboxItem|null>(null)
  const [reason,setReason]=useState('')
  const [confirmed,setConfirmed]=useState(false)
  const [showProfile,setShowProfile]=useState(false)
  const [profile,setProfile]=useState<Models['UserProfileV2']|null>(null)
  const [mobileMenu,setMobileMenu]=useState(false)
  const [unreadOnly,setUnreadOnly]=useState(false)
  const [inboxPages,setInboxPages]=useState(1)
  const [recipients,setRecipients]=useState<Models['RecipientMatch'][]|null>(null)
  const [checking,setChecking]=useState('')
  const activeUser=useRef<string|undefined>(undefined)
  activeUser.current=session?.user_id
  const admin=session?.role==='ADMIN'
  const api=useCallback(<T,>(path:string,options:RequestInit={})=>fetchApi<T>(path,session.csrf_token,options).catch(reason=>{if(reason instanceof ApiFailure&&reason.status===401&&['SESSION_REQUIRED','SESSION_EXPIRED'].includes(reason.code??''))onExpired();throw reason}),[session.csrf_token,onExpired])

  const refresh=useCallback(async()=>{
    if(!session)return
    const cat=await api<Catalog>('/catalog');if(activeUser.current!==session.user_id)return;setCatalog(cat)
    if(session.role==='ADMIN') {
      const [stats,sourceList,queue,aiHealth,jobs]=await Promise.all([api<Dashboard>('/admin/dashboard'),api<Source[]>('/admin/sources'),api<Notice[]>('/admin/notices'),api<Models['SarvamHealth']>('/admin/sarvam'),api<Models['ProcessingQueue']>('/admin/processing')])
      if(activeUser.current!==session.user_id)return
      setDashboard(stats);setSources(sourceList);setNotices(queue);setSarvam(aiHealth);setProcessing(jobs)
    } else {
      const [subs,firstPage]=await Promise.all([api<Subscription[]>('/me/subscriptions'),api<Models['NotificationsResponse']>('/me/notifications?unread_only='+unreadOnly)])
      let messages=firstPage
      for(let page=1;page<inboxPages&&messages.next_cursor;page++) {
        const next=await api<Models['NotificationsResponse']>('/me/notifications?cursor='+encodeURIComponent(messages.next_cursor)+'&unread_only='+unreadOnly)
        messages={...next,notifications:[...messages.notifications,...next.notifications]}
      }
      if(activeUser.current!==session.user_id)return
      setSubscriptions(subs);setInbox(messages)
    }
    if(initialCycle&&cat.cycles.some(c=>c.cycle_id===initialCycle)){const cycle=cat.cycles.find(c=>c.cycle_id===initialCycle)!;setSelectedCycle(value=>({...value,[cycle.exam_id]:initialCycle}))}
    setLoaded(true)
  },[api,session,unreadOnly,inboxPages,initialCycle])

  useEffect(()=>{if(!session)return;refresh().catch(e=>setError(e.message));const interval=setInterval(()=>refresh().catch(e=>setError(e.message)),8000);return()=>clearInterval(interval)},[refresh,session])
  useEffect(()=>{if(!toast)return;const timer=setTimeout(()=>setToast(''),4500);return()=>clearTimeout(timer)},[toast])

  async function perform(action:()=>Promise<unknown>,message?:string) {
    setBusy(true);setError('')
    try {await action();await refresh();if(message)setToast(message)}catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  function navigate(next:View){setView(next);setMobileMenu(false);setSearch('')}
  const cycleName=(id:string)=>catalog?.cycles.find(c=>c.cycle_id===id)?.display_name||id
  const examName=(id:string)=>catalog?.exams.find(e=>e.exam_id===catalog.cycles.find(c=>c.cycle_id===id)?.exam_id)?.display_name||id
  const pending=notices.filter(n=>n.review_status==='NEEDS_REVIEW')

  async function follow(examId:string) {
    const cycle=selectedCycle[examId]||catalog?.cycles.find(c=>c.exam_id===examId)?.cycle_id
    if(!cycle)return
    await perform(()=>api('/me/subscriptions',{method:'POST',body:JSON.stringify({cycle_id:cycle,topics:[selectedTopic[examId]||'ALL'],application_status:'INTERESTED'})}),'Added to your exam watchlist')
  }
  async function openNotice(notice:Notice){setError('');try{setDetail(await api<Detail>('/admin/notices/'+notice.notice_id));setReason('');setConfirmed(false)}catch(e){setError((e as Error).message)}}
  async function analyzeNotice() {
    if(!detail)return
    await perform(async()=>{
      await api('/admin/notices/'+detail.notice.notice_id+'/analyze',{method:'POST',body:JSON.stringify({expected_revision:detail.notice.revision})})
      setDetail(await api<Detail>('/admin/notices/'+detail.notice.notice_id));setConfirmed(false);setReason('')
    },'Extraction recorded. Check the evidence before reviewing.')
  }
  async function recoverOcr() {
    if(!detail)return
    await perform(async()=>{
      const result=await api<Models['OcrResult']>('/admin/notices/'+detail.notice.notice_id+'/ocr',{method:'POST',body:JSON.stringify({expected_revision:detail.notice.revision})})
      setDetail(await api<Detail>('/admin/notices/'+detail.notice.notice_id));setConfirmed(false);setReason('')
      setToast(result.status==='PENDING'?'OCR is processing. Use the same button to resume the saved job.':'OCR recovered. Compare the text with the original PDF, then extract facts.')
    })
  }
  async function openNotification(notification:Notification){await perform(async()=>{setInboxItem(await api<InboxItem>('/me/notifications/'+notification.notification_id));await api('/me/notifications/'+notification.notification_id+'/read',{method:'POST'})})}
  async function review(action:'APPROVE'|'QUARANTINE'|'REJECT') {
    if(!detail||!session)return
    await perform(async()=>{await api('/admin/notices/'+detail.notice.notice_id+'/review',{method:'POST',body:JSON.stringify({notice_id:detail.notice.notice_id,reviewer_id:session.user_id,action,reason,reviewed_at:new Date().toISOString(),expected_revision:detail.notice.revision})});setDetail(null)},action==='APPROVE'?'Published. Matching subscribers have an in-app alert.':'Review decision saved')
  }
  async function checkSource(source:Source){setChecking(source.source_id);await perform(()=>api('/admin/monitor/'+source.source_id+'/check',{method:'POST',body:JSON.stringify({dry_run:false})}),'Source check completed');setChecking('')}
  function loadMore(){if(inbox.next_cursor)setInboxPages(value=>value+1)}

  const navItems=admin ? [
    {id:'overview',label:'Operations overview',icon:<LayoutDashboard size={19}/>},
    {id:'review',label:'Review queue',icon:<ListChecks size={19}/>,count:dashboard?.totals.notices_pending_review},
    {id:'sources',label:'Source monitor',icon:<Radio size={19}/>},
    {id:'delivery',label:'Publication & delivery',icon:<ArrowUpRight size={19}/>},
  ] : [
    {id:'overview',label:'My overview',icon:<LayoutDashboard size={19}/>},
    {id:'explore',label:'Explore exams',icon:<GraduationCap size={19}/>},
    {id:'following',label:'My subscriptions',icon:<BookOpen size={19}/>},
    {id:'inbox',label:'My inbox',icon:<Bell size={19}/>,count:inbox.unread_count},
  ]

  const sectionTitle:Record<View,string>={overview:admin?'Operations overview':'My overview',explore:'Find your next opportunity',following:'Your exams. Your preferences.',inbox:'The updates that matter',review:'A careful review. A useful alert.',sources:'A clear view of every source',delivery:'From publication to inbox'}
  const filtered=catalog?.exams.filter(e=>(audience==='ALL'||e.audiences.includes(audience as Models['Audience']))&&(!search||(e.display_name+' '+e.description).toLowerCase().includes(search.toLowerCase())))||[]

  function notificationCard(item:Notification) {
    return <button key={item.notification_id} className={'notification-card '+(item.delivery!=='READ'?'unread':'')} onClick={()=>openNotification(item)}>
      <span className="notification-symbol"><BellRing size={19}/></span><span className="notification-content"><span className="eyebrow">{examName(item.cycle_id)} <span className="dot-separator">·</span> Reviewed source update</span><strong>{item.headline}</strong><span className="notification-time">{date(item.created_at)} · {item.language==='en'?'English source excerpt':'Controlled Hindi overview'} · {item.delivery==='READ'?'Read':'Unread'}</span></span><ChevronRight size={18}/>
    </button>
  }

  function examGrid(short=false) {
    const items=short?filtered.filter(e=>e.active).slice(0,4):filtered
    return <div className="exam-grid">{items.map(exam=>{
      const cycles=catalog?.cycles.filter(c=>c.exam_id===exam.exam_id&&c.is_active)||[]
      const cycle=selectedCycle[exam.exam_id]||cycles[0]?.cycle_id
      const sub=subscriptions.find(s=>s.cycle_id===cycle)
      const coverage=catalog?.coverage?.[exam.exam_id]||'CATALOG_ONLY'
      return <article className="exam-card" key={exam.exam_id}>
        <div className="card-top"><div className={'exam-monogram tone-'+(exam.audiences[0]==='ENGINEERING'?'purple':exam.exam_family==='DEFENCE_ENTRANCE'?'orange':'green')}>{exam.display_name.split(' ')[0].slice(0,4)}</div><span className={'coverage '+(coverage==='LIVE_MONITORED'?'live':'')}>{coverage==='LIVE_MONITORED'?<><span className="status-dot"/>Monitored</>:coverage==='SOURCE_CONFIGURED'?'Source ready':'Catalog only'}</span></div>
        <h3>{exam.display_name}</h3><p className="exam-description">{exam.description}</p>
        <div className="exam-audience">{exam.audiences.map(a=><span key={a}>{a==='SCHOOL'?'School & entrance':a==='ENGINEERING'?'Engineering':'General recruitment'}</span>)}</div>
        {cycles.length>0?<><label className="sr-only" htmlFor={'cycle-'+exam.exam_id}>{exam.display_name} cycle</label><select id={'cycle-'+exam.exam_id} value={cycle} onChange={e=>setSelectedCycle({...selectedCycle,[exam.exam_id]:e.target.value})}>{cycles.map(c=><option key={c.cycle_id} value={c.cycle_id}>{c.display_name}</option>)}</select>
          {!sub&&<label className="topic-picker"><SlidersHorizontal size={13}/><select aria-label={'Topics for '+exam.display_name} value={selectedTopic[exam.exam_id]||'ALL'} onChange={e=>setSelectedTopic({...selectedTopic,[exam.exam_id]:e.target.value as Topic})}>{topics.map(t=><option key={t} value={t}>{topicLabels[t]}</option>)}</select></label>}
          <button disabled={busy||!!sub} className={'track-button '+(sub?'following':'')} onClick={()=>follow(exam.exam_id)}>{sub?<><Check size={16}/>Following this cycle</>:<>Follow exam <ArrowRight size={16}/></>}</button>
        </>:<div className="coming-soon">More cycles coming soon</div>}
      </article>
    })}</div>
  }

  function sourcePanel(compact=false) {
    return <div className="source-list">{(compact?sources.filter(s=>s.enabled):sources).map(source=>{
      const health=dashboard?.source_checks?.find(h=>h.source_id===source.source_id)
      const waiting=health?.next_due_at&&new Date(health.next_due_at).getTime()>Date.now()
      return <article className="source-row" key={source.source_id}><div className={'source-icon '+(health?.status==='LIVE_OK'?'healthy':'')}><Radio size={20}/></div><div className="source-main"><strong>{source.organization}</strong><a href={source.listing_url} target="_blank" rel="noreferrer">{new URL(source.listing_url).hostname}<ArrowUpRight size={12}/></a><small>{source.enabled?'Every '+source.poll_interval_minutes+' minutes':'Disabled · adapter awaiting verification'}</small>{!!health?.pending_extractions&&<small>Last check: {health.pending_extractions} awaiting OCR</small>}{health?.last_error&&<small className="danger-text">{health.last_error}</small>}</div><div className="source-meta"><span className={'badge '+(health?.status==='LIVE_OK'?'green':health?.status==='ERROR'?'amber':'neutral')}>{health?.status==='LIVE_OK'?'Last fetch succeeded':health?.status==='ERROR'?'Source unavailable':'Not active'}</span><small>{date(health?.last_success_at)}</small>{!compact&&<small>Next: {date(health?.next_due_at)}</small>}</div>{!compact&&<button className="button secondary small" disabled={busy||!source.adapter_name||!!waiting} onClick={()=>checkSource(source)}>{checking===source.source_id?<LoaderCircle className="spin" size={14}/>:<Activity size={14}/>} {waiting?'Scheduled':'Check source'}</button>}</article>
    })}{sources.filter(s=>s.enabled).length===0&&compact&&<p className="muted pad">No live adapters enabled. Untested sources stay disabled.</p>}</div>
  }

  return <div className="app-shell">
    {mobileMenu&&<div className="sidebar-scrim" onClick={()=>setMobileMenu(false)}/>}
    <aside className={'sidebar '+(mobileMenu?'open':'')}>
      <a className="brand" href="#" onClick={e=>{e.preventDefault();navigate('overview')}}><span className="brand-mark"><Waves size={25}/></span><span>Niyam<span className="brand-light">Pulse</span><small>CLARITY FOR WHAT'S NEXT</small></span></a>
      <div className="workspace-label">{admin?'OPERATOR WORKSPACE':'YOUR LEARNING JOURNEY'}</div>
      <nav>{navItems.map(item=><button key={item.id} className={view===item.id?'active':''} onClick={()=>navigate(item.id as View)}>{item.icon}<span>{item.label}</span>{!!item.count&&<b>{item.count}</b>}</button>)}</nav>
      <div className="sidebar-note"><div className="sidebar-note-icon"><ShieldCheck size={20}/></div><strong>Source first. Always.</strong><p>Every update comes with the evidence behind it.</p><span>Built for informed next steps <ArrowUpRight size={14}/></span></div>
      <div className="sidebar-bottom"><button onClick={async()=>{try{setProfile(await api<Models['UserProfileV2']>('/me/profile'));setShowProfile(true)}catch(e){setError((e as Error).message)}}}><Settings2 size={18}/><span>Privacy & preferences</span></button><span className="version-label">NIYAMPULSE <span>EXAM UPDATES</span></span></div>
    </aside>

    <div className="main-shell">
      <header className="topbar"><div className="breadcrumbs"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={()=>setMobileMenu(true)}><Menu size={21}/></button><span>{admin?'Operator workspace':'Student workspace'}</span><ChevronRight size={13}/><strong>{navItems.find(i=>i.id===view)?.label||'Overview'}</strong></div><div className="topbar-right"><span className="role-tag">{admin?'Administrator account':'Personal account'}</span><div className="account-switch"><Users size={15}/><button className="account-menu-button" onClick={async()=>{try{setProfile(await api<Models['UserProfileV2']>('/me/profile'));setShowProfile(true)}catch(reason){setError((reason as Error).message)}}}>{profile?.display_name??session.display_name}<ChevronDown size={15}/></button><button className="icon-button" aria-label="Sign out" onClick={()=>{setBusy(true);onLogout().catch(reason=>setError((reason as Error).message)).finally(()=>setBusy(false))}}><LogOut size={18}/></button></div><span className="avatar">{session.display_name.slice(0,2).toUpperCase()}</span></div></header>
      <main id="main-content" tabIndex={-1}>
        {error&&<div className="error-banner" role="alert"><CircleHelp size={19}/><span>{error}</span><button aria-label="Dismiss error" onClick={()=>setError('')}><X size={17}/></button></div>}
        <div className="page-heading"><div><div className="eyebrow green-text">{admin?'THE OPERATIONS DESK':'A LITTLE CLARITY. A LOT OF POSSIBILITY.'}</div><h1>{sectionTitle[view]}</h1><p>{admin?'Review carefully. Reach the right learners. Keep every source in sight.':'One place for the exams you follow and the updates worth your attention.'}</p></div><div className="heading-actions">{admin?<button className="button secondary" disabled={busy} onClick={()=>perform(refresh,'Workspace refreshed')}><Sparkles size={16}/>Refresh workspace</button>:<button className="button secondary" onClick={()=>navigate(view==='explore'?'inbox':'explore')}>{view==='explore'?<Bell size={16}/>:<GraduationCap size={17}/>} {view==='explore'?'Open inbox':'Explore exams'}<ArrowUpRight size={16}/></button>}</div></div>

        {!loaded?<div className="loading-state"><LoaderCircle className="spin" size={28}/><p>Connecting to your workspace…</p></div>:<>
          {view==='overview'&&!admin&&<>
            <section className="hero"><div className="hero-copy"><span className="hero-kicker"><span className="status-dot"/>YOUR NEXT CHAPTER STARTS HERE</span><h2>Your next move,<br/><em>already in view.</em></h2><p>Follow your exams. Get source-linked updates.<br/>Make room for the work that moves you forward.</p><button className="button primary" onClick={()=>navigate('explore')}>Build your exam watchlist<ArrowRight size={17}/></button><span className="hero-footnote"><LockKeyhole size={13}/>No marks, income or date of birth needed.</span></div><div className="hero-art" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit orbit-three"/><div className="orbit-center"><Waves size={42}/></div><span className="orbit-exam orbit-jee">JEE<small>SCHOOL ENTRANCE</small></span><span className="orbit-exam orbit-gate">GATE<small>ENGINEERING</small></span><span className="orbit-spark"><Sparkles size={20}/></span><span className="orbit-point p1"/><span className="orbit-point p2"/><div className="art-caption">Different paths.<br/><strong>One clear view.</strong></div></div></section>
            <div className="student-stats"><button onClick={()=>navigate('following')}><span className="stat-symbol green"><BookOpen size={21}/></span><span><strong>{subscriptions.length}</strong><small>Exam cycles followed</small></span><ArrowUpRight size={18}/></button><button onClick={()=>navigate('inbox')}><span className="stat-symbol purple"><Bell size={21}/></span><span><strong>{inbox.unread_count}</strong><small>Unread updates</small></span><ArrowUpRight size={18}/></button><div><span className="stat-symbol orange"><ShieldCheck size={21}/></span><span><strong>Source-linked</strong><small>Evidence before assertions</small></span><CheckCheck size={18}/></div></div>
            <div className="overview-columns"><section className="panel"><div className="section-head"><h2>Your latest updates</h2><button className="text-button" onClick={()=>navigate('inbox')}>View inbox<ArrowRight size={14}/></button></div>{inbox.notifications.length?inbox.notifications.slice(0,3).map(notificationCard):<Empty icon={<Bell size={25}/>} heading="A quieter inbox. A clearer focus." body="Approved updates for your subscribed cycles will appear here. Start by following an exam." action={<button className="text-button" onClick={()=>navigate('explore')}>Find your exams<ArrowRight size={14}/></button>}/>}</section><aside className="insight-card"><span className="insight-icon"><GraduationCap size={25}/></span><span className="eyebrow">MADE FOR YOUR JOURNEY</span><h3>Big plans.<br/>Small, useful updates.</h3><p>School entrance, engineering, defence or recruitment. Follow multiple cycles, and choose the topics you care about.</p><button className="text-button" onClick={()=>navigate('explore')}>Find your path<ArrowRight size={15}/></button></aside></div>
            <div className="section-head spaced"><div><h2>A world of possibilities</h2><p>Explore the exam catalog. Monitoring coverage is shown for each exam.</p></div><button className="text-button" onClick={()=>navigate('explore')}>See all exams<ArrowRight size={15}/></button></div>{examGrid(true)}
          </>}

          {view==='explore'&&!admin&&<><VoiceSearch api={api} onSearch={(query,examId)=>setSearch(catalog?.exams.find(exam=>exam.exam_id===examId)?.display_name??query)}/><div className="catalog-toolbar"><div className="filter-tabs">{[['ALL','All exams'],['SCHOOL','School & entrance'],['ENGINEERING','Engineering'],['GENERAL','General']].map(([key,label])=><button key={key} className={audience===key?'selected':''} onClick={()=>setAudience(key)}>{label}</button>)}</div><label className="search-box"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search for your next exam…" aria-label="Search exams"/></label></div><div className="catalog-note"><ShieldCheck size={16}/><span>Subscriptions are cycle-specific. “Catalog only” means live monitoring is not active for that exam.</span></div>{filtered.length?examGrid():<Empty icon={<Search size={24}/>} heading="No exams found" body="Try another search or audience filter."/>}</>}

          {view==='following'&&!admin&&<section className="panel">{subscriptions.length?subscriptions.map(sub=><article className="subscription-row" key={sub.subscription_id}><span className="subscription-icon"><GraduationCap size={23}/></span><div className="subscription-info"><h3>{cycleName(sub.cycle_id)}</h3><span>{(sub.topics??['ALL']).map(t=>topicLabels[t]).join(', ')} · {sub.application_status==='APPLIED_SELF_REPORTED'?'Applied · self-reported':titleCase(sub.application_status)}</span></div><SubscriptionTopics value={sub.topics??['ALL']} onSave={async values=>{await api('/me/subscriptions/'+sub.subscription_id,{method:'PATCH',body:JSON.stringify({topics:values})});await refresh()}}/><select aria-label={'Application status for '+cycleName(sub.cycle_id)} value={sub.application_status} onChange={e=>perform(()=>api('/me/subscriptions/'+sub.subscription_id,{method:'PATCH',body:JSON.stringify({application_status:e.target.value})}))}><option value="UNKNOWN">Not specified</option><option value="INTERESTED">Interested</option><option value="PLANNING_TO_APPLY">Planning to apply</option><option value="APPLIED_SELF_REPORTED">Applied (self-reported)</option><option value="NO_LONGER_INTERESTED">No longer interested</option></select><button className="button secondary small" disabled={busy} onClick={()=>perform(()=>api('/me/subscriptions/'+sub.subscription_id,{method:'PATCH',body:JSON.stringify({notifications_enabled:!sub.notifications_enabled})}))}>{sub.notifications_enabled?'Pause alerts':'Resume alerts'}</button><button className="icon-button" aria-label={'Unfollow '+cycleName(sub.cycle_id)} disabled={busy} onClick={()=>perform(()=>api('/me/subscriptions/'+sub.subscription_id,{method:'DELETE'}),'Subscription removed')}><X size={18}/></button></article>):<Empty icon={<BookOpen size={26}/>} heading="Make this space yours" body="Follow an exam cycle to receive relevant, reviewed updates. Your personal details are optional." action={<button className="button primary" onClick={()=>navigate('explore')}>Explore the catalog<ArrowRight size={16}/></button>}/>}</section>}

          {view==='inbox'&&!admin&&<section className="panel"><div className="section-head"><h2>Personal inbox <span className="count-pill">{inbox.unread_count} unread</span></h2><label className="checkbox-label"><input type="checkbox" checked={unreadOnly} onChange={e=>{setUnreadOnly(e.target.checked);setInboxPages(1)}}/>Unread only</label></div>{inbox.notifications.length?inbox.notifications.map(notificationCard):<Empty icon={<Bell size={27}/>} heading={unreadOnly?'You’re all caught up':'No updates yet'} body="Only reviewed updates matching your subscribed exam cycles and topics arrive here."/>}{inbox.next_cursor&&<button className="button secondary load-more" onClick={loadMore}>Load more updates</button>}</section>}

          {view==='overview'&&admin&&dashboard&&<><EvaluationPanel api={api}/>
            <section className="admin-banner"><div><span className="eyebrow">INFORMATION WITH ACCOUNTABILITY</span><h2>The right update.<br/><em>The right learner.</em></h2><p>Every publication starts with a source and a human review.</p></div><div className="admin-banner-state"><span className={'worker-state '+(dashboard.monitor_running?'running':'')}><span className="status-dot"/>{dashboard.monitor_running?'Source worker heartbeat active':'Source worker not running'}</span><span>Verified accounts · persisted activity</span><ShieldCheck size={72} strokeWidth={1}/></div></section>
            <div className="admin-stats">{[[dashboard.totals.notices_pending_review,'Awaiting review',<ListChecks size={21}/>,'orange'],[dashboard.totals.active_subscriptions,'Active subscriptions',<BookOpen size={21}/>,'purple'],[dashboard.totals.notifications_delivered,'In-app alerts delivered',<ArrowDownLeft size={21}/>,'green'],[dashboard.totals.notifications_read,'Alerts read',<CheckCheck size={21}/>,'blue']].map(([value,label,icon,tone])=><article key={String(label)}><div className={'stat-symbol '+tone}>{icon}</div><strong>{value}</strong><span>{label}</span></article>)}</div>
            <div className="admin-columns"><section className="panel"><div className="section-head"><h2>Ready for a closer look</h2><button className="text-button" onClick={()=>navigate('review')}>Open queue<ArrowRight size={14}/></button></div>{pending.length?pending.slice(0,3).map(notice=><button className="review-preview" key={notice.notice_id} onClick={()=>openNotice(notice)}><span className="notice-source-tag">{notice.source_id?.startsWith('nta')?'NTA':'UPSC'}</span><span><strong>{notice.title}</strong><small>{cycleName(notice.cycle_id)} · {date(notice.first_seen_at)}</small></span><ChevronRight size={17}/></button>):<Empty icon={<CheckCheck size={25}/>} heading="The queue is clear" body="New discoveries will wait here for operator review. Nothing is sent automatically."/>}</section><section className="panel"><div className="section-head"><h2>Subscriptions by cycle</h2><Users size={18}/></div><div className="cycle-chart">{(dashboard.by_cycle??[]).filter(c=>c.subscriptions>0).length?(dashboard.by_cycle??[]).filter(c=>c.subscriptions>0).map(c=><div key={c.cycle_id}><span>{cycleName(c.cycle_id)}</span><div className="bar-line"><i style={{width:Math.max(3,c.subscriptions/Math.max(...(dashboard.by_cycle??[]).map(v=>v.subscriptions))*100)+'%'}}/><b>{c.subscriptions}</b></div></div>):<Empty icon={<Users size={24}/>} heading="Learners set the direction" body="This chart fills from persisted subscriptions as learners follow exam cycles."/>}</div></section></div>
            <section className="panel spaced"><div className="section-head"><h2>Source health</h2><button className="text-button" onClick={()=>navigate('sources')}>All sources<ArrowRight size={14}/></button></div>{sourcePanel(true)}</section>
          </>}

          {view==='review'&&admin&&<><div className="catalog-note"><ShieldCheck size={17}/><span>Review the source, exact year/session and evidence. Publication targets matching subscriptions; it is never an official eligibility decision.</span></div><div className="review-grid">{notices.length?notices.map(notice=><article className="review-card" key={notice.notice_id}><div className="card-top"><span className="badge green">Official-source discovery</span><span className="review-status">{titleCase(notice.review_status)}</span></div><span className="eyebrow">{cycleName(notice.cycle_id)}</span><h3>{notice.title}</h3><div className="topic-chips">{(notice.topics??['OTHER']).map(t=><span key={t}>{topicLabels[t]}</span>)}</div><div className="review-card-footer"><small>Discovered {date(notice.first_seen_at)}</small><button className="text-button" onClick={()=>openNotice(notice)}>Inspect evidence<ArrowRight size={15}/></button></div></article>):<section className="panel"><Empty icon={<ListChecks size={27}/>} heading="Waiting for the next discovery" body="The source worker captures notices independently of this page. Every new notice waits for a source review before publication."/></section>}</div></>}

          {view==='sources'&&admin&&<><section className="panel"><div className="section-head"><div><h2>Configured official sources</h2><p>Only individually tested adapters are enabled. An allowlisted host is not cryptographic authenticity.</p></div><span className={'badge '+(dashboard?.monitor_running?'green':'amber')}>{dashboard?.monitor_running?'Worker heartbeat active':'Worker offline'}</span></div>{sourcePanel()}<div className="panel-footnote">Scheduled polling runs on the backend, even when this browser is closed. Check times and failures are recorded by the service.</div></section>
            <section className="panel spaced"><div className="section-head"><div><h2>Sarvam credit reserve</h2><p>A fresh manual balance snapshot is required for new paid requests. Cached results remain available.</p></div><span className={'badge '+(sarvam?.credit_safety?.paid_requests_allowed?'green':'amber')}>{sarvam?.credit_safety?.paid_requests_allowed?'Paid requests allowed':'Paid requests paused'}</span></div><div className="budget-grid"><div><span className="eyebrow">RESERVED FOR THE HACKATHON</span><h3>{((sarvam?.credit_safety?.floor_hundredths??50000)/100).toFixed(0)} credits</h3><p>Local test reservations: ₹{((sarvam?.reserved_paise??0)/100).toFixed(2)} {sarvam?.budget_limit_paise==null?'(local INR cap removed; 500-credit reserve remains)':`of ₹${((sarvam.budget_limit_paise??0)/100).toFixed(2)}`}.</p></div><div><strong>Last reported balance: {sarvam?.credit_safety?.reported_balance_hundredths!=null?((sarvam?.credit_safety?.reported_balance_hundredths??0)/100).toFixed(2):'Not reported'}</strong><p className="muted">Valid until {date(sarvam?.credit_safety?.valid_until)}. This is not a live provider balance; all organisation keys share credits.</p><label className="field-label">Refresh balance from Sarvam Billing<input inputMode="decimal" value={creditBalance} onChange={e=>setCreditBalance(e.target.value)} placeholder="Credits Left, e.g. 598.12"/></label><button className="button secondary small" disabled={busy||!/^\d+(?:\.\d{1,2})?$/.test(creditBalance)} onClick={()=>perform(()=>api('/admin/sarvam/credit-balance',{method:'POST',body:JSON.stringify({credits:creditBalance})}),'Balance snapshot saved; the local cap still applies')}>Record current balance</button></div></div></section>
            <section className="panel spaced"><div className="section-head"><div><h2>Processing queue</h2><p>Extraction prepares evidence for review. It never publishes a notice.</p></div><span className={'badge '+(processing?.worker_active?'green':'amber')}>{processing?.worker_active?'Processing worker active':'Processing worker offline'}</span></div><div className="topic-chips">{Object.entries(processing?.counts??{}).map(([state,count])=><span key={state}>{titleCase(state)} · {count}</span>)}</div>{processing?.jobs?.length?<div className="processing-list">{(processing?.jobs??[]).map(job=><article className="processing-row" key={job.notice_id}><div><button className="text-button" onClick={()=>{const item=notices.find(n=>n.notice_id===job.notice_id);if(item)openNotice(item)}}>{notices.find(n=>n.notice_id===job.notice_id)?.title??job.notice_id}</button><small>{job.last_error?titleCase(job.last_error):job.status==='COMPLETE'?'Review completed':job.status==='REVIEW_READY'?'Waiting for human source review':'Queued for extraction'} · {job.attempts} processing attempts</small></div><span className={'badge '+(job.status==='REVIEW_READY'?'green':job.status==='HELD'||job.status==='PAUSED'?'amber':'neutral')}>{titleCase(job.status)}</span>{['PAUSED','HELD'].includes(job.status)&&job.attempts<3&&<button className="button secondary small" disabled={busy} onClick={()=>perform(()=>api('/admin/processing/'+job.notice_id+'/retry',{method:'POST'}),'Processing retry queued')}>Retry</button>}</article>)}</div>:<p className="muted">No persisted jobs yet. The backend queues new official-source discoveries.</p>}</section></>}

          {view==='delivery'&&admin&&<section className="panel"><div className="section-head"><h2>Reviewed publications</h2><span className="badge green">Persisted in-app delivery</span></div>{dashboard?.recent_updates?.length?(dashboard.recent_updates??[]).map(update=><article className="update-row" key={update.update_id}><span className="stat-symbol green"><CheckCheck size={21}/></span><div><h3>{cycleName(update.cycle_id)}</h3><p>{update.summary_en.slice(0,160)}{update.summary_en.length>160?'…':''}</p><small>Published {date(update.published_at)} · {update.rule_changes?.length?'Validated rule update':'Informational · no decision assessment'}</small></div><button className="button secondary small" onClick={async()=>{try{setRecipients(await api<Models['RecipientMatch'][]>('/admin/updates/'+update.update_id+'/recipients'))}catch(e){setError((e as Error).message)}}}>View recipients<ArrowUpRight size={14}/></button></article>):<Empty icon={<ArrowUpRight size={26}/>} heading="Nothing published yet" body="Approved notices and their matching recipients will appear here. No delivery rate is estimated."/>}</section>}
        </>}
        <footer className="app-footer"><span><ShieldCheck size={14}/>{DISCLAIMER}</span><span>Source-linked. Human-reviewed. <strong>NiyamPulse.</strong></span></footer>
      </main>
    </div>
    {toast&&<div className="toast" role="status"><CheckCheck size={18}/>{toast}</div>}

    {detail&&<Modal title="Source & publication review" wide onClose={()=>setDetail(null)}><div className="modal-content"><div className="topic-chips"><span>Official-source discovery</span><span>{titleCase(detail.notice.trust)}</span><span>Revision {detail.notice.revision}</span></div><h3 className="detail-title">{detail.notice.title}</h3><p className="muted">{cycleName(detail.notice.cycle_id)} · {(detail.notice.topics??['OTHER']).map(t=>topicLabels[t]).join(', ')}</p>{detail.notice.source_url&&<a className="source-link" href={detail.notice.source_url} target="_blank" rel="noreferrer">Open original source<ExternalLink size={15}/></a>}{detail.source_listing_url&&<a className="source-link" href={detail.source_listing_url} target="_blank" rel="noreferrer">Observed listing<ExternalLink size={15}/></a>}<section className="analysis-panel"><div className="analysis-heading"><div><span className="eyebrow">SARVAM · EVIDENCE FIRST</span><h4>Notice extraction</h4></div>{['NEEDS_REVIEW','QUARANTINED'].includes(detail.notice.review_status)&&<button className="button secondary small" disabled={busy||detail.analysis?.status==='VALIDATED'} onClick={analyzeNotice}>{busy?<LoaderCircle className="spin" size={14}/>:<Activity size={14}/>} {detail.analysis?.status==='VALIDATED'?'Extraction recorded':'Extract with Sarvam'}</button>}</div>{sarvam&&<p className="muted">{titleCase(sarvam.status)} · ₹{(sarvam.reserved_paise/100).toFixed(2)} reserved · {sarvam.budget_limit_paise==null?'no local INR cap (500-credit reserve)':`₹${(sarvam.budget_limit_paise/100).toFixed(2)} local cap`} · {sarvam.requests} admitted operations</p>}{detail.analysis?<><span className={'badge '+(detail.analysis.status==='VALIDATED'?'green':'amber')}>{detail.analysis.status==='VALIDATED'?'Candidate validated · review still required':'Candidate blocked by evidence guard'}</span><p className="muted">{detail.analysis.cache_hit?'Cached Sarvam result':'Recorded Sarvam response'} · {date(detail.analysis.created_at)} · Captured pages {detail.analysis.pages_processed.join(', ')} of {detail.analysis.total_pages}{!detail.analysis.coverage_complete?' · PARTIAL DOCUMENT INPUT':''}</p>{detail.analysis.summary_hi&&<div className="localized-summary" lang="hi"><strong>नियंत्रित हिंदी सारांश</strong><p>{detail.analysis.summary_hi}</p></div>}{(detail.analysis.diagnostics??[]).map(line=><p className="warning-note" key={line}>{line}</p>)}</>:<p className="muted">Extract source-backed facts once per notice. Processing never approves a notice or sends an alert.</p>}</section>{detail.notice.source_url&&new URL(detail.notice.source_url).pathname.toLowerCase().endsWith('.pdf')&&['NEEDS_REVIEW','QUARANTINED'].includes(detail.notice.review_status)&&<div className="ocr-actions"><button className="button secondary small" disabled={busy} onClick={recoverOcr}>{busy?<LoaderCircle className="spin" size={14}/>:<FileText size={14}/>} Recover PDF text with Vision</button><p className="muted">Use for scanned or garbled text. Existing jobs and outputs are reused. Compare recovered text with the original PDF.</p></div>}{detail.notice.requires_rule_validation&&<section className="analysis-panel"><h4>{detail.analysis?.notice_changes?.length?'Rule proposals · human review required':'Held · unsupported or ambiguous requirements'}</h4>{detail.analysis?.notice_changes?.length?detail.analysis.notice_changes.map(change=><div className="rule-proposal" key={change.change_id}><strong>{change.operation} · {titleCase(change.rule_type)}</strong><p>Effective {change.effective_from}{change.target_rule_id?' · Target '+change.target_rule_id:''}</p><pre>{JSON.stringify(change.proposed_rule,null,2)}</pre></div>):<p>These requirements cannot safely change the current rule set. Inspect the source, then quarantine or reject the notice while the ambiguity is resolved.</p>}</section>}{detail.notice.review_status==='APPROVED'&&<NoticeNarration api={api} path={'/admin/notices/'+detail.notice.notice_id+'/audio'}/>}<EvidenceViewer base={'/admin/notices/'+detail.notice.notice_id} pages={(detail.notice.evidence??[]).map(e=>e.page_number)}/><h4>Exact source evidence</h4>{(detail.notice.evidence??[]).map((anchor,index)=><div className="evidence" key={index}><span>PAGE {anchor.page_number} · {detail.notice.processing_mode==='OFFLINE_REPLAY'?'OFFLINE REPLAY':'EXACT SOURCE QUOTE'}</span><pre>{anchor.literal_quote}</pre><code>SHA-256 {anchor.document_sha256}</code></div>)}{[...new Set(detail.notice.diagnostics??[])].map(line=><p className="warning-note" key={line}>{line}</p>)}<p className="modal-disclaimer">{DISCLAIMER}</p>{['NEEDS_REVIEW','QUARANTINED'].includes(detail.notice.review_status)&&<><label className="field-label">Review reason<textarea value={reason} onChange={e=>setReason(e.target.value)} placeholder="Describe the source, cycle and evidence you checked." rows={3}/></label><label className="checkbox-label review-check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I checked the source evidence and exact exam cycle.</label><div className="review-actions"><button className="button secondary" disabled={busy||reason.trim().length<5} onClick={()=>review('REJECT')}>Reject</button><button className="button secondary" disabled={busy||reason.trim().length<5} onClick={()=>review('QUARANTINE')}>Quarantine</button><button className="button primary" disabled={busy||!confirmed||reason.trim().length<5||(detail.notice.requires_rule_validation&&!(detail.analysis?.notice_changes?.length))||detail.analysis?.status==='GUARD_REJECTED'} onClick={()=>review('APPROVE')}>{busy?<LoaderCircle className="spin" size={16}/>:<CheckCheck size={16}/>}Approve & notify matching subscribers</button></div></>}</div></Modal>}

    {inboxItem&&<Modal title="Your exam update" wide onClose={()=>setInboxItem(null)}><div className="modal-content"><span className="badge green">{inboxItem.match.relevance==='GENERAL_UPDATE'?'Informational update':titleCase(inboxItem.match.relevance)}</span><h3 className="detail-title">{inboxItem.notification.headline}</h3><p className="muted">{cycleName(inboxItem.notification.cycle_id)} · {date(inboxItem.notification.created_at)}</p><p>{inboxItem.match.before!=null&&inboxItem.match.after!=null?`${inboxItem.match.before} → ${inboxItem.match.after}. Reviewed rules were evaluated for this historical assessment.`:inboxItem.match.relevance==='POSSIBLE_IMPACT'?'A reviewed rule may affect this exam cycle. An individual outcome has not been established.':'This update matches your exam cycle and selected topics. No eligibility assessment was made.'}</p>{inboxItem.notification.official_source_url&&<a href={inboxItem.notification.official_source_url} target="_blank" rel="noreferrer" className="button primary source-link">Read the original notice<ExternalLink size={15}/></a>}<h4>{inboxItem.notification.language==='hi'?'Controlled Hindi overview':'Source-backed overview'}</h4><div className="localized-summary" lang={inboxItem.notification.language}><p>{inboxItem.notification.body}</p></div><ImpactDetail match={inboxItem.match}/><NoticeNarration api={api} path={'/me/notifications/'+inboxItem.notification.notification_id+'/audio'}/><EvidenceViewer base={'/me/notifications/'+inboxItem.notification.notification_id} pages={inboxItem.notification.evidence.map(e=>e.page_number)}/><h4>Original source evidence</h4>{inboxItem.notification.evidence.map((anchor,index)=><div className="evidence" key={index}><span>PAGE {anchor.page_number}</span><pre>{anchor.literal_quote}</pre></div>)}<p className="modal-disclaimer">{inboxItem.notification.disclaimer}</p></div></Modal>}

    {showProfile&&profile&&<Modal title="Account & preferences" onClose={()=>setShowProfile(false)}><div className="modal-content"><AccountSettings session={session} profile={profile} api={api} onSaved={setProfile} onLogout={onLogout}/></div></Modal>}

    {recipients&&<Modal title="Persisted recipient matches" onClose={()=>setRecipients(null)}><div className="modal-content"><p className="muted">Pseudonymous account IDs only. Matching is deterministic by cycle and topic.</p>{recipients.length?recipients.map(match=><div className="recipient-row" key={match.match_id}><span className="avatar">{match.user_id.includes('school')?'SL':'EL'}</span><span><strong>{match.user_id}</strong><small>{titleCase(match.relevance)}</small></span><CheckCheck size={17}/></div>):<Empty icon={<Users size={24}/>} heading="No matching subscribers" body="The notice was published, but no active cycle/topic subscription matched."/>}</div></Modal>}
  </div>
}
