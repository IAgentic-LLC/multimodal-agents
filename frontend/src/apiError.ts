/** Turns a failed fetch response into a real, human-readable message
 * instead of a raw JSON error blob. FastAPI's own error shape is
 * {"detail": "..."}; this extracts that real detail text when present,
 * falling back to the raw body only when it genuinely isn't JSON.
 */
export async function humanizeApiError(response: Response, action: string): Promise<string> {
  const bodyText = await response.text();
  try {
    const parsed = JSON.parse(bodyText);
    if (typeof parsed.detail === "string") {
      return `${action}: ${parsed.detail}`;
    }
  } catch {
    // not JSON: fall through to the raw text below
  }
  return `${action} (status ${response.status}): ${bodyText}`;
}
