import { expect, test } from "@playwright/test";
import path from "node:path";

test("requires declared ground truth before capture", async ({ page }) => {
  await page.goto("/");
  const start = page.getByRole("button", {
    name: "Start consented session",
  });
  await expect(start).toBeDisabled();
  await page.getByLabel("Object you will point at").fill("red mug");
  await expect(start).toBeEnabled();
});

test("surfaces a media permission failure", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => {
          throw new DOMException("Permission denied", "NotAllowedError");
        },
      },
    });
  });
  await page.goto("/");
  await page.getByLabel("Object you will point at").fill("red mug");
  await page.getByRole("button", {
    name: "Start consented session",
  }).click();
  await expect(page.getByText("Permission denied")).toBeVisible();
  await expect(page.getByRole("button", {
    name: "Start consented session",
  })).toBeEnabled();
});

test("prefers physical inputs over virtual devices", async ({ page }) => {
  await page.addInitScript(() => {
    const track = { stop: () => undefined };
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => ({ getTracks: () => [track, track] }),
        enumerateDevices: async () => [
          { kind: "videoinput", deviceId: "droid", label: "DroidCam Video" },
          {
            kind: "videoinput",
            deviceId: "camera",
            label: "Integrated Camera",
          },
          { kind: "videoinput", deviceId: "soft", label: "DirectShow Softcam" },
          { kind: "audioinput", deviceId: "cable", label: "VB Audio cable" },
          {
            kind: "audioinput",
            deviceId: "microphone",
            label: "Microphone Array (Realtek(R) Audio)",
          },
          { kind: "audioinput", deviceId: "phone", label: "DroidCam Audio" },
        ],
      },
    });
  });
  await page.goto("/");
  await page.getByRole("button", {
    name: "Discover cameras and microphones",
  }).click();
  const camera = page.getByRole("combobox", { name: "Camera" });
  const microphone = page.getByRole("combobox", { name: "Microphone" });
  await expect(camera).toHaveValue("camera");
  await expect(microphone).toHaveValue("microphone");
  await camera.selectOption("droid");
  await expect(camera).toHaveValue("droid");
});

test("remains usable on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth
      > document.documentElement.clientWidth,
  );
  expect(overflow).toBe(false);
  for (const button of await page.getByRole("button").all()) {
    const box = await button.boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(48);
  }
});

test("shows the coordinate transform instead of copying a box", async ({
  page,
}) => {
  await page.goto("/");
  const mapped = page.getByText("0.200, 0.331, 0.550, 0.641");
  await expect(mapped).toBeVisible();
  await page.getByRole("region", { name: /The pixels moved/ })
    .screenshot({ path: path.resolve("..", "..", "multimodal-agents-book",
      "figures", "ch05-coordinate-lab.png") });
  await page.getByRole("combobox", { name: "Fit mode" }).selectOption("cover");
  await expect(page.getByText("0.000, 0.200, 0.589, 0.750")).toBeVisible();
  await expect(page.getByLabel("Transformed visible region")).toBeVisible();
});

test("drops old frames and refuses a stale visual reference", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "Bind speech to a fresh frame",
  });
  await expect(lab.getByText("fresh", { exact: true })).toBeVisible();
  await expect(lab.getByText("300 ms", { exact: true })).toBeVisible();
  await lab.screenshot({ path: path.resolve("..", "..",
    "multimodal-agents-book", "figures", "ch12-live-session-policy.png") });
  await lab.getByRole("button", { name: "Simulate frame burst" }).click();
  await expect(lab.getByText("frame-0050")).toBeVisible();
  await expect(lab.getByText("3", { exact: true })).toBeVisible();
  await lab.getByRole("button", { name: "Advance until stale" }).click();
  await expect(lab.getByText("stale", { exact: true })).toBeVisible();
  await expect(lab.getByText("1200 ms", { exact: true })).toBeVisible();
});

test("compares pixels, semantics, and the actual hit target", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", { name: "Three views of one button" });
  const deploy = lab.getByRole("button", { name: "Deploy build" });
  await expect(deploy).toBeEnabled();
  await expect(lab.getByText("button occluded")).toBeVisible();
  await lab.screenshot({ path: path.resolve("..", "..",
    "multimodal-agents-book", "figures", "ch13-screen-state-mismatch.png") });
  await lab.getByRole("button", { name: "Inspect hit target" }).click();
  await expect(lab.getByText("sync overlay", { exact: true })).toBeVisible();
  await lab.getByRole("button", { name: "Finish synchronization" }).click();
  await lab.getByRole("button", { name: "Inspect hit target" }).click();
  await expect(lab.getByText("deploy button", { exact: true })).toBeVisible();
  await expect(lab.getByText("button visible")).toBeVisible();
});

test("preserves conflicting sources until a new observation agrees", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "Agreement is earned, not overwritten",
  });
  await expect(lab.getByText("conflicted", { exact: true })).toBeVisible();
  await expect(lab.getByText("Action withheld", { exact: false })).toBeVisible();
  await expect(lab.getByRole("article")).toHaveCount(4);
  await lab.screenshot({ path: path.resolve("..", "..",
    "multimodal-agents-book", "figures", "ch14-source-preserving-fusion.png") });
  await lab.getByRole("button", {
    name: "Observe reconciled state",
  }).click();
  await expect(lab.getByText("agreed", { exact: true })).toBeVisible();
  await expect(lab.getByText("Action may proceed", { exact: false })).toBeVisible();
});

test("rejects a stale target then proves the refreshed action", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "Reject, refresh, act, prove",
  });
  await expect(lab.getByText("stale", { exact: true })).toBeVisible();
  await expect(lab.getByText("Rejected: observed rev-41", {
    exact: false,
  })).toBeVisible();
  await lab.screenshot({ path: path.resolve("..", "..",
    "multimodal-agents-book", "figures", "ch15-stale-target-rejection.png") });
  await lab.getByRole("button", { name: "Refresh evidence" }).click();
  await expect(lab.getByText("ready", { exact: true })).toBeVisible();
  await lab.getByRole("button", { name: "Execute and verify" }).click();
  await expect(lab.getByText("proved", { exact: true })).toBeVisible();
  await expect(lab.getByText("release-43 reports deployed", {
    exact: false,
  })).toBeVisible();
});

test("screen agent proves a task and refuses the stale variant", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", { name: "One task, two release tests" });
  await lab.getByRole("button", {
    name: "Run approved current action",
  }).click();
  await expect(lab.getByText("proved", { exact: true })).toBeVisible();
  await expect(lab.getByText("release-43 deployed")).toBeVisible();
  await expect(lab.getByText("postcondition.proved")).toBeVisible();
  await lab.getByRole("button", { name: "Plant stale target" }).click();
  await expect(lab.getByText("refused", { exact: true })).toBeVisible();
  await expect(lab.getByText("no state change")).toBeVisible();
  await expect(lab.getByText("action.refused: stale revision")).toBeVisible();
  await lab.screenshot({ path: path.resolve("..", "..",
    "multimodal-agents-book", "figures", "ch16-safe-screen-agent.png") });
});

test("document view preserves table, figure, caption, and relation", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", { name: "A page is more than its text" });
  await expect(lab.getByRole("table")).toBeVisible();
  await expect(lab.getByRole("row")).toHaveCount(3);
  await expect(lab.getByRole("figure")).toBeVisible();
  await expect(lab.getByText("caption_of relation")).toBeVisible();
  await expect(lab.getByText("Flat text retains", { exact: false })).toBeVisible();
  await lab.screenshot({ path: path.resolve("..", "..",
    "multimodal-agents-book", "figures", "ch17-layout-preserving-document.png") });
});

for (const [fixture, file, width, height] of [
  ["scene-overlay.html", "ch07-scene-reading-overlay.png", 1200, 800],
  ["robustness-matrix.html", "ch08-visual-robustness-matrix.png", 1200, 760],
  ["temporal-evidence.html", "ch09-temporal-evidence.png", 1200, 700],
  ["sampling-comparison.html", "ch10-video-sampling.png", 1200, 700],
  ["interval-retrieval.html", "ch11-interval-retrieval.png", 1200, 720],
] as const) {
  test(`captures editorial fixture ${fixture}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await page.goto(`/fixtures/${fixture}`);
    await page.screenshot({
      path: path.resolve("..", "..", "multimodal-agents-book", "figures", file),
      animations: "disabled",
    });
  });
}

test("search results retain object identity and index provenance", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", { name: "A vector hit is not yet evidence" });
  await expect(lab.getByRole("listitem")).toHaveCount(3);
  await expect(lab.getByText("report:p1:table:1")).toBeVisible();
  await expect(lab.getByText("index: release-report-v1")).toBeVisible();
  await expect(lab.getByText("model: gemini-embedding-2")).toBeVisible();
  await expect(lab.getByText("context only")).toBeVisible();
  await expect(lab.getByText("contains evidence")).toHaveCount(2);
  await lab.screenshot({
    path: path.resolve(
      "..",
      "..",
      "multimodal-agents-book",
      "figures",
      "ch18-search-index-provenance.png",
    ),
  });
});

test("cross-modal results expose each measured query direction", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "One space, three different searches",
  });
  await expect(lab.getByRole("article")).toHaveCount(3);
  await expect(lab.getByText("TEXT → IMAGE")).toBeVisible();
  await expect(lab.getByText("SCREENSHOT → INCIDENT")).toBeVisible();
  await expect(lab.getByText("IMAGE → IMAGE")).toBeVisible();
  await expect(lab.getByText("correct")).toHaveCount(3);
  await expect(lab.getByText("tenant filter: tenant-blue")).toBeVisible();
  await lab.screenshot({
    path: path.resolve(
      "..",
      "..",
      "multimodal-agents-book",
      "figures",
      "ch19-cross-modal-directions.png",
    ),
  });
});

test("hybrid retrieval shows failures fusion and abstention", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "Each retrieval leg fails differently",
  });
  await expect(lab.getByRole("article")).toHaveCount(3);
  await expect(lab.getByText("wrong: INC-4828")).toBeVisible();
  await expect(lab.getByText("correct: INC-4827")).toBeVisible();
  await expect(lab.getByText("reranked to evidence")).toBeVisible();
  await expect(lab.getByText("abstain")).toBeVisible();
  await expect(lab.getByText("fusion: Qdrant RRF")).toBeVisible();
  await lab.screenshot({
    path: path.resolve(
      "..",
      "..",
      "multimodal-agents-book",
      "figures",
      "ch20-hybrid-retrieval.png",
    ),
  });
});

test("evidence package remains supported after modality removal", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "The answer survives one missing modality",
  });
  await expect(lab.getByRole("article")).toHaveCount(4);
  await expect(lab.getByText("Search API", { exact: true })).toBeVisible();
  await expect(lab.getByText("verified")).toHaveCount(4);
  await expect(lab.getByText("yes", { exact: true })).toHaveCount(4);
  await expect(lab.getByText("0 citation errors")).toBeVisible();
  await lab.screenshot({
    path: path.resolve(
      "..",
      "..",
      "multimodal-agents-book",
      "figures",
      "ch21-evidence-package-removal.png",
    ),
  });
});

test("event memory preserves original and corrected projections", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "Corrections do not erase history",
  });
  await expect(lab.getByRole("article")).toHaveCount(3);
  await expect(lab.getByText("kitchen counter", { exact: true })).toBeVisible();
  await expect(lab.getByText("kitchen drawer", { exact: true })).toBeVisible();
  await expect(lab.getByText("original retained", { exact: false }))
    .toBeVisible();
  await lab.screenshot({
    path: path.resolve(
      "..",
      "..",
      "multimodal-agents-book",
      "figures",
      "ch22-event-memory.png",
    ),
  });
});

test("temporal queries distinguish what was known at each time", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "Ask what was known, not only what is true now",
  });
  await expect(lab.getByRole("article")).toHaveCount(3);
  await expect(lab.getByText("kitchen counter", { exact: true })).toBeVisible();
  await expect(lab.getByText("kitchen drawer", { exact: true })).toBeVisible();
  await expect(lab.getByText("counter → drawer at 19:44")).toBeVisible();
  await expect(lab.getByText("world time", { exact: false })).toBeVisible();
  await expect(lab.getByText("record time", { exact: false })).toBeVisible();
  await lab.screenshot({
    path: path.resolve(
      "..",
      "..",
      "multimodal-agents-book",
      "figures",
      "ch23-ask-the-past.png",
    ),
  });
});

test("acoustic events expose localization error and release checks", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "A transcript cannot represent a knock",
  });
  await expect(lab.getByRole("article")).toHaveCount(3);
  await expect(lab.getByText("alarm tone", { exact: true })).toBeVisible();
  await expect(lab.getByText("knock", { exact: true })).toBeVisible();
  await expect(lab.getByText("2 / 2 events found")).toBeVisible();
  await expect(lab.getByText("0 false positives", { exact: false }))
    .toBeVisible();
  await lab.screenshot({
    path: path.resolve(
      "..",
      "..",
      "multimodal-agents-book",
      "figures",
      "ch24-audio-beyond-speech.png",
    ),
  });
});

test("sensor world state keeps conflict and supported derivation", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "Fuse evidence without making it agree",
  });
  await expect(lab.getByRole("article")).toHaveCount(4);
  await expect(lab.getByText("closed", { exact: true })).toBeVisible();
  await expect(lab.getByText("open", { exact: true })).toBeVisible();
  await expect(lab.getByText("conflicted", { exact: true })).toBeVisible();
  await expect(lab.getByText("supported", { exact: true })).toBeVisible();
  await expect(lab.getByText("68 Cel + alarm within 0.7 s")).toBeVisible();
  await lab.screenshot({
    path: path.resolve(
      "..",
      "..",
      "multimodal-agents-book",
      "figures",
      "ch25-sensor-world-state.png",
    ),
  });
});

test("contradiction stays open until linked resolution evidence arrives", async ({
  page,
}) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "Disagreement is a record, not an overwrite",
  });
  await expect(lab.getByText("open", { exact: true })).toBeVisible();
  await expect(lab.getByText("action withheld")).toBeVisible();
  await expect(lab.getByText("higher reliability alone", { exact: false }))
    .toBeVisible();
  await lab.getByRole("button", { name: "Record inspected latch" }).click();
  await expect(lab.getByText("resolved", { exact: true })).toBeVisible();
  await expect(lab.getByText("human-review-4 · open")).toBeVisible();
  await expect(lab.getByText("originals retained", { exact: false }))
    .toBeVisible();
  await lab.screenshot({
    path: path.resolve(
      "..",
      "..",
      "multimodal-agents-book",
      "figures",
      "ch26-contradiction-lifecycle.png",
    ),
  });
});

test("policy gate binds approval and blocks mutation and conflict", async ({ page }) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "Approval binds the action, not the conversation",
  });
  await expect(lab.getByRole("article")).toHaveCount(4);
  await expect(lab.getByText("pending", { exact: true })).toBeVisible();
  await expect(lab.getByText("allowed", { exact: true })).toBeVisible();
  await expect(lab.getByText("denied", { exact: true })).toHaveCount(2);
  await expect(lab.getByText("approval scope mismatch", { exact: false }))
    .toBeVisible();
  await lab.screenshot({
    path: path.resolve("..", "..", "multimodal-agents-book", "figures",
      "ch27-evidence-before-action.png"),
  });
});

test("sandbox exposes deterministic timeline and boundary scores", async ({ page }) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "Replay the same world, score every boundary",
  });
  await expect(lab.getByRole("article")).toHaveCount(5);
  await expect(lab.getByText("pass", { exact: true })).toHaveCount(3);
  await expect(lab.getByText("identical", { exact: true })).toBeVisible();
  await expect(lab.getByText("3 / 3 checks")).toBeVisible();
  await lab.screenshot({
    path: path.resolve("..", "..", "multimodal-agents-book", "figures",
      "ch28-multimodal-sandbox.png"),
  });
});

test("evaluation report keeps six release boundaries visible", async ({ page }) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "One passing average cannot hide one unsafe boundary",
  });
  await expect(lab.getByRole("article")).toHaveCount(6);
  await expect(lab.getByText("release passed")).toBeVisible();
  await expect(lab.locator("article span")).toHaveCount(6);
  await expect(lab.getByText("6 / 6 explicit gates")).toBeVisible();
  await lab.screenshot({
    path: path.resolve("..", "..", "multimodal-agents-book", "figures",
      "ch29-evaluate-every-boundary.png"),
  });
});

test("failure suite contains five seeded failures", async ({ page }) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "Break the boundary, prove the safe response",
  });
  await expect(lab.getByRole("article")).toHaveCount(5);
  await expect(lab.getByText("blocked", { exact: true })).toHaveCount(4);
  await expect(lab.getByText("abstained", { exact: true })).toBeVisible();
  await expect(lab.getByText("5 / 5 contained")).toBeVisible();
  await lab.screenshot({
    path: path.resolve("..", "..", "multimodal-agents-book", "figures",
      "ch30-break-it-deliberately.png"),
  });
});

test("runtime view correlates spans backpressure and metrics", async ({ page }) => {
  await page.goto("/");
  const lab = page.getByRole("region", {
    name: "One trace explains pressure, work, and evidence",
  });
  await expect(lab.getByRole("article")).toHaveCount(5);
  await expect(lab.getByText("rejected_full", { exact: false })).toBeVisible();
  await expect(lab.getByText("REJECTED FULL")).toBeVisible();
  await expect(lab.getByText("raw audio", { exact: false })).toBeVisible();
  await lab.screenshot({
    path: path.resolve("..", "..", "multimodal-agents-book", "figures",
      "ch31-runtime-observability.png"),
  });
});

test("studio coordinates session tools and keyboard tabs", async ({ page }) => {
  await page.goto("/");
  const studio = page.getByRole("region", {
    name: "Inspect one session end to end",
  });
  await expect(studio.getByText("frame-0087")).toBeVisible();
  await studio.getByRole("tab", { name: "Evidence" }).click();
  await expect(studio.getByText("sha256: 51a7…29cc")).toBeVisible();
  const search = studio.getByRole("tab", { name: "Search" });
  await search.focus();
  await search.press("ArrowRight");
  await expect(studio.getByRole("tab", { name: "Evaluation" }))
    .toHaveAttribute("aria-selected", "true");
  await expect(studio.getByText("84 ms")).toBeVisible();
  await studio.screenshot({
    path: path.resolve("..", "..", "multimodal-agents-book", "figures",
      "ch32-multimodal-studio.png"),
  });
});

test("production control gate exposes every required boundary", async ({ page }) => {
  await page.goto("/");
  const gate = page.getByRole("region", {
    name: "Ship only with inspectable controls",
  });
  await expect(gate.getByRole("article")).toHaveCount(8);
  await expect(gate.getByText("PASS", { exact: true })).toHaveCount(8);
  await expect(gate.getByText("8 / 8 passed")).toBeVisible();
  await expect(gate.getByText("engineering mapping, not certification"))
    .toBeVisible();
  await gate.screenshot({
    path: path.resolve("..", "..", "multimodal-agents-book", "figures",
      "ch33-production-control-gate.png"),
  });
});

test("final gate releases with verified organization claims", async ({ page }) => {
  await page.goto("/");
  const gate = page.getByRole("region", {
    name: "Evidence decides whether we ship",
  });
  await expect(gate.getByRole("article")).toHaveCount(6);
  await expect(gate.getByText("PASS", { exact: true })).toHaveCount(6);
  await expect(gate.getByText("READY", { exact: true })).toBeVisible();
  await expect(gate.getByText("6 / 6 passed")).toBeVisible();
  await gate.screenshot({
    path: path.resolve("..", "..", "multimodal-agents-book", "figures",
      "ch34-final-release-gate.png"),
  });
});

for (const [name, file, articles] of [
  ["Bind this to one session clock", "ch01-synchronized-capture.png", 3],
  ["An evidence event can be inspected", "ch02-evidence-event.png", 3],
  ["Keep each modality honest", "ch03-modality-honesty.png", 2],
  ["Build a world state without erasing evidence", "ch04-world-state.png", 3],
] as const) {
  test(`captures opening figure: ${name}`, async ({ page }) => {
    await page.goto("/");
    const lab = page.getByRole("region", { name });
    await expect(lab).toBeVisible();
    await expect(lab.getByRole("article")).toHaveCount(articles);
    await lab.screenshot({
      path: path.resolve(
        "..", "..", "multimodal-agents-book", "figures", file,
      ),
    });
  });
}
