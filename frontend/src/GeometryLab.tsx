import { useMemo, useState } from "react";

import { fitRegion, type FitMode } from "./geometry";
import type { NormalizedRegion } from "./types";

const source = { width: 1920, height: 1080 };
const target = { width: 640, height: 640 };
const sourceRegion: NormalizedRegion = {
  left: 0.2,
  top: 0.2,
  right: 0.55,
  bottom: 0.75,
};

const percentStyle = (region: NormalizedRegion) => ({
  left: `${region.left * 100}%`,
  top: `${region.top * 100}%`,
  width: `${(region.right - region.left) * 100}%`,
  height: `${(region.bottom - region.top) * 100}%`,
});

const displayRegion = (region: NormalizedRegion): string => [
  region.left,
  region.top,
  region.right,
  region.bottom,
].map((value) => value.toFixed(3)).join(", ");

export default function GeometryLab() {
  const [mode, setMode] = useState<FitMode>("contain");
  const result = useMemo(
    () => fitRegion(sourceRegion, source, target, mode),
    [mode],
  );
  const renderedWidth = source.width * result.scale / target.width * 100;
  const renderedHeight = source.height * result.scale / target.height * 100;

  return (
    <section className="geometry-lab" aria-labelledby="geometry-heading">
      <div className="geometry-copy">
        <p className="eyebrow">COORDINATE LAB</p>
        <h2 id="geometry-heading">The pixels moved. Did the evidence?</h2>
        <p>
          A 1920×1080 frame enters a 640×640 viewport. The dotted box copies
          the source coordinates blindly. The green box applies the recorded
          resize and offset.
        </p>
        <label>
          Fit mode
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value as FitMode)}
          >
            <option value="contain">Contain with letterboxing</option>
            <option value="cover">Cover with cropping</option>
          </select>
        </label>
        <dl>
          <div><dt>Scale</dt><dd>{result.scale.toFixed(4)}</dd></div>
          <div>
            <dt>Offset</dt>
            <dd>{result.offsetX.toFixed(1)}, {result.offsetY.toFixed(1)} px</dd>
          </div>
          <div><dt>Mapped box</dt><dd>{displayRegion(result.region)}</dd></div>
        </dl>
      </div>
      <div
        className="fit-viewport"
        aria-label={`${mode} coordinate preview`}
      >
        <div
          className="source-frame"
          style={{
            width: `${renderedWidth}%`,
            height: `${renderedHeight}%`,
          }}
        />
        <div
          className="naive-region"
          style={percentStyle(sourceRegion)}
          aria-label="Untransformed source region"
        />
        <div
          className="mapped-region"
          style={percentStyle(result.region)}
          aria-label="Transformed visible region"
        />
      </div>
    </section>
  );
}
