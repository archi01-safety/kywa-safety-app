// Original text stays in component memory. Only this result may enter a request.
const initials = "㉠ㄲ㉡㉢ㄸ㉣㉤㉥ㅃ㉦ㅆ㉧㉨ㅉ㉩㉪㉫㉬㉭";
export type NameMode = "disabled" | "optional" | "required";
export function submissionName(raw: string, mode: NameMode) {
  if (mode === "disabled") return { value: "", error: "" };
  const name = raw.replace(/\s/gu, "").normalize("NFC");
  if (!name) return { value: "", error: mode === "required" ? "성명을 입력해 주세요." : "" };
  if (name.length > 100) return { value: "", error: "성명은 공백을 제외하고 최대 100글자까지 입력할 수 있습니다." };
  if (!/^[가-힣]+$/u.test(name)) return { value: "", error: "완성된 한글로 입력해 주세요. 숫자·영문·기호는 사용할 수 없습니다." };
  return { value: name[0] + Array.from(name.slice(1), c => initials[Math.floor((c.charCodeAt(0) - 0xAC00) / 588)]).join(""), error: "" };
}

export function composingNamePreview(raw: string) {
  // A trailing, unfinished jamo must not trigger an error or appear in the preview.
  const completed = raw.replace(/\s/gu, "").normalize("NFC").match(/^[가-힣]+/u)?.[0] || "";
  return submissionName(completed, "optional").value;
}
