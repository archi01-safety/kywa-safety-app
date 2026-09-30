"use client";

type Item = { selected: boolean; category: string; location: string; scenario: string; solution: string; law: string; p: number; s: number; score: number; grade: string };
const grades = ["매우 낮음", "낮음", "보통", "약간 높음", "높음", "매우 높음"];

export function AssessmentResults({ items, onChange }: { items: Item[]; onChange: (items: Item[]) => void }) {
  const update = (index: number, change: Partial<Item>) => onChange(items.map((item, i) => i === index ? { ...item, ...change } : item));
  return <div className="evaluation-scroll" tabIndex={0} aria-label="위험성평가 결과 표, 좁은 화면에서는 좌우로 이동할 수 있습니다">
    <table className="evaluation-table"><caption>분석 항목을 선택하고 장소·위험상황·감소대책을 수정하세요. 점수는 빈도 × 강도입니다.</caption>
      <thead><tr>{["선택 / 분류", "장소", "위험상황", "빈도", "강도", "점수", "등급", "관련근거", "감소대책"].map(title => <th key={title} scope="col">{title}</th>)}</tr></thead>
      <tbody>{items.map((item, index) => <tr className={`evaluation-row ${item.selected ? "" : "unselected"}`} key={index}>
        <td data-label="분류"><label className="checkbox-label"><input type="checkbox" aria-label={`${String(index + 1).padStart(2, "0")} · ${item.category}`} checked={item.selected} onChange={e => update(index, { selected: e.target.checked })} /><span><small>위험요인 {String(index + 1).padStart(2, "0")}</small>{item.category}</span></label></td>
        <td data-label="장소"><input aria-label="장소" value={item.location} maxLength={200} onChange={e => update(index, { location: e.target.value })} /></td>
        <td data-label="위험상황"><textarea aria-label="위험상황" rows={4} value={item.scenario} maxLength={2000} onChange={e => update(index, { scenario: e.target.value })} /></td>
        <td data-label="빈도" className="evaluation-number">{item.p}</td>
        <td data-label="강도" className="evaluation-number">{item.s}</td>
        <td data-label="점수" className="evaluation-number"><strong>{item.score}</strong></td>
        <td data-label="등급"><span className={`badge tone-${grades.indexOf(item.grade)}`}>{item.grade}</span></td>
        <td data-label="관련근거" className="evaluation-law">{item.law || "원문 확인이 필요합니다."}</td>
        <td data-label="감소대책"><textarea aria-label="감소대책" rows={4} value={item.solution} maxLength={3000} onChange={e => update(index, { solution: e.target.value })} /></td>
      </tr>)}</tbody>
    </table>
  </div>;
}
