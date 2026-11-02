export type SheetIssue = { id: string; row: number; revision: number; code: string; messages: string[]; can_confirm_policy: boolean; facility: string };

export function SheetIssues({ items, admin, busy, onConfirm, onRefresh }: {
  items: SheetIssue[]; admin: boolean; busy: boolean;
  onConfirm: (item: SheetIssue) => void; onRefresh: () => void;
}) {
  if (!items.length) return null;
  return <section className="panel sheet-issues" aria-label="시트 확인 필요">
    <div className="panel-heading"><h2>시트 확인 필요 <span className="count">{items.length}건</span></h2>
      <button className="text-button" disabled={busy} onClick={onRefresh}>수정 후 새로고침</button></div>
    <p>아래 항목을 확인하면 목록에 다시 표시됩니다. 새 평가는 계속 제출할 수 있습니다. 이 항목이 포함된 보고서는 수정 후 생성해 주세요.</p>
    {items.map(item => <div className="sheet-issue" key={item.id}>
      <div><strong>{item.row}행{item.facility ? ` · ${item.facility}` : ""}</strong>
        <ul>{item.messages.map((text, i) => <li key={i}>{text}</li>)}</ul></div>
      {admin && item.can_confirm_policy && <button className="button secondary" disabled={busy} onClick={() => onConfirm(item)}>현재 KYWA 기준 적용</button>}
    </div>)}
  </section>;
}
