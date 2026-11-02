// The model reads images up to 3 MB, so larger photos are shrunk in the browser before upload
const MAX_IMAGE_BYTES = 2_500_000;
const MAX_SIDE = 2400;
const QUALITIES = [0.9, 0.8, 0.7];
const EXTENSIONS: Record<string, string> = { "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif" };

export const IMAGE_NAME = /\.(png|jpe?g|webp|gif)$/i;

export function isImage(file: File): boolean {
  return file.type.startsWith("image/");
}

function baseName(name: string): string {
  return name.replace(/\.[^.]+$/, "") || "gambar";
}

function toBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
}

// Keeps small PNG, JPG, WEBP, and GIF files as they are; anything else becomes a JPG of at most 2.5 MB
export async function prepareImage(file: File): Promise<File> {
  const extension = EXTENSIONS[file.type];
  if (extension && file.size <= MAX_IMAGE_BYTES) {
    // a pasted screenshot can arrive without a proper name, and the server picks the reader by extension
    return IMAGE_NAME.test(file.name) ? file : new File([file], `${baseName(file.name)}.${extension}`, { type: file.type });
  }

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error("Format gambar ini tidak bisa dibaca browser. Pakai PNG atau JPG.");
  }
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (context === null) {
    bitmap.close();
    throw new Error("Gambar gagal diproses.");
  }

  try {
    let scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    for (let round = 0; round < 4; round++) {
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      // JPG has no transparency; a white background keeps dark formulas on transparent PNGs readable
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      for (const quality of QUALITIES) {
        const blob = await toBlob(canvas, quality);
        if (blob !== null && blob.size <= MAX_IMAGE_BYTES) {
          return new File([blob], `${baseName(file.name)}.jpg`, { type: "image/jpeg" });
        }
      }
      scale *= 0.75;
    }
  } finally {
    bitmap.close();
  }
  throw new Error("Gambar terlalu besar. Potong bagian soalnya saja lalu coba lagi.");
}