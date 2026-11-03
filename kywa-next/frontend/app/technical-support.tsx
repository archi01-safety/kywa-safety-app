"use client";
import { useEffect, useRef } from "react";
import { Mail, Phone, ShieldCheck, X } from "lucide-react";

export function TechnicalSupport() {
  return <section className="technical-support" aria-label="KYWA 기술지원">
    <ShieldCheck size={16} aria-hidden="true" />
    <div><strong>KYWA AI 위험성평가 시스템<br />기술지원 사업</strong>
      <p>한국청소년활동진흥원이 시스템 구축과 운영을 지원합니다.</p></div>
  </section>;
}

export function DeveloperDialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog=ref.current, previous=document.activeElement as HTMLElement | null;
    dialog?.showModal();
    return () => { dialog?.close(); if (previous?.isConnected) previous.focus(); };
  }, []);
  return <dialog ref={ref} className="developer-dialog" aria-labelledby="developer-title"
    onCancel={e => { e.preventDefault(); onClose(); }}
    onClick={e => {
      const r=e.currentTarget.getBoundingClientRect();
      if (e.target === e.currentTarget && (e.clientX<r.left || e.clientX>r.right || e.clientY<r.top || e.clientY>r.bottom)) onClose();
    }}>
    <button type="button" autoFocus className="icon-button progress-close" aria-label="개발자정보 닫기" onClick={onClose}><X size={18} /></button>
    <h2 id="developer-title">개발자정보</h2><p>한국청소년활동진흥원</p><strong>경영지원본부 안전경영부</strong>
    <a href="mailto:archi01@kywa.or.kr"><Mail size={17} />archi01@kywa.or.kr</a>
    <a href="tel:0269597138"><Phone size={17} />02-6959-7138</a>
  </dialog>;
}
