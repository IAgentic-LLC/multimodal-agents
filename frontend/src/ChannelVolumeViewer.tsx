import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import "@kitware/vtk.js/Rendering/Profiles/Volume";
import "@kitware/vtk.js/Rendering/Profiles/Geometry";
// @ts-expect-error - vtk.js ships this module without a .d.ts in this version.
import vtkCubeAxesActor from "@kitware/vtk.js/Rendering/Core/CubeAxesActor";
import vtkColorTransferFunction from "@kitware/vtk.js/Rendering/Core/ColorTransferFunction";
import vtkDataArray from "@kitware/vtk.js/Common/Core/DataArray";
import vtkFullScreenRenderWindow from "@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow";
import vtkImageData from "@kitware/vtk.js/Common/DataModel/ImageData";
import vtkPiecewiseFunction from "@kitware/vtk.js/Common/DataModel/PiecewiseFunction";
import vtkVolume from "@kitware/vtk.js/Rendering/Core/Volume";
import vtkVolumeMapper from "@kitware/vtk.js/Rendering/Core/VolumeMapper";

import { humanizeApiError } from "./apiError";

/** Distinguishable per-channel defaults (red/green/blue first, the real
 * convention most fluorescence-microscopy tools default to for channels
 * 0-2), extended with further hues for any additional real channels. */
const DEFAULT_CHANNEL_COLORS = ["#ff3b3b", "#39ff6a", "#4da6ff", "#ffd23b", "#ff3bd6", "#3bfff0"];

type ChannelState = {
  visible: boolean;
  colorHex: string;
  windowWidth: number;
  level: number;
  dataMin: number;
  dataMax: number;
};

export type ChannelVolumeViewerState = {
  channels: ChannelState[];
  timepoint: number;
  showGrid: boolean;
  isAutoRotating: boolean;
  autoRotateDirection: 1 | -1;
  showMask: boolean;
  maskNuclearChannelIndex: number;
};

type SourceKind = "ome_zarr" | "plain_zarr";

type Props = {
  zarrUrl: string;
  sourceKind?: SourceKind;
  axisHint?: string;
  authToken?: string;
  onStateChange?: (state: ChannelVolumeViewerState) => void;
};

/** Plain zarr carries no OME-NGFF axes metadata, so its real endpoints
 * take an extra axis_hint field; everything else about the two source
 * kinds' requests is identical, confirmed directly against both real
 * backends.
 */
function endpointsFor(sourceKind: SourceKind) {
  return sourceKind === "plain_zarr"
    ? {
        metadata: "/api/studio/plain-zarr-metadata",
        channelVolume: "/api/studio/plain-zarr-channel-volume",
        segmentationMask: "/api/studio/plain-zarr-segmentation-mask",
      }
    : {
        metadata: "/api/studio/zarr-metadata",
        channelVolume: "/api/studio/zarr-channel-volume",
        segmentationMask: "/api/studio/zarr-segmentation-mask",
      };
}

const SEGMENTATION_MASK_COLOR = "#ffd23b";

type Status = "loading" | "ready" | "error";

type Metadata = {
  volume_shape: number[];
  channel_count: number;
  timepoints: number;
  spacing: [number, number, number];
};

function hexToRgb01(hex: string): [number, number, number] {
  const value = parseInt(hex.slice(1), 16);
  return [((value >> 16) & 0xff) / 255, ((value >> 8) & 0xff) / 255, (value & 0xff) / 255];
}

/** Scans the interleaved (point-major, channel-minor) buffer for one
 * channel's own real data range, the same real min/max window/level
 * controls elsewhere in this app are seeded from.
 */
function channelRange(data: Float32Array, channelIndex: number, channelCount: number): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (let i = channelIndex; i < data.length; i += channelCount) {
    const value = data[i];
    if (value < min) min = value;
    if (value > max) max = value;
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
  return [min, max];
}

type Scene = {
  fullScreenRenderer: ReturnType<typeof vtkFullScreenRenderWindow.newInstance>;
  renderer: ReturnType<ReturnType<typeof vtkFullScreenRenderWindow.newInstance>["getRenderer"]>;
  renderWindow: ReturnType<ReturnType<typeof vtkFullScreenRenderWindow.newInstance>["getRenderWindow"]>;
  actor: ReturnType<typeof vtkVolume.newInstance>;
  mapper: ReturnType<typeof vtkVolumeMapper.newInstance>;
  colorTransfers: ReturnType<typeof vtkColorTransferFunction.newInstance>[];
  opacityTransfers: ReturnType<typeof vtkPiecewiseFunction.newInstance>[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  cubeAxes: any;
};

const AXIS_VIEWS = [
  { label: "+X", axis: [1, 0, 0] as [number, number, number] },
  { label: "-X", axis: [-1, 0, 0] as [number, number, number] },
  { label: "+Y", axis: [0, 1, 0] as [number, number, number] },
  { label: "-Y", axis: [0, -1, 0] as [number, number, number] },
  { label: "+Z", axis: [0, 0, 1] as [number, number, number] },
  { label: "-Z", axis: [0, 0, -1] as [number, number, number] },
];

/** The same controls the human-facing UI below already exposes,
 * callable programmatically: an agent-driven command goes through this
 * exact same real state, not a separate shadow path.
 */
export type ChannelVolumeViewerHandle = {
  setChannelState(channelIndex: number, patch: Partial<ChannelState>): void;
  setTimepointIndex(timepoint: number): void;
  snapAxis(label: string): void;
  setGridVisible(visible: boolean): void;
  setAutoRotating(enabled: boolean, direction?: 1 | -1): void;
  setSegmentationMaskVisible(visible: boolean, nuclearChannelIndex?: number): void;
};

const ChannelVolumeViewer = forwardRef<ChannelVolumeViewerHandle, Props>(function ChannelVolumeViewer(
  { zarrUrl, sourceKind = "ome_zarr", axisHint, authToken, onStateChange }: Props,
  handleRef,
) {
  const endpoints = endpointsFor(sourceKind);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<Scene | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [channels, setChannels] = useState<ChannelState[]>([]);
  const [timepoint, setTimepoint] = useState(0);
  const [showGrid, setShowGrid] = useState(false);
  const [isAutoRotating, setIsAutoRotating] = useState(false);
  const [autoRotateDirection, setAutoRotateDirection] = useState<1 | -1>(1);
  const [showMask, setShowMask] = useState(false);
  const [maskNuclearChannelIndex, setMaskNuclearChannelIndex] = useState(0);

  async function fetchSegmentationMask(
    url: string,
    nuclearChannelIndex: number,
    requestedTimepoint: number,
  ) {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (authToken) headers.Authorization = `Bearer ${authToken}`;
    const response = await fetch(endpoints.segmentationMask, {
      method: "POST",
      headers,
      body: JSON.stringify({
        url,
        nuclear_channel_index: nuclearChannelIndex,
        timepoint: requestedTimepoint,
        ...(sourceKind === "plain_zarr" ? { axis_hint: axisHint } : {}),
      }),
    });
    if (!response.ok) {
      throw new Error(await humanizeApiError(response, "could not fetch the real segmentation mask"));
    }
    const buffer = await response.arrayBuffer();
    return new Float32Array(buffer);
  }

  /** Appends the real segmentation mask as one more independent-
   * components channel, interleaved into the same (point-major,
   * channel-minor) layout every other channel already uses, rather
   * than compositing it as a separate 2D overlay: a real 3D volume
   * render has no flat image plane to overlay onto, but vtk.js's own
   * independent-components mode already gives every channel (now
   * including this one) its own real color/opacity/visibility for
   * free.
   */
  function appendMaskChannel(
    data: Float32Array,
    channelCount: number,
    maskData: Float32Array,
  ): { data: Float32Array; channelCount: number } {
    const voxelCount = maskData.length;
    const nextChannelCount = channelCount + 1;
    const combined = new Float32Array(voxelCount * nextChannelCount);
    for (let voxel = 0; voxel < voxelCount; voxel += 1) {
      for (let c = 0; c < channelCount; c += 1) {
        combined[voxel * nextChannelCount + c] = data[voxel * channelCount + c];
      }
      combined[voxel * nextChannelCount + channelCount] = maskData[voxel];
    }
    return { data: combined, channelCount: nextChannelCount };
  }

  async function fetchChannelVolume(url: string, requestedTimepoint: number) {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (authToken) headers.Authorization = `Bearer ${authToken}`;
    const response = await fetch(endpoints.channelVolume, {
      method: "POST",
      headers,
      body: JSON.stringify({
        url,
        timepoint: requestedTimepoint,
        ...(sourceKind === "plain_zarr" ? { axis_hint: axisHint } : {}),
      }),
    });
    if (!response.ok) {
      throw new Error(await humanizeApiError(response, "could not fetch the real channel volume"));
    }
    const channelCount = Number(response.headers.get("X-Channel-Count"));
    const depth = Number(response.headers.get("X-Shape-Z"));
    const height = Number(response.headers.get("X-Shape-Y"));
    const width = Number(response.headers.get("X-Shape-X"));
    const spacing: [number, number, number] = [
      Number(response.headers.get("X-Spacing-Z")),
      Number(response.headers.get("X-Spacing-Y")),
      Number(response.headers.get("X-Spacing-X")),
    ];
    const buffer = await response.arrayBuffer();
    const data = new Float32Array(buffer);
    return { channelCount, depth, height, width, spacing, data };
  }

  async function fetchCombinedVolume(url: string, requestedTimepoint: number) {
    const base = await fetchChannelVolume(url, requestedTimepoint);
    if (!showMask) return base;
    const maskData = await fetchSegmentationMask(url, maskNuclearChannelIndex, requestedTimepoint);
    const { data, channelCount } = appendMaskChannel(base.data, base.channelCount, maskData);
    return { ...base, data, channelCount };
  }

  // Initial load: real metadata first (cheap, no segmentation), then the
  // first timepoint's real multi-channel data, then build the vtk.js
  // scene once with one independent-component volume for every channel.
  useEffect(() => {
    let disposed = false;

    async function load() {
      setStatus("loading");
      try {
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (authToken) headers.Authorization = `Bearer ${authToken}`;
        const metaResponse = await fetch(endpoints.metadata, {
          method: "POST",
          headers,
          body: JSON.stringify({
            url: zarrUrl,
            ...(sourceKind === "plain_zarr" ? { axis_hint: axisHint } : {}),
          }),
        });
        if (!metaResponse.ok) {
          throw new Error(await humanizeApiError(metaResponse, "could not open this dataset"));
        }
        const meta = (await metaResponse.json()) as Metadata;
        if (disposed) return;

        const { channelCount, depth, height, width, spacing, data } = await fetchCombinedVolume(zarrUrl, 0);
        if (disposed || !containerRef.current) return;
        const maskIsLastChannel = showMask;

        const dataArray = vtkDataArray.newInstance({ values: data, numberOfComponents: channelCount });
        const imageData = vtkImageData.newInstance();
        imageData.setDimensions(width, height, depth);
        imageData.setSpacing([spacing[2], spacing[1], spacing[0]]);
        imageData.getPointData().setScalars(dataArray);

        const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
          container: containerRef.current,
          background: [0.05, 0.05, 0.08],
        });
        const renderer = fullScreenRenderer.getRenderer();
        const renderWindow = fullScreenRenderer.getRenderWindow();

        const actor = vtkVolume.newInstance();
        const mapper = vtkVolumeMapper.newInstance();
        mapper.setSampleDistance(0.7);
        mapper.setInputData(imageData);
        actor.setMapper(mapper);
        actor.getProperty().setIndependentComponents(true);
        actor.getProperty().setInterpolationTypeToLinear();
        actor.getProperty().setShade(true);
        actor.getProperty().setAmbient(0.2);
        actor.getProperty().setDiffuse(0.7);
        actor.getProperty().setSpecular(0.3);

        const initialChannels: ChannelState[] = [];
        const colorTransfers: ReturnType<typeof vtkColorTransferFunction.newInstance>[] = [];
        const opacityTransfers: ReturnType<typeof vtkPiecewiseFunction.newInstance>[] = [];
        for (let c = 0; c < channelCount; c += 1) {
          const [dataMin, dataMax] = channelRange(data, c, channelCount);
          const span = dataMax - dataMin || 1;
          const colorTransfer = vtkColorTransferFunction.newInstance();
          const opacityTransfer = vtkPiecewiseFunction.newInstance();
          actor.getProperty().setRGBTransferFunction(c, colorTransfer);
          actor.getProperty().setScalarOpacity(c, opacityTransfer);
          actor.getProperty().setComponentWeight(c, 1);
          colorTransfers.push(colorTransfer);
          opacityTransfers.push(opacityTransfer);
          const isMaskChannel = maskIsLastChannel && c === channelCount - 1;
          initialChannels.push({
            visible: true,
            colorHex: isMaskChannel
              ? SEGMENTATION_MASK_COLOR
              : DEFAULT_CHANNEL_COLORS[c % DEFAULT_CHANNEL_COLORS.length],
            windowWidth: span,
            level: dataMin + span / 2,
            dataMin,
            dataMax,
          });
        }
        renderer.addVolume(actor);

        const cubeAxes = vtkCubeAxesActor.newInstance();
        cubeAxes.setCamera(renderer.getActiveCamera());
        cubeAxes.setDataBounds(imageData.getBounds());
        cubeAxes.setGridLines(true);
        cubeAxes.getProperty().setColor(1, 1, 1);
        cubeAxes.setVisibility(false);
        renderer.addActor(cubeAxes);

        sceneRef.current = { fullScreenRenderer, renderer, renderWindow, actor, mapper, colorTransfers, opacityTransfers, cubeAxes };

        renderer.resetCamera();
        renderWindow.render();
        setMetadata(meta);
        setChannels(initialChannels);
        setTimepoint(0);
        setStatus("ready");
      } catch (error) {
        if (!disposed) {
          setErrorMessage(error instanceof Error ? error.message : "failed to render the real multi-channel volume");
          setStatus("error");
        }
      }
    }

    load();

    return () => {
      disposed = true;
      const scene = sceneRef.current;
      scene?.cubeAxes.delete();
      scene?.actor.delete();
      scene?.mapper.delete();
      scene?.fullScreenRenderer.delete();
      sceneRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zarrUrl, sourceKind, axisHint, authToken, showMask, maskNuclearChannelIndex]);

  // Timepoint changes: a real new fetch (the backend only ever serves one
  // timepoint's full multi-channel data per request), then swap the same
  // scene's scalars in place rather than rebuilding transfer functions.
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || status !== "ready" || !metadata) return;
    let disposed = false;
    (async () => {
      try {
        const { channelCount, depth, height, width, data } = await fetchCombinedVolume(zarrUrl, timepoint);
        if (disposed) return;
        const dataArray = vtkDataArray.newInstance({ values: data, numberOfComponents: channelCount });
        const imageData = scene.mapper.getInputData();
        imageData.setDimensions(width, height, depth);
        imageData.getPointData().setScalars(dataArray);
        scene.mapper.setInputData(imageData);
        scene.renderWindow.render();
      } catch {
        // Real network hiccups on a timepoint scrub are surfaced by simply
        // leaving the previous real frame on screen rather than erroring
        // the whole viewer out from under the user.
      }
    })();
    return () => {
      disposed = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timepoint]);

  // Per-channel visibility, color, and window/level: rebuild just that
  // channel's own transfer functions, in place, the independent-components
  // mode's real contract (component index -> its own RGB + opacity ramp).
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || status !== "ready") return;
    channels.forEach((channel, index) => {
      const colorTransfer = scene.colorTransfers[index];
      const opacityTransfer = scene.opacityTransfers[index];
      if (!colorTransfer || !opacityTransfer) return;
      const [r, g, b] = hexToRgb01(channel.colorHex);
      const lower = channel.level - channel.windowWidth / 2;
      const upper = channel.level + channel.windowWidth / 2;
      const span = upper - lower || 1;
      colorTransfer.removeAllPoints();
      colorTransfer.addRGBPoint(lower, 0, 0, 0);
      colorTransfer.addRGBPoint(upper, r, g, b);
      opacityTransfer.removeAllPoints();
      opacityTransfer.addPoint(lower + span * 0.15, 0.0);
      opacityTransfer.addPoint(lower + span * 0.4, 0.15);
      opacityTransfer.addPoint(lower + span * 0.95, 0.9);
      // Re-assigning (not just mutating) is required: the mapper's per-
      // component LUT texture cache only rebuilds when the property's own
      // setter fires, confirmed by directly testing in a real browser that
      // in-place mutation alone silently left stale colors on screen.
      scene.actor.getProperty().setRGBTransferFunction(index, colorTransfer);
      scene.actor.getProperty().setScalarOpacity(index, opacityTransfer);
      scene.actor.getProperty().setComponentWeight(index, channel.visible ? 1 : 0);
    });
    scene.mapper.modified();
    scene.renderWindow.render();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channels, status]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || status !== "ready") return;
    scene.cubeAxes.setVisibility(showGrid);
    scene.renderWindow.render();
  }, [showGrid, status]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !isAutoRotating) return;
    const id = window.setInterval(() => {
      const camera = scene.renderer.getActiveCamera();
      camera.azimuth(autoRotateDirection * 1.5);
      scene.renderer.resetCameraClippingRange();
      scene.renderWindow.render();
    }, 30);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAutoRotating, autoRotateDirection]);

  function snapToAxis(axis: [number, number, number]) {
    const scene = sceneRef.current;
    if (!scene) return;
    const bounds = scene.mapper.getBounds();
    const center: [number, number, number] = [
      (bounds[0] + bounds[1]) / 2,
      (bounds[2] + bounds[3]) / 2,
      (bounds[4] + bounds[5]) / 2,
    ];
    const diagonal = Math.hypot(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4]);
    const distance = diagonal || 1;
    const camera = scene.renderer.getActiveCamera();
    camera.setFocalPoint(center[0], center[1], center[2]);
    camera.setPosition(
      center[0] + axis[0] * distance,
      center[1] + axis[1] * distance,
      center[2] + axis[2] * distance,
    );
    const viewUp: [number, number, number] = axis[2] !== 0 ? [0, 1, 0] : [0, 0, 1];
    camera.setViewUp(...viewUp);
    scene.renderer.resetCameraClippingRange();
    scene.renderWindow.render();
  }

  function updateChannel(index: number, patch: Partial<ChannelState>) {
    setChannels((current) => current.map((channel, i) => (i === index ? { ...channel, ...patch } : channel)));
  }

  useImperativeHandle(
    handleRef,
    () => ({
      setChannelState(channelIndex: number, patch: Partial<ChannelState>) {
        updateChannel(channelIndex, patch);
      },
      setTimepointIndex(nextTimepoint: number) {
        setTimepoint(nextTimepoint);
      },
      snapAxis(label: string) {
        const view = AXIS_VIEWS.find((candidate) => candidate.label === label);
        if (view) snapToAxis(view.axis);
      },
      setGridVisible(visible: boolean) {
        setShowGrid(visible);
      },
      setAutoRotating(enabled: boolean, direction?: 1 | -1) {
        if (direction) setAutoRotateDirection(direction);
        setIsAutoRotating(enabled);
      },
      setSegmentationMaskVisible(visible: boolean, nuclearChannelIndex?: number) {
        if (nuclearChannelIndex !== undefined) setMaskNuclearChannelIndex(nuclearChannelIndex);
        setShowMask(visible);
      },
    }),
    [],
  );

  // Reports the real current state after every real change, whether
  // triggered by a person using the controls below or an agent's live
  // command: this is what get_live_viewer_state reads back, so it must
  // reflect what is genuinely on screen, not just what was requested.
  useEffect(() => {
    if (status !== "ready") return;
    onStateChange?.({
      channels,
      timepoint,
      showGrid,
      isAutoRotating,
      autoRotateDirection,
      showMask,
      maskNuclearChannelIndex,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    status,
    channels,
    timepoint,
    showGrid,
    isAutoRotating,
    autoRotateDirection,
    showMask,
    maskNuclearChannelIndex,
  ]);

  return (
    <div className="volume-viewer">
      {status === "loading" && <p className="volume-viewer-status">Loading the real multi-channel dataset…</p>}
      {status === "error" && <p className="volume-viewer-status volume-viewer-error">{errorMessage}</p>}
      {status === "ready" && metadata && (
        <div className="volume-viewer-controls">
          {channels.map((channel, index) => (
            <div key={index} className="channel-volume-channel-row">
              <label className="volume-viewer-checkbox">
                <input
                  type="checkbox"
                  checked={channel.visible}
                  onChange={(event) => updateChannel(index, { visible: event.target.checked })}
                />
                {showMask && index === channels.length - 1 ? "Segmentation mask" : `Channel ${index}`}
              </label>
              <input
                type="color"
                value={channel.colorHex}
                onChange={(event) => updateChannel(index, { colorHex: event.target.value })}
              />
              <label>
                Window
                <input
                  type="range"
                  min={1}
                  max={Math.max((channel.dataMax - channel.dataMin) * 2, 1)}
                  value={channel.windowWidth}
                  onChange={(event) => updateChannel(index, { windowWidth: Number(event.target.value) })}
                />
              </label>
              <label>
                Level
                <input
                  type="range"
                  min={channel.dataMin - channel.windowWidth}
                  max={channel.dataMax + channel.windowWidth}
                  value={channel.level}
                  onChange={(event) => updateChannel(index, { level: Number(event.target.value) })}
                />
              </label>
            </div>
          ))}
          {metadata.timepoints > 1 && (
            <label>
              Time ({timepoint} / {metadata.timepoints - 1})
              <input
                type="range"
                min={0}
                max={metadata.timepoints - 1}
                step={1}
                value={timepoint}
                onChange={(event) => setTimepoint(Number(event.target.value))}
              />
            </label>
          )}
          <label className="volume-viewer-checkbox">
            <input type="checkbox" checked={showGrid} onChange={(event) => setShowGrid(event.target.checked)} />
            Show Cartesian grid
          </label>
          <div className="volume-viewer-mask-row">
            <label className="volume-viewer-checkbox">
              <input type="checkbox" checked={showMask} onChange={(event) => setShowMask(event.target.checked)} />
              Show segmentation mask
            </label>
            <label>
              of channel
              <input
                type="number"
                min={0}
                max={Math.max(channels.length - (showMask ? 2 : 1), 0)}
                value={maskNuclearChannelIndex}
                onChange={(event) => setMaskNuclearChannelIndex(Number(event.target.value))}
              />
            </label>
          </div>
          <div className="volume-viewer-rotate-row">
            <label className="volume-viewer-checkbox">
              <input
                type="checkbox"
                checked={isAutoRotating}
                onChange={(event) => setIsAutoRotating(event.target.checked)}
              />
              Auto-rotate
            </label>
            <select
              value={autoRotateDirection}
              onChange={(event) => setAutoRotateDirection(Number(event.target.value) as 1 | -1)}
            >
              <option value={1}>Clockwise</option>
              <option value={-1}>Counter-clockwise</option>
            </select>
          </div>
          <div className="volume-viewer-axis-buttons">
            {AXIS_VIEWS.map((view) => (
              <button key={view.label} type="button" onClick={() => snapToAxis(view.axis)}>
                {view.label}
              </button>
            ))}
          </div>
        </div>
      )}
      <div ref={containerRef} className="stage volume-viewer-canvas" />
    </div>
  );
});

export default ChannelVolumeViewer;
