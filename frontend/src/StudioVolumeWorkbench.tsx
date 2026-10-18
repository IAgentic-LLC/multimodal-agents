import { useCallback, useEffect, useRef, useState } from "react";

import { humanizeApiError } from "./apiError";
import { useLiveAgentSession, type LiveCommand } from "./useLiveAgentSession";
import { useStudioToken } from "./useStudioToken";
import VolumeViewer, { type Region, type VolumeViewerHandle, type VolumeViewerState } from "./VolumeViewer";

export default function StudioVolumeWorkbench() {
  const getToken = useStudioToken();
  const [docId, setDocId] = useState<string | null>(null);
  const [fileName, setFileName] = useState("");
  const [status, setStatus] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const viewerRef = useRef<VolumeViewerHandle>(null);

  // Every real command an agent sends goes through the exact same
  // imperative handle the viewer exposes, which in turn sets the exact
  // same React state a person dragging a slider or clicking a button
  // would: the browser responds as if a real person operated it.
  const handleLiveCommand = useCallback(({ action, params }: LiveCommand) => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    switch (action) {
      case "set_window_level":
        viewer.setWindowLevel(Number(params.window), Number(params.level));
        break;
      case "set_colormap":
        viewer.setColormap(String(params.name));
        break;
      case "set_timepoint":
        viewer.setTimepointIndex(Number(params.timepoint));
        break;
      case "snap_axis":
        viewer.snapAxis(String(params.axis));
        break;
      case "set_segmentation_visible":
        viewer.setSegmentationVisible(Boolean(params.visible));
        break;
      case "set_grid_visible":
        viewer.setGridVisible(Boolean(params.visible));
        break;
      case "set_auto_rotate":
        viewer.setAutoRotating(Boolean(params.enabled), params.direction as 1 | -1 | undefined);
        break;
      case "capture_screenshot": {
        const dataUrl = viewer.captureScreenshot();
        const sessionId = liveSessionIdRef.current;
        const accessToken = tokenRef.current;
        if (dataUrl && sessionId && accessToken) {
          void fetch(`/api/studio/live-sessions/${sessionId}/screenshot`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
            body: JSON.stringify({ image_base64: dataUrl }),
          });
        }
        break;
      }
      default:
        break;
    }
  }, []);

  const liveSessionId = useLiveAgentSession("volume", token ?? undefined, handleLiveCommand);
  const liveSessionIdRef = useRef(liveSessionId);
  const tokenRef = useRef(token);
  useEffect(() => {
    liveSessionIdRef.current = liveSessionId;
    tokenRef.current = token;
  }, [liveSessionId, token]);

  // Reports the viewer's own real current state back to the
  // coordinator after every real change, so an agent's
  // get_live_viewer_state call reflects what is genuinely on screen,
  // not just what was last requested (self-correction depends on this
  // being real and current, not a cached assumption).
  const handleStateChange = useCallback((state: VolumeViewerState) => {
    const sessionId = liveSessionIdRef.current;
    const accessToken = tokenRef.current;
    if (!sessionId || !accessToken) return;
    void fetch(`/api/studio/live-sessions/${sessionId}/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify(state),
    });
  }, []);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setStatus("Uploading…");
    try {
      const accessToken = await getToken();
      if (!accessToken) {
        throw new Error("could not get a real access token");
      }
      const form = new FormData();
      form.append("file", file);
      const response = await fetch("/api/studio/upload-volume", {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
        body: form,
      });
      if (!response.ok) {
        throw new Error(await humanizeApiError(response, "upload failed"));
      }
      const body = await response.json();
      setDocId(body.doc_id);
      setFileName(file.name);
      setToken(accessToken);
      setRegions(body.regions ?? []);
      setStatus(`Uploaded. ${body.claim}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "upload failed");
    }
  };

  return (
    <section className="stage" style={{ padding: "1rem" }}>
      <h3>Real studio volume workbench</h3>
      <input type="file" accept=".nii,.nii.gz" onChange={handleUpload} />
      <p>{status}</p>
      {liveSessionId && (
        <p className="live-session-id">
          Live session: <code>{liveSessionId}</code> (give this to an agent to drive this viewer live)
        </p>
      )}
      {docId && token && (
        <VolumeViewer
          ref={viewerRef}
          volumeUrl={`/api/studio/volumes/${docId}`}
          fileName={fileName}
          authToken={token}
          regions={regions}
          onStateChange={handleStateChange}
        />
      )}
    </section>
  );
}
