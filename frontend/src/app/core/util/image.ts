const MAX_SIDE = 1280;
const QUALITY = 0.8;

/**
 * Reduce la foto antes de enviarla (las cámaras de celular superan fácilmente los 5 MB
 * que acepta el servidor). Si el navegador no puede, devuelve el archivo original.
 */
export async function compressImage(file: File): Promise<File> {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', QUALITY),
    );
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], 'constancia.jpg', { type: 'image/jpeg' });
  } catch {
    return file;
  }
}
