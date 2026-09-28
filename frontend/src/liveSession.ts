export type TimedFrame = {
  id: string;
  offsetMs: number;
};

export type FrameDecision = {
  status: "fresh" | "stale" | "missing";
  frame: TimedFrame | null;
  ageMs: number | null;
};

export const latestFrameQueue = (
  frames: TimedFrame[],
  capacity: number,
): TimedFrame[] => {
  if (capacity < 1) throw new Error("capacity must be positive");
  return [...frames]
    .sort((left, right) => left.offsetMs - right.offsetMs)
    .slice(-capacity);
};

export const frameForReference = (
  frames: TimedFrame[],
  referenceOffsetMs: number,
  maxAgeMs: number,
): FrameDecision => {
  const eligible = frames
    .filter((frame) => frame.offsetMs <= referenceOffsetMs)
    .sort((left, right) => right.offsetMs - left.offsetMs);
  const frame = eligible[0] ?? null;
  if (!frame) return { status: "missing", frame: null, ageMs: null };
  const ageMs = referenceOffsetMs - frame.offsetMs;
  if (ageMs > maxAgeMs) return { status: "stale", frame, ageMs };
  return { status: "fresh", frame, ageMs };
};
