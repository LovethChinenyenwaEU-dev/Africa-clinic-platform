"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError, errorMessage } from "@/lib/api-client";
import { formatTime } from "@/lib/format";

import {
  getMessages,
  getTeleconsultStatus,
  mergeMessages,
  openRoom,
  sendMessage,
  switchMode,
  type ModeReason,
} from "./api";
import { readConnection, shouldStepDown, suggestedMode } from "./connection";
import type { ConsultMode, Message, Room } from "./schemas";

const POLL_MS = 5_000; // a small request: only messages since the last one seen
const MODE_LABELS: Record<ConsultMode, string> = {
  video: "Video",
  audio: "Audio only",
  text: "Text (chat) only",
};
const REASON_LABELS: Record<ModeReason, string> = {
  poor_connection: "Poor connection",
  patient_choice: "The patient asked",
  clinician_choice: "My choice",
};

/*
 * The remote side of an encounter (FR-C3, FR-C4): open the room, join the call in a
 * new tab, step down from video to audio to text when the connection is poor, and
 * chat. Shows nothing for an in-person visit.
 */
export function ConsultPanel({
  appointmentId,
  canRun,
  live,
}: {
  appointmentId: string;
  canRun: boolean; // the clinician running this visit
  live: boolean; // the encounter is open
}) {
  const status = useQuery({
    queryKey: ["teleconsult-status", appointmentId],
    queryFn: () => getTeleconsultStatus(appointmentId),
    retry: false,
  });
  const [room, setRoom] = useState<Room | null>(null);
  const [reason, setReason] = useState<ModeReason>("poor_connection");
  const open = useMutation({ mutationFn: () => openRoom(appointmentId), onSuccess: setRoom });
  const change = useMutation({
    mutationFn: (mode: ConsultMode) => switchMode(appointmentId, mode, reason),
    onSuccess: setRoom,
  });

  // Not a remote visit: the status door answers "conflict". Show nothing.
  if (status.error instanceof ApiError && status.error.kind === "conflict") return null;
  if (!status.data) return null;

  const hint = suggestedMode(readConnection());
  const failure = open.error ?? change.error;

  return (
    <section aria-labelledby="consult-heading" className="card grid gap-3">
      <h2 id="consult-heading" className="mb-0">
        Remote consultation
      </h2>

      {!room && canRun && live && (
        <div>
          <button
            className="button"
            type="button"
            disabled={open.isPending}
            onClick={() => open.mutate()}
          >
            {open.isPending ? "Opening..." : "Open the consult room"}
          </button>
        </div>
      )}
      {!room && !(canRun && live) && (
        <p className="text-sm">Only the clinician running this visit opens the room.</p>
      )}

      {room && (
        <div className="grid gap-3">
          <p>
            Now on: <span className="font-semibold">{MODE_LABELS[room.mode]}</span>
          </p>
          {room.mode !== "text" && (
            <p className="flex flex-wrap gap-3">
              {room.mode === "video" && room.video_url && (
                <a className="button" href={room.video_url} target="_blank" rel="noreferrer">
                  Join the video call
                </a>
              )}
              {room.audio_url && (
                <a
                  className={room.mode === "audio" ? "button" : "button-secondary"}
                  href={room.audio_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Join by audio only
                </a>
              )}
            </p>
          )}
          {shouldStepDown(room.mode, hint) && hint && (
            <p role="status" className="notice">
              This device&apos;s connection looks too weak for {MODE_LABELS[room.mode].toLowerCase()}.
              Consider switching to {MODE_LABELS[hint].toLowerCase()}.
            </p>
          )}
          {canRun && live && (
            <div className="flex flex-wrap items-end gap-3">
              <div className="field">
                <label htmlFor="mode-reason">Why switch</label>
                <select
                  id="mode-reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value as ModeReason)}
                >
                  {Object.entries(REASON_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              {(Object.keys(MODE_LABELS) as ConsultMode[])
                .filter((mode) => mode !== room.mode)
                .filter((mode) => mode === "text" || room.video_url !== null)
                .map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className="button-secondary"
                    disabled={change.isPending}
                    onClick={() => change.mutate(mode)}
                  >
                    Switch to {MODE_LABELS[mode].toLowerCase()}
                  </button>
                ))}
            </div>
          )}
        </div>
      )}
      {failure && (
        <p role="alert" className="error">
          {errorMessage(failure)}
        </p>
      )}

      <Chat appointmentId={appointmentId} canWrite={canRun && live} />
    </section>
  );
}

function Chat({ appointmentId, canWrite }: { appointmentId: string; canWrite: boolean }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const newest = useRef<string | undefined>(undefined);

  // Opening the chat (in the diary), then a small check every few seconds.
  const first = useQuery({
    queryKey: ["consult-chat", appointmentId],
    queryFn: () => getMessages(appointmentId),
  });
  useEffect(() => {
    if (first.data) setMessages((known) => mergeMessages(known, first.data));
  }, [first.data]);
  useEffect(() => {
    newest.current = messages.at(-1)?.sent_at;
  }, [messages]);
  useEffect(() => {
    if (!first.data) return;
    const timer = setInterval(() => {
      getMessages(appointmentId, newest.current)
        .then((fresh) => setMessages((known) => mergeMessages(known, fresh)))
        .catch(() => {}); // a missed check is retried at the next tick
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [appointmentId, first.data]);

  const send = useMutation({
    mutationFn: () => sendMessage(appointmentId, draft),
    onSuccess: (message) => {
      setMessages((known) => mergeMessages(known, [message]));
      setDraft("");
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.trim()) send.mutate();
  }

  return (
    <div className="grid gap-2 border-t border-line pt-3">
      <h3 className="mb-0 text-base font-semibold">Chat</h3>
      {first.isError && <p className="error">{errorMessage(first.error)}</p>}
      {messages.length === 0 && first.data && <p className="text-sm">No messages yet.</p>}
      <ul className="grid max-h-72 gap-1 overflow-y-auto" aria-live="polite">
        {messages.map((message) => (
          <li key={message.id} className="text-sm">
            <span className="font-mono">{formatTime(message.sent_at)}</span>{" "}
            <span className="font-semibold">
              {message.sender === "patient" ? "Patient" : "Clinician"}:
            </span>{" "}
            <span className="whitespace-pre-wrap">{message.body}</span>
          </li>
        ))}
      </ul>
      {canWrite && (
        <form onSubmit={handleSubmit} className="flex gap-2">
          <label htmlFor={`chat-${appointmentId}`} className="sr-only">
            Message
          </label>
          <input
            id={`chat-${appointmentId}`}
            className="flex-1"
            autoComplete="off"
            maxLength={2000}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button className="button" type="submit" disabled={send.isPending || !draft.trim()}>
            {send.isPending ? "Sending..." : "Send"}
          </button>
        </form>
      )}
      {send.isError && (
        <p role="alert" className="error">
          {errorMessage(send.error)}
        </p>
      )}
    </div>
  );
}
