import type { PublicBranding } from './brand';
export type Policy = {
  version: string; method: "product" | "matrix";
  p_levels: {value: number; description: string}[];
  s_levels: {value: number; description: string}[];
  grades: {name: string; tone: number; urgent: boolean}[];
  cells: {p: number; s: number; score: number; grade: string}[];
};
export type Organization = {
  id: string; name: string; short_name: string; policy: Policy; branding: PublicBranding;
  submitter_name: {mode: "disabled" | "optional" | "required"; label: string; notice: string; show_in_reports: boolean};
};
export function calculated(policy: Policy, p: number, s: number) {
  const cell = policy.cells.find(c => c.p === p && c.s === s);
  if (!cell) throw new Error("기관 평가표에 없는 값입니다.");
  const grade = policy.grades.find(g => g.name === cell.grade)!;
  return {...cell, tone: grade.tone, urgent: grade.urgent};
}
export function Criteria({policy}: {policy: Policy}) {
  return <details className="policy-details"><summary>적용 평가 기준 · {policy.version}</summary>
    <p>{policy.method === "product" ? "점수 = 빈도 × 강도" : "기관별 위험도 매트릭스 적용"}</p>
    <p>빈도: {policy.p_levels.map(x => `${x.value} ${x.description}`).join(" / ")}</p>
    <p>강도: {policy.s_levels.map(x => `${x.value} ${x.description}`).join(" / ")}</p>
    <div className="table-scroll"><table><caption>빈도·강도별 점수와 위험등급</caption><thead><tr><th>빈도 / 강도</th>{policy.s_levels.map(s => <th key={s.value}>{s.value}</th>)}</tr></thead><tbody>{policy.p_levels.map(p => <tr key={p.value}><th>{p.value}</th>{policy.s_levels.map(s => {const c=calculated(policy,p.value,s.value);return <td key={s.value}><span className={`badge tone-${c.tone}`}>{c.grade}</span> {c.score}점</td>;})}</tr>)}</tbody></table></div>
  </details>;
}
