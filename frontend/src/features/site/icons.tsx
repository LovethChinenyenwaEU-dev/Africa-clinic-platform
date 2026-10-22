import {
  CalendarDays,
  ClipboardList,
  FileCheck2,
  HeartPulse,
  Pill,
  Send,
  Siren,
  Smartphone,
  Stethoscope,
  UserRoundPlus,
  Video,
  WifiOff,
  type LucideIcon,
} from "lucide-react";

import type { IconName } from "./content";

// The content file names icons by word; this turns the word into the drawing.
export const ICONS: Record<IconName, LucideIcon> = {
  "wifi-off": WifiOff,
  siren: Siren,
  video: Video,
  smartphone: Smartphone,
  "user-plus": UserRoundPlus,
  pill: Pill,
  send: Send,
  "file-check": FileCheck2,
  clipboard: ClipboardList,
  stethoscope: Stethoscope,
  "heart-pulse": HeartPulse,
  calendar: CalendarDays,
};
