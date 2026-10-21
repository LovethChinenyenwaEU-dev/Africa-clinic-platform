"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { RED_FLAG_LABELS } from "@/features/scheduling/labels";
import { mergeMessages } from "@/features/telehealth/api";
import { ApiError, errorMessage } from "@/lib/api-client";
import { formatDateTime, formatTime } from "@/lib/format";

import {
  answerIntake,
  getMyChat,
  getMyRoom,
  remoteStep,
  sendMyMessage,
  type ChatMessage,
  type MyVisit,
} from "./api";

const ROOM_CHECK_MS = 10_000; // while waiting: is the clinician ready?
const CHAT_CHECK_MS = 5_000;

/*
 * One remote visit on the patient page: answer the questions, wait for the clinician,
 * then join the call and chat. Each step shows only when it is the next one.
 */
export function PatientRemoteVisit({ visit }: { visit: MyVisit }) {
  const step = remoteStep(visit);
  if (step === null) return null;
  return (
    <section aria-labelledby={`remote-${visit.appointment_id}`} className="card grid gap-3">
      <h2 id={`remote-${visit.appointment_id}`} className="mb-0">
        Remote consultation, {formatDateTime(visit.starts_at)}
        {visit.clinician_name ? ` with ${visit.clinician_name}` : ""}
      </h2>
      {step === "intake" ? <Intake visitId={visit.appointment_id} /> : <Room visit={visit} />}
    </section>
  );
}

function Intake({ visitId }: { visitId: string }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [redFlags, setRedFlags] = useState<string[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => answerIntake(visitId, reason, redFlags),
    onSuccess: (answer) => {
      if (answer.outcome === "ready") void queryClient.invalidateQueries({ queryKey: ["portal"] });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reason.trim()) return setProblem("Please say why you want to see the clinician.");
    setProblem(null);
    save.mutate();
  }

  if (save.data?.outcome === "escalated") {
    return (
      <div role="alert" className="grid gap-2 rounded border border-red-300 bg-red-50 p-3">
        <p className="font-semibold text-red-900">Please do not wait for a remote consultation</p>
        <p>{save.data.advice}</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3" noValidate>
      <p className="text-sm">
        Answer these before your consultation. Your answers go to your clinician.
      </p>
      <div className="field">
        <label htmlFor={`my-reason-${visitId}`}>Why do you want to see the clinician?</label>
        <textarea
          id={`my-reason-${visitId}`}
          rows={3}
          maxLength={500}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </div>
      <fieldset className="grid gap-1">
        <legend className="font-semibold">Do you have any of these right now?</legend>
        {Object.entries(RED_FLAG_LABELS).map(([flag, label]) => (
          <label key={flag} className="flex items-center gap-2 font-normal">
            <input
              type="checkbox"
              checked={redFlags.includes(flag)}
              onChange={(event) =>
                setRedFlags((flags) =>
                  event.target.checked ? [...flags, flag] : flags.filter((f) => f !== flag),
                )
              }
            />
            {label}
          </label>
        ))}
      </fieldset>
      {(problem || save.isError) && (
        <p role="alert" className="error">
          {problem ?? errorMessage(save.error)}
        </p>
      )}
      <button className="button" type="submit" disabled={save.isPending}>
        {save.isPending ? "Sending..." : "Send my answers"}
      </button>
    </form>
  );
}

function Room({ visit }: { visit: MyVisit }) {
  const live = visit.status === "in_consult";
  // The room opens when the clinician starts: check every few seconds until then.
  const room = useQuery({
    queryKey: ["portal", "room", visit.appointment_id],
    queryFn: () => getMyRoom(visit.appointment_id),
    retry: false,
    refetchInterval: (query) => (query.state.data ? false : ROOM_CHECK_MS),
  });
  const notOpenYet = room.error instanceof ApiError && room.error.kind === "conflict";

  return (
    <div className="grid gap-3">
      {!room.data && (
        <p role="status" className="notice">
          You are in the waiting room. Keep this page open: the call appears here when your
          clinician is ready.
        </p>
      )}
      {room.isError && !notOpenYet && <p className="error">{errorMessage(room.error)}</p>}
      {room.data && (
        <div className="flex flex-wrap gap-3">
          {room.data.mode === "video" && room.data.video_url && (
            <a className="button" href={room.data.video_url} target="_blank" rel="noreferrer">
              Join the video call
            </a>
          )}
          {room.data.mode !== "text" && room.data.audio_url && (
            <a
              className={room.data.mode === "audio" ? "button" : "button-secondary"}
              href={room.data.audio_url}
              target="_blank"
              rel="noreferrer"
            >
              Join by audio only (uses less data)
            </a>
          )}
          {room.data.mode === "text" && (
            <p>Your clinician is using the chat below, which works on a weak connection.</p>
          )}
        </div>
      )}
      {(room.data || live) && <Chat visitId={visit.appointment_id} />}
    </div>
  );
}

function Chat({ visitId }: { visitId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const newest = useRef<string | undefined>(undefined);
  const first = useQuery({ queryKey: ["portal", "chat", visitId], queryFn: () => getMyChat(visitId) });

  useEffect(() => {
    if (first.data) setMessages((known) => mergeMessages(known, first.data));
  }, [first.data]);
  useEffect(() => {
    newest.current = messages.at(-1)?.sent_at;
  }, [messages]);
  useEffect(() => {
    if (!first.data) return;
    const timer = setInterval(() => {
      getMyChat(visitId, newest.current)
        .then((fresh) => setMessages((known) => mergeMessages(known, fresh)))
        .catch(() => {});
    }, CHAT_CHECK_MS);
    return () => clearInterval(timer);
  }, [visitId, first.data]);

  const send = useMutation({
    mutationFn: () => sendMyMessage(visitId, draft),
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
      <h3 className="mb-0 text-base font-semibold">Chat with your clinician</h3>
      <ul className="grid max-h-72 gap-1 overflow-y-auto" aria-live="polite">
        {messages.map((message) => (
          <li key={message.id}>
            <span className="font-mono text-sm">{formatTime(message.sent_at)}</span>{" "}
            <span className="font-semibold">
              {message.sender === "patient" ? "You" : "Clinician"}:
            </span>{" "}
            <span className="whitespace-pre-wrap">{message.body}</span>
          </li>
        ))}
      </ul>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <label htmlFor={`my-chat-${visitId}`} className="sr-only">
          Message
        </label>
        <input
          id={`my-chat-${visitId}`}
          className="flex-1"
          autoComplete="off"
          maxLength={2000}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button className="button" type="submit" disabled={send.isPending || !draft.trim()}>
          Send
        </button>
      </form>
      {send.isError && <p className="error">{errorMessage(send.error)}</p>}
    </div>
  );
}
