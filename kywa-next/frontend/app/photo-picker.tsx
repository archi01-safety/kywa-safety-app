"use client";
import {useRef,useState} from "react";
import {ArrowLeft,ArrowRight,ImagePlus,Plus,RotateCcw,X} from "lucide-react";
import {LoadingPhoto} from "./loading-photo";

export type PreparedPhoto={id:string;url:string;confirmed:boolean;processed?:boolean};
type Props={value:PreparedPhoto[];limit:1|2;disabled:boolean;onUpload:(files:File[],replace?:number)=>Promise<void>;onChange:(photos:PreparedPhoto[])=>void};

export function PhotoPicker({value,limit,disabled,onUpload,onChange}:Props){
  const input=useRef<HTMLInputElement>(null),replacement=useRef<number|undefined>(undefined);
  const [dragging,setDragging]=useState(false),[error,setError]=useState("");
  const choose=(index?:number)=>{replacement.current=index;input.current?.click();};
  const receive=async(files:File[])=>{
    if(disabled||!files.length)return;
    const replace=replacement.current;replacement.current=undefined;
    if(files.length+(replace===undefined?value.length:value.length-1)>limit){setError(`사진은 최대 ${limit}장까지 등록할 수 있습니다. 기존 사진을 제거하거나 교체해 주세요.`);return;}
    if(files.some(file=>file.size>20*1024*1024)){setError("각 사진은 20MB 이하로 등록해 주세요.");return;}
    setError("");await onUpload(files,replace);
  };
  const reorder=(index:number,step:number)=>{const next=[...value];[next[index],next[index+step]]=[next[index+step],next[index]];onChange(next);};
  return <div className="photo-input">
    <div className={`photo-dropbox ${dragging?"dragging":""}`} aria-label={limit===2?"최초 평가 사진 업로드 영역":"개선 후 사진 업로드 영역"}
      onDragOver={event=>{if(event.dataTransfer.types.includes("Files")){event.preventDefault();if(!disabled)setDragging(true);}}}
      onDragLeave={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node))setDragging(false);}}
      onDrop={event=>{event.preventDefault();setDragging(false);replacement.current=undefined;if(!disabled)void receive(Array.from(event.dataTransfer.files));}}>
      <input ref={input} className="sr-only" type="file" multiple={limit===2} accept=".jpg,.jpeg,.png,.webp,.heic,.heif,image/jpeg,image/png,image/webp,image/heic,image/heif" aria-label="현장 사진 선택" disabled={disabled}
        onChange={event=>{const files=Array.from(event.target.files||[]);event.target.value="";void receive(files);}} />
      {value.length>0?<div className="photo-thumbnails">{value.map((photo,index)=><div className="photo-tile" key={photo.id}>
        <div className="photo-preview"><LoadingPhoto url={photo.url} alt={photo.processed?`제출할 사진 ${index+1} 미리보기`:`분석 전 사진 ${index+1} 미리보기`} />
          <button type="button" className="icon-button remove-photo" aria-label={`사진 ${index+1} 제거`} disabled={disabled} onClick={()=>onChange(value.filter((_,i)=>i!==index))}><X size={17}/></button></div>
        <div className="photo-tile-tools"><small>{index===0&&limit===2?"대표사진":`사진 ${index+1}`}</small><button type="button" className="text-button" disabled={disabled} onClick={()=>choose(index)}><RotateCcw size={13}/>교체</button>
          {value.length===2&&<button type="button" className="icon-button" disabled={disabled} aria-label={`사진 ${index+1}을 ${index===0?"뒤로":"대표사진으로"} 이동`} onClick={()=>reorder(index,index===0?1:-1)}>{index===0?<ArrowRight size={14}/>:<ArrowLeft size={14}/>}</button>}</div>
        {photo.processed&&<label className="checkbox-label photo-confirm"><input type="checkbox" disabled={disabled} checked={photo.confirmed} aria-label={`사진 ${index+1} 개인정보 확인`} onChange={event=>onChange(value.map((p,i)=>i===index?{...p,confirmed:event.target.checked}:p))}/><span>사진에 남은 얼굴·개인정보가 없는지 확인했습니다.</span></label>}
      </div>)}</div>:<div className="upload-copy"><span className="upload-icon"><ImagePlus size={25} strokeWidth={1.5}/></span><strong>현장 사진을 추가해 주세요</strong><span>사진 선택 · 모바일 촬영 · 드래그 앤 드롭</span><small>JPG, PNG, WebP, HEIC · 각 20MB 이하 · 가로사진 권장</small></div>}
      {value.length<limit&&<button type="button" className={value.length?"button secondary":"upload-pill"} disabled={disabled} onClick={()=>choose()}><Plus size={14}/>{value.length?"사진 한 장 더 추가":"사진 추가"}</button>}
    </div>
    {error&&<p className="small upload-error" role="alert">{error}</p>}
    <p className="small muted photo-guidance">{limit===2?<>같은 위험상황의 사진을 최대 2장까지 등록할 수 있습니다. 사진을 선택하거나 이 영역에 끌어다 놓아 주세요.<br/>위험상황과 주변 환경이 함께 보이는 전체 사진과, 위험 부위가 선명하게 보이는 근접 사진을 권장합니다.<br/>촬영을 위해 위험구역에 들어가거나 위험한 동작을 재현하지 마세요.</>:<>개선 후 사진은 최대 1장 등록할 수 있습니다. 사진을 선택하거나 이 영역에 끌어다 놓아 주세요.<br/>가능하면 개선 전 사진과 비슷한 위치·각도에서 조치 결과가 보이도록 촬영해 주세요.</>}</p>
    <p className="small muted">분석 시 얼굴을 찾아 블러 처리합니다. 회사 문서·개인정보·민감정보가 포함되지 않았는지 확인해 주세요.<br/>위험상황을 설명해주면 더 정확한 결과가 나옵니다.</p>
  </div>;
}
