"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { useSync } from "@/features/sync/SyncProvider";
import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import { getNotes, noteAmendmentWrite, noteWrite } from "./api";
import { NOTE_KIND_LABELS } from "./labels";
import type { Note } from "./schemas";
import type { RecordContext } from "./VitalsPanel";

const MAX_NOTE = 10_000;

function NoteText({ value, onChange, id }: { value: string; onChange: (v: string) => void; id: string }) {
  return (
    <textarea
      id={id}
      rows={6}
      maxLength={MAX_NOTE}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function NotesPanel({ encounter, meId, nameOf }: RecordContext) {
  const queryClient = useQueryClient();
  const { queue } = useSync();
  const [showHistory, setShowHistory] = useState(false);
  const [writing, setWriting] = useState(false);
  const [kind, setKind] = useState("history");
  const [body, setBody] = useState("");
  const [amending, setAmending] = useState<Note | null>(null);
  const [amendBody, setAmendBody] = useState("");
  const [problem, setProblem] = useState<string | null>(null);

  const notes = useQuery({
    queryKey: ["notes", encounter.id, showHistory],
    queryFn: () => getNotes(encounter.id, showHistory),
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["notes", encounter.id] });
  const write = useMutation({
    mutationFn: () => queue(noteWrite(encounter.id, kind, body)),
    onSuccess: () => {
      setWriting(false);
      setBody("");
      refresh();
    },
  });
  const amend = useMutation({
    mutationFn: (note: Note) => queue(noteAmendmentWrite(note.id, encounter.id, amendBody)),
    onSuccess: () => {
      setAmending(null);
      refresh();
    },
  });

  const isOpen = encounter.status === "open";
  // A note is the author's own words: only the author may amend it.
  const canAmend = (note: Note) =>
    note.version_status === "current" &&
    note.recorded_by_id === meId &&
    encounter.status !== "entered_in_error";

  function handleWrite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!body.trim()) return setProblem("A note cannot be empty.");
    setProblem(null);
    write.mutate();
  }

  return (
    <section aria-labelledby="notes-heading" className="card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="notes-heading" className="mb-0">
          Notes
        </h2>
        <label className="flex items-center gap-2 text-sm font-normal">
          <input
            type="checkbox"
            checked={showHistory}
            onChange={(event) => setShowHistory(event.target.checked)}
          />
          Show earlier wordings
        </label>
      </div>

      {notes.isPending && <p>Loading notes...</p>}
      {notes.isError && (
        <p role="alert" className="error">
          {errorMessage(notes.error)}
        </p>
      )}
      {notes.data?.length === 0 && <p>No notes yet.</p>}
      {notes.data && notes.data.length > 0 && (
        <ul className="grid gap-3">
          {notes.data.map((note) => (
            <li key={note.id} className="grid gap-1 border-t border-line pt-2">
              <p className="flex flex-wrap items-center gap-x-3 text-sm">
                <span className="font-semibold">{NOTE_KIND_LABELS[note.kind] ?? note.kind}</span>
                <span>
                  {nameOf(note.recorded_by_id)},{" "}
                  {formatDateTime(note.written_at ?? note.recorded_at)}
                </span>
                {note.version_status === "superseded" && (
                  <span className="badge bg-gray-200 text-gray-800">Earlier wording</span>
                )}
                {note.replaces_id && note.version_status === "current" && (
                  <span className="badge bg-blue-100 text-blue-900">Amended</span>
                )}
                {note.synced_late && (
                  <span
                    className="badge bg-amber-100 text-amber-900"
                    title={`Written before sign-off on a device that was offline; it arrived ${formatDateTime(note.recorded_at)}.`}
                  >
                    Synced late
                  </span>
                )}
              </p>
              {amending?.id === note.id ? (
                <div className="grid gap-2">
                  <label htmlFor={`amend-${note.id}`} className="sr-only">
                    Amended wording
                  </label>
                  <NoteText id={`amend-${note.id}`} value={amendBody} onChange={setAmendBody} />
                  <div className="flex gap-3">
                    <button
                      className="button"
                      type="button"
                      disabled={amend.isPending || !amendBody.trim()}
                      onClick={() => amend.mutate(note)}
                    >
                      {amend.isPending ? "Saving..." : "Save amendment"}
                    </button>
                    <button
                      className="button-secondary"
                      type="button"
                      onClick={() => setAmending(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap items-start gap-3">
                  <p
                    className={`flex-1 whitespace-pre-wrap ${
                      note.version_status === "superseded" ? "text-gray-600" : ""
                    }`}
                  >
                    {note.body}
                  </p>
                  {canAmend(note) && (
                    <button
                      className="button-secondary"
                      type="button"
                      onClick={() => {
                        setAmending(note);
                        setAmendBody(note.body);
                      }}
                    >
                      Amend
                    </button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {amend.isError && (
        <p role="alert" className="error">
          {errorMessage(amend.error)}
        </p>
      )}

      {isOpen &&
        (writing ? (
          <form onSubmit={handleWrite} noValidate className="grid gap-3">
            <div className="field">
              <label htmlFor="note-kind">Kind of note</label>
              <select id="note-kind" value={kind} onChange={(event) => setKind(event.target.value)}>
                {Object.entries(NOTE_KIND_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="note-body">Note</label>
              <NoteText id="note-body" value={body} onChange={setBody} />
            </div>
            {problem && <p className="error">{problem}</p>}
            {write.isError && (
              <p role="alert" className="error">
                {errorMessage(write.error)}
              </p>
            )}
            <div className="flex gap-3">
              <button className="button" type="submit" disabled={write.isPending}>
                {write.isPending ? "Saving..." : "Save note"}
              </button>
              <button className="button-secondary" type="button" onClick={() => setWriting(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div>
            <button className="button" type="button" onClick={() => setWriting(true)}>
              Write a note
            </button>
          </div>
        ))}
    </section>
  );
}
