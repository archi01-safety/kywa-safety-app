"use client";
import { useEffect, useRef, useState } from "react";

export type AuthSession = { active: boolean; server_time: number; expires_at: number | null; remaining_seconds: number };

export function SessionClock({ status, expired, onExpire, onExtend, onLogin }: {
  status?: AuthSession | null; expired: boolean; onExpire: () => void; onExtend: () => Promise<void>; onLogin: () => void;
}) {
  const [remaining, setRemaining] = useState(status?.remaining_seconds || 0);
  const [extending, setExtending] = useState(false);
  const expire = useRef(onExpire); expire.current = onExpire;
  useEffect(() => {
    if (!status?.active) { setRemaining(0); return; }
    const deadline = Date.now() + Math.max(0, (status.expires_at || 0) - status.server_time) * 1000;
    let notified = false;
    const tick = () => { const n = Math.max(0, Math.ceil((deadline-Date.now())/1000)); setRemaining(n); if (!n && !notified) { notified=true; expire.current(); } };
    tick(); const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [status]);
  if (!status?.active && !expired) return null;
  const ended = expired || !remaining;
  return <div className={`session-clock ${ended ? "expired" : remaining <= 300 ? "ending" : ""}`}>
    {ended ? <><span role="status">로그인 만료</span><button type="button" onClick={onLogin}>다시 로그인</button></> : <>
      <span className="session-clock-label">로그인 남은 시간</span><time aria-label="로그인 남은 시간">{String(Math.floor(remaining/60)).padStart(2,"0")}:{String(remaining%60).padStart(2,"0")}</time>
      <button type="button" disabled={extending} onClick={async () => { setExtending(true); try { await onExtend(); } finally { setExtending(false); } }}>연장</button>
    </>}
  </div>;
}
