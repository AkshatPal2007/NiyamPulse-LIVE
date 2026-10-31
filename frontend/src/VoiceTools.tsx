import { useEffect, useRef, useState } from 'react'
import { Mic, Square, Volume2, LoaderCircle, Search } from 'lucide-react'
import type { components } from './generated/api'
type Models = components['schemas']
type Api = <T>(path: string, options?: RequestInit) => Promise<T>

function pcmWav(chunks: Float32Array[], rate: number) {
  const input = new Float32Array(chunks.reduce((sum, c) => sum + c.length, 0)); let at = 0
  for (const chunk of chunks) { input.set(chunk, at); at += chunk.length }
  const count = Math.min(25 * 16000, Math.floor(input.length * 16000 / rate)); const data = new ArrayBuffer(44 + count * 2); const view = new DataView(data)
  const word = (offset: number, value: string) => [...value].forEach((char, i) => view.setUint8(offset + i, char.charCodeAt(0)))
  word(0, 'RIFF'); view.setUint32(4, 36 + count * 2, true); word(8, 'WAVE'); word(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); word(36, 'data'); view.setUint32(40, count * 2, true)
  for (let i = 0; i < count; i++) { const position = i * rate / 16000; const n = Math.floor(position); const sample = (input[n] ?? 0) * (1 - (position - n)) + (input[n + 1] ?? 0) * (position - n); view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, sample)) * 32767, true) }
  return new Blob([data], { type: 'audio/wav' })
}

export function VoiceSearch({ api, onSearch }: { api: Api; onSearch: (query: string, examId?: string) => void }) {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const stopRef = useRef<(() => void) | null>(null)
  const recogRef = useRef<any>(null)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      stopRef.current?.()
      recogRef.current?.stop?.()
    }
  }, [])

  async function handleAudioUpload(clip: Blob) {
    setBusy(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', clip, 'query.wav')
      const result = await api<Models['VoiceSearchResult']>('/me/voice-search', { method: 'POST', body: form })
      if (result.transcript) {
        setTranscript(result.transcript)
        onSearch(result.transcript, result.exam_ids?.[0])
      }
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      if (alive.current) setBusy(false)
    }
  }

  function startWebSpeech(SpeechRecog: any) {
    try {
      const recog = new SpeechRecog()
      recogRef.current = recog
      recog.lang = 'hi-IN'
      recog.continuous = false
      recog.interimResults = true
      recog.maxAlternatives = 1
      let finalSpeech = ''

      recog.onresult = (event: any) => {
        let interim = ''
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalSpeech += event.results[i][0].transcript
          } else {
            interim += event.results[i][0].transcript
          }
        }
        const text = finalSpeech || interim
        if (text && alive.current) setTranscript(text)
      }

      recog.onerror = (event: any) => {
        if (event.error !== 'no-speech' && alive.current) {
          setError('Speech recognition issue: ' + event.error + '. You can type your query below.')
        }
        if (alive.current) setRecording(false)
      }

      recog.onend = () => {
        if (alive.current) {
          setRecording(false)
          if (finalSpeech.trim()) {
            onSearch(finalSpeech.trim())
          }
        }
      }

      recog.start()
      setRecording(true)
      setSeconds(0)
      const started = performance.now()
      const timer = window.setInterval(() => {
        if (alive.current) setSeconds(Math.floor((performance.now() - started) / 1000))
      }, 250)

      stopRef.current = () => {
        window.clearInterval(timer)
        try { recog.stop() } catch (_) { }
        if (alive.current) setRecording(false)
        stopRef.current = null
      }
      return true
    } catch (_) {
      return false
    }
  }

  async function startNativeRecord() {
    let stream: MediaStream | undefined, context: AudioContext | undefined
    const release = () => { stream?.getTracks().forEach(track => track.stop()); void context?.close().catch(() => { }) }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!alive.current) { release(); return }
      const activeContext = new AudioContext(); context = activeContext; await activeContext.resume()
      if (!alive.current) { release(); return }
      const source = activeContext.createMediaStreamSource(stream), processor = activeContext.createScriptProcessor(4096, 1, 1), chunks: Float32Array[] = []
      processor.onaudioprocess = event => chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)))
      source.connect(processor); processor.connect(activeContext.destination)
      let active = true; const started = performance.now()
      const timer = window.setInterval(() => { if (alive.current) setSeconds(Math.floor((performance.now() - started) / 1000)) }, 250)
      const timeout = window.setTimeout(() => stopRef.current?.(), 15000)
      stopRef.current = () => {
        if (!active) return
        active = false
        window.clearInterval(timer)
        window.clearTimeout(timeout)
        processor.disconnect()
        source.disconnect()
        release()
        if (alive.current) {
          setRecording(false)
          const clip = pcmWav(chunks, activeContext.sampleRate)
          void handleAudioUpload(clip)
        }
        stopRef.current = null
      }
      setSeconds(0); setRecording(true)
    } catch (reason) {
      release()
      if (alive.current) {
        setError(!window.isSecureContext ? 'Microphone needs HTTPS or localhost.' : (reason as DOMException).name === 'NotFoundError' ? 'No microphone was found.' : 'Microphone access was blocked. Allow Microphone permissions, or use typed search below.')
      }
    }
  }

  function toggleVoice() {
    setError('')
    if (recording) {
      stopRef.current?.()
      return
    }
    setTranscript('')
    const SpeechRecog = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (SpeechRecog) {
      const ok = startWebSpeech(SpeechRecog)
      if (ok) return
    }
    void startNativeRecord()
  }

  return <section className="voice-search">
    <div>
      <span className="eyebrow">VOICE SEARCH</span>
      <h3>Tap, say your exam query, and search.</h3>
      <p>Tap the mic, ask in Hindi, Hinglish or English (e.g., “JEE Main registration last date”), and tap stop to search immediately.</p>
    </div>
    <div className="voice-controls">
      <button
        className={'button ' + (recording ? 'primary' : 'secondary') + ' small'}
        disabled={busy}
        onClick={toggleVoice}
        aria-label={recording ? 'Stop and search' : 'Tap to speak'}
      >
        {busy ? <LoaderCircle className="spin" size={16} /> : recording ? <Square size={16} /> : <Mic size={16} />}
        {busy ? 'Searching...' : recording ? `Stop & Search (${seconds}s)` : 'Tap to speak'}
      </button>
    </div>
    {error && <p role="alert" className="voice-error">{error}</p>}
    {transcript && <div className="voice-transcript">
      <span className="eyebrow">{recording ? 'LISTENING...' : 'SEARCHING FOR'}</span>
      <p>“{transcript}”</p>
    </div>}
  </section>
}

export function NoticeNarration({ api, path }: { api: Api; path: string }) {
  const [audio, setAudio] = useState<Models['NoticeAudio'] | null>(null), [url, setUrl] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  useEffect(() => () => { if (url) URL.revokeObjectURL(url) }, [url])
  async function generate() { setBusy(true); setError(''); try { const result = await api<Models['NoticeAudio']>(path, { method: 'POST' }); const raw = Uint8Array.from(atob(result.audio_base64), c => c.charCodeAt(0)); setUrl(URL.createObjectURL(new Blob([raw], { type: 'audio/wav' }))); setAudio(result) } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) } }
  return <section className="narration"><div className="section-head"><h4>Listen to this source-backed update</h4><button className="button secondary small" disabled={busy} onClick={() => void generate()}>{busy ? <LoaderCircle className="spin" size={15} /> : <Volume2 size={15} />} {audio ? 'Load audio again' : 'Generate audio · Sarvam'}</button></div><p className="muted">Audio reads the reviewed summary. Check dates and requirements against the written update and official notice.</p>{error && <p role="alert" className="voice-error">{error} The written overview remains available.</p>}{audio && <><audio controls src={url} aria-label="Reviewed notice narration" /><span className="eyebrow">{audio.cache_hit ? 'CACHED AUDIO' : 'BULBUL V4 FLASH · GENERATED AUDIO'}</span><details><summary>Exact text sent for speech</summary><p>{audio.text}</p></details></>}</section>
}
