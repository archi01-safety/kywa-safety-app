"use client";
import {useState} from "react";
export type FactQuestion={index:number;field:string;location:string;label:string;options:{value:string;label:string}[]};
export type FactAnswer={index:number;field:string;value:string};
export function FactQuestions({questions,disabled,onConfirm}:{questions:FactQuestion[];disabled:boolean;onConfirm:(answers:FactAnswer[])=>void}){
  const [answers,setAnswers]=useState<Record<string,string>>({});
  return <section className="panel fact-questions next-action"><h3>현장 조건을 조금 더 확인해 주세요</h3><p className="small muted">사진과 설명에서 확인되지 않은 정보입니다. 실제 현장 조건에 맞춰 선택해 주세요.</p>
    {questions.map(q=><label key={`${q.index}:${q.field}`}>{q.location} · {q.label}<select disabled={disabled} value={answers[`${q.index}:${q.field}`]||""} onChange={e=>setAnswers(a=>({...a,[`${q.index}:${q.field}`]:e.target.value}))}><option value="">선택해 주세요</option>{q.options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</select></label>)}
    <button className="button primary" disabled={disabled||questions.some(q=>!answers[`${q.index}:${q.field}`])} onClick={()=>onConfirm(questions.map(q=>({index:q.index,field:q.field,value:answers[`${q.index}:${q.field}`]})))}>확인한 조건으로 결과 보기</button>
  </section>;
}
