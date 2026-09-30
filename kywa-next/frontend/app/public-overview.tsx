"use client";

import { useEffect, useState } from "react";
import { BarChart3, CheckCircle2, Building2 } from "lucide-react";
type Count = { name: string; count: number };
type Summary = { year: number; years: number[]; total: number; completed: number; facility_count: number; categories: Count[]; facilities: Count[] };
type Api = (path: string, body?: object | FormData) => Promise<Response>;

export function PublicOverview({ api, revision }: { api: Api; revision: number }) {
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let live = true; setError(""); setData(null);
    api(`/overview?year=${year}`).then(r => r.json()).then(d => { if (live) setData(d); }).catch(e => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [api, year, revision, retry]);
  return <section className="public-overview" aria-labelledby="overview-title">
    <div className="section-top"><div><div className="eyebrow">SAFETY OVERVIEW</div><h2 id="overview-title">함께 만드는 안전 현황</h2><p className="muted">시설별 참여와 위험요인 분포를 확인하세요. 평가항목 기준 집계입니다.</p></div><label className="year-filter">조회 연도<select value={year} onChange={e => setYear(Number(e.target.value))}>{(data?.years || [year]).map(y => <option key={y} value={y}>{y}년</option>)}</select></label></div>
    {error ? <div className="panel overview-error" role="status"><p>현황을 불러오지 못했습니다.</p><button className="button secondary" onClick={() => setRetry(v => v + 1)}>다시 조회</button></div> : !data ? <p className="muted" role="status">현황을 불러오고 있습니다.</p> : <>
      <div className="overview-stats">{[{ title: "위험성평가 항목", count: data.total, unit: "건", icon: <BarChart3 size={22} /> }, { title: "참여 시설", count: data.facility_count, unit: "곳", icon: <Building2 size={22} /> }, { title: "개선조치 완료", count: data.completed, unit: "건", icon: <CheckCircle2 size={22} /> }].map(v => <div className="panel overview-stat" key={v.title}><span>{v.icon}{v.title}</span><strong>{v.count.toLocaleString()}<small>{v.unit}</small></strong></div>)}</div>
      <div className="overview-charts"><CountChart title="시설별 평가 현황" items={data.facilities} total={data.total} /><CountChart title="위험요인 분류" items={data.categories} total={data.total} /></div>
    </>}
  </section>;
}

function CountChart({ title, items, total }: { title: string; items: Count[]; total: number }) {
  const max = Math.max(1, ...items.map(i => i.count));
  return <section className="panel count-chart"><h3>{title}</h3>{total ? <ul>{items.map(item => <li key={item.name}><div><span>{item.name}</span><strong>{item.count.toLocaleString()}건 <small>({Math.round(item.count / total * 100)}%)</small></strong></div><div className="count-track" aria-hidden="true"><i style={{ width: `${item.count / max * 100}%` }} /></div></li>)}</ul> : <p className="muted">선택한 연도의 평가가 없습니다.</p>}</section>;
}
