import { useEffect, useRef, useState } from "react";
import { Niivue, type NVImage } from "@niivue/niivue";

type Region = { region_id: string; label: string; voxel_count: number; mean_intensity: number; timepoint: number };
type MedicalEvidence = { status: string; claim: string; regions: Region[]; volume_shape: number[] };
type TimepointComparison = {
  timepoint: number;
  baseline_instance_count: number;
  ground_truth_instance_count: number;
  matches_ground_truth: boolean;
};
type GroundTruthLineage = {
  total_tracked_nuclei: number;
  total_lineage_edges: number;
  root_nodes: number;
  leaf_nodes: number;
};
type MicroscopyEvidence = {
  status: string;
  claim: string;
  comparisons: TimepointComparison[];
  ground_truth: GroundTruthLineage;
  volume_shape: number[];
};
type Detection = { frame_index: number; track_id: number; class_name: string; confidence: number };
type VideoEvidence = { status: string; claim: string; detections: Detection[] };

export default function DetectionSegmentationLab() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nvRef = useRef<Niivue | null>(null);
  const [medical, setMedical] = useState<MedicalEvidence | null>(null);
  const [microscopy, setMicroscopy] = useState<MicroscopyEvidence | null>(null);
  const [video, setVideo] = useState<VideoEvidence | null>(null);
  const [overlayVisible, setOverlayVisible] = useState(true);
  const [timepoint, setTimepoint] = useState(0);

  useEffect(() => {
    void fetch("/fixtures/ch09-medical-segmentation.json")
      .then((r) => (r.ok ? r.json() : null))
      .then(setMedical);
    void fetch("/fixtures/ch09-microscopy-tracking.json")
      .then((r) => (r.ok ? r.json() : null))
      .then(setMicroscopy);
    void fetch("/fixtures/ch09-video-tracking.json")
      .then((r) => (r.ok ? r.json() : null))
      .then(setVideo);
  }, []);

  useEffect(() => {
    if (!canvasRef.current) return;
    const nv = new Niivue({ show3Dcrosshair: true });
    nvRef.current = nv;
    nv.attachToCanvas(canvasRef.current);
    const volumes = [{ url: "/fixtures/ch09-mri-4d.nii.gz", colormap: "gray", frame4D: 0 }];
    if (overlayVisible) {
      volumes.push({
        url: "/fixtures/ch09-mri-4d-mask.nii.gz",
        colormap: "red",
        opacity: 0.5,
        frame4D: 0,
      } as (typeof volumes)[number]);
    }
    void nv.loadVolumes(volumes);
    return () => nv.closeDrawing?.();
  }, [overlayVisible]);

  const onTimepointChange = (value: number) => {
    setTimepoint(value);
    const nv = nvRef.current;
    if (!nv) return;
    for (const vol of nv.volumes as NVImage[]) {
      vol.frame4D = value;
    }
    nv.updateGLVolume();
  };

  const regionsAtTimepoint = medical
    ? medical.regions.filter((r) => r.timepoint === timepoint).length
    : 0;
  const matchedTimepoints = microscopy
    ? microscopy.comparisons.filter((c) => c.matches_ground_truth).length
    : 0;
  const persistentVideoTracks = video
    ? new Set(video.detections.map((d) => d.track_id)).size
    : 0;

  return (
    <section className="detection-lab" aria-labelledby="detection-heading">
      <div className="runtime-head">
        <div>
          <p className="eyebrow">DETECTION, SEGMENTATION, TRACKING</p>
          <h2 id="detection-heading">Retained evidence across three domains</h2>
        </div>
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <label>
            Timepoint{" "}
            <select
              data-testid="timepoint-select"
              value={timepoint}
              onChange={(event) => onTimepointChange(Number(event.target.value))}
            >
              <option value={0}>t=0</option>
              <option value={1}>t=1</option>
            </select>
          </label>
          <label>
            <input
              type="checkbox"
              checked={overlayVisible}
              onChange={(event) => setOverlayVisible(event.target.checked)}
            />{" "}
            Show segmentation overlay
          </label>
        </div>
      </div>
      <canvas
        ref={canvasRef}
        data-testid="ct-volume-canvas"
        style={{ width: "100%", height: 280, background: "#000" }}
      />
      <div className="detection-grid">
        <article data-testid="medical-evidence-card">
          <small>MRI SEGMENTATION, 4D (X, Y, 24 SLICES, 2 TIMEPOINTS)</small>
          <b>{medical ? medical.claim : "loading retained evidence"}</b>
          <span>{medical ? `${regionsAtTimepoint} region(s) at t=${timepoint}` : ""}</span>
        </article>
        <article data-testid="microscopy-evidence-card">
          <small>MICROSCOPY, 5D (T, C, Z, Y, X), vs. REAL GROUND TRUTH</small>
          <b>{microscopy ? microscopy.claim : "loading retained evidence"}</b>
          <span>
            {microscopy
              ? `baseline matched ground truth at ${matchedTimepoints} of ${microscopy.comparisons.length} timepoints`
              : ""}
          </span>
        </article>
        <article data-testid="video-evidence-card">
          <small>VIDEO TRACKING</small>
          <b>{video ? video.claim : "loading retained evidence"}</b>
          <span>{video ? `${persistentVideoTracks} tracked object(s)` : ""}</span>
        </article>
      </div>
      <footer>
        A real 4D MRI series (24 slices, 2 timepoints) rendered live with
        NiiVue. Segmentation, tracking, and detection all run in Python;
        this panel only displays the retained result and lets you switch
        between the two real timepoints.
      </footer>
    </section>
  );
}
