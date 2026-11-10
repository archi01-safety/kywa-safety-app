/** JPEG transport for browser-readable photos. Native HEIF decoding remains on the pilot origin. */
export async function uploadPhoto(file: File): Promise<File> {
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    return file;
  }
  try {
    if (bitmap.width * bitmap.height > 50_000_000) throw new Error("사진은 5,000만 화소 이하로 선택해 주세요.");
    const ratio = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * ratio));
    canvas.height = Math.max(1, Math.round(bitmap.height * ratio));
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("사진 변환을 시작할 수 없습니다.");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    for (const quality of [0.92, 0.82, 0.7, 0.55]) {
      const blob = await new Promise<Blob | null>(done => canvas.toBlob(done, "image/jpeg", quality));
      if (blob && blob.size <= 3_000_000) return new File([blob], "현장사진.jpg", { type: "image/jpeg" });
    }
    throw new Error("사진을 3MB 이내로 변환하지 못했습니다.");
  } finally {
    bitmap.close();
  }
}
