"use client";
import { useState } from "react";
import { submissionName, composingNamePreview } from "./submitter-name";
import type { Organization } from "./policy";

export function SubmitterNameInput({ config, value, composing, onChange, onComposition }: {
  config: Organization["submitter_name"]; value: string; composing: boolean;
  onChange: (value: string) => void; onComposition: (value: boolean) => void;
}) {
  const [touched, setTouched] = useState(false);
  if (config.mode === "disabled") return null;
  const result = submissionName(value, config.mode);
  const composingPreview = composing ? composingNamePreview(value) : "";
  const error = !composing && (value !== "" || touched) ? result.error : "";
  return <div className="submitter-field">
    <label htmlFor="submitter-name">{config.label} <span className="optional">{config.mode === "required" ? "필수" : "선택"}</span></label>
    <input id="submitter-name" aria-label={config.label} autoComplete="off" spellCheck={false}
      required={config.mode === "required"} value={value} aria-invalid={!!error}
      aria-describedby="submitter-name-preview submitter-name-help"
      onChange={e => onChange(e.target.value)}
      onCompositionStart={() => onComposition(true)}
      onCompositionEnd={e => { onChange(e.currentTarget.value); onComposition(false); }}
      onBlur={() => setTouched(true)} />
    <small id="submitter-name-preview" className={error ? "name-error" : "name-preview"} role="status" aria-live="polite" aria-atomic="true">
      {composing ? (composingPreview ? `${composingPreview}으로 제출됩니다. (입력 중)` : "한글 입력을 완료하면 제출될 이름을 안내합니다.") : error || (result.value ? `${result.value}으로 제출됩니다.` : "이름을 입력하면 제출될 이름을 미리 확인할 수 있습니다.")}
    </small>
    <small id="submitter-name-help">첫 글자를 제외한 이름은 초성으로 변환됩니다. 성명 입력란의 원본은 서버와 AI에 전송하지 않습니다.{config.notice && ` ${config.notice}`}</small>
  </div>;
}
