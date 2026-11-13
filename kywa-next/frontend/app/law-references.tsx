"use client";
import {useEffect,useState} from "react";
import {requestApi,aborted} from "./request-api";
export type LawReference={label:string;url:string;verified:boolean;effective_date:string;message:string};
function official(url:string){try{const u=new URL(url);return u.protocol==="https:"&&["www.law.go.kr","law.go.kr"].includes(u.hostname)&&!u.username&&!u.password&&!u.searchParams.has("OC");}catch{return false;}}
export function LawReferences({text,initial=[]}:{text:string;initial?:LawReference[]}){
  const [refs,setRefs]=useState(initial),[failed,setFailed]=useState(false),[reload,setReload]=useState(0);
  useEffect(()=>{const controller=new AbortController();setRefs(initial);setFailed(false);
    if(text)requestApi(`/law-links?${new URLSearchParams({text})}`,undefined,"",controller.signal).then(r=>r.json()).then(d=>setRefs(d.items)).catch(e=>{if(!aborted(e))setFailed(true);});
    return()=>controller.abort();
  },[text,reload]);
  return <div className="law-references"><span>{text||"관련근거 확인이 필요합니다."}</span>{refs.filter(r=>official(r.url)).map((ref,i)=><a key={`${ref.url}:${i}`} href={ref.url} target="_blank" rel="noreferrer">{ref.label} ↗<small>{ref.verified?`공식 원문 · 시행 ${ref.effective_date}`:"원문 확인 필요 · 법령 검색"}</small></a>)}{failed&&<button className="text-button" type="button" onClick={()=>setReload(v=>v+1)}>법령 연결 다시 확인</button>}</div>;
}
