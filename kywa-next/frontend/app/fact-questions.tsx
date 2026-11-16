"use client";
import {useState} from "react";
export type FactQuestion={index:number;field:string;location:string;label:string;options:{value:string;label:string}[]};
export type FactAnswer={index:number;field:string;value:string};
export function FactQuestions({questions,disabled,onConfirm}:{questions:FactQuestion[];disabled:boolean;onConfirm:(answers:FactAnswer[])=>void}){
  const [answers,setAnswers]=useState<Record<string,string>>({});
  return <details className="panel fact-questions"><summary>현장 조건 보완 <span className="optional">선택</span></summary><p className="small muted">답하지 않아도 현재 초안을 검토한 뒤 제출할 수 있습니다. 알고 있는 조건만 선택하면 결과에 반영합니다.</p>
    {questions.map(q=><label key={`${q.index}:${q.field}`}>{q.location} · {q.label}<select disabled={disabled} value={answers[`${q.index}:${q.field}`]||""} onChange={e=>setAnswers(a=>({...a,[`${q.index}:${q.field}`]:e.target.value}))}><option value="">선택해 주세요</option>{q.options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</select></label>)}
    <button className="button secondary" disabled={disabled||!questions.some(q=>!!answers[`${q.index}:${q.field}`])} onClick={()=>onConfirm(questions.filter(q=>!!answers[`${q.index}:${q.field}`]).map(q=>({index:q.index,field:q.field,value:answers[`${q.index}:${q.field}`]})))}>선택한 조건 반영</button>
  </details>;
}
