import { expect, test } from "@playwright/test";

const chapters = [
  ["01-the-frame-behind-this", /The Frame Behind/],
  ["02-an-evidence-event", /An Evidence Event/],
  ["03-keep-each-modality-honest", /Keep Each Modality Honest/],
  ["04-build-the-first-world-state", /Build the First World State/],
  ["05-pixels-are-not-objects", /Pixels Are Not Objects/],
  ["06-ground-the-claim", /Ground the Claim/],
  ["07-read-the-scene", /Read the Scene/],
  ["08-test-what-the-agent-sees", /Test What the Agent Sees/],
  ["09-an-image-has-no-before", /An Image Has No Before/],
  ["10-sample-what-matters", /Sample What Matters/],
  ["11-find-the-moment", /Find the Moment/],
  ["12-resolve-this-while-the-world-moves", /Resolve.*This.*World Moves/],
  ["13-see-the-screen-read-the-interface", /See the Screen, Read the Interface/],
  ["14-prefer-structure-when-it-exists", /Prefer Structure When It Exists/],
  ["15-turn-observations-into-actions", /Turn Observations into Actions/],
  ["16-build-a-safe-screen-agent", /Build a Safe Screen Agent/],
  ["17-a-page-is-more-than-its-text", /A Page Is More Than Its Text/],
  ["18-search-beyond-text", /Search Beyond Text/],
  ["19-cross-modal-search", /Cross-Modal Search/],
  ["20-hybrid-retrieval-and-reranking", /Hybrid Retrieval and Reranking/],
  ["21-multimodal-rag-with-citations", /Multimodal RAG with Citations/],
  ["22-memory-is-an-event-store", /Memory Is an Event Store/],
  ["23-ask-the-past", /Ask the Past/],
  ["24-audio-beyond-speech", /Audio Beyond Speech/],
  ["25-sensors-and-world-state", /Sensors and World State/],
  ["26-when-modalities-disagree", /When Modalities Disagree/],
  ["27-evidence-before-action", /Evidence Before Action/],
  ["28-build-the-multimodal-sandbox", /Build the Multimodal Sandbox/],
  ["29-evaluate-every-boundary", /Evaluate Every Boundary/],
  ["30-break-it-deliberately", /Break It Deliberately/],
  ["31-design-the-runtime", /Design the Runtime/],
  ["32-build-iagentic-multimodal-studio", /Build IAgentic Multimodal Studio/],
  ["33-deploy-without-losing-the-evidence", /Deploy Without Losing the Evidence/],
  ["34-release-with-tenant-boundaries", /Release with Tenant Boundaries/],
] as const;

test("all chapters render accessible evidence on desktop and mobile", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.route("**/*", async (route) => {
    const type = route.request().resourceType();
    if (type === "script" || type === "font") {
      await route.abort();
      return;
    }
    await route.continue();
  });
  for (const [chapter, title] of chapters) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`http://127.0.0.1:8770/chapters/${chapter}.html`, {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page.getByRole("heading", { level: 1, name: title }),
      `${chapter}: chapter heading`,
    )
      .toBeVisible();

    const figure = page.locator("main img").first();
    await expect(figure, `${chapter}: opening figure`).toBeVisible();
    const image = await figure.evaluate((element) => ({
      alt: element.alt.trim(),
      complete: element.complete,
      height: element.naturalHeight,
      width: element.naturalWidth,
    }));
    expect(image.complete, `${chapter}: image loaded`).toBe(true);
    expect(image.alt.length, `${chapter}: meaningful alt text`).toBeGreaterThan(20);
    expect(image.width, `${chapter}: source width`).toBeGreaterThanOrEqual(900);
    expect(image.height, `${chapter}: source height`).toBeGreaterThan(250);
    expect(await page.locator("img").evaluateAll((images) => images.filter(
      (candidate) => !candidate.complete || candidate.naturalWidth === 0,
    ).length)).toBe(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth
      > document.documentElement.clientWidth)).toBe(false);

    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth
      > document.documentElement.clientWidth)).toBe(false);
  }
});
