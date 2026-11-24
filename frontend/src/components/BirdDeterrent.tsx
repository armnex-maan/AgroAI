import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Icon } from "./Icon";
import { dateTime } from "../lib/it";

const API = import.meta.env.VITE_API_URL || "";

type Src = { title: string; url: string };
type Profile = {
  name: string; examples: string; sound_efficacy: "buona" | "media" | "bassa";
  best_band_hz: [number, number]; audible_band_hz: [number, number];
  hearing: string; predator: string; when: string; notes: string; sources: Src[];
};
type Clip = {
  id: string; target: string; kind: "alarm_call" | "predator_call"; scientific_name: string;
  recordist: string; country: string; licence: string; source_url: string;
};
type Guide = {
  profiles: Record<string, Profile>;
  methods: { name: string; evidence: string; tone: string; text: string; sources: Src[] }[];
  legal: { text: string; sources: Src[] };
  library: Clip[];
};
type Program = {
  target: string; sound_type: string; recording_id: null; f_lo: number; f_hi: number;
  windows: { start: string; end: string }[]; plays_per_hour: number; clip_seconds: number;
  random_intervals: boolean; trigger_on_detection: boolean;
};
type Deterrent = { id: string; name: string; program: Program; log: { ts: string; reason: string }[] };

const IT_NAME: Record<string, string> = {
  "Passer italiae": "Passera d'Italia", "Passer domesticus": "Passera europea", "Passer montanus": "Passera mattugia",
  "Accipiter nisus": "Sparviero", "Sturnus vulgaris": "Storno", "Falco peregrinus": "Falco pellegrino",
  "Astur gentilis": "Astore", "Corvus cornix": "Cornacchia grigia",
};
const ALARM_OF: Record<string, string> = { sparrows: "dei passeri", starlings: "degli storni", corvids: "delle cornacchie" };
const EFFICACY = { buona: { label: "Buona", cls: "ok" }, media: { label: "Media", cls: "warn" }, bassa: { label: "Bassa", cls: "bad" } };
const SOUND_OPTIONS = [
  { id: "mix", label: "Mix consigliato (allarme + predatore)" },
  { id: "alarm_call", label: "Solo grido d'allarme" },
  { id: "predator_call", label: "Solo verso del predatore" },
  { id: "tones", label: "Toni artificiali (poco efficaci)" },
];
const SLOTS = [
  { id: "dawn", label: "Alba", icon: "sunrise", start: "05:30", end: "08:30" },
  { id: "noon", label: "Giorno", icon: "sun", start: "11:30", end: "13:30" },
  { id: "dusk", label: "Tramonto", icon: "sunset", start: "17:30", end: "19:30" },
];
const nameOf = (c: Clip) => IT_NAME[c.scientific_name] ?? c.scientific_name;

/** One shared player, so starting a sound stops the previous one. */
function usePlayer() {
  const ref = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  useEffect(() => () => ref.current?.pause(), []);
  const play = (src: string, key: string) => {
    ref.current?.pause();
    const a = new Audio(src);
    a.onended = () => setPlaying(null);
    ref.current = a;
    a.play();
    setPlaying(key);
  };
  const waiter = useRef<(() => void) | null>(null);
  const stop = () => { ref.current?.pause(); setPlaying(null); waiter.current?.(); waiter.current = null; };
  /** Plays and resolves when the sound ends (or is stopped). */
  const playAndWait = (src: string, key: string) => new Promise<void>((resolve) => {
    ref.current?.pause();
    waiter.current?.();
    const a = new Audio(src);
    const done = () => { waiter.current = null; resolve(); };
    waiter.current = done;
    a.onended = done;
    a.onerror = done;
    ref.current = a;
    setPlaying(key);
    a.play().catch(done);
  });
  return { play, stop, playAndWait, playing };
}

export default function BirdDeterrent() {
  const guide = useQuery({ queryKey: ["deterrent-guide"], queryFn: () => api.get<Guide>("/api/v1/deterrent/guide") });
  const [target, setTarget] = useState("sparrows");
  const player = usePlayer();
  const g = guide.data;
  if (!g) return <div className="card muted">Caricamento…</div>;
  const clipsOf = (t: string) => g.library.filter((c) => c.target === t);

  return (
    <div className="stack">
      <div className="card">
        <h3><Icon name="volume" />Quale suono usare per ogni uccello</h3>
        <div className="sound-table">
          <div className="st-head">
            <span>Uccello</span><span>Grido d'allarme</span><span>Predatore</span><span>Efficacia</span>
          </div>
          {Object.entries(g.profiles).map(([k, p]) => {
            const clips = clipsOf(k);
            const alarm = clips.find((c) => c.kind === "alarm_call");
            const pred = clips.find((c) => c.kind === "predator_call");
            const eff = EFFICACY[p.sound_efficacy];
            return (
              <button key={k} className={`st-row ${target === k ? "on" : ""}`} onClick={() => { setTarget(k); player.stop(); }}>
                <span className="st-bird"><Icon name="bird" size={18} /><b>{p.name}</b></span>
                <span data-label="Grido d'allarme">{alarm ? nameOf(alarm) : <i className="muted">non utile</i>}</span>
                <span data-label="Predatore">{pred ? nameOf(pred) : "—"}</span>
                <span data-label="Efficacia"><span className={`badge badge-${eff.cls}`}>{eff.label}</span></span>
              </button>
            );
          })}
        </div>
      </div>

      <SoundSet key={target} target={target} profile={g.profiles[target]} clips={clipsOf(target)} player={player} />
      <Schedule key={`s-${target}`} target={target} profile={g.profiles[target]}
                hasAlarm={clipsOf(target).some((c) => c.kind === "alarm_call")} />

      <div className="facts">
        <span className="fact ok"><Icon name="net" size={14} />Le reti sono il metodo più sicuro</span>
        <span className="fact ok"><Icon name="shuffle" size={14} />Suoni diversi a orari casuali</span>
        <span className="fact bad"><Icon name="ban" size={14} />Gli ultrasuoni non funzionano</span>
      </div>

      <Devices profiles={g.profiles} />
      <MoreInfo guide={g} profile={g.profiles[target]} />
    </div>
  );
}

function SoundSet({ target, profile, clips, player }: {
  target: string; profile: Profile; clips: Clip[]; player: ReturnType<typeof usePlayer>;
}) {
  const alarm = clips.filter((c) => c.kind === "alarm_call");
  const pred = clips.filter((c) => c.kind === "predator_call");
  const [now, setNow] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [minutes, setMinutes] = useState(5);
  const [mode, setMode] = useState<"waves" | "continuous">("waves");
  const [pauseUntil, setPauseUntil] = useState<number | null>(null);
  const [endsAt, setEndsAt] = useState<number | null>(null);
  const [count, setCount] = useState(0);
  const [, tick] = useState(0);
  const run = useRef(0);

  useEffect(() => {
    if (!endsAt) return;
    const t = setInterval(() => tick((x) => x + 1), 500);
    return () => clearInterval(t);
  }, [endsAt]);
  useEffect(() => () => { run.current++; }, []);

  const fetchClip = async () => {
    const r = await fetch(`${API}/api/v1/deterrent/preview`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target, sound_type: alarm.length ? "mix" : "predator_call", clip_seconds: 5 }),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Errore");
    const info = JSON.parse(decodeURIComponent(r.headers.get("X-Sound") ?? "%7B%7D"));
    return {
      url: URL.createObjectURL(await r.blob()),
      label: `${IT_NAME[info.scientific_name] ?? ""} — ${info.kind === "alarm_call" ? "grido d'allarme" : "predatore"}`,
    };
  };

  const stopSession = () => { run.current++; setEndsAt(null); setPauseUntil(null); player.stop(); setNow(null); };

  /**
   * Natural distress calls are short series of notes (< 5 s) separated by silence (Conover 1994),
   * so clips are 5 s with 0.5–2 s gaps. "waves": 20–30 s bursts, then 1–3 min of silence — birds
   * habituate faster to constant playback. "continuous": no long pauses, for birds on the field now.
   */
  const startSession = async () => {
    const id = ++run.current;
    const end = Date.now() + minutes * 60_000;
    const alive = () => run.current === id && Date.now() < end;
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
    setEndsAt(end); setCount(0); setErr(null); setBusy(true); setPauseUntil(null);
    let lock: any = null;
    try { lock = await (navigator as any).wakeLock?.request("screen"); } catch { /* not supported */ }
    try {
      let next = fetchClip();
      while (alive()) {
        const burstEnd = mode === "waves" ? Date.now() + (20 + Math.random() * 10) * 1000 : end;
        while (alive() && Date.now() < burstEnd) {
          const clip = await next;
          setBusy(false);
          if (run.current !== id) break;
          next = fetchClip(); // prepare the following sound while this one plays
          setNow(clip.label);
          await player.playAndWait(clip.url, "mix");
          URL.revokeObjectURL(clip.url);
          setCount((c) => c + 1);
          if (run.current !== id) break;
          await sleep(500 + Math.random() * 1500);
        }
        if (mode === "waves" && alive()) {
          const until = Math.min(end, Date.now() + (60 + Math.random() * 120) * 1000);
          setNow(null); setPauseUntil(until);
          while (run.current === id && Date.now() < until) await sleep(250);
          setPauseUntil(null);
        }
      }
      next.catch(() => undefined);
    } catch (e: any) { setErr(String(e.message ?? e)); }
    finally {
      lock?.release?.().catch?.(() => undefined);
      if (run.current === id) { setEndsAt(null); setPauseUntil(null); setNow(null); player.stop(); }
      setBusy(false);
    }
  };

  const left = endsAt ? Math.max(0, Math.round((endsAt - Date.now()) / 1000)) : 0;
  const mmss = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  const progress = endsAt ? 100 - (left / (minutes * 60)) * 100 : 0;
  const pauseLeft = pauseUntil ? Math.max(0, Math.round((pauseUntil - Date.now()) / 1000)) : 0;
  const fmt = (t: number) => `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;

  const clipButtons = (list: Clip[]) => list.map((c) => {
    const same = list.filter((x) => x.scientific_name === c.scientific_name);
    const on = player.playing === c.id;
    return (
      <button key={c.id} className={`clip ${on ? "on" : ""}`} aria-label={`Ascolta ${nameOf(c)}`} title={`Registrazione di ${c.recordist} (${c.country})`}
              onClick={() => { if (endsAt) stopSession(); if (on) player.stop(); else { player.play(`${API}/api/v1/deterrent/library/${c.id}.ogg`, c.id); setNow(null); } }}>
        <Icon name={on ? "pause" : "play"} size={12} />
        {nameOf(c)}{same.length > 1 ? ` ${same.indexOf(c) + 1}` : ""}
      </button>
    );
  });

  return (
    <div className="card">
      <div className="mix-head">
        <button className={`play-big ${endsAt ? "running" : ""} ${busy ? "busy" : ""}`}
                onClick={() => (endsAt ? stopSession() : startSession())}
                aria-label={endsAt ? "Ferma" : `Avvia per ${minutes} ${minutes === 1 ? "minuto" : "minuti"}`}
                style={endsAt ? { ["--p" as any]: `${progress}%` } : undefined}>
          <Icon name={endsAt ? "stop" : "play"} size={30} />
        </button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="tiny muted">Suoni per allontanare i {profile.name.toLowerCase()}</div>
          {endsAt ? (
            <>
              <div className="mix-title">In riproduzione · restano {mmss}</div>
              <div className="small muted">
                {pauseUntil ? `Pausa di silenzio · prossima ondata tra ${fmt(pauseLeft)}` : (now ?? "Preparo il suono…")} · {count} suoni
              </div>
            </>
          ) : (
            <>
              <div className="mix-title">Fai suonare per</div>
              <div className="duration-row">
                {[1, 5, 10, 15, 30].map((m) => (
                  <button key={m} className={`dur ${minutes === m ? "on" : ""}`} onClick={() => setMinutes(m)}>{m} min</button>
                ))}
              </div>
              <div className="duration-row" role="radiogroup" aria-label="Modo">
                <button className={`dur ${mode === "waves" ? "on" : ""}`} onClick={() => setMode("waves")}>
                  <Icon name="wave" size={12} /> A ondate (consigliato)
                </button>
                <button className={`dur ${mode === "continuous" ? "on" : ""}`} onClick={() => setMode("continuous")}>
                  <Icon name="volume" size={12} /> Continuo
                </button>
              </div>
              <div className="tiny muted" style={{ marginTop: 4 }}>
                {mode === "waves"
                  ? "20–30 secondi di richiami, poi 1–3 minuti di silenzio: si abituano più lentamente."
                  : "Senza pause lunghe: usalo solo quando gli uccelli sono sul campo adesso."}
              </div>
            </>
          )}
        </div>
      </div>
      {endsAt && <div className="session-bar"><span style={{ width: `${progress}%` }} /></div>}
      {endsAt && <div className="tiny muted" style={{ marginTop: 6 }}>Tieni aperta questa pagina e il volume alto.</div>}
      {err && <div className="small" style={{ color: "var(--danger)" }}>{err}</div>}

      <div className="sound-steps">
        <div className={`sound-step ${alarm.length ? "" : "disabled"}`}>
          <div className="step-icon"><Icon name="megaphone" size={18} /></div>
          <div className="step-body">
            <b>1 · Grido d'allarme {ALARM_OF[target] ?? ""}</b>
            <div className="small muted">
              {alarm.length ? "È il segnale che si scambiano quando c'è un pericolo: scappano subito."
                : "Non utile per questa specie: reagisce poco ai richiami."}
            </div>
            {!!alarm.length && <div className="clips">{clipButtons(alarm)}</div>}
          </div>
        </div>
        <div className="sound-step">
          <div className="step-icon"><Icon name="eye" size={18} /></div>
          <div className="step-body">
            <b>2 · Verso del predatore: {pred[0] ? nameOf(pred[0]).toLowerCase() : profile.predator}</b>
            <div className="small muted">Il rapace che li caccia: sentirlo li mette in fuga.</div>
            <div className="clips">{clipButtons(pred)}</div>
          </div>
        </div>
        <div className="sound-step tip">
          <div className="step-icon"><Icon name="bulb" size={18} /></div>
          <div className="step-body small">
            <div>{profile.notes}</div>
            <div><b>Più efficace:</b> metti un rapace finto vicino all'altoparlante e spostalo ogni pochi giorni.</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Schedule({ target, profile, hasAlarm }: { target: string; profile: Profile; hasAlarm: boolean }) {
  const qc = useQueryClient();
  const [sound, setSound] = useState(hasAlarm ? "mix" : "predator_call");
  const [band, setBand] = useState<[number, number]>(profile.best_band_hz);
  const [slots, setSlots] = useState<string[]>(["dawn", "dusk"]);
  const [perHour, setPerHour] = useState(4);
  const [onDetect, setOnDetect] = useState(true);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => api.post("/api/v1/deterrent/devices", {
      name: `Dissuasore ${profile.name.toLowerCase()}`,
      program: {
        target, sound_type: sound, recording_id: null, f_lo: band[0], f_hi: band[1],
        windows: SLOTS.filter((s) => slots.includes(s.id)).map(({ start, end }) => ({ start, end })),
        plays_per_hour: perHour, clip_seconds: 4, random_intervals: true, trigger_on_detection: onDetect,
      },
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deterrents"] });
      setSaved(true); setErr(null); setTimeout(() => setSaved(false), 2500);
    },
    onError: (e: any) => setErr(String(e.message ?? e)),
  });

  return (
    <div className="card">
      <h3><Icon name="clock" />Programma automatico</h3>
      <div className="grid cols-2" style={{ gap: 18 }}>
        <div className="stack" style={{ gap: 10 }}>
          <label className="small muted">Suono da usare</label>
          <select value={sound} onChange={(e) => setSound(e.target.value)}>
            {SOUND_OPTIONS.filter((o) => hasAlarm || (o.id !== "mix" && o.id !== "alarm_call")).map((o) => (
              <option key={o.id} value={o.id}>{o.label}</option>
            ))}
          </select>
          {sound === "tones" && (
            <div>
              <div className="row small"><span>{band[0]} Hz</span><span className="spacer" /><span>{band[1]} Hz</span></div>
              <div className="row" style={{ gap: 8 }}>
                <input type="range" min={profile.audible_band_hz[0]} max={profile.audible_band_hz[1]} step={100} value={band[0]}
                       onChange={(e) => setBand([Math.min(+e.target.value, band[1] - 200), band[1]])} style={{ flex: 1 }} />
                <input type="range" min={profile.audible_band_hz[0]} max={profile.audible_band_hz[1]} step={100} value={band[1]}
                       onChange={(e) => setBand([band[0], Math.max(+e.target.value, band[0] + 200)])} style={{ flex: 1 }} />
              </div>
            </div>
          )}
          <label className="small muted">Fasce orarie</label>
          <div className="slot-row">
            {SLOTS.map((s) => (
              <button key={s.id} className={`slot ${slots.includes(s.id) ? "on" : ""}`}
                      onClick={() => setSlots(slots.includes(s.id) ? slots.filter((x) => x !== s.id) : [...slots, s.id])}>
                <Icon name={s.icon} size={18} /><span>{s.label}</span><span className="tiny muted">{s.start}–{s.end}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="stack" style={{ gap: 10 }}>
          <label className="row small"><span className="muted">Riproduzioni all'ora</span><span className="spacer" /><b style={{ fontSize: 16 }}>{perHour}</b></label>
          <input type="range" min={1} max={12} value={perHour} onChange={(e) => setPerHour(+e.target.value)} style={{ width: "100%" }} />
          <label className="toggle">
            <input type="checkbox" checked={onDetect} onChange={(e) => setOnDetect(e.target.checked)} />
            <span className="knob" /> Suona anche quando AGROAI li sente
          </label>
          <button className="btn" style={{ width: "100%", marginTop: 6 }} onClick={() => save.mutate()}
                  disabled={save.isPending || !slots.length}>
            <Icon name={saved ? "check" : "shield"} size={15} />{saved ? "Dissuasore attivato" : "Attiva dissuasore"}
          </button>
          <div className="tiny muted row" style={{ justifyContent: "center", gap: 6 }}>
            <Icon name="lock" size={12} />Simulato: nel campo non suona nulla
          </div>
          {err && <div className="small" style={{ color: "var(--danger)" }}>{err}</div>}
        </div>
      </div>
    </div>
  );
}

function Devices({ profiles }: { profiles: Record<string, Profile> }) {
  const qc = useQueryClient();
  const devices = useQuery({ queryKey: ["deterrents"], queryFn: () => api.get<Deterrent[]>("/api/v1/deterrent/devices") });
  const [planFor, setPlanFor] = useState<string | null>(null);
  const plan = useQuery({
    queryKey: ["deterrent-plan", planFor], enabled: !!planFor,
    queryFn: () => api.get<{ times: string[] }>(`/api/v1/deterrent/devices/${planFor}/plan`),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["deterrents"] });
  const test = useMutation({ mutationFn: (id: string) => api.post(`/api/v1/deterrent/devices/${id}/test`), onSuccess: refresh });
  const del = useMutation({ mutationFn: (id: string) => api.del(`/api/v1/deterrent/devices/${id}`), onSuccess: refresh });
  const list = devices.data ?? [];
  if (!list.length) return null;
  const soundName = (t: string) => SOUND_OPTIONS.find((o) => o.id === t)?.label.split(" (")[0] ?? t;

  return (
    <div className="card">
      <h3><Icon name="shield" />I tuoi dissuasori</h3>
      <div className="stack" style={{ gap: 8 }}>
        {list.map((d) => (
          <div key={d.id} className="device-row">
            <span className="dot-live" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <b>{d.name}</b>
              <div className="tiny muted">
                {profiles[d.program.target]?.name} · {soundName(d.program.sound_type)} · {d.program.plays_per_hour}/ora
                {" · "}{d.program.windows.map((w) => w.start).join(", ")}
                {d.log[0] && <> · ultima: {dateTime(d.log[0].ts)}</>}
              </div>
              {planFor === d.id && plan.data && (
                <div className="row" style={{ gap: 4, marginTop: 6 }}>
                  {plan.data.times.map((t, i) => <span key={i} className="chip tiny">{t}</span>)}
                </div>
              )}
            </div>
            <button className="icon-btn" title="Prova simulata" onClick={() => test.mutate(d.id)}><Icon name="play" size={14} /></button>
            <button className="icon-btn" title="Orari di oggi" onClick={() => setPlanFor(planFor === d.id ? null : d.id)}><Icon name="clock" size={15} /></button>
            <button className="icon-btn" title="Elimina"
                    onClick={() => { if (confirm(`Eliminare «${d.name}»?`)) del.mutate(d.id); }}><Icon name="trash" size={15} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}

function MoreInfo({ guide, profile }: { guide: Guide; profile: Profile }) {
  const credits = guide.library.filter((c, i, a) => a.findIndex((x) => x.id === c.id) === i);
  return (
    <details className="card more">
      <summary><Icon name="book" size={15} />Come funziona, regole e crediti</summary>
      <div className="stack" style={{ marginTop: 12 }}>
        <div className="small"><b>{profile.name}:</b> {profile.hearing} {profile.when}</div>
        <div className="grid cols-2" style={{ gap: 8 }}>
          {guide.methods.map((m) => (
            <div key={m.name} className={`method ${m.tone}`}>
              <b className="small">{m.name}</b> <span className="tiny muted">— {m.evidence}</span>
              <div className="tiny" style={{ color: "var(--text-2)", marginTop: 2 }}>{m.text}</div>
            </div>
          ))}
        </div>
        <div className="small">{guide.legal.text}</div>
        <div className="tiny muted">
          Registrazioni reali da xeno-canto ({credits[0]?.licence}), verificate con l'AI. Autori:{" "}
          {credits.map((c, i) => (
            <span key={c.id}>{i > 0 && ", "}<a href={c.source_url} target="_blank" rel="noreferrer">{c.recordist} ({c.id})</a></span>
          ))}.
        </div>
        <div className="tiny muted">
          Fonti: {[...profile.sources, ...guide.methods.flatMap((m) => m.sources), ...guide.legal.sources]
            .filter((s, i, a) => a.findIndex((x) => x.url === s.url) === i)
            .map((s, i) => <span key={s.url}>{i > 0 && " · "}<a href={s.url} target="_blank" rel="noreferrer">{s.title}</a></span>)}
        </div>
      </div>
    </details>
  );
}
