import type { CaptureMetadata, CaptureResponse } from "./types";

export const makeIdentifier = (prefix: string): string =>
  `${prefix}-${crypto.randomUUID()}`;

export const blobBase64 = async (blob: Blob): Promise<string> => {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  const blockSize = 0x8000;
  for (let start = 0; start < bytes.length; start += blockSize) {
    binary += String.fromCharCode(
      ...bytes.subarray(start, start + blockSize),
    );
  }
  return btoa(binary);
};

export const saveCapture = async (
  metadata: CaptureMetadata,
  frame: string,
  audio: Blob,
): Promise<CaptureResponse> => {
  const response = await fetch("/api/captures", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      metadata,
      frame,
      audio_base64: await blobBase64(audio),
    }),
  });
  const result = (await response.json()) as CaptureResponse;
  if (!response.ok) {
    throw new Error(result.error ?? "Capture save failed");
  }
  return result;
};
