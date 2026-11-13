/** The server fixes the filename when it creates the artifact, including KST date. */
export function downloadName(disposition: string | null): string {
  const encoded = disposition?.match(/filename\*\s*=\s*UTF-8''([^;]+)/i)?.[1];
  const plain = disposition?.match(/filename\s*=\s*"([^"]+)"/i)?.[1];
  let name = plain || "";
  if (encoded) {
    try { name = decodeURIComponent(encoded.trim()); } catch { throw new Error("보고서 파일명을 확인하지 못했습니다. 다시 생성해 주세요."); }
  }
  if (!name || /[\x00-\x1f/\\]/.test(name) || !/\.(pdf|xlsx|hwpx)$/i.test(name)) throw new Error("보고서 파일명을 확인하지 못했습니다. 다시 생성해 주세요.");
  return name;
}
