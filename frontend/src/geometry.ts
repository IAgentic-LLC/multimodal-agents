import type { NormalizedRegion } from "./types";

export type FitMode = "contain" | "cover";

export interface ImageSize {
  width: number;
  height: number;
}

export interface FitResult {
  region: NormalizedRegion;
  scale: number;
  offsetX: number;
  offsetY: number;
}

export const fitRegion = (
  region: NormalizedRegion,
  source: ImageSize,
  target: ImageSize,
  mode: FitMode,
): FitResult => {
  const widthScale = target.width / source.width;
  const heightScale = target.height / source.height;
  const scale = mode === "contain"
    ? Math.min(widthScale, heightScale)
    : Math.max(widthScale, heightScale);
  const offsetX = (target.width - source.width * scale) / 2;
  const offsetY = (target.height - source.height * scale) / 2;
  const horizontal = (value: number) => Math.min(
    1,
    Math.max(0, (value * source.width * scale + offsetX) / target.width),
  );
  const vertical = (value: number) => Math.min(
    1,
    Math.max(0, (value * source.height * scale + offsetY) / target.height),
  );
  return {
    scale,
    offsetX,
    offsetY,
    region: {
      left: horizontal(region.left),
      top: vertical(region.top),
      right: horizontal(region.right),
      bottom: vertical(region.bottom),
    },
  };
};
