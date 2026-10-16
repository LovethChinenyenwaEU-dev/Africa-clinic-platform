import type { ConsultMode } from "./schemas";

/*
 * FR-C4: step down from video to audio to text when the connection is poor. The
 * browser's own estimate (Network Information API, in Chrome and Android browsers)
 * is a hint only: the clinician decides, and the switch is recorded with its reason.
 */

export type ConnectionHint = {
  effectiveType?: string; // "slow-2g", "2g", "3g" or "4g"
  downlink?: number; // megabits per second
  saveData?: boolean; // the person asked their browser to save data
};

/** The richest mode this connection can carry, or null when the browser cannot tell. */
export function suggestedMode(hint: ConnectionHint | null | undefined): ConsultMode | null {
  if (!hint || (hint.effectiveType === undefined && hint.downlink === undefined)) return null;
  if (hint.effectiveType === "slow-2g" || (hint.downlink !== undefined && hint.downlink < 0.15)) {
    return "text";
  }
  if (
    hint.saveData ||
    hint.effectiveType === "2g" ||
    (hint.downlink !== undefined && hint.downlink < 0.7)
  ) {
    return "audio";
  }
  return "video";
}

const RANK: Record<ConsultMode, number> = { video: 2, audio: 1, text: 0 };

/** Should the screen suggest stepping down? Only ever down, never up on its own. */
export function shouldStepDown(current: ConsultMode, suggested: ConsultMode | null): boolean {
  return suggested !== null && RANK[suggested] < RANK[current];
}

/** This browser's estimate, if it gives one. */
export function readConnection(): ConnectionHint | null {
  if (typeof navigator === "undefined") return null;
  const connection = (navigator as Navigator & { connection?: ConnectionHint }).connection;
  return connection
    ? {
        effectiveType: connection.effectiveType,
        downlink: connection.downlink,
        saveData: connection.saveData,
      }
    : null;
}
