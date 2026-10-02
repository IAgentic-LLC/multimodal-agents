import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";

import { humanizeApiError } from "./apiError";

type SourceKind = "ome_zarr" | "plain_zarr";

type FilterName =
  | "gaussian_blur"
  | "median_filter"
  | "sharpen"
  | "enhance_contrast"
  | "subtract_background"
  | "morphological_operation"
  | "normalize_intensity";

type ParamField = {
  key: string;
  label: string;
  type: "number" | "select";
  defaultValue: string;
  options?: string[];
};

type FilterOption = { value: FilterName; label: string; paramFields: ParamField[] };

/** Mirrors tenant_filters.FILTER_CATALOG exactly: these are the same
 * real filter names and real parameter names the backend's
 * apply_filter dispatches on, not a cosmetic relabeling.
 */
const FILTER_OPTIONS: FilterOption[] = [
  { value: "gaussian_blur", label: "Gaussian blur", paramFields: [
    { key: "sigma", label: "Sigma", type: "number", defaultValue: "1.0" },
  ] },
  { value: "median_filter", label: "Median filter", paramFields: [
    { key: "size", label: "Size", type: "number", defaultValue: "3" },
  ] },
  { value: "sharpen", label: "Sharpen (unsharp mask)", paramFields: [
    { key: "radius", label: "Radius", type: "number", defaultValue: "1.0" },
    { key: "amount", label: "Amount", type: "number", defaultValue: "1.0" },
  ] },
  { value: "enhance_contrast", label: "Enhance contrast (CLAHE)", paramFields: [
    { key: "clip_limit", label: "Clip limit", type: "number", defaultValue: "0.01" },
  ] },
  { value: "subtract_background", label: "Subtract background", paramFields: [
    { key: "radius", label: "Radius", type: "number", defaultValue: "5" },
  ] },
  { value: "morphological_operation", label: "Morphology", paramFields: [
    { key: "operation", label: "Operation", type: "select", defaultValue: "erosion",
      options: ["erosion", "dilation", "opening", "closing"] },
    { key: "radius", label: "Radius", type: "number", defaultValue: "1" },
  ] },
  { value: "normalize_intensity", label: "Normalize intensity", paramFields: [] },
];

type Step = { filter: FilterName; params: Record<string, string> };

function defaultParamsFor(filter: FilterName): Record<string, string> {
  const option = FILTER_OPTIONS.find((candidate) => candidate.value === filter);
  return Object.fromEntries((option?.paramFields ?? []).map((field) => [field.key, field.defaultValue]));
}

function coerceParams(step: Step): Record<string, number | string> {
  const option = FILTER_OPTIONS.find((candidate) => candidate.value === step.filter);
  const result: Record<string, number | string> = {};
  for (const field of option?.paramFields ?? []) {
    const raw = step.params[field.key] ?? field.defaultValue;
    result[field.key] = field.type === "number" ? Number(raw) : raw;
  }
  return result;
}

type Metadata = { channel_count: number; timepoints: number };
type Stats = { min: number; max: number; mean: number };

export type RawFilterStep = { filter: string; params?: Record<string, number | string> };

export type FilterApplyResult = {
  steps: RawFilterStep[];
  channelIndex: number;
  timepoint: number;
  before: Stats;
  after: Stats;
};

/** The same "apply a real pipeline" action the human-facing "Apply
 * pipeline" button triggers below, callable programmatically: a
 * live-driven apply_filter_pipeline command goes through this exact
 * same real request/state, not a separate shadow path, matching
 * ChannelVolumeViewerHandle's own established pattern.
 */
export type FilterPanelHandle = {
  applyRemotePipeline(
    steps: RawFilterStep[],
    channelIndex?: number,
    timepoint?: number,
  ): Promise<void>;
};

type Props = {
  sourceKind: SourceKind;
  sourceUrl: string;
  axisHint?: string;
  authToken?: string;
  onApplied?: (result: FilterApplyResult) => void;
};

function rawStepToFormStep(raw: RawFilterStep): Step {
  const filter = raw.filter as FilterName;
  const defaults = defaultParamsFor(filter);
  const params = { ...defaults };
  for (const [key, value] of Object.entries(raw.params ?? {})) {
    params[key] = String(value);
  }
  return { filter, params };
}

/** Draws a real client-side max-intensity projection of a filtered
 * (Z, Y, X) float32 volume onto a canvas, the browser-side equivalent
 * of render_volume_max_projection_png: no extra preview-image endpoint
 * is needed because filter-ome-zarr/filter-plain-zarr already return
 * the real filtered volume's own raw bytes.
 */
function drawMaxProjection(canvas: HTMLCanvasElement, data: Float32Array, depth: number, height: number, width: number) {
  canvas.width = width;
  canvas.height = height;
  const planeSize = height * width;
  const projection = new Float32Array(planeSize).fill(-Infinity);
  for (let z = 0; z < depth; z += 1) {
    const zOffset = z * planeSize;
    for (let i = 0; i < planeSize; i += 1) {
      const value = data[zOffset + i];
      if (value > projection[i]) projection[i] = value;
    }
  }
  let min = Infinity;
  let max = -Infinity;
  for (let i = 0; i < planeSize; i += 1) {
    if (Number.isFinite(projection[i])) {
      if (projection[i] < min) min = projection[i];
      if (projection[i] > max) max = projection[i];
    }
  }
  const span = max - min || 1;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const imageData = ctx.createImageData(width, height);
  for (let i = 0; i < planeSize; i += 1) {
    const normalized = Math.round(Math.min(Math.max((projection[i] - min) / span, 0), 1) * 255);
    imageData.data[i * 4] = normalized;
    imageData.data[i * 4 + 1] = normalized;
    imageData.data[i * 4 + 2] = normalized;
    imageData.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(imageData, 0, 0);
}

const FilterPanel = forwardRef<FilterPanelHandle, Props>(function FilterPanel(
  { sourceKind, sourceUrl, axisHint, authToken, onApplied }: Props,
  handleRef,
) {
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [channelIndex, setChannelIndex] = useState(0);
  const [timepoint, setTimepoint] = useState(0);
  const [steps, setSteps] = useState<Step[]>([{ filter: "gaussian_blur", params: defaultParamsFor("gaussian_blur") }]);
  const [status, setStatus] = useState("");
  const [before, setBefore] = useState<Stats | null>(null);
  const [after, setAfter] = useState<Stats | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let disposed = false;
    (async () => {
      try {
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (authToken) headers.Authorization = `Bearer ${authToken}`;
        const path = sourceKind === "plain_zarr" ? "/api/studio/plain-zarr-metadata" : "/api/studio/zarr-metadata";
        const response = await fetch(path, {
          method: "POST",
          headers,
          body: JSON.stringify({ url: sourceUrl, ...(sourceKind === "plain_zarr" ? { axis_hint: axisHint } : {}) }),
        });
        if (!response.ok || disposed) return;
        const body = (await response.json()) as Metadata;
        if (!disposed) setMetadata(body);
      } catch {
        // A failed metadata probe just leaves the channel/timepoint
        // selectors at their real defaults (0); applyPipeline below
        // will surface a real error if the source itself is bad.
      }
    })();
    return () => {
      disposed = true;
    };
  }, [sourceKind, sourceUrl, axisHint, authToken]);

  function addStep() {
    setSteps((current) => [...current, { filter: "gaussian_blur", params: defaultParamsFor("gaussian_blur") }]);
  }

  function removeStep(index: number) {
    setSteps((current) => current.filter((_, i) => i !== index));
  }

  function setStepFilter(index: number, filter: FilterName) {
    setSteps((current) => current.map((step, i) => (i === index ? { filter, params: defaultParamsFor(filter) } : step)));
  }

  function setStepParam(index: number, key: string, value: string) {
    setSteps((current) => current.map((step, i) => (i === index ? { ...step, params: { ...step.params, [key]: value } } : step)));
  }

  /** The real shared core both the "Apply pipeline" button and a
   * live-driven apply_filter_pipeline command go through: rawSteps is
   * always the real request-body shape (filter + already-typed
   * params), never the form's own string-keyed Step representation.
   */
  async function runPipeline(
    rawSteps: RawFilterStep[],
    atChannelIndex: number,
    atTimepoint: number,
  ) {
    if (rawSteps.length === 0) {
      setStatus("Add at least one real filter step first.");
      return;
    }
    setStatus("Applying the real filter pipeline…");
    setBefore(null);
    setAfter(null);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (authToken) headers.Authorization = `Bearer ${authToken}`;
      const path = sourceKind === "plain_zarr" ? "/api/studio/filter-plain-zarr" : "/api/studio/filter-ome-zarr";
      const body = {
        url: sourceUrl,
        channel_index: atChannelIndex,
        timepoint: atTimepoint,
        steps: rawSteps,
        ...(sourceKind === "plain_zarr" ? { axis_hint: axisHint } : {}),
      };
      const response = await fetch(path, { method: "POST", headers, body: JSON.stringify(body) });
      if (!response.ok) {
        throw new Error(await humanizeApiError(response, "could not apply the real filter pipeline"));
      }
      const depth = Number(response.headers.get("X-Shape-Z"));
      const height = Number(response.headers.get("X-Shape-Y"));
      const width = Number(response.headers.get("X-Shape-X"));
      const nextBefore: Stats = {
        min: Number(response.headers.get("X-Before-Min")),
        max: Number(response.headers.get("X-Before-Max")),
        mean: Number(response.headers.get("X-Before-Mean")),
      };
      const nextAfter: Stats = {
        min: Number(response.headers.get("X-After-Min")),
        max: Number(response.headers.get("X-After-Max")),
        mean: Number(response.headers.get("X-After-Mean")),
      };
      const buffer = await response.arrayBuffer();
      const data = new Float32Array(buffer);
      if (canvasRef.current) drawMaxProjection(canvasRef.current, data, depth, height, width);
      setBefore(nextBefore);
      setAfter(nextAfter);
      setStatus("");
      onApplied?.({
        steps: rawSteps,
        channelIndex: atChannelIndex,
        timepoint: atTimepoint,
        before: nextBefore,
        after: nextAfter,
      });
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "could not apply the real filter pipeline");
    }
  }

  async function applyPipeline() {
    await runPipeline(
      steps.map((step) => ({ filter: step.filter, params: coerceParams(step) })),
      channelIndex,
      timepoint,
    );
  }

  useImperativeHandle(
    handleRef,
    () => ({
      async applyRemotePipeline(
        rawSteps: RawFilterStep[],
        atChannelIndex = channelIndex,
        atTimepoint = timepoint,
      ) {
        // Updates the exact same real form state a person editing the
        // steps by hand would leave behind, so the browser visibly
        // reflects what an agent just drove, not just the end result.
        setSteps(rawSteps.map(rawStepToFormStep));
        setChannelIndex(atChannelIndex);
        setTimepoint(atTimepoint);
        await runPipeline(rawSteps, atChannelIndex, atTimepoint);
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [channelIndex, timepoint, sourceKind, sourceUrl, axisHint, authToken],
  );

  return (
    <div className="filter-panel">
      <h4>Real filter / processing pipeline</h4>
      <div className="filter-panel-row">
        <label>
          Channel
          <input
            type="number"
            min={0}
            max={Math.max((metadata?.channel_count ?? 1) - 1, 0)}
            value={channelIndex}
            onChange={(event) => setChannelIndex(Number(event.target.value))}
          />
        </label>
        <label>
          Timepoint
          <input
            type="number"
            min={0}
            max={Math.max((metadata?.timepoints ?? 1) - 1, 0)}
            value={timepoint}
            onChange={(event) => setTimepoint(Number(event.target.value))}
          />
        </label>
      </div>

      {steps.map((step, index) => {
        const option = FILTER_OPTIONS.find((candidate) => candidate.value === step.filter);
        return (
          <div key={index} className="filter-panel-step">
            <select
              value={step.filter}
              onChange={(event) => setStepFilter(index, event.target.value as FilterName)}
            >
              {FILTER_OPTIONS.map((candidate) => (
                <option key={candidate.value} value={candidate.value}>
                  {candidate.label}
                </option>
              ))}
            </select>
            {option?.paramFields.map((field) =>
              field.type === "select" ? (
                <label key={field.key}>
                  {field.label}
                  <select
                    value={step.params[field.key] ?? field.defaultValue}
                    onChange={(event) => setStepParam(index, field.key, event.target.value)}
                  >
                    {field.options?.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <label key={field.key}>
                  {field.label}
                  <input
                    type="number"
                    step="any"
                    value={step.params[field.key] ?? field.defaultValue}
                    onChange={(event) => setStepParam(index, field.key, event.target.value)}
                  />
                </label>
              ),
            )}
            <button type="button" onClick={() => removeStep(index)} aria-label="Remove this filter step">
              ✕
            </button>
          </div>
        );
      })}
      <div className="filter-panel-actions">
        <button type="button" onClick={addStep}>
          Add filter step
        </button>
        <button type="button" onClick={() => void applyPipeline()}>
          Apply pipeline
        </button>
      </div>
      <p>{status}</p>
      {before && after && (
        <table className="filter-panel-stats">
          <thead>
            <tr>
              <th />
              <th>Min</th>
              <th>Max</th>
              <th>Mean</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Before</td>
              <td>{before.min.toFixed(2)}</td>
              <td>{before.max.toFixed(2)}</td>
              <td>{before.mean.toFixed(2)}</td>
            </tr>
            <tr>
              <td>After</td>
              <td>{after.min.toFixed(2)}</td>
              <td>{after.max.toFixed(2)}</td>
              <td>{after.mean.toFixed(2)}</td>
            </tr>
          </tbody>
        </table>
      )}
      <canvas ref={canvasRef} className="filter-panel-canvas" />
    </div>
  );
});

export default FilterPanel;
