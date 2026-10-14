export const STATUS_LABELS: Record<string, string> = {
  booked: "Booked",
  waiting: "Waiting",
  in_consult: "With clinician",
  done: "Done",
  cancelled: "Cancelled",
  no_show: "Did not come",
};

// Colours for the status badge. Text and colour together, never colour alone.
export const STATUS_STYLES: Record<string, string> = {
  booked: "bg-blue-100 text-blue-900",
  waiting: "bg-amber-100 text-amber-900",
  in_consult: "bg-green-100 text-green-900",
  done: "bg-gray-200 text-gray-800",
  cancelled: "bg-gray-200 text-gray-800",
  no_show: "bg-red-100 text-red-900",
};

export const KIND_LABELS: Record<string, string> = {
  scheduled: "Appointment",
  walk_in: "Walk-in",
};
