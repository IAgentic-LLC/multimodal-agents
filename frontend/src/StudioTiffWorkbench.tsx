import { useState } from "react";

import { humanizeApiError } from "./apiError";
import { useStudioToken } from "./useStudioToken";

type UploadResult = {
  doc_id: string;
  claim: string;
  volume_shape: number[];
  channel_count: number;
  instance_counts_by_timepoint: number[];
};

export default function StudioTiffWorkbench() {
  const getToken = useStudioToken();
  const [fileName, setFileName] = useState("");
  const [status, setStatus] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setStatus("Uploading the real TIFF file…");
    setResult(null);
    setPreviewUrl(null);
    try {
      const accessToken = await getToken();
      if (!accessToken) {
        throw new Error("could not get a real access token");
      }
      const form = new FormData();
      form.append("file", file);
      const response = await fetch("/api/studio/upload-tiff", {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
        body: form,
      });
      if (!response.ok) {
        throw new Error(await humanizeApiError(response, "upload failed"));
      }
      const body = (await response.json()) as UploadResult;
      setFileName(file.name);
      setResult(body);
      const previewResponse = await fetch(`/api/studio/tiff-preview/${body.doc_id}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (previewResponse.ok) {
        // A data: URI, not URL.createObjectURL's blob: URI: this app's
        // own real CSP only allows 'self' and data: for img-src
        // (confirmed directly - a blob: <img> src is blocked and
        // logs a real CSP violation), so this reads the real PNG
        // bytes into a base64 data URI instead of relaxing the policy.
        const buffer = await previewResponse.arrayBuffer();
        let binary = "";
        for (const byte of new Uint8Array(buffer)) binary += String.fromCharCode(byte);
        setPreviewUrl(`data:image/png;base64,${btoa(binary)}`);
      }
      setStatus(`Uploaded. ${body.claim}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "upload failed");
    }
  };

  return (
    <section className="stage" style={{ padding: "1rem" }}>
      <h3>Real plain-TIFF / OME-TIFF workbench</h3>
      <p>
        Plain TIFF and OME-TIFF share one real upload path: tifffile's own
        real axes string tells the backend which real file kind it got, a
        real Otsu segmentation runs against the real nuclear channel, and a
        real max-intensity-projection preview renders below.
      </p>
      <input type="file" accept=".tif,.tiff,.ome.tif,.ome.tiff" onChange={handleUpload} />
      <p>{status}</p>
      {result && (
        <dl className="tiff-result-grid">
          <div>
            <dt>File</dt>
            <dd>{fileName}</dd>
          </div>
          <div>
            <dt>Volume shape (C, Z, Y, X)</dt>
            <dd>{result.volume_shape.join(" × ")}</dd>
          </div>
          <div>
            <dt>Channels</dt>
            <dd>{result.channel_count}</dd>
          </div>
          <div>
            <dt>Instances per timepoint</dt>
            <dd>{result.instance_counts_by_timepoint.join(", ")}</dd>
          </div>
        </dl>
      )}
      {previewUrl && (
        <img
          src={previewUrl}
          alt="Real max-intensity-projection preview of the uploaded TIFF's nuclear channel"
          className="tiff-preview-image"
        />
      )}
    </section>
  );
}
