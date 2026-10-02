import { useCallback, useEffect, useRef, useState } from "react";

import ChannelVolumeViewer, {
  type ChannelVolumeViewerHandle,
  type ChannelVolumeViewerState,
} from "./ChannelVolumeViewer";
import FilterPanel, { type FilterApplyResult, type FilterPanelHandle } from "./FilterPanel";
import { useLiveAgentSession, type LiveCommand } from "./useLiveAgentSession";
import { useStudioToken } from "./useStudioToken";

type SourceKind = "ome_zarr" | "plain_zarr";

/** The real IDR dataset used throughout this book's own OME-Zarr
 * validation: the base group URL for OME-Zarr's own NGFF-aware reader,
 * or one specific resolution level's array path for the plain zarr
 * opener, which expects a single array rather than a group.
 */
const DEFAULT_URLS: Record<SourceKind, string> = {
  ome_zarr: "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr",
  plain_zarr: "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr/2",
};

export default function StudioZarrWorkbench() {
  const getToken = useStudioToken();
  const [sourceKind, setSourceKind] = useState<SourceKind>("ome_zarr");
  const [urlInput, setUrlInput] = useState(DEFAULT_URLS.ome_zarr);
  const [axisHintInput, setAxisHintInput] = useState("");
  const [openedUrl, setOpenedUrl] = useState<string | null>(null);
  const [openedAxisHint, setOpenedAxisHint] = useState<string | undefined>(undefined);
  const [openedSourceKind, setOpenedSourceKind] = useState<SourceKind>("ome_zarr");
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const viewerRef = useRef<ChannelVolumeViewerHandle>(null);
  const filterPanelRef = useRef<FilterPanelHandle>(null);

  // report_state's own real contract overwrites the whole state dict
  // per call, so a viewer-state report and a filter-result report
  // (sent independently, from two different components) must be
  // merged here before posting, or each would silently erase the
  // other's real last-known data instead of combining with it.
  const latestViewerStateRef = useRef<ChannelVolumeViewerState | null>(null);
  const latestFilterResultRef = useRef<FilterApplyResult | null>(null);

  const handleLiveCommand = useCallback(({ action, params }: LiveCommand) => {
    const viewer = viewerRef.current;
    switch (action) {
      case "set_channel_state":
        viewer?.setChannelState(Number(params.channel_index), {
          ...(params.visible !== undefined ? { visible: Boolean(params.visible) } : {}),
          ...(params.color_hex !== undefined ? { colorHex: String(params.color_hex) } : {}),
          ...(params.window !== undefined ? { windowWidth: Number(params.window) } : {}),
          ...(params.level !== undefined ? { level: Number(params.level) } : {}),
        });
        break;
      case "set_timepoint":
        viewer?.setTimepointIndex(Number(params.timepoint));
        break;
      case "snap_axis":
        viewer?.snapAxis(String(params.axis));
        break;
      case "set_grid_visible":
        viewer?.setGridVisible(Boolean(params.visible));
        break;
      case "set_auto_rotate":
        viewer?.setAutoRotating(Boolean(params.enabled), params.direction as 1 | -1 | undefined);
        break;
      case "apply_filter_pipeline":
        void filterPanelRef.current?.applyRemotePipeline(
          params.steps as { filter: string; params?: Record<string, number | string> }[],
          params.channel_index !== undefined ? Number(params.channel_index) : undefined,
          params.timepoint !== undefined ? Number(params.timepoint) : undefined,
        );
        break;
      case "set_segmentation_mask_visible":
        viewer?.setSegmentationMaskVisible(
          Boolean(params.visible),
          params.nuclear_channel_index !== undefined ? Number(params.nuclear_channel_index) : undefined,
        );
        break;
      default:
        break;
    }
  }, []);

  const liveSessionId = useLiveAgentSession("channel_volume", token ?? undefined, handleLiveCommand);
  const liveSessionIdRef = useRef(liveSessionId);
  const tokenRef = useRef(token);
  useEffect(() => {
    liveSessionIdRef.current = liveSessionId;
    tokenRef.current = token;
  }, [liveSessionId, token]);

  const postCombinedState = useCallback(() => {
    const sessionId = liveSessionIdRef.current;
    const accessToken = tokenRef.current;
    if (!sessionId || !accessToken) return;
    const combined = {
      ...(latestViewerStateRef.current ?? {}),
      ...(latestFilterResultRef.current
        ? { lastFilterResult: latestFilterResultRef.current }
        : {}),
    };
    void fetch(`/api/studio/live-sessions/${sessionId}/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify(combined),
    });
  }, []);

  const handleStateChange = useCallback(
    (state: ChannelVolumeViewerState) => {
      latestViewerStateRef.current = state;
      postCombinedState();
    },
    [postCombinedState],
  );

  const handleFilterApplied = useCallback(
    (result: FilterApplyResult) => {
      latestFilterResultRef.current = result;
      postCombinedState();
    },
    [postCombinedState],
  );

  const handleOpen = async () => {
    if (!urlInput.trim()) return;
    setStatus("Fetching a real access token…");
    try {
      const accessToken = await getToken();
      if (!accessToken) {
        throw new Error("could not get a real access token");
      }
      setToken(accessToken);
      setOpenedUrl(urlInput.trim());
      setOpenedAxisHint(sourceKind === "plain_zarr" ? axisHintInput.trim() || undefined : undefined);
      setOpenedSourceKind(sourceKind);
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "could not open the real dataset");
    }
  };

  return (
    <section className="stage" style={{ padding: "1rem" }}>
      <h3>Real multi-channel Zarr workbench</h3>
      <p>
        Zarr datasets are a remote reference, not an uploaded file: paste a
        real zarr URL and every real channel renders with its own
        independent color, visibility, and window/level control.
      </p>
      <div className="zarr-source-kind-row" role="radiogroup" aria-label="Zarr source kind">
        <label>
          <input
            type="radio"
            name="zarr-source-kind"
            checked={sourceKind === "ome_zarr"}
            onChange={() => {
              setSourceKind("ome_zarr");
              setUrlInput(DEFAULT_URLS.ome_zarr);
            }}
          />
          OME-Zarr (has real NGFF axes metadata)
        </label>
        <label>
          <input
            type="radio"
            name="zarr-source-kind"
            checked={sourceKind === "plain_zarr"}
            onChange={() => {
              setSourceKind("plain_zarr");
              setUrlInput(DEFAULT_URLS.plain_zarr);
              setAxisHintInput("CZYX");
            }}
          />
          Plain zarr (no OME-NGFF metadata)
        </label>
      </div>
      <input
        type="text"
        value={urlInput}
        onChange={(event) => setUrlInput(event.target.value)}
        style={{ width: "100%" }}
      />
      {sourceKind === "plain_zarr" && (
        <label className="zarr-axis-hint-label">
          Axis hint (optional, e.g. "CZYX" - letters T, C, Z, Y, X in real on-disk order)
          <input
            type="text"
            value={axisHintInput}
            onChange={(event) => setAxisHintInput(event.target.value)}
            placeholder="CZYX"
          />
        </label>
      )}
      <button type="button" onClick={() => void handleOpen()}>
        Open dataset
      </button>
      <p>{status}</p>
      {liveSessionId && (
        <p className="live-session-id">
          Live session: <code>{liveSessionId}</code> (give this to an agent to drive this viewer live)
        </p>
      )}
      {openedUrl && token && (
        <>
          <ChannelVolumeViewer
            ref={viewerRef}
            zarrUrl={openedUrl}
            sourceKind={openedSourceKind}
            axisHint={openedAxisHint}
            authToken={token}
            onStateChange={handleStateChange}
          />
          <FilterPanel
            ref={filterPanelRef}
            sourceKind={openedSourceKind}
            sourceUrl={openedUrl}
            axisHint={openedAxisHint}
            authToken={token}
            onApplied={handleFilterApplied}
          />
        </>
      )}
    </section>
  );
}
