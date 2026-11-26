"use client";
import {useEffect,useRef,useState} from "react";
import {LoaderCircle,RotateCcw} from "lucide-react";
import {appPath} from "./base-path";

export function LoadingPhoto({url,alt}:{url?:string;alt:string}){
  const image=useRef<HTMLImageElement>(null);
  const [state,setState]=useState("loading"),[attempt,setAttempt]=useState(0);
  useEffect(()=>{setState(image.current?.complete&&image.current.naturalWidth>0?"loaded":"loading");const timer=setTimeout(()=>setState(s=>s==="loading"?"delayed":s),12000);return()=>clearTimeout(timer);},[url,attempt]);
  if(!url)return <div className="photo-status" role="status">등록된 사진이 없습니다</div>;
  return <div className="loading-photo">
    <img ref={image} className={`record-photo ${state==="loaded"?"":"photo-pending"}`} src={appPath(url)+(attempt?(url.includes("?")?"&":"?")+`retry=${attempt}`:"")} alt={alt} onLoad={()=>setState("loaded")} onError={()=>setState("failed")}/>
    {state!=="loaded"&&<div className="photo-status" role="status">{state!=="failed"&&<LoaderCircle className="spin" size={20}/>}<span>{state==="failed"?"사진을 불러오지 못했습니다":state==="delayed"?"사진 연결이 지연되고 있습니다. 잠시 기다리거나 다시 시도해 주세요.":"사진을 불러오는 중입니다"}</span>{(state==="failed"||state==="delayed")&&<button type="button" className="text-button" onClick={()=>{setState("loading");setAttempt(a=>a+1);}}><RotateCcw size={14}/>사진 다시 불러오기</button>}</div>}
  </div>;
}
