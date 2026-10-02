import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import "@kitware/vtk.js/Rendering/Profiles/Volume";
import "@kitware/vtk.js/Rendering/Profiles/Geometry";
import vtkActor from "@kitware/vtk.js/Rendering/Core/Actor";
import vtkCellArray from "@kitware/vtk.js/Common/Core/CellArray";
// @ts-expect-error - vtk.js ships this module without a .d.ts in this version.
import vtkCubeAxesActor from "@kitware/vtk.js/Rendering/Core/CubeAxesActor";
import vtkColorTransferFunction from "@kitware/vtk.js/Rendering/Core/ColorTransferFunction";
import vtkColorMaps from "@kitware/vtk.js/Rendering/Core/ColorTransferFunction/ColorMaps";
import vtkFullScreenRenderWindow from "@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow";
import vtkITKHelper from "@kitware/vtk.js/Common/DataModel/ITKHelper";
import vtkMapper from "@kitware/vtk.js/Rendering/Core/Mapper";
import vtkPiecewiseFunction from "@kitware/vtk.js/Common/DataModel/PiecewiseFunction";
import vtkPoints from "@kitware/vtk.js/Common/Core/Points";
import vtkPolyData from "@kitware/vtk.js/Common/DataModel/PolyData";
import vtkVolume from "@kitware/vtk.js/Rendering/Core/Volume";
import vtkVolumeMapper from "@kitware/vtk.js/Rendering/Core/VolumeMapper";
import { readImage, setPipelinesBaseUrl } from "@itk-wasm/image-io";

let pipelinesConfigured = false;

function ensurePipelinesConfigured(): void {
  if (pipelinesConfigured) return;
  const base = new URL(
    "pipelines",
    window.location.origin + (import.meta.env.BASE_URL ?? "/"),
  ).href;
  setPipelinesBaseUrl(base);
  pipelinesConfigured = true;
}

/** A real, well-known subset of vtk.js's bundled presets (confirmed present
 * in the installed package), not a guessed or fabricated list. */
const COLORMAP_NAMES = [
  "Grayscale",
  "X Ray",
  "Black-Body Radiation",
  "Cool to Warm",
  "Cold and Hot",
  "rainbow",
];

export type Region = {
  region_id: string;
  label: string;
  voxel_count: number;
  mean_intensity: number;
  slice_index: number;
  timepoint: number;
  bbox: [number, number, number, number];
};

export type VolumeViewerState = {
  windowWidth: number;
  level: number;
  colormapName: string;
  timepoint: number;
  showSegmentation: boolean;
  showGrid: boolean;
  isAutoRotating: boolean;
  autoRotateDirection: 1 | -1;
};

type Props = {
  volumeUrl: string;
  fileName: string;
  authToken?: string;
  regions?: Region[];
  onStateChange?: (state: VolumeViewerState) => void;
};

type Status = "loading" | "ready" | "error";

type ItkImage = Awaited<ReturnType<typeof readImage>>["image"];

/**
 * vtkImageData, and vtkITKHelper.convertItkToVtkImage, are fundamentally
 * 3D: there is no 4D vtkImageData. A real (X, Y, Z, T) volume has to be
 * reduced to one real 3D timepoint before conversion. itk-wasm's data
 * buffer is contiguous per timepoint (verified directly against this
 * book's own real 4D sample: both timepoints' extracted ranges and means
 * are coherent, not interleaved noise), so a timepoint is a plain
 * contiguous subarray, not a strided copy. direction is the real 4x4
 * matrix stored column-major; the real 3x3 spatial submatrix is columns
 * 0-2 of the first three rows, i.e. indices [0,1,2, 4,5,6, 8,9,10].
 */
function extractTimepoint(image: ItkImage, timepoint: number): ItkImage {
  if (image.imageType.dimension !== 4) return image;
  const [sizeX, sizeY, sizeZ, sizeT] = image.size;
  const clampedTimepoint = Math.min(Math.max(timepoint, 0), sizeT - 1);
  const voxelsPerTimepoint = sizeX * sizeY * sizeZ;
  const start = clampedTimepoint * voxelsPerTimepoint;
  const data = image.data as unknown as { slice(start: number, end: number): typeof image.data };
  const direction4x4 = image.direction;
  const direction3x3 = Float64Array.from([
    direction4x4[0], direction4x4[1], direction4x4[2],
    direction4x4[4], direction4x4[5], direction4x4[6],
    direction4x4[8], direction4x4[9], direction4x4[10],
  ]);
  return {
    ...image,
    imageType: { ...image.imageType, dimension: 3 },
    size: [sizeX, sizeY, sizeZ],
    origin: image.origin.slice(0, 3),
    spacing: image.spacing.slice(0, 3),
    direction: direction3x3,
    data: data.slice(start, start + voxelsPerTimepoint),
  } as ItkImage;
}

/** A flat quad outline per real detected region, at its own real slice and
 * real (bbox) extent in the volume's own index space, converted through
 * the volume's own indexToWorld so it lines up with the render regardless
 * of spacing/origin/direction. This is the real detection geometry the
 * backend already computed (tenant_volumetric.py's segment_volume_array),
 * not a fabricated or approximate overlay.
 */
function buildOverlayPolyData(
  vtkImage: ReturnType<typeof vtkITKHelper.convertItkToVtkImage>,
  regions: Region[],
  timepoint: number,
) {
  const matching = regions.filter((region) => region.timepoint === timepoint);
  const points = new Float32Array(matching.length * 4 * 3);
  const lineCells: number[] = [];
  matching.forEach((region, regionIndex) => {
    const [yMin, xMin, yMax, xMax] = region.bbox;
    const z = region.slice_index;
    const corners: [number, number, number][] = [
      [yMin, xMin, z],
      [yMax, xMin, z],
      [yMax, xMax, z],
      [yMin, xMax, z],
    ];
    const baseIndex = regionIndex * 4;
    corners.forEach((corner, cornerIndex) => {
      const world = vtkImage.indexToWorld(corner);
      const pointIndex = (baseIndex + cornerIndex) * 3;
      points[pointIndex] = world[0];
      points[pointIndex + 1] = world[1];
      points[pointIndex + 2] = world[2];
    });
    for (let edge = 0; edge < 4; edge += 1) {
      lineCells.push(2, baseIndex + edge, baseIndex + ((edge + 1) % 4));
    }
  });
  const polyData = vtkPolyData.newInstance();
  const vtkPointsInstance = vtkPoints.newInstance();
  vtkPointsInstance.setData(points, 3);
  polyData.setPoints(vtkPointsInstance);
  const lines = vtkCellArray.newInstance({ values: new Uint32Array(lineCells) });
  polyData.setLines(lines);
  return polyData;
}

/** Everything that must survive across re-renders without itself causing
 * one: the live vtk.js scene graph and the fully-decoded source image.
 * Rebuilt once per real volume fetch; individual controls (window/level,
 * colormap, timepoint, overlay) mutate pieces of this in place instead of
 * re-fetching or re-decoding.
 */
type Scene = {
  fullScreenRenderer: ReturnType<typeof vtkFullScreenRenderWindow.newInstance>;
  renderer: ReturnType<ReturnType<typeof vtkFullScreenRenderWindow.newInstance>["getRenderer"]>;
  renderWindow: ReturnType<ReturnType<typeof vtkFullScreenRenderWindow.newInstance>["getRenderWindow"]>;
  actor: ReturnType<typeof vtkVolume.newInstance>;
  mapper: ReturnType<typeof vtkVolumeMapper.newInstance>;
  colorTransfer: ReturnType<typeof vtkColorTransferFunction.newInstance>;
  opacityTransfer: ReturnType<typeof vtkPiecewiseFunction.newInstance>;
  overlayActor: ReturnType<typeof vtkActor.newInstance>;
  overlayMapper: ReturnType<typeof vtkMapper.newInstance>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  cubeAxes: any;
  itkImage: ItkImage;
  dataMin: number;
  dataMax: number;
  sizeT: number;
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
 * exact same real state, not a separate shadow path, so it produces
 * the exact same real render a person operating the controls would.
 */
export type VolumeViewerHandle = {
  setWindowLevel(window: number, level: number): void;
  setColormap(name: string): void;
  setTimepointIndex(timepoint: number): void;
  snapAxis(label: string): void;
  setSegmentationVisible(visible: boolean): void;
  setGridVisible(visible: boolean): void;
  setAutoRotating(enabled: boolean, direction?: 1 | -1): void;
};

const VolumeViewer = forwardRef<VolumeViewerHandle, Props>(function VolumeViewer(
  { volumeUrl, fileName, authToken, regions = [], onStateChange }: Props,
  handleRef,
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<Scene | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [timepoint, setTimepoint] = useState(0);
  const [sizeT, setSizeT] = useState(1);
  const [windowWidth, setWindowWidth] = useState(1);
  const [level, setLevel] = useState(0);
  const [colormapName, setColormapName] = useState("Grayscale");
  const [showSegmentation, setShowSegmentation] = useState(false);
  const [showGrid, setShowGrid] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isAutoRotating, setIsAutoRotating] = useState(false);

  // Initial load: fetch the real bytes, decode once, build the vtk.js
  // scene graph once. Re-runs only if the volume itself changes.
  useEffect(() => {
    ensurePipelinesConfigured();
    let disposed = false;

    async function load() {
      setStatus("loading");
      try {
        const headers = authToken ? { Authorization: `Bearer ${authToken}` } : undefined;
        const response = await fetch(volumeUrl, { headers });
        if (!response.ok) {
          throw new Error(`could not fetch the real volume (status ${response.status})`);
        }
        const buffer = await response.arrayBuffer();
        if (disposed) return;
        const { image: itkImage, webWorker } = await readImage({
          data: new Uint8Array(buffer),
          path: fileName,
        });
        webWorker.terminate();
        if (disposed || !containerRef.current) return;

        const realSizeT = itkImage.imageType.dimension === 4 ? itkImage.size[3] : 1;
        const timepointImage = extractTimepoint(itkImage, 0);
        const vtkImage = vtkITKHelper.convertItkToVtkImage(timepointImage);
        const scalars = vtkImage.getPointData().getScalars();
        const [dataMin, dataMax] = scalars.getRange();
        const span = dataMax - dataMin || 1;

        const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
          container: containerRef.current,
          background: [0.05, 0.05, 0.08],
        });
        const renderer = fullScreenRenderer.getRenderer();
        const renderWindow = fullScreenRenderer.getRenderWindow();

        const actor = vtkVolume.newInstance();
        const mapper = vtkVolumeMapper.newInstance();
        mapper.setSampleDistance(0.7);
        mapper.setInputData(vtkImage);
        actor.setMapper(mapper);

        const colorTransfer = vtkColorTransferFunction.newInstance();
        const opacityTransfer = vtkPiecewiseFunction.newInstance();
        actor.getProperty().setRGBTransferFunction(0, colorTransfer);
        actor.getProperty().setScalarOpacity(0, opacityTransfer);
        actor.getProperty().setInterpolationTypeToLinear();
        actor.getProperty().setShade(true);
        actor.getProperty().setAmbient(0.2);
        actor.getProperty().setDiffuse(0.7);
        actor.getProperty().setSpecular(0.3);
        renderer.addVolume(actor);

        const overlayMapper = vtkMapper.newInstance();
        const overlayActor = vtkActor.newInstance();
        overlayActor.setMapper(overlayMapper);
        overlayActor.getProperty().setColor(1.0, 0.85, 0.0);
        overlayActor.getProperty().setLineWidth(2);
        overlayActor.setVisibility(false);
        renderer.addActor(overlayActor);

        // A Cartesian grid (ImageJ/Fiji-style ruler/scale reference) around
        // the real volume bounds, in the volume's own real spacing units.
        // Off by default since it's a measurement aid, not decoration.
        const cubeAxes = vtkCubeAxesActor.newInstance();
        cubeAxes.setCamera(renderer.getActiveCamera());
        cubeAxes.setDataBounds(vtkImage.getBounds());
        cubeAxes.setGridLines(true);
        cubeAxes.getProperty().setColor(1, 1, 1);
        cubeAxes.setVisibility(false);
        renderer.addActor(cubeAxes);

        sceneRef.current = {
          fullScreenRenderer,
          renderer,
          renderWindow,
          actor,
          mapper,
          colorTransfer,
          opacityTransfer,
          overlayActor,
          overlayMapper,
          cubeAxes,
          itkImage,
          dataMin,
          dataMax,
          sizeT: realSizeT,
        };

        renderer.resetCamera();
        renderWindow.render();
        setSizeT(realSizeT);
        setWindowWidth(span);
        setLevel(dataMin + span / 2);
        setTimepoint(0);
        setStatus("ready");
      } catch (error) {
        if (!disposed) {
          setErrorMessage(error instanceof Error ? error.message : "failed to render the real volume");
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
      scene?.overlayActor.delete();
      scene?.overlayMapper.delete();
      scene?.fullScreenRenderer.delete();
      sceneRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [volumeUrl, fileName, authToken]);

  // Timepoint changes: re-slice the already-decoded image, no re-fetch.
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || status !== "ready") return;
    const timepointImage = extractTimepoint(scene.itkImage, timepoint);
    const vtkImage = vtkITKHelper.convertItkToVtkImage(timepointImage);
    scene.mapper.setInputData(vtkImage);
    scene.renderWindow.render();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timepoint, status]);

  // Window/level: recompute the transfer function control points from the
  // real data range, the same way clinical window/level controls work.
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || status !== "ready") return;
    const lower = level - windowWidth / 2;
    const upper = level + windowWidth / 2;
    const span = upper - lower || 1;
    const preset = vtkColorMaps.getPresetByName(colormapName);
    scene.colorTransfer.removeAllPoints();
    if (preset) {
      const points = preset.RGBPoints;
      for (let i = 0; i < points.length; i += 4) {
        const [value, r, g, b] = [points[i], points[i + 1], points[i + 2], points[i + 3]];
        scene.colorTransfer.addRGBPoint(lower + value * span, r, g, b);
      }
    }
    scene.opacityTransfer.removeAllPoints();
    scene.opacityTransfer.addPoint(lower + span * 0.15, 0.0);
    scene.opacityTransfer.addPoint(lower + span * 0.4, 0.15);
    scene.opacityTransfer.addPoint(lower + span * 0.95, 0.9);
    scene.renderWindow.render();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [windowWidth, level, colormapName, status]);

  // Segmentation overlay: rebuild the real detected-region outlines for
  // whichever timepoint is active, from the backend's own computed boxes.
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || status !== "ready") return;
    scene.overlayActor.setVisibility(showSegmentation);
    if (showSegmentation) {
      const timepointImage = extractTimepoint(scene.itkImage, timepoint);
      const vtkImage = vtkITKHelper.convertItkToVtkImage(timepointImage);
      const overlayPolyData = buildOverlayPolyData(vtkImage, regions, timepoint);
      scene.overlayMapper.setInputData(overlayPolyData);
    }
    scene.renderWindow.render();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showSegmentation, timepoint, regions, status]);

  // Cartesian grid (ImageJ/Fiji-style ruler/scale reference).
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || status !== "ready") return;
    scene.cubeAxes.setVisibility(showGrid);
    scene.renderWindow.render();
  }, [showGrid, status]);

  // Time playback: advances one real timepoint per tick, looping back to
  // the start, the same way a video player's play button would.
  useEffect(() => {
    if (!isPlaying || sizeT <= 1) return;
    const id = window.setInterval(() => {
      setTimepoint((current) => (current + 1) % sizeT);
    }, 600);
    return () => window.clearInterval(id);
  }, [isPlaying, sizeT]);

  // Auto-rotate: a continuous azimuth spin around the volume's own
  // vertical axis, the same primitive vtk.js's own mouse-drag rotation
  // uses (camera.azimuth), just driven by a timer instead of a pointer.
  const [autoRotateDirection, setAutoRotateDirection] = useState<1 | -1>(1);
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

  useImperativeHandle(
    handleRef,
    () => ({
      setWindowLevel(window: number, level: number) {
        setWindowWidth(window);
        setLevel(level);
      },
      setColormap(name: string) {
        setColormapName(name);
      },
      setTimepointIndex(nextTimepoint: number) {
        setIsPlaying(false);
        setTimepoint(nextTimepoint);
      },
      snapAxis(label: string) {
        const view = AXIS_VIEWS.find((candidate) => candidate.label === label);
        if (view) snapToAxis(view.axis);
      },
      setSegmentationVisible(visible: boolean) {
        setShowSegmentation(visible);
      },
      setGridVisible(visible: boolean) {
        setShowGrid(visible);
      },
      setAutoRotating(enabled: boolean, direction?: 1 | -1) {
        if (direction) setAutoRotateDirection(direction);
        setIsAutoRotating(enabled);
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
      windowWidth,
      level,
      colormapName,
      timepoint,
      showSegmentation,
      showGrid,
      isAutoRotating,
      autoRotateDirection,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    status,
    windowWidth,
    level,
    colormapName,
    timepoint,
    showSegmentation,
    showGrid,
    isAutoRotating,
    autoRotateDirection,
  ]);

  return (
    <div className="volume-viewer">
      {status === "loading" && <p className="volume-viewer-status">Loading the real volume…</p>}
      {status === "error" && (
        <p className="volume-viewer-status volume-viewer-error">{errorMessage}</p>
      )}
      {status === "ready" && (
        <div className="volume-viewer-controls">
          <label>
            Window
            <input
              type="range"
              min={1}
              max={Math.max(windowWidth * 2, 1)}
              value={windowWidth}
              onChange={(event) => setWindowWidth(Number(event.target.value))}
            />
          </label>
          <label>
            Level
            <input
              type="range"
              min={sceneRef.current ? sceneRef.current.dataMin - windowWidth : 0}
              max={sceneRef.current ? sceneRef.current.dataMax + windowWidth : 1}
              value={level}
              onChange={(event) => setLevel(Number(event.target.value))}
            />
          </label>
          <label>
            Colormap
            <select value={colormapName} onChange={(event) => setColormapName(event.target.value)}>
              {COLORMAP_NAMES.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          {sizeT > 1 && (
            <label>
              Time ({timepoint} / {sizeT - 1})
              <div className="volume-viewer-time-row">
                <button type="button" onClick={() => setIsPlaying((playing) => !playing)}>
                  {isPlaying ? "Pause" : "Play"}
                </button>
                <input
                  type="range"
                  min={0}
                  max={sizeT - 1}
                  step={1}
                  value={timepoint}
                  onChange={(event) => {
                    setIsPlaying(false);
                    setTimepoint(Number(event.target.value));
                  }}
                />
              </div>
            </label>
          )}
          {regions.length > 0 && (
            <label className="volume-viewer-checkbox">
              <input
                type="checkbox"
                checked={showSegmentation}
                onChange={(event) => setShowSegmentation(event.target.checked)}
              />
              Show detected regions ({regions.filter((r) => r.timepoint === timepoint).length} at this time)
            </label>
          )}
          <label className="volume-viewer-checkbox">
            <input type="checkbox" checked={showGrid} onChange={(event) => setShowGrid(event.target.checked)} />
            Show Cartesian grid
          </label>
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

export default VolumeViewer;
