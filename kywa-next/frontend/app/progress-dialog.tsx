"use client";
import { useEffect, useRef } from "react";
import { CheckCircle2, LoaderCircle, TriangleAlert, X } from "lucide-react";

export function ProgressDialog({ busy, error, notice, onClose, onRetry, onHome }: {
  busy: string; error: string; notice: string; onClose: () => void; onRetry?: () => void; onHome?: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const success = !busy && !error && !!notice;
  useEffect(() => {
    const target = dialog.current, previous = document.activeElement as HTMLElement | null;
    target?.showModal();
    return () => { target?.close(); if (previous?.isConnected) previous.focus(); };
  }, []);
  useEffect(() => {
    if (!success) return;
    try { navigator.vibrate?.(45); } catch { /* Browser capability is optional. */ }
    const timer = setTimeout(onClose, 1500);
    return () => clearTimeout(timer);
  }, [success, notice, onClose]);
  return <dialog ref={dialog} className={`progress-dialog ${success ? "is-success" : ""}`} aria-labelledby="progress-title"
    onCancel={e => { if (busy) e.preventDefault(); else onClose(); }}>
    {!busy && <button className="icon-button progress-close" aria-label="알림 닫기" onClick={onClose}><X size={18} /></button>}
    <div className="progress-symbol">{busy ? <LoaderCircle className="spin" /> : error ? <TriangleAlert /> : <CheckCircle2 />}</div>
    <h2 id="progress-title">{busy ? "잠시만 기다려 주세요" : error ? "작업을 완료하지 못했습니다" : "완료되었습니다"}</h2>
    <p role={error ? "alert" : "status"} aria-live="polite">{busy || error || notice}</p>
    {busy && <div className="progress-track" aria-hidden="true"><i /></div>}
    {error && <div className="button-row">{onRetry && <button className="button primary" onClick={onRetry}>다시 시도</button>}<button className="button secondary" onClick={onClose}>내용 확인</button></div>}
    {busy && onHome && <button className="text-button" onClick={onHome}>입력 초기화하고 처음으로</button>}
  </dialog>;
}
