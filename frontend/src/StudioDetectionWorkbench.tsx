import { useCallback, useEffect, useRef, useState } from "react";

import { humanizeApiError } from "./apiError";
import { useLiveAgentSession, type LiveCommand } from "./useLiveAgentSession";
import { useStudioToken } from "./useStudioToken";

type Detection = {
  class_name: string;
  confidence: number;
  bbox_xyxy: [number, number, number, number];
};

type UploadResult = {
  doc_id: string;
  claim: string;
  detections: Detection[];
};

type DisplayState = {
  confidenceThreshold: number;
  boxesVisible: boolean;
  highlightedIndex: number | null;
};

export default function StudioDetectionWorkbench() {
  const getToken = useStudioToken();
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(null);
  const [display, setDisplay] = useState<DisplayState>({
    confidenceThreshold: 0,
    boxesVisible: true,
    highlightedIndex: null,
  });

  const handleLiveCommand = useCallback(({ action, params }: LiveCommand) => {
    if (action !== "set_detection_display") return;
    setDisplay((current) => ({
      confidenceThreshold:
        params.confidence_threshold !== undefined
          ? Number(params.confidence_threshold)
          : current.confidenceThreshold,
      boxesVisible:
        params.boxes_visible !== undefined ? Boolean(params.boxes_visible) : current.boxesVisible,
      highlightedIndex:
        params.highlighted_index !== undefined ? Number(params.highlighted_index) : current.highlightedIndex,
    }));
  }, []);

  const liveSessionId = useLiveAgentSession("detection", token ?? undefined, handleLiveCommand);
  const liveSessionIdRef = useRef(liveSessionId);
  const tokenRef = useRef(token);
  useEffect(() => {
    liveSessionIdRef.current = liveSessionId;
    tokenRef.current = token;
  }, [liveSessionId, token]);

  // Reports the real current display state after every real change,
  // whether triggered by a person using the controls below or an
  // agent's live command, the same self-correction contract every
  // other live-controlled viewer in this app already follows.
  useEffect(() => {
    const sessionId = liveSessionIdRef.current;
    const accessToken = tokenRef.current;
    if (!sessionId || !accessToken || !result) return;
    void fetch(`/api/studio/live-sessions/${sessionId}/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({
        confidenceThreshold: display.confidenceThreshold,
        boxesVisible: display.boxesVisible,
        highlightedIndex: display.highlightedIndex,
        detections: result.detections,
        claim: result.claim,
      }),
    });
  }, [display, result]);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setStatus("Uploading and running real YOLO detection…");
    setResult(null);
    setImageUrl(null);
    setImageSize(null);
    setDisplay({ confidenceThreshold: 0, boxesVisible: true, highlightedIndex: null });
    try {
      const accessToken = await getToken();
      if (!accessToken) {
        throw new Error("could not get a real access token");
      }
      setToken(accessToken);
      const form = new FormData();
      form.append("file", file);
      const response = await fetch("/api/studio/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
        body: form,
      });
      if (!response.ok) {
        throw new Error(await humanizeApiError(response, "upload failed"));
      }
      const body = (await response.json()) as UploadResult;
      setResult(body);

      const previewResponse = await fetch(`/api/studio/volumes/${body.doc_id}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (previewResponse.ok) {
        const buffer = await previewResponse.arrayBuffer();
        let binary = "";
        for (const byte of new Uint8Array(buffer)) binary += String.fromCharCode(byte);
        setImageUrl(`data:image/png;base64,${btoa(binary)}`);
      }
      setStatus(`Uploaded. ${body.claim}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "upload failed");
    }
  };

  const visibleDetections = (result?.detections ?? []).filter((detection, index) => {
    if (!display.boxesVisible) return false;
    if (index === display.highlightedIndex) return true;
    return detection.confidence >= display.confidenceThreshold;
  });

  return (
    <section className="stage" style={{ padding: "1rem" }}>
      <h3>Real object detection workbench</h3>
      <p>
        A real yolo11n model runs against whatever image you upload; every real
        bounding box, class name, and confidence score below is the model's own
        real output, not a fixture.
      </p>
      <input type="file" accept="image/*" onChange={handleUpload} />
      <p>{status}</p>
      {liveSessionId && (
        <p className="live-session-id">
          Live session: <code>{liveSessionId}</code> (give this to an agent to drive this viewer live)
        </p>
      )}
      {result && (
        <div className="detection-controls">
          <label>
            Confidence threshold ({display.confidenceThreshold.toFixed(2)})
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={display.confidenceThreshold}
              onChange={(event) =>
                setDisplay((current) => ({ ...current, confidenceThreshold: Number(event.target.value) }))
              }
            />
          </label>
          <label className="volume-viewer-checkbox">
            <input
              type="checkbox"
              checked={display.boxesVisible}
              onChange={(event) => setDisplay((current) => ({ ...current, boxesVisible: event.target.checked }))}
            />
            Show boxes
          </label>
        </div>
      )}
      {imageUrl && imageSize && (
        <div className="detection-image-wrap" style={{ aspectRatio: `${imageSize.width} / ${imageSize.height}` }}>
          <img
            src={imageUrl}
            alt="Real uploaded image with real yolo11n detections"
            onLoad={(event) =>
              setImageSize({
                width: event.currentTarget.naturalWidth,
                height: event.currentTarget.naturalHeight,
              })
            }
          />
          <svg
            className="detection-overlay"
            viewBox={`0 0 ${imageSize.width} ${imageSize.height}`}
            preserveAspectRatio="none"
          >
            {visibleDetections.map((detection) => {
              const index = result?.detections.indexOf(detection) ?? -1;
              const [x1, y1, x2, y2] = detection.bbox_xyxy;
              const isHighlighted = index === display.highlightedIndex;
              return (
                <g key={index}>
                  <rect
                    x={x1}
                    y={y1}
                    width={x2 - x1}
                    height={y2 - y1}
                    className={isHighlighted ? "detection-box detection-box-highlighted" : "detection-box"}
                  />
                  <text x={x1} y={Math.max(y1 - 4, 10)} className="detection-label">
                    {detection.class_name} {detection.confidence.toFixed(2)}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      )}
      {imageUrl && !imageSize && (
        <img
          src={imageUrl}
          alt="Real uploaded image with real yolo11n detections"
          onLoad={(event) =>
            setImageSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })
          }
        />
      )}
    </section>
  );
}
