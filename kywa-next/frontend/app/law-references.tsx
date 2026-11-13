"use client";
import {useEffect,useState} from "react";
import {requestApi} from "./request-api";
export type LawReference={label:string;url:string;verified:boolean;effective_date:string;message:string};
const cache=new Map<string,{at:number;items:LawReference[]}>(),pending=new Map<string,Promise<LawReference[]>>();
function official(url:string){try{const u=new URL(url);return u.protocol==="https:"&&["www.law.go.kr","law.go.kr"].includes(u.hostname)&&!u.username&&!u.password&&![...u.searchParams.keys()].some(k=>["oc","key","token"].includes(k.toLowerCase()));}catch{return false;}}
function lookup(text:string,force:boolean){
  const found=cache.get(text);
  if(!force&&found&&Date.now()-found.at<(found.items.every(r=>r.verified)?300000:60000))return Promise.resolve(found.items);
  if(pending.has(text))return pending.get(text)!;
  const request=requestApi(`/law-links?${new URLSearchParams({text})}`,undefined,"").then(r=>r.json()).then(data=>{
    const items:LawReference[]=data.items;
    if(cache.size>=128)cache.delete(cache.keys().next().value!);
    cache.set(text,{at:Date.now(),items});return items;
  }).finally(()=>pending.delete(text));
  pending.set(text,request);return request;
}
export function LawReferences({text,initial=[]}:{text:string;initial?:LawReference[]}){
  const [refs,setRefs]=useState(initial),[failed,setFailed]=useState(false),[reload,setReload]=useState(0),[loading,setLoading]=useState(false);
  useEffect(()=>{let current=true;setRefs(initial);setFailed(false);setLoading(!!text);
    if(text)lookup(text,reload>0).then(items=>{if(current)setRefs(items);}).catch(()=>{if(current)setFailed(true);}).finally(()=>{if(current)setLoading(false);});
    return()=>{current=false;};
  },[text,reload]);
  return <div className="law-references"><span>{text||"관련근거 확인이 필요합니다."}</span>{loading&&<small role="status">법령 원문을 확인하고 있습니다</small>}{refs.filter(r=>official(r.url)).map((ref,i)=><a key={`${ref.url}:${i}`} href={ref.url} target="_blank" rel="noreferrer">{ref.label} ↗<small>{ref.verified?`공식 원문 · 시행 ${ref.effective_date}`:"원문 확인 필요 · 법령 검색"}</small></a>)}{failed&&<button className="text-button" type="button" onClick={()=>setReload(v=>v+1)}>법령 연결 다시 확인</button>}</div>;
}
