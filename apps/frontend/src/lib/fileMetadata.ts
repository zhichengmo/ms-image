export interface QualifiedFileMetadata {
  fileFormat: "jpeg" | "png" | "dicom";
  contentType: "image/jpeg" | "image/png" | "application/dicom";
  sha256: string;
  sizeBytes: number;
}
function toHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export async function inspectFile(file: File): Promise<QualifiedFileMetadata> {
  const lowerName = file.name.toLowerCase();
  let fileFormat: QualifiedFileMetadata["fileFormat"];
  let contentType: QualifiedFileMetadata["contentType"];

  if (file.type === "image/jpeg" || /\.jpe?g$/.test(lowerName)) {
    fileFormat = "jpeg";
    contentType = "image/jpeg";
  } else if (file.type === "image/png" || lowerName.endsWith(".png")) {
    fileFormat = "png";
    contentType = "image/png";
  } else if (
    file.type === "application/dicom" ||
    lowerName.endsWith(".dcm") ||
    lowerName.endsWith(".dicom")
  ) {
    fileFormat = "dicom";
    contentType = "application/dicom";
  } else {
    throw new Error(`不支持的文件格式：${file.name}。仅支持 JPEG、PNG 或 DICOM。`);
  }

  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return {
    fileFormat,
    contentType,
    sha256: toHex(digest),
    sizeBytes: file.size,
  };
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
