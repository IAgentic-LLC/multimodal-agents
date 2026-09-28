export type SessionState =
  | "idle"
  | "requesting"
  | "live"
  | "annotating"
  | "saving";

export interface NormalizedRegion {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export interface CaptureMetadata {
  schema_version: 1;
  session_id: string;
  capture_id: string;
  frame_captured_at: string;
  frame_offset_ms: number;
  voice_start_ms: number;
  voice_end_ms: number;
  browser_time_origin_ms: number;
  consent: "explicit_start_button";
  devices: {
    camera_label: string;
    microphone_label: string;
    video_settings: MediaTrackSettings;
    audio_settings: MediaTrackSettings;
  };
  ground_truth: {
    expected_transcript: string;
    expected_object: string;
    expected_region: NormalizedRegion;
  };
}

export interface CaptureResponse {
  frame: string;
  audio: string;
  manifest: string;
  error?: string;
}
