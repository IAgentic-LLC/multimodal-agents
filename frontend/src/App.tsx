import {
  type PointerEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { makeIdentifier, saveCapture } from "./capture";
import GeometryLab from "./GeometryLab";
import FusionLab from "./FusionLab";
import LiveSessionLab from "./LiveSessionLab";
import ScreenStateLab from "./ScreenStateLab";
import SafeActionLab from "./SafeActionLab";
import ScreenAgentLab from "./ScreenAgentLab";
import DocumentLayoutLab from "./DocumentLayoutLab";
import SearchIndexLab from "./SearchIndexLab";
import CrossModalSearchLab from "./CrossModalSearchLab";
import HybridRetrievalLab from "./HybridRetrievalLab";
import EvidencePackageLab from "./EvidencePackageLab";
import EventMemoryLab from "./EventMemoryLab";
import MemoryQueryLab from "./MemoryQueryLab";
import AcousticEventLab from "./AcousticEventLab";
import SensorWorldLab from "./SensorWorldLab";
import ContradictionLab from "./ContradictionLab";
import PolicyGateLab from "./PolicyGateLab";
import SandboxLab from "./SandboxLab";
import EvaluationLab from "./EvaluationLab";
import FailureLab from "./FailureLab";
import RuntimeLab from "./RuntimeLab";
import MultimodalStudio from "./MultimodalStudio";
import ProductionControlLab from "./ProductionControlLab";
import ReleaseGateLab from "./ReleaseGateLab";
import OpeningEvidenceLabs from "./OpeningEvidenceLabs";
import type {
  CaptureMetadata,
  NormalizedRegion,
  SessionState,
} from "./types";
import "./styles.css";

const preferredDevice = (
  devices: MediaDeviceInfo[],
  preferred: RegExp,
  rejected: RegExp,
): string => devices.find((device) => (
  preferred.test(device.label) && !rejected.test(device.label)
))?.deviceId ?? devices.find((device) => !rejected.test(device.label))?.deviceId
  ?? devices[0]?.deviceId ?? "";

export default function App() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const sessionStartRef = useRef(0);
  const voiceStartRef = useRef(0);
  const frameRef = useRef({ data: "", offset: 0, capturedAt: "" });
  const pendingRef = useRef<{
    audio: Blob;
    metadata: Omit<CaptureMetadata, "ground_truth">;
  } | null>(null);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const [state, setState] = useState<SessionState>("idle");
  const [sessionId, setSessionId] = useState("Not started");
  const [frameTime, setFrameTime] = useState("Not captured");
  const [voiceTime, setVoiceTime] = useState("Not captured");
  const [status, setStatus] = useState("Ready");
  const [recording, setRecording] = useState(false);
  const [capturedFrame, setCapturedFrame] = useState("");
  const [expectedRegion, setExpectedRegion] = useState<NormalizedRegion | null>(
    null,
  );
  const [expectedTranscript, setExpectedTranscript] = useState(
    "Remember where I put this.",
  );
  const [expectedObject, setExpectedObject] = useState("");
  const [cameras, setCameras] = useState<MediaDeviceInfo[]>([]);
  const [microphones, setMicrophones] = useState<MediaDeviceInfo[]>([]);
  const [cameraId, setCameraId] = useState("");
  const [microphoneId, setMicrophoneId] = useState("");
  const groundTruthReady = Boolean(
    expectedTranscript.trim() && expectedObject.trim(),
  );

  const offset = () => Math.round(performance.now() - sessionStartRef.current);

  const stopTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  useEffect(() => stopTracks, [stopTracks]);

  const fail = (error: unknown) => {
    const message = error instanceof Error ? error.message : "Capture failed";
    stopTracks();
    setRecording(false);
    setState("idle");
    setStatus(message);
  };

  const discoverDevices = async () => {
    try {
      setState("requesting");
      setStatus("Waiting for permission to discover media devices");
      const probe = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });
      probe.getTracks().forEach((track) => track.stop());
      const devices = await navigator.mediaDevices.enumerateDevices();
      const nextCameras = devices.filter((item) => item.kind === "videoinput");
      const nextMicrophones = devices.filter(
        (item) => item.kind === "audioinput",
      );
      setCameras(nextCameras);
      setMicrophones(nextMicrophones);
      setCameraId(preferredDevice(
        nextCameras,
        /integrated|usb camera|webcam/i,
        /droidcam|softcam|virtual/i,
      ));
      setMicrophoneId(preferredDevice(
        nextMicrophones,
        /realtek|microphone array/i,
        /droidcam|virtual|cable/i,
      ));
      setState("idle");
      setStatus("Devices discovered. Confirm the physical inputs below.");
    } catch (error) {
      fail(error);
    }
  };

  const startSession = async () => {
    try {
      setState("requesting");
      setStatus("Waiting for camera and microphone permission");
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          deviceId: cameraId ? { exact: cameraId } : undefined,
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: {
          deviceId: microphoneId ? { exact: microphoneId } : undefined,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;
      if (!videoRef.current) throw new Error("Video preview is unavailable");
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      const nextSession = makeIdentifier("session");
      sessionStartRef.current = performance.now();
      setSessionId(nextSession);
      setState("live");
      setStatus("Session live. Preview is not being saved.");
    } catch (error) {
      fail(error);
    }
  };

  const snapshot = (): void => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !video.videoWidth) {
      throw new Error("Camera frame is not ready");
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    const frame = {
      data: canvas.toDataURL("image/jpeg", 0.9),
      offset: offset(),
      capturedAt: new Date().toISOString(),
    };
    frameRef.current = frame;
    setFrameTime(`${frame.offset} ms`);
  };

  const beginReference = (event: PointerEvent<HTMLButtonElement>) => {
    try {
      if (event.nativeEvent.isTrusted) {
        event.currentTarget.setPointerCapture(event.pointerId);
      }
      const stream = streamRef.current;
      if (!stream) throw new Error("Start a session first");
      const audioTracks = stream.getAudioTracks();
      if (!audioTracks.length) throw new Error("No microphone track is available");
      snapshot();
      chunksRef.current = [];
      voiceStartRef.current = offset();
      const preferred = "audio/webm;codecs=opus";
      const options = MediaRecorder.isTypeSupported(preferred)
        ? { mimeType: preferred }
        : undefined;
      const recorder = new MediaRecorder(
        new MediaStream(audioTracks),
        options,
      );
      recorderRef.current = recorder;
      recorder.addEventListener("dataavailable", (item) => {
        if (item.data.size) chunksRef.current.push(item.data);
      });
      recorder.start(250);
      setRecording(true);
      setStatus("Recording the spoken reference");
    } catch (error) {
      fail(error);
    }
  };

  const endReference = async () => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state !== "recording") return;
    const voiceEnd = offset();
    const stopped = new Promise<void>((resolve) => {
      recorder.addEventListener("stop", () => resolve(), { once: true });
    });
    recorder.stop();
    await stopped;
    setRecording(false);
    setVoiceTime(`${voiceStartRef.current}–${voiceEnd} ms`);
    const captureId = makeIdentifier("capture");
    const metadata: Omit<CaptureMetadata, "ground_truth"> = {
        schema_version: 1,
        session_id: sessionId,
        capture_id: captureId,
        frame_captured_at: frameRef.current.capturedAt,
        frame_offset_ms: frameRef.current.offset,
        voice_start_ms: voiceStartRef.current,
        voice_end_ms: voiceEnd,
        browser_time_origin_ms: performance.timeOrigin,
        consent: "explicit_start_button",
        devices: {
          camera_label: streamRef.current?.getVideoTracks()[0]?.label ?? "",
          microphone_label: streamRef.current?.getAudioTracks()[0]?.label ?? "",
          video_settings:
            streamRef.current?.getVideoTracks()[0]?.getSettings() ?? {},
          audio_settings:
            streamRef.current?.getAudioTracks()[0]?.getSettings() ?? {},
        },
    };
    pendingRef.current = {
      metadata,
      audio: new Blob(chunksRef.current, { type: recorder.mimeType }),
    };
    setCapturedFrame(frameRef.current.data);
    setExpectedRegion(null);
    setState("annotating");
    setStatus("Draw a box around the object you named");
  };

  const pointerPosition = (
    event: PointerEvent<HTMLDivElement>,
  ): { x: number; y: number } => {
    const bounds = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
      y: Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
    };
  };

  const beginRegion = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = pointerPosition(event);
    dragStartRef.current = point;
    setExpectedRegion({
      left: point.x,
      top: point.y,
      right: point.x,
      bottom: point.y,
    });
  };

  const updateRegion = (event: PointerEvent<HTMLDivElement>) => {
    const start = dragStartRef.current;
    if (!start) return;
    const point = pointerPosition(event);
    setExpectedRegion({
      left: Math.min(start.x, point.x),
      top: Math.min(start.y, point.y),
      right: Math.max(start.x, point.x),
      bottom: Math.max(start.y, point.y),
    });
  };

  const endRegion = (event: PointerEvent<HTMLDivElement>) => {
    updateRegion(event);
    dragStartRef.current = null;
  };

  const saveAnnotatedCapture = async () => {
    const pending = pendingRef.current;
    if (!pending || !expectedRegion) return;
    const hasArea = expectedRegion.right - expectedRegion.left >= 0.02
      && expectedRegion.bottom - expectedRegion.top >= 0.02;
    if (!hasArea) {
      setStatus("Draw a box at least 2% wide and 2% high");
      return;
    }
    setState("saving");
    setStatus("Saving inspectable evidence");
    try {
      const metadata: CaptureMetadata = {
        ...pending.metadata,
        ground_truth: {
          expected_transcript: expectedTranscript.trim(),
          expected_object: expectedObject.trim(),
          expected_region: expectedRegion,
        },
      };
      await saveCapture(metadata, frameRef.current.data, pending.audio);
      pendingRef.current = null;
      setCapturedFrame("");
      setState("live");
      setStatus(`Saved ${metadata.capture_id}`);
    } catch (error) {
      fail(error);
    }
  };

  const endSession = () => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
    stopTracks();
    pendingRef.current = null;
    setCapturedFrame("");
    setExpectedRegion(null);
    setRecording(false);
    setState("idle");
    setStatus("Session ended");
  };

  const live = state !== "idle" && state !== "requesting";
  return (
    <main>
      <header>
        <p className="eyebrow">BOOK 6 · VERTICAL SLICE</p>
        <h1>Capture what “this” refers to</h1>
        <p className="lede">
          Preview first. Record deliberately. Keep the exact evidence.
        </p>
      </header>

      <section className="stage" aria-label="Camera preview">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          hidden={state === "annotating" || state === "saving"}
        />
        <canvas ref={canvasRef} hidden />
        {capturedFrame && (
          <div
            className="annotation-surface"
            aria-label="Draw expected object region"
            role="img"
            onPointerDown={beginRegion}
            onPointerMove={updateRegion}
            onPointerUp={endRegion}
            onPointerCancel={endRegion}
          >
            <img src={capturedFrame} alt="Captured frame awaiting annotation" />
            {expectedRegion && (
              <span
                className="region-box"
                style={{
                  left: `${expectedRegion.left * 100}%`,
                  top: `${expectedRegion.top * 100}%`,
                  width: `${(expectedRegion.right - expectedRegion.left) * 100}%`,
                  height: `${(expectedRegion.bottom - expectedRegion.top) * 100}%`,
                }}
              />
            )}
          </div>
        )}
        <div className={`state-pill ${recording ? "recording" : ""}`}>
          <span aria-hidden="true" />
          {recording ? "Recording reference" : live ? "Preview only" : "Camera off"}
        </div>
      </section>

      <section className="controls" aria-label="Capture controls">
        <button
          className="quiet"
          disabled={state !== "idle"}
          onClick={() => void discoverDevices()}
        >
          Discover cameras and microphones
        </button>
        <button
          className="primary"
          disabled={state !== "idle" || !groundTruthReady}
          onClick={startSession}
        >
          Start consented session
        </button>
        <button
          className="record"
          disabled={state !== "live"}
          onPointerDown={beginReference}
          onPointerUp={() => void endReference()}
          onPointerCancel={() => void endReference()}
        >
          Hold to record reference
        </button>
        <button className="quiet" disabled={!live} onClick={endSession}>
          End session
        </button>
        <button
          className="save"
          disabled={state !== "annotating" || !expectedRegion}
          onClick={() => void saveAnnotatedCapture()}
        >
          Save annotated evidence
        </button>
      </section>

      <section className="devices" aria-labelledby="devices-heading">
        <div>
          <p className="eyebrow">PHYSICAL INPUTS</p>
          <h2 id="devices-heading">Choose the evidence sources</h2>
          <p>
            Virtual cameras are valid only when their feed contains the scene
            being tested. The app prefers locally attached hardware.
          </p>
        </div>
        <label>
          Camera
          <select
            value={cameraId}
            disabled={state !== "idle" || cameras.length === 0}
            onChange={(event) => setCameraId(event.target.value)}
          >
            {cameras.length === 0 && <option>Discover devices first</option>}
            {cameras.map((camera) => (
              <option key={camera.deviceId} value={camera.deviceId}>
                {camera.label || "Unnamed camera"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Microphone
          <select
            value={microphoneId}
            disabled={state !== "idle" || microphones.length === 0}
            onChange={(event) => setMicrophoneId(event.target.value)}
          >
            {microphones.length === 0 && <option>Discover devices first</option>}
            {microphones.map((microphone) => (
              <option key={microphone.deviceId} value={microphone.deviceId}>
                {microphone.label || "Unnamed microphone"}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="ground-truth" aria-labelledby="truth-heading">
        <div>
          <p className="eyebrow">BEFORE RECORDING</p>
          <h2 id="truth-heading">Declare the expected evidence</h2>
          <p>
            These labels are stored for evaluation. They are never shown to
            the perception model.
          </p>
        </div>
        <label>
          Exact phrase you will say
          <input
            value={expectedTranscript}
            required
            disabled={state !== "idle"}
            onChange={(event) => setExpectedTranscript(event.target.value)}
          />
        </label>
        <label>
          Object you will point at
          <input
            value={expectedObject}
            required
            disabled={state !== "idle"}
            placeholder="For example: red mug"
            onChange={(event) => setExpectedObject(event.target.value)}
          />
        </label>
      </section>

      <section className="evidence" aria-labelledby="evidence-heading">
        <div>
          <p className="eyebrow">CURRENT EVENT</p>
          <h2 id="evidence-heading">Inspectable evidence</h2>
        </div>
        <dl>
          <div><dt>Session</dt><dd>{sessionId}</dd></div>
          <div><dt>Frame time</dt><dd>{frameTime}</dd></div>
          <div><dt>Voice interval</dt><dd>{voiceTime}</dd></div>
          <div><dt>Status</dt><dd aria-live="polite">{status}</dd></div>
        </dl>
      </section>
      <OpeningEvidenceLabs />
      <GeometryLab />
      <LiveSessionLab />
      <ScreenStateLab />
      <FusionLab />
      <SafeActionLab />
      <ScreenAgentLab />
      <DocumentLayoutLab />
      <SearchIndexLab />
      <CrossModalSearchLab />
      <HybridRetrievalLab />
      <EvidencePackageLab />
      <EventMemoryLab />
      <MemoryQueryLab />
      <AcousticEventLab />
      <SensorWorldLab />
      <ContradictionLab />
      <PolicyGateLab />
      <SandboxLab />
      <EvaluationLab />
      <FailureLab />
      <RuntimeLab />
      <MultimodalStudio />
      <ProductionControlLab />
      <ReleaseGateLab />
    </main>
  );
}
