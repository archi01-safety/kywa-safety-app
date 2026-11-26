"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, FileText, LoaderCircle, Search } from "lucide-react";
type Api = (path: string, body?: object | FormData) => Promise<Response>;

export function Guides({ api, keywords, analysisId }: { api: Api; keywords: string[]; analysisId: string }) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<{ number: string; title: string; url: string }[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const request = useRef(0);
  const search = useCallback(async (keyword: string) => {
    if (!keyword.trim()) return;
    const current = ++request.current;
    setQuery(keyword); setLoading(true); setItems([]); setMessage("");
    try {
      const data = await (await api(`/guides?keyword=${encodeURIComponent(keyword.trim())}`)).json();
      if (current !== request.current) return;
      setItems(data.items);
      if (!data.items.length) setMessage(data.message || "검색 결과가 없습니다. 다른 추천 키워드나 검색어를 선택하세요.");
    } catch (e) { if (current === request.current) setMessage(e instanceof Error ? e.message : "검색에 실패했습니다."); }
    finally { if (current === request.current) setLoading(false); }
  }, [api]);
  const recommended = keywords.join("|");
  useEffect(() => {
    const first = recommended.split("|")[0];
    if (analysisId && first) void search(first);
    else { ++request.current; setItems([]); setQuery(""); setLoading(false); setMessage(analysisId ? "자동 추천 키워드가 없습니다. 위험요인에 맞는 검색어를 입력하세요." : ""); }
    return () => { ++request.current; };
  }, [analysisId, recommended, search]);
  return <section className="panel guide-panel"><div className="guide-heading"><span className="guide-icon"><FileText size={23} /></span><div><h2>KOSHA GUIDE</h2><p>분석 결과에서 추천한 키워드로 기술지침을 자동 검색합니다.</p></div><span className="guide-tag">안전보건공단</span></div>
    {!!keywords.length && <div className="guide-keywords"><span>추천 키워드</span>{keywords.map(word => <button type="button" key={word} className={query === word ? "selected" : ""} onClick={() => void search(word)}>{word}</button>)}</div>}
    <form className="guide-search" onSubmit={e => { e.preventDefault(); void search(query); }}><Search size={18} /><input aria-label="KOSHA 검색어" maxLength={80} value={query} onChange={e => { setQuery(e.target.value); ++request.current; setItems([]); setMessage(""); setLoading(false); }} placeholder="예: 난간, 사다리, 감전" /><button className="button secondary" disabled={loading || !query.trim()}>{loading ? <LoaderCircle className="spin" size={16} /> : "지침 검색"}</button></form>
    {loading && <p className="small muted" role="status">관련 기술지침을 찾고 있습니다.</p>}{message && <p className="small muted" role="status">{message}</p>}
    {items.map((item, i) => <div className="guide-result" key={`${item.number}-${i}`}><div><span>{item.number}</span><strong>{item.title}</strong></div>{item.url ? <a href={item.url} target="_blank" rel="noopener noreferrer">원문 다운로드<ArrowUpRight size={16} /></a> : <small>원문 링크 없음</small>}</div>)}
  </section>;
}
