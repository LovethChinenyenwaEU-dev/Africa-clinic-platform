import "server-only";

const DEVICE_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_AGENT_LENGTH = 300;

/*
 * What the backend needs to name a new sign-in in the person's device list (Week 11):
 * the browser's own description ("Chrome on Windows" is made from it) and this
 * device's random id. Nothing else from the browser is passed on.
 */
export function signInHeaders(request: Request): Record<string, string> {
  const headers: Record<string, string> = {};
  const agent = request.headers.get("user-agent");
  if (agent) headers["User-Agent"] = agent.slice(0, MAX_AGENT_LENGTH);
  const deviceId = request.headers.get("x-device-id");
  if (deviceId && DEVICE_ID.test(deviceId)) headers["X-Device-Id"] = deviceId;
  return headers;
}
