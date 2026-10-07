"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDownToLine, ArrowRight, ArrowUpRight, Check, CheckCircle2, ChevronRight, ClipboardCheck, FileBarChart2, FileText, ImagePlus, LayoutDashboard, LoaderCircle, LockKeyhole, LogIn, LogOut, Mail, Phone, Plus, RotateCcw, Search, ShieldCheck, Sparkles, TriangleAlert, X } from "lucide-react";

import { AssessmentResults } from "./assessment-results";
import { PublicOverview } from "./public-overview";
import { Guides } from "./guides";
import { brand } from "./brand";
import { ThemeToggle } from "./theme-toggle";

type User = { name: string; email: string; role: string; facilities: string[] };
type Bootstrap = { mode: string; auth_mode: "google" | "pin"; local_workspace: boolean; csrf: string; user: User | null; facilities: string[]; departments: string[]; policy: string; report_max_rows: number };
type Risk = { p: number; s: number; score: number; grade: string };
type Before = Risk & { category: string; location: string; scenario: string; solution: string; law: string };
type After = Risk & { text: string; actor: string; created_at: string; photo_url?: string };
type Assessment = { id: string; facility: string; department: string; created_at: string; before: Before; after: After | null; photo_url: string; policy: string; status: string; revision: number; current_risk: Risk | null };
type Photo = { id: string; url: string; confirmed: boolean } | null;
type Draft = { draft_id: string; guide_keywords: string[]; items: (Before & { selected: boolean })[] };
type Reassessment = Risk & { draft_id: string; revision: number; rationale: string };
type Filters = { facility: string; department: string; status: string; start: string; end: string };
type History = { id: string; at: string; actor: string; kind: string; text: string; after?: After };
const emptyFilters: Filters = { facility: "", department: "", status: "", start: "", end: "" };
const grades = ["매우 낮음", "낮음", "보통", "약간 높음", "높음", "매우 높음"];
function grade(score: number) { return score <= 3 ? grades[0] : score <= 6 ? grades[1] : score === 8 ? grades[2] : score <= 12 ? grades[3] : score === 15 ? grades[4] : grades[5]; }
function dateText(value: string) { const d = new Date(value); return Number.isNaN(+d) ? value : d.toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit" }); }
function Badge({ value }: { value: string }) { return <span className={`badge tone-${grades.indexOf(value)} ${value === "완료" ? "done" : value === "조치 중" ? "progress" : ""}`}>{value === "완료" && <Check size={12} />}{value}</span>; }
function Score({ value }: { value: Risk }) { return <span className="score"><strong>{value.score}</strong><span>점</span><Badge value={value.grade} /></span>; }
function Empty({ children }: { children: React.ReactNode }) { return <div className="empty"><ClipboardCheck size={32} /><p>{children}</p></div>; }

export default function Home() {
  const [boot, setBoot] = useState<Bootstrap | null>(null);
  const [tab, setTab] = useState("inspect");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [records, setRecords] = useState<Assessment[]>([]);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [selectedId, setSelectedId] = useState("");
  const [facility, setFacility] = useState("중앙");
  const [department, setDepartment] = useState("협력부(국립청소년시설)");
  const [description, setDescription] = useState("");
  const [photo, setPhoto] = useState<Photo>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [revision, setRevision] = useState(0);
  const requests = useRef(new Map<string, string>());
  const csrf = useRef("");
  const running = useRef(false);

  const api = useCallback(async (path: string, body?: object | FormData) => {
    const form = body instanceof FormData;
    const res = await fetch(`/api${path}`, { credentials: "same-origin", cache: "no-store", method: body ? "POST" : "GET", headers: body ? { "X-CSRF-Token": csrf.current, ...(form ? {} : { "Content-Type": "application/json" }) } : {}, body: body ? form ? body : JSON.stringify(body) : undefined });
    if (!res.ok) { if (res.status === 401) { setBoot(current => current ? { ...current, user: null } : current); setRecords([]); setSelectedId(""); } const data = await res.json().catch(() => ({})); throw new Error(typeof data.detail === "string" ? data.detail : "입력 내용을 확인해 주세요." + ` (${res.status})`); }
    return res;
  }, []);
  const bootstrap = useCallback(async () => { const data = await (await api("/bootstrap")).json(); csrf.current = data.csrf; setBoot(data); return data as Bootstrap; }, [api]);
  const run = async (label: string, work: () => Promise<void>) => {
    if (running.current) return;
    running.current = true; setBusy(label); setError(""); setNotice("");
    try { await work(); } catch (e) { setError(e instanceof Error ? e.message : "연결을 확인하고 다시 시도해 주세요."); }
    finally { running.current = false; setBusy(""); }
  };
  const requestId = (scope: string, body: object) => { const key = scope + JSON.stringify(body); if (!requests.current.has(key)) requests.current.set(key, crypto.randomUUID()); return requests.current.get(key)!; };
  useEffect(() => { bootstrap().catch(e => setError(e.message)); if (["inspect", "actions", "reports"].includes(location.hash.slice(1))) setTab(location.hash.slice(1)); if (new URLSearchParams(location.search).has("login_error")) setError("로그인하지 못했습니다. 승인된 Google 계정인지 확인해 주세요."); }, [bootstrap]);
  useEffect(() => {
    if (!boot?.user) return;
    const refresh = () => { void bootstrap().catch(() => {}); };
    const timer = window.setInterval(refresh, 60000);
    window.addEventListener("focus", refresh);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", refresh); };
  }, [boot?.user?.email, bootstrap]);
  useEffect(() => {
    let cancelled = false;
    if (!boot?.user) { setRecords([]); return; }
    api(`/assessments?${new URLSearchParams(filters)}`).then(r => r.json()).then(data => { if (!cancelled) setRecords(data.items); }).catch(e => { if (!cancelled) { setRecords([]); setError(e.message); } });
    return () => { cancelled = true; };
  }, [api, boot?.user?.email, filters, revision]);
  const navigate = (next: string) => { setTab(next); setSelectedId(""); setError(""); setFilters(emptyFilters); history.replaceState(null, "", `/#${next}`); };
  const login = (role: string) => run("로그인 중", async () => { const f = new FormData(); f.set("role", role); await api("/auth/demo", f); await bootstrap(); setRevision(v => v + 1); });
  const loginPin = (pin: string) => run("비밀번호를 확인하고 있습니다", async () => { const f = new FormData(); f.set("pin", pin); await api("/auth/pin", f); await bootstrap(); setRevision(v => v + 1); });
  const upload = async (file: File, update: (p: Photo) => void) => {
    await run("사진을 안전하게 처리하고 있습니다", async () => {
      update(null); if (file.size > 10 * 1024 * 1024) throw new Error("사진은 10MB 이하로 업로드해 주세요.");
      const f = new FormData(); f.set("photo", file); const result = await (await api("/photos/prepare", f)).json(); update({ ...result, confirmed: false });
    });
  };
  const analyze = () => run("AI가 현장 위험요인을 분석하고 있습니다", async () => {
    const f = new FormData(); f.set("facility", facility); f.set("department", department); f.set("description", description); if (photo) f.set("photo_id", photo.id);
    const result = await (await api("/analyses", f)).json(); setDraft({ ...result, items: result.items.map((item: Before) => ({ ...item, selected: true })) });
    setNotice("분석을 완료했습니다. 장소와 위험상황, 감소대책을 검토한 뒤 제출하세요.");
  });
  const submit = () => run("선택한 평가를 제출하고 있습니다", async () => {
    if (!draft) return;
    const body = { draft_id: draft.draft_id, items: draft.items.flatMap((item, index) => item.selected ? [{ index, location: item.location, scenario: item.scenario, solution: item.solution }] : []) };
    const result = await (await api("/assessments", { ...body, request_id: requestId("submit", body) })).json();
    setDraft(null); setDescription(""); setPhoto(null); setRevision(v => v + 1); setNotice(`${result.ids.length}건을 제출했습니다. 담당자가 개선조치를 이어서 진행할 수 있습니다.`);
  });
  const download = (format: string) => run(`${format.toUpperCase()} 보고서를 만들고 있습니다`, async () => {
    const res = await api("/reports", { ...filters, format }); const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a"); a.href = url; a.download = `KYWA_위험성평가_${new Date().toLocaleDateString("sv-SE")}.${format}`; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000); setNotice("보고서를 다운로드했습니다.");
  });
  const selected = records.find(r => r.id === selectedId);
  const completeCount = records.filter(r => r.status === "완료").length;
  const urgentCount = records.filter(r => r.status !== "완료" && (r.after || r.before).score >= 9).length;
  const pendingCount = records.length - completeCount;

  return <div className="app-shell">
    <header className="institution-header"><a className="brand" href="/#inspect" onClick={e => { e.preventDefault(); navigate("inspect"); }}><img src={brand.logo} alt={`${brand.name} ${brand.shortName}`} /><span>SAFETY MANAGEMENT</span></a><div className="topbar-right"><ThemeToggle />{boot?.user && <button className="icon-button mobile-account" aria-label="현재 계정 로그아웃" title={boot.user.name} disabled={!!busy} onClick={() => run("로그아웃 중", async () => { await api("/auth/logout", {}); await bootstrap(); setSelectedId(""); })}><LogOut size={16} /></button>}<span className={`environment ${boot?.mode === "production" ? "live" : ""}`}><i />{!boot ? "연결 중" : boot.mode === "demo" ? "체험 환경" : boot.mode === "development" ? "개발 환경" : "운영 환경"}</span></div></header>
    <aside className="sidebar">

      <div className="workspace-label">안전한 일터, 함께 만드는 변화</div>
      <nav aria-label="주 메뉴">
        <button className={tab === "inspect" ? "active" : ""} onClick={() => navigate("inspect")}><Sparkles size={19} />AI 위험성평가<ChevronRight size={15} /></button>
        <button className={tab === "actions" ? "active" : ""} onClick={() => navigate("actions")}><ClipboardCheck size={19} />개선조치 · 재평가<ChevronRight size={15} /></button>
        <button className={tab === "reports" ? "active" : ""} onClick={() => navigate("reports")}><FileBarChart2 size={19} />결과보고서<ChevronRight size={15} /></button>
      </nav>
      <div className="sidebar-guide"><ShieldCheck size={27} /><strong>작은 발견이<br />더 큰 안전으로.</strong><p>위험요인 발견부터 개선까지<br />현장의 안전을 함께 관리합니다.</p><span>{brand.name}</span></div>
      <div className="account-area">{boot?.user ? <><div className="avatar">{boot.user.name[0]}</div><div><strong>{boot.user.name}</strong><small>{boot.user.role === "admin" ? "관리자" : "시설 담당자"}</small></div><button className="icon-button" aria-label="로그아웃" disabled={!!busy} onClick={() => run("로그아웃 중", async () => { await api("/auth/logout", {}); await bootstrap(); setSelectedId(""); })}><LogOut size={17} /></button></> : <><div className="avatar"><LogIn size={19} /></div><div><strong>현장 참여자</strong><small>누구나 평가를 제출할 수 있어요</small></div></>}</div>
    </aside>
    <div className="main-wrap">
      <div className="breadcrumb-bar"><div><span className="breadcrumb">안전경영</span><ChevronRight size={13} /><strong>{tab === "inspect" ? "AI 위험성평가" : tab === "actions" ? "개선조치 · 재평가" : "결과보고서"}</strong></div></div>
      <main>
        {boot?.mode === "demo" && <div className="demo-banner">{boot.local_workspace ? <><span><strong>로컬 운영 사본 시험</strong> 기존 평가 사본을 사용합니다. 새 AI 분석은 가상 응답이며 변경사항은 이 PC에만 저장됩니다.</span><span>LOCAL</span></> : <><span><strong>미리 보는 새로운 {brand.shortName} Safety</strong> 가상 분석·임시 저장 환경입니다. 실제 업무자료나 개인정보는 입력하지 마세요.</span><span>DEMO</span></>}</div>}
        {(error || notice || busy) && <div className={`message ${error ? "error" : busy ? "loading" : "success"}`} role={error ? "alert" : "status"}>{busy ? <LoaderCircle className="spin" size={19} /> : error ? <TriangleAlert size={19} /> : <CheckCircle2 size={19} />}<span>{error || busy || notice}</span>{!busy && <button aria-label="알림 닫기" className="icon-button" onClick={() => { setError(""); setNotice(""); }}><X size={17} /></button>}</div>}
        {!boot ? <div className="empty"><LoaderCircle className="spin" /><p>안전관리 공간을 준비하고 있습니다.</p><button className="button secondary" onClick={() => bootstrap().catch(e => setError(e.message))}>다시 연결</button></div> : <>
          <div className="page-heading"><div><div className="eyebrow">{brand.shortName} · SMART SAFETY</div><h1>{tab === "inspect" ? "안전은 발견에서 시작됩니다." : tab === "actions" ? "발견한 위험을, 확실한 개선으로." : "우리의 안전, 한눈에 확인하세요."}</h1><p>{tab === "inspect" ? "현장의 사진과 설명을 남겨주세요. AI가 위험요인과 개선 방향을 함께 살펴봅니다." : tab === "actions" ? "접수된 위험요인을 확인하고, 개선조치와 재평가를 기록하세요." : "시설별 위험성평가 현황을 살펴보고 결과보고서를 내려받으세요."}</p></div></div>
          {tab === "inspect" ? <>
            <div className="steps"><div className={!draft ? "current" : "finished"}><span>{draft ? <Check size={15} /> : "01"}</span><strong>현장 정보 입력</strong></div><i /><div className={draft ? "current" : ""}><span>02</span><strong>AI 분석 · 검토</strong></div><i /><div><span>03</span><strong>평가 제출</strong></div></div>
            <div className="inspection-grid">
              <section className="panel input-panel"><div className="panel-heading"><span className="section-number">01</span><h2>현장 정보</h2><span className="muted small">사진 또는 설명 입력</span></div>
                <fieldset disabled={!!busy}><div className="field-row"><label>시설<select value={facility} onChange={e => { setFacility(e.target.value); setDraft(null); }}>{boot.facilities.map(f => <option key={f}>{f}</option>)}</select></label><label>담당 부서<select value={department} onChange={e => { setDepartment(e.target.value); setDraft(null); }}>{boot.departments.map(d => <option key={d}>{d}</option>)}</select></label></div>
                  <label>현장 사진 <span className="optional">선택</span></label><PhotoInput value={photo} disabled={!!busy} onUpload={f => upload(f, p => { setPhoto(p); setDraft(null); })} onChange={p => { setPhoto(p); setDraft(null); }} />
                  <label className="description-label" htmlFor="description">어떤 위험이 있나요?<span className="optional">사진만으로 분석할 수도 있어요</span></label><textarea id="description" rows={5} value={description} maxLength={6000} placeholder="예: 본관 2층 테라스의 난간 고정부가 흔들립니다. 청소년이 기대면 추락할 위험이 있습니다." onChange={e => { setDescription(e.target.value); setDraft(null); }} /><div className="char-count">{description.length.toLocaleString()} / 6,000</div>
                  <button className="button primary full analyze-button" disabled={!!busy || (!description.trim() && !photo) || !!photo && !photo.confirmed} onClick={analyze}><Sparkles size={18} />{draft ? "다시 분석하기" : "AI 위험성 분석하기"}<ArrowRight size={18} /></button>
                </fieldset><p className="privacy-note"><ShieldCheck size={14} />사진의 얼굴·이름 등 개인정보를 확인한 뒤 분석해 주세요.</p>
              </section>

            </div>
            {draft && <section className="results-section"><div className="section-top"><div><div className="eyebrow">REVIEW & SUBMIT</div><h2>AI 분석 결과 <span>{draft.items.length}건</span></h2><p className="muted">제출할 항목을 선택하고 내용을 수정할 수 있습니다. 관련근거는 원문을 확인하세요.</p></div><Badge value="검토 필요" /></div><fieldset disabled={!!busy}><AssessmentResults items={draft.items} onChange={items => setDraft({ ...draft, items })} /><div className="submit-bar"><div><strong>{draft.items.filter(i => i.selected).length}개 항목 선택</strong><span>검토를 마치면 담당자에게 전달됩니다.</span></div><button className="button primary" disabled={!!busy || !draft.items.some(i => i.selected) || draft.items.some(i => i.selected && (!i.location.trim() || !i.scenario.trim() || !i.solution.trim()))} onClick={submit}>선택한 평가 제출<ArrowRight size={17} /></button></div></fieldset></section>}
            <Guides api={api} keywords={draft?.guide_keywords || []} analysisId={draft?.draft_id || ""} />
            <PublicOverview api={api} revision={revision} />
          </> : !boot.user ? <LoginPanel boot={boot} busy={!!busy} onPin={loginPin} onDemo={login} /> : tab === "reports" && boot.user.role !== "admin" ? <section className="panel"><Empty>결과보고서는 관리자 계정으로 이용할 수 있습니다.</Empty></section> : <>
            <div className="stats-grid"><Stat title="전체 위험성평가" value={records.length} unit="건" icon={<LayoutDashboard size={20} />} note="조회 조건에 해당하는 평가" /><Stat title="개선이 필요한 항목" value={pendingCount} unit="건" icon={<ClipboardCheck size={20} />} note="접수 및 조치 진행 중" /><Stat title="우선 확인할 위험" value={urgentCount} unit="건" icon={<TriangleAlert size={20} />} note="미완료 · 최신 평가 9점 이상" accent /><Stat title="개선조치 완료율" value={records.length ? Math.round(completeCount / records.length * 100) : 0} unit="%" icon={<CheckCircle2 size={20} />} note={`총 ${completeCount}건의 개선을 완료했어요`} /></div>
            <section className="panel filter-panel"><div className="filter-heading"><Search size={17} /><strong>조회 조건</strong><button className="text-button" onClick={() => { setFilters(emptyFilters); setSelectedId(""); }}><RotateCcw size={13} />초기화</button></div><div className="filters"><label>시설<select value={filters.facility} onChange={e => setFilters({ ...filters, facility: e.target.value })}><option value="">전체 시설</option>{boot.facilities.filter(f => boot.user!.role === "admin" || boot.user!.facilities.includes(f)).map(f => <option key={f}>{f}</option>)}</select></label><label>부서<select value={filters.department} onChange={e => setFilters({ ...filters, department: e.target.value })}><option value="">전체 부서</option>{boot.departments.map(d => <option key={d}>{d}</option>)}</select></label><label>처리상태<select value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}><option value="">전체 상태</option>{["접수", "조치 중", "완료"].map(s => <option key={s}>{s}</option>)}</select></label><label>시작일<input aria-label="조회 시작일" type="date" value={filters.start} onChange={e => setFilters({ ...filters, start: e.target.value })} /></label><label>종료일<input aria-label="조회 종료일" type="date" value={filters.end} onChange={e => setFilters({ ...filters, end: e.target.value })} /></label></div></section>
            {tab === "actions" ? <div className="actions-grid"><section className="panel record-list"><div className="panel-heading"><h2>위험요인 목록 <span className="count">{records.length}</span></h2><button aria-label="목록 새로고침" className="icon-button" onClick={() => setRevision(v => v + 1)}><RotateCcw size={16} /></button></div>{records.length ? records.map(r => <button key={r.id} className={`record-item ${selectedId === r.id ? "selected" : ""}`} onClick={() => setSelectedId(r.id)}><div><span className="facility-tag">{r.facility}</span><Badge value={r.status} /><span className="record-date">{dateText(r.created_at)}</span></div><h3>{r.before.location}</h3><p>{r.before.scenario}</p><div className="record-meta"><span>{r.before.category}</span><Score value={r.after || r.before} /></div></button>) : <Empty>조회 조건에 맞는 평가가 없습니다.</Empty>}</section><section className="panel detail-panel">{selected ? <ActionDetail key={`${selected.id}:${selected.revision}`} record={selected} busy={busy} api={api} run={run} upload={upload} requestId={requestId} onSaved={() => { setRevision(v => v + 1); setNotice("개선조치 기록을 저장했습니다."); }} /> : <Empty>목록에서 평가를 선택하면<br />개선조치와 이력을 확인할 수 있습니다.</Empty>}</section></div> : <>
              <div className="report-grid"><section className="panel distribution"><div className="panel-heading"><h2>최초 위험등급 분포</h2><span className="muted small">당시 평가 기준</span></div>{grades.map((g, i) => { const count = records.filter(r => r.before.grade === g).length; return <div className="bar-row" key={g}><span>{g}</span><div className="bar-track"><i className={`bar-${i}`} style={{ width: `${records.length ? count / records.length * 100 : 0}%` }} /></div><strong>{count}<small>건</small></strong></div>; })}<p className="small muted">과거 평가의 등급은 그대로 보존됩니다.{records.some(r => !grades.includes(r.before.grade)) && ` 기타 기존 등급 ${records.filter(r => !grades.includes(r.before.grade)).length}건`}</p></section><section className="panel export-panel"><span className="export-icon"><FileText size={28} /></span><h2>평가 결과를 보고서로</h2><p>현재 조회 조건의 평가와 개선 전후 사진,<br />조치내용을 하나의 보고서에 담습니다.</p><div className="download-options"><button disabled={!!busy || !records.length} onClick={() => download("xlsx")}><span className="file-format excel">X</span><span><strong>Excel 다운로드</strong><small>평가 목록과 집계 · .xlsx</small></span><ArrowDownToLine size={18} /></button><button disabled={!!busy || !records.length} onClick={() => download("pdf")}><span className="file-format pdf">P</span><span><strong>PDF 다운로드</strong><small>개선 전후 사진 포함 · .pdf</small></span><ArrowDownToLine size={18} /></button><button disabled><span className="file-format">H</span><span><strong>한글 보고서</strong><small>HWPX 양식 연동 준비 중</small></span><span className="coming-soon">예정</span></button></div><p className="small muted">한 번에 최대 {boot.report_max_rows}건까지 출력할 수 있습니다.</p></section></div>
              <section className="panel table-panel"><div className="panel-heading"><h2>위험성평가 내역 <span className="count">{records.length}</span></h2><span className="muted small">조회 결과 기준</span></div><div className="table-scroll"><table><thead><tr><th>시설 / 장소</th><th>위험요인</th><th>최초 평가</th><th>개선 후</th><th>상태</th><th>평가일</th></tr></thead><tbody>{records.map(r => <tr key={r.id}><td><strong>{r.facility} · {r.before.location}</strong><small>{r.department}</small></td><td>{r.before.category}</td><td><Badge value={r.before.grade} /><small>{r.before.score}점</small></td><td>{r.after ? <><Badge value={r.after.grade} /><small>{r.after.score}점</small></> : <span className="muted">대기</span>}</td><td><Badge value={r.status} /></td><td>{dateText(r.created_at)}</td></tr>)}</tbody></table>{!records.length && <Empty>조회 조건에 맞는 평가가 없습니다.</Empty>}</div></section>
            </>}
          </>}
          <SiteFooter />
        </>}
      </main>
    </div>
  </div>;
}

function LoginPanel({ boot, busy, onPin, onDemo }: { boot: Bootstrap; busy: boolean; onPin: (pin: string) => Promise<void>; onDemo: (role: string) => Promise<void> }) {
  const [pin, setPin] = useState("");
  const isPin = boot.auth_mode === "pin";
  return <section className="panel login-panel">
    <div className="login-icon">{isPin ? <LockKeyhole size={34} /> : <ShieldCheck size={38} />}</div>
    <h2>{isPin ? "관리자 비밀번호 확인" : "담당자 로그인"}</h2>
    <p>{isPin ? <>개선조치와 결과보고서를 보려면<br />관리자 비밀번호를 입력해 주세요.</> : "개선조치와 결과보고서는 승인된 담당자·관리자 계정으로 이용할 수 있습니다."}</p>
    {isPin ? <form className="pin-form" onSubmit={async e => { e.preventDefault(); if (!busy && /^[0-9]{4}$/.test(pin)) { const value = pin; setPin(""); await onPin(value); } }}>
      <label htmlFor="admin-pin">관리자 비밀번호</label>
      <input id="admin-pin" name="password" type="password" inputMode="numeric" autoComplete="current-password" pattern="[0-9]{4}" minLength={4} maxLength={4} placeholder="숫자 4자리" aria-describedby="pin-help" required disabled={busy} value={pin} onChange={e => setPin(e.target.value.replace(/[^0-9]/g, "").slice(0, 4))} />
      <button type="submit" className="button primary full" disabled={busy || pin.length !== 4}><LockKeyhole size={16} />{busy ? "확인 중" : "확인하고 입장하기"}<ArrowRight size={16} /></button>
      <p id="pin-help" className="pin-help">로그인은 1시간 동안 유지됩니다.<br />공용 PC에서는 사용 후 로그아웃해 주세요.</p>
    </form> : boot.mode === "demo" ? <div className="button-row"><button className="button primary" disabled={busy} onClick={() => onDemo("admin")}>관리자로 체험하기<ArrowRight size={16} /></button><button className="button secondary" disabled={busy} onClick={() => onDemo("staff")}>중앙 담당자로 체험하기</button></div> : <a className="button primary" href="/api/auth/google"><LogIn size={18} />Google 계정으로 로그인</a>}
  </section>;
}

function SiteFooter() {
  return <footer className="site-footer">
    <div className="footer-grid">
      <section className="footer-policy" aria-labelledby="footer-policy-title">
        <div className="footer-heading"><ShieldCheck size={19} /><h2 id="footer-policy-title">데이터 관리와 이용 안내</h2></div>
        <p className="footer-copyright">© {new Date().getFullYear()} {brand.name}({brand.shortName}) {brand.department}.</p>
        <dl>
          <div><dt>데이터 보안</dt><dd>AI 분석에 전송되는 입력 정보에는 API 옵트아웃(Opt-out) 설정이 적용되어 외부 AI 모델의 학습에 활용되지 않습니다.</dd></div>
          <div><dt>데이터 이용</dt><dd>사진과 설명은 위험요인 분석 및 평가 기록 관리에 사용됩니다. 실제 AI 분석 시 외부 AI 서비스로 전송되므로, 불필요한 개인정보는 입력하지 마세요.</dd></div>
          <div><dt>운영 방침</dt><dd>제출된 자료는 담당자의 적합성 검토를 거칩니다. 부적절하거나 중복된 내용은 운영 기준에 따라 정정·정리될 수 있습니다.</dd></div>
          <div><dt>AI 결과 검토</dt><dd>AI 분석은 위험요인 발굴을 돕는 참고자료입니다. 실제 위험성평가와 개선조치는 현장 상황을 반영하여 담당자가 최종 확인해 주세요.</dd></div>
        </dl>
      </section>
      <section className="footer-contact" aria-labelledby="footer-contact-title">
        <div className="footer-heading"><Phone size={17} /><h2 id="footer-contact-title">운영 문의</h2></div>
        <strong>{brand.department}</strong>
        <a href={`mailto:${brand.email}`}><Mail size={15} />{brand.email}</a>
        <a href={`tel:${brand.telephone}`}><Phone size={15} />{brand.phone}</a>
      </section>
    </div>
    <div className="footer-bottom"><span><strong>{brand.shortName}</strong> {brand.name}</span><span>Safe Together, {brand.shortName} AI Risk Assessment System</span></div>
  </footer>;
}

function PhotoInput({ value, disabled, onUpload, onChange }: { value: Photo; disabled: boolean; onUpload: (file: File) => Promise<void>; onChange: (p: Photo) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return <div className="photo-input"><input ref={input} className="sr-only" type="file" accept="image/jpeg,image/png" aria-label="현장 사진 선택" disabled={disabled} onChange={e => { const f = e.target.files?.[0]; if (f) void onUpload(f); e.target.value = ""; }} />{value ? <><div className="photo-preview"><img src={value.url} alt="개인정보 처리 후 현장 사진 미리보기" /><button type="button" className="icon-button remove-photo" aria-label="사진 제거" disabled={disabled} onClick={() => onChange(null)}><X size={17} /></button></div><label className="checkbox-label photo-confirm"><input type="checkbox" checked={value.confirmed} disabled={disabled} onChange={e => onChange({ ...value, confirmed: e.target.checked })} /><span>사진에 남은 얼굴·개인정보가 없는지 확인했습니다.</span></label><p className="small muted">자동 처리에 누락이 있다면 사진을 제거하고, 직접 가린 사진을 다시 올려주세요.</p></> : <button type="button" className="upload-zone" disabled={disabled} onClick={() => input.current?.click()}><span className="upload-icon"><ImagePlus size={25} strokeWidth={1.5} /></span><strong>현장 사진을 추가해 주세요</strong><span>사진 선택 또는 모바일 카메라 촬영</span><small>JPG, PNG · 최대 10MB</small><span className="upload-pill"><Plus size={14} />사진 추가</span></button>}</div>;
}

function Stat({ title, value, unit, icon, note, accent }: { title: string; value: number; unit: string; icon: React.ReactNode; note: string; accent?: boolean }) { return <section className={`stat ${accent ? "accent" : ""}`}><div><span>{title}</span>{icon}</div><strong>{value.toLocaleString()}<small>{unit}</small></strong><p>{note}</p></section>; }

type Api = (path: string, body?: object | FormData) => Promise<Response>;
type Runner = (label: string, work: () => Promise<void>) => Promise<void>;
function ActionDetail({ record: r, busy, api, run, upload, requestId, onSaved }: { record: Assessment; busy: string; api: Api; run: Runner; upload: (f: File, update: (p: Photo) => void) => Promise<void>; requestId: (scope: string, body: object) => string; onSaved: () => void }) {
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<Photo>(null);
  const [result, setResult] = useState<Reassessment | null>(null);
  const [events, setEvents] = useState<History[]>([]);
  const [historyError, setHistoryError] = useState("");
  useEffect(() => { let live = true; api(`/assessments/${r.id}/history`).then(res => res.json()).then(data => { if (live) setEvents(data.items); }).catch(e => { if (live) setHistoryError(e.message); }); return () => { live = false; }; }, [api, r.id, r.revision]);
  const reassess = () => run("개선조치의 위험도를 재평가하고 있습니다", async () => { const f = new FormData(); f.set("text", text); if (photo) f.set("photo_id", photo.id); setResult(await (await api(`/assessments/${r.id}/reassess`, f)).json()); });
  const save = (complete: boolean) => run("개선조치 기록을 저장하고 있습니다", async () => { if (!result) return; const body = { draft_id: result.draft_id, revision: result.revision, p: result.p, s: result.s, complete }; await api(`/assessments/${r.id}/actions`, { ...body, request_id: requestId(r.id, body) }); onSaved(); });
  const reopen = () => run("평가 상태를 변경하고 있습니다", async () => { const body = { revision: r.revision, status: "조치 중" }; await api(`/assessments/${r.id}/state`, { ...body, request_id: requestId(r.id, body) }); onSaved(); });
  return <><div className="detail-heading"><span className="eyebrow">ASSESSMENT DETAIL</span><Badge value={r.status} /></div><h2>{r.facility} · {r.before.location}</h2><p className="muted small">{r.department} · {dateText(r.created_at)}</p><div className="detail-risk"><span>{r.before.category}</span><Score value={r.before} /></div><dl className="record-description"><dt>위험상황</dt><dd>{r.before.scenario}</dd><dt>감소대책</dt><dd>{r.before.solution}</dd></dl>{r.photo_url && <img className="record-photo" src={r.photo_url} alt="개선 전 현장 사진" />}<details><summary>평가 기준 · 관련근거</summary><p>{r.policy} · 빈도 {r.before.p} × 강도 {r.before.s}</p>{r.current_risk && r.policy !== "KYWA-2026-6LEVEL-v1" && <p>현행 기준 참고 환산: {r.current_risk.grade} {r.current_risk.score}점 (원래 기록 유지)</p>}<p>{r.before.law || "근거 확인 필요"}</p></details>
    {r.after && <div className="saved-action"><div><strong>최근 개선조치</strong><Score value={r.after} /></div><p>{r.after.text || "기존 기록에 조치내용 없음"}</p>{r.after.photo_url && <img className="record-photo" src={r.after.photo_url} alt="개선 후 현장 사진" />}<small>{r.after.actor || "기존 기록"} · {dateText(r.after.created_at || "")}</small></div>}
    {r.status === "완료" ? <div className="completed-panel"><CheckCircle2 size={22} /><strong>개선조치가 완료되었습니다.</strong><button className="button secondary" disabled={!!busy} onClick={reopen}><RotateCcw size={15} />다시 열기</button></div> : <fieldset disabled={!!busy} className="action-form"><h3><ClipboardCheck size={18} />개선조치 기록</h3><label>실제 조치내용<textarea rows={4} maxLength={6000} value={text} placeholder="어떤 개선을 했는지 구체적으로 작성해 주세요." onChange={e => { setText(e.target.value); setResult(null); }} /></label><label>개선 후 사진 <span className="optional">선택</span></label><PhotoInput value={photo} disabled={!!busy} onUpload={f => upload(f, p => { setPhoto(p); setResult(null); })} onChange={p => { setPhoto(p); setResult(null); }} /><button className="button secondary full" disabled={!!busy || !text.trim() || !!photo && !photo.confirmed} onClick={reassess}><Sparkles size={17} />AI 재평가하기</button>{result && <div className="reassessment"><h3>재평가 결과 검토</h3><p>{result.rationale}</p><div className="field-row"><label>빈도<select value={result.p} onChange={e => { const p = +e.target.value; setResult({ ...result, p, score: p * result.s, grade: grade(p * result.s) }); }}>{[1, 2, 3, 4, 5].map(v => <option key={v} value={v}>{v}</option>)}</select></label><label>강도<select value={result.s} onChange={e => { const s = +e.target.value; setResult({ ...result, s, score: result.p * s, grade: grade(result.p * s) }); }}>{[1, 2, 3, 4].map(v => <option key={v} value={v}>{v}</option>)}</select></label><Score value={result} /></div><p className="small muted">현장 확인에 따라 값을 조정한 뒤 저장하세요. 완료 처리는 담당자의 확인을 의미합니다.</p><div className="button-row"><button className="button secondary" disabled={!!busy} onClick={() => save(false)}>조치 중으로 저장</button><button className="button primary" disabled={!!busy} onClick={() => save(true)}><Check size={16} />확인 후 완료</button></div></div>}</fieldset>}
    <div className="history"><h3>변경 이력 <span>{events.length}</span></h3>{historyError ? <p role="alert">{historyError}</p> : events.length ? [...events].reverse().map(e => <div className="history-event" key={e.id}><i /><div><strong>{e.kind}</strong><span>{dateText(e.at)} · {e.actor}</span><p>{e.text}</p>{e.after && <Badge value={`${e.after.grade} · ${e.after.score}점`} />}</div></div>) : <p className="muted small">아직 변경 이력이 없습니다.</p>}</div></>;
}

