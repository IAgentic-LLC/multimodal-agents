import { useCallback, useEffect, useRef, useState } from "react";

import { humanizeApiError } from "./apiError";
import { useLiveAgentSession, type LiveCommand } from "./useLiveAgentSession";
import { useStudioToken } from "./useStudioToken";

type TrackedDetection = {
  frame_index: number;
  track_id: number;
  class_name: string;
  confidence: number;
  bbox_xyxy: [number, number, number, number];
};

type UploadResult = {
  doc_id: string;
  claim: string;
  frame_count: number;
  tracks: TrackedDetection[][];
};

type DisplayState = {
  frameIndex: number;
  confidenceThreshold: number;
  boxesVisible: boolean;
  highlightedTrackId: number | null;
};

/** A stable color per real track_id (not per detection), so the same
 * real tracked object keeps the same real color across every frame -
 * the visual proof that tracking identity persists, not just per-
 * frame detection.
 */
const TRACK_COLORS = ["#ff3b3b", "#39ff6a", "#4da6ff", "#ffd23b", "#ff3bd6", "#3bfff0", "#ff9f3b", "#8a6bff"];
function colorForTrack(trackId: number): string {
  return TRACK_COLORS[trackId % TRACK_COLORS.length];
}

export default function StudioTrackingWorkbench() {
  const getToken = useStudioToken();
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [docId, setDocId] = useState<string | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(null);
  const [display, setDisplay] = useState<DisplayState>({
    frameIndex: 0,
    confidenceThreshold: 0,
    boxesVisible: true,
    highlightedTrackId: null,
  });

  const handleLiveCommand = useCallback(({ action, params }: LiveCommand) => {
    if (action !== "set_track_display") return;
    setDisplay((current) => ({
      frameIndex: params.frame_index !== undefined ? Number(params.frame_index) : current.frameIndex,
      confidenceThreshold:
        params.confidence_threshold !== undefined
          ? Number(params.confidence_threshold)
          : current.confidenceThreshold,
      boxesVisible:
        params.boxes_visible !== undefined ? Boolean(params.boxes_visible) : current.boxesVisible,
      highlightedTrackId:
        params.highlighted_track_id !== undefined
          ? Number(params.highlighted_track_id)
          : current.highlightedTrackId,
    }));
  }, []);

  const liveSessionId = useLiveAgentSession("tracking", token ?? undefined, handleLiveCommand);
  const liveSessionIdRef = useRef(liveSessionId);
  const tokenRef = useRef(token);
  useEffect(() => {
    liveSessionIdRef.current = liveSessionId;
    tokenRef.current = token;
  }, [liveSessionId, token]);

  useEffect(() => {
    const sessionId = liveSessionIdRef.current;
    const accessToken = tokenRef.current;
    if (!sessionId || !accessToken || !result) return;
    void fetch(`/api/studio/live-sessions/${sessionId}/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({
        frameIndex: display.frameIndex,
        confidenceThreshold: display.confidenceThreshold,
        boxesVisible: display.boxesVisible,
        highlightedTrackId: display.highlightedTrackId,
        frameCount: result.frame_count,
        detectionsThisFrame: result.tracks[display.frameIndex] ?? [],
        claim: result.claim,
      }),
    });
  }, [display, result]);

  // Fetches the real extracted frame image whenever the frame index
  // or the uploaded video changes, the same data-URI approach
  // StudioTiffWorkbench already uses: this app's own real CSP allows
  // 'self' and data: for img-src, not blob:, confirmed directly.
  useEffect(() => {
    if (!docId || !token) return;
    let disposed = false;
    (async () => {
      try {
        const response = await fetch(`/api/studio/video-frame/${docId}/${display.frameIndex}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok || disposed) return;
        const buffer = await response.arrayBuffer();
        let binary = "";
        for (const byte of new Uint8Array(buffer)) binary += String.fromCharCode(byte);
        if (!disposed) setImageUrl(`data:image/png;base64,${btoa(binary)}`);
      } catch {
        // A failed frame fetch just leaves the previous real frame on
        // screen rather than erroring the whole workbench out.
      }
    })();
    return () => {
      disposed = true;
    };
  }, [docId, token, display.frameIndex]);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setStatus("Uploading and running real tracking…");
    setResult(null);
    setDocId(null);
    setImageUrl(null);
    setImageSize(null);
    setDisplay({ frameIndex: 0, confidenceThreshold: 0, boxesVisible: true, highlightedTrackId: null });
    try {
      const accessToken = await getToken();
      if (!accessToken) {
        throw new Error("could not get a real access token");
      }
      setToken(accessToken);
      const form = new FormData();
      form.append("file", file);
      const response = await fetch("/api/studio/upload-video", {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
        body: form,
      });
      if (!response.ok) {
        throw new Error(await humanizeApiError(response, "upload failed"));
      }
      const body = (await response.json()) as UploadResult;
      setResult(body);
      setDocId(body.doc_id);
      setStatus(`Uploaded. ${body.claim}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "upload failed");
    }
  };

  const frameDetections = result?.tracks[display.frameIndex] ?? [];
  const visibleDetections = frameDetections.filter((detection) => {
    if (!display.boxesVisible) return false;
    if (detection.track_id === display.highlightedTrackId) return true;
    return detection.confidence >= display.confidenceThreshold;
  });

  return (
    <section className="stage" style={{ padding: "1rem" }}>
      <h3>Real multi-frame object tracking workbench</h3>
      <p>
        A real yolo11n + ByteTrack pipeline runs against whatever video you
        upload; the same real track_id colors the same real tracked object
        consistently as you scrub between frames.
      </p>
      <input type="file" accept="video/*" onChange={handleUpload} />
      <p>{status}</p>
      {liveSessionId && (
        <p className="live-session-id">
          Live session: <code>{liveSessionId}</code> (give this to an agent to drive this viewer live)
        </p>
      )}
      {result && (
        <div className="detection-controls">
          <label>
            Frame ({display.frameIndex} / {result.frame_count - 1})
            <input
              type="range"
              min={0}
              max={Math.max(result.frame_count - 1, 0)}
              value={display.frameIndex}
              onChange={(event) => setDisplay((current) => ({ ...current, frameIndex: Number(event.target.value) }))}
            />
          </label>
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
            alt="Real uploaded video frame with real tracked detections"
            onLoad={(event) =>
              setImageSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })
            }
          />
          <svg
            className="detection-overlay"
            viewBox={`0 0 ${imageSize.width} ${imageSize.height}`}
            preserveAspectRatio="none"
          >
            {visibleDetections.map((detection) => {
              const [x1, y1, x2, y2] = detection.bbox_xyxy;
              const isHighlighted = detection.track_id === display.highlightedTrackId;
              const color = colorForTrack(detection.track_id);
              return (
                <g key={detection.track_id}>
                  <rect
                    x={x1}
                    y={y1}
                    width={x2 - x1}
                    height={y2 - y1}
                    className={isHighlighted ? "detection-box detection-box-highlighted" : "detection-box"}
                    style={{ stroke: color }}
                  />
                  <text x={x1} y={Math.max(y1 - 4, 10)} className="detection-label" style={{ fill: color }}>
                    #{detection.track_id} {detection.class_name} {detection.confidence.toFixed(2)}
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
          alt="Real uploaded video frame with real tracked detections"
          onLoad={(event) =>
            setImageSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })
          }
        />
      )}
    </section>
  );
}
