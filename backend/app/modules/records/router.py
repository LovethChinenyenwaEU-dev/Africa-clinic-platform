"""Doors to the clinical record. Doctors and nurses only; every read and write is in the diary.

The guards check the role; the services check everything else (open encounter,
owner, author, same clinic). Another clinic's records answer 404, exactly like
an ID that does not exist.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.patients.service import PatientNotFoundError
from app.modules.records.chart import (
    AllergyDetails,
    AllergyNotFoundError,
    InvalidChartEntryError,
    ProblemDetails,
    ProblemNotFoundError,
    WrongPatientError,
    list_patient_allergies,
    list_patient_problems,
    record_allergy,
    record_problem,
    resolve_allergy_conflict,
    resolve_problem_conflict,
    revise_allergy,
    revise_problem,
)
from app.modules.records.conflicts import NotAConflictError
from app.modules.records.notes import (
    InvalidNoteError,
    NoteNotFoundError,
    NotNoteAuthorError,
    amend_note,
    list_encounter_notes,
    resolve_note_conflict,
    write_note,
)
from app.modules.records.prescriptions import (
    InvalidPrescriptionError,
    NotAPrescriberError,
    PrescriptionDetails,
    PrescriptionNotFoundError,
    list_encounter_prescriptions,
    resolve_prescription_conflict,
    revise_prescription,
    write_prescription,
)
from app.modules.records.schemas import (
    AllergyForm,
    AllergyResponse,
    AmendNote,
    CorrectVitals,
    EncounterResponse,
    NoteResponse,
    OpenEncounter,
    PrescriptionForm,
    PrescriptionResponse,
    ProblemForm,
    ProblemResponse,
    Readings,
    RecordVitals,
    ResolveConflict,
    ReviseAllergy,
    RevisePrescription,
    ReviseProblem,
    VitalsResponse,
    WriteNote,
)
from app.modules.records.service import (
    EncounterNotFoundError,
    EncounterNotOpenError,
    InvalidEncounterMoveError,
    NotAClinicianError,
    NotCurrentVersionError,
    NotEncounterOwnerError,
    VisitMismatchError,
    VisitNotFoundError,
    close_encounter,
    get_encounter,
    list_patient_encounters,
    mark_entered_in_error,
    open_encounter,
)
from app.modules.records.vitals import (
    InvalidVitalsError,
    NotVitalsAuthorError,
    VitalReadings,
    VitalsNotFoundError,
    correct_vitals,
    list_encounter_vitals,
    record_vitals,
    resolve_vitals_conflict,
)

router = APIRouter(tags=["records"])

READ = [Depends(require(Capability.CLINICAL_READ))]
WRITE = [Depends(require(Capability.CLINICAL_WRITE))]
PRESCRIBE = [Depends(require(Capability.PRESCRIBE))]  # doctors only
# One message for every missing thing, so nobody can probe what exists in another clinic.
NOT_FOUND = "Not found."

INVALID = (InvalidVitalsError, InvalidChartEntryError, InvalidNoteError, InvalidPrescriptionError)
MISSING = (
    EncounterNotFoundError,
    PatientNotFoundError,
    VisitNotFoundError,
    VitalsNotFoundError,
    AllergyNotFoundError,
    ProblemNotFoundError,
    NoteNotFoundError,
    PrescriptionNotFoundError,
)
CONFLICT = (
    InvalidEncounterMoveError,
    EncounterNotOpenError,
    NotCurrentVersionError,
    NotAConflictError,
    VisitMismatchError,
    WrongPatientError,
)
FORBIDDEN = (
    NotAClinicianError,
    NotEncounterOwnerError,
    NotVitalsAuthorError,
    NotNoteAuthorError,
    NotAPrescriberError,
)
KNOWN_ERRORS = INVALID + MISSING + CONFLICT + FORBIDDEN


def _http_error(error: Exception) -> HTTPException:
    """Turn our own named errors into answers. Messages never contain clinical text."""
    if isinstance(error, INVALID):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, MISSING):
        return HTTPException(status_code=404, detail=NOT_FOUND)
    if isinstance(error, CONFLICT):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, FORBIDDEN):
        return HTTPException(status_code=403, detail=str(error))
    raise error


def _readings(form: Readings) -> VitalReadings:
    return VitalReadings(**form.model_dump(include=set(Readings.model_fields)))


def _who(staff) -> dict:
    return {"tenant_id": staff.tenant_id, "actor_id": staff.id}


def _choice(body: ResolveConflict) -> dict:
    return {"keep_conflict": body.keep == "this"}


# Encounters


@router.post(
    "/encounters",
    response_model=EncounterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE,
)
def start_encounter(
    body: OpenEncounter, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """Open an encounter. Sending the same ID or visit again returns the same encounter."""
    try:
        return open_encounter(
            session,
            **_who(current_staff),
            patient_id=body.patient_id,
            appointment_id=body.appointment_id,
            encounter_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.get("/encounters/{encounter_id}", response_model=EncounterResponse, dependencies=READ)
def read_encounter(
    encounter_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    found = get_encounter(session, **_who(current_staff), encounter_id=encounter_id)
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return found


@router.post(
    "/encounters/{encounter_id}/close", response_model=EncounterResponse, dependencies=WRITE
)
def sign_off_encounter(
    encounter_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """Only the clinician who opened the encounter may close it."""
    try:
        return close_encounter(session, **_who(current_staff), encounter_id=encounter_id)
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/encounters/{encounter_id}/entered-in-error",
    response_model=EncounterResponse,
    dependencies=WRITE,
)
def flag_encounter_as_mistake(
    encounter_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """Only the clinician who opened the encounter may mark it as a mistake. It is kept."""
    try:
        return mark_entered_in_error(session, **_who(current_staff), encounter_id=encounter_id)
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.get(
    "/patients/{patient_id}/encounters",
    response_model=list[EncounterResponse],
    dependencies=READ,
)
def read_patient_encounters(
    patient_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    try:
        return list_patient_encounters(session, **_who(current_staff), patient_id=patient_id)
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


# Vitals


@router.post(
    "/encounters/{encounter_id}/vitals",
    response_model=VitalsResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE,
)
def add_vitals(
    encounter_id: uuid.UUID,
    body: RecordVitals,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    try:
        return record_vitals(
            session,
            **_who(current_staff),
            encounter_id=encounter_id,
            readings=_readings(body),
            measured_at=body.measured_at,
            vitals_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.get(
    "/encounters/{encounter_id}/vitals", response_model=list[VitalsResponse], dependencies=READ
)
def read_vitals(
    encounter_id: uuid.UUID,
    current_staff: CurrentStaff,
    include_history: bool = False,
    session: Session = Depends(get_session),
):
    try:
        return list_encounter_vitals(
            session,
            **_who(current_staff),
            encounter_id=encounter_id,
            include_history=include_history,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/vitals/{vitals_id}/corrections",
    response_model=VitalsResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE,
)
def fix_vitals(
    vitals_id: uuid.UUID,
    body: CorrectVitals,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """A new version. Only whoever recorded the vitals, or the encounter's owner."""
    try:
        return correct_vitals(
            session,
            **_who(current_staff),
            vitals_id=vitals_id,
            readings=_readings(body),
            correction_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post("/vitals/{vitals_id}/resolve", response_model=VitalsResponse, dependencies=WRITE)
def choose_vitals(
    vitals_id: uuid.UUID,
    body: ResolveConflict,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Settle a conflict: keep this set or the current one. Answers with the set kept."""
    try:
        return resolve_vitals_conflict(
            session, **_who(current_staff), conflict_id=vitals_id, **_choice(body)
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


# Allergies


def _allergy(body: AllergyForm) -> AllergyDetails:
    return AllergyDetails(
        substance=body.substance,
        reaction=body.reaction,
        severity=body.severity,
        clinical_status=body.clinical_status,
    )


@router.post(
    "/encounters/{encounter_id}/allergies",
    response_model=AllergyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE,
)
def add_allergy(
    encounter_id: uuid.UUID,
    body: AllergyForm,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    try:
        return record_allergy(
            session,
            **_who(current_staff),
            encounter_id=encounter_id,
            details=_allergy(body),
            allergy_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/allergies/{allergy_id}/revisions",
    response_model=AllergyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE,
)
def change_allergy(
    allergy_id: uuid.UUID,
    body: ReviseAllergy,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    try:
        return revise_allergy(
            session,
            **_who(current_staff),
            allergy_id=allergy_id,
            encounter_id=body.encounter_id,
            details=_allergy(body),
            revision_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/allergies/{allergy_id}/resolve", response_model=AllergyResponse, dependencies=WRITE
)
def choose_allergy(
    allergy_id: uuid.UUID,
    body: ResolveConflict,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    try:
        return resolve_allergy_conflict(
            session, **_who(current_staff), conflict_id=allergy_id, **_choice(body)
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.get(
    "/patients/{patient_id}/allergies",
    response_model=list[AllergyResponse],
    dependencies=READ,
)
def read_allergies(
    patient_id: uuid.UUID,
    current_staff: CurrentStaff,
    include_history: bool = False,
    session: Session = Depends(get_session),
):
    try:
        return list_patient_allergies(
            session,
            **_who(current_staff),
            patient_id=patient_id,
            include_history=include_history,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


# Problems and diagnoses


def _problem(body: ProblemForm) -> ProblemDetails:
    return ProblemDetails(
        description=body.description,
        category=body.category,
        code=body.code,
        clinical_status=body.clinical_status,
        onset_date=body.onset_date,
    )


@router.post(
    "/encounters/{encounter_id}/problems",
    response_model=ProblemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE,
)
def add_problem(
    encounter_id: uuid.UUID,
    body: ProblemForm,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    try:
        return record_problem(
            session,
            **_who(current_staff),
            encounter_id=encounter_id,
            details=_problem(body),
            problem_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/problems/{problem_id}/revisions",
    response_model=ProblemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE,
)
def change_problem(
    problem_id: uuid.UUID,
    body: ReviseProblem,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    try:
        return revise_problem(
            session,
            **_who(current_staff),
            problem_id=problem_id,
            encounter_id=body.encounter_id,
            details=_problem(body),
            revision_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/problems/{problem_id}/resolve", response_model=ProblemResponse, dependencies=WRITE
)
def choose_problem(
    problem_id: uuid.UUID,
    body: ResolveConflict,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    try:
        return resolve_problem_conflict(
            session, **_who(current_staff), conflict_id=problem_id, **_choice(body)
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.get(
    "/patients/{patient_id}/problems",
    response_model=list[ProblemResponse],
    dependencies=READ,
)
def read_problems(
    patient_id: uuid.UUID,
    current_staff: CurrentStaff,
    include_history: bool = False,
    session: Session = Depends(get_session),
):
    try:
        return list_patient_problems(
            session,
            **_who(current_staff),
            patient_id=patient_id,
            include_history=include_history,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


# Notes


@router.post(
    "/encounters/{encounter_id}/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE,
)
def add_note(
    encounter_id: uuid.UUID,
    body: WriteNote,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    try:
        return write_note(
            session,
            **_who(current_staff),
            encounter_id=encounter_id,
            kind=body.kind,
            body=body.body,
            note_id=body.id,
            written_at=body.written_at,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/notes/{note_id}/amendments",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE,
)
def change_note(
    note_id: uuid.UUID,
    body: AmendNote,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Only the note's author may amend it. The old wording is kept."""
    try:
        return amend_note(
            session,
            **_who(current_staff),
            note_id=note_id,
            body=body.body,
            amendment_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post("/notes/{note_id}/resolve", response_model=NoteResponse, dependencies=WRITE)
def choose_note(
    note_id: uuid.UUID,
    body: ResolveConflict,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Only the note's author may choose between two wordings."""
    try:
        return resolve_note_conflict(
            session, **_who(current_staff), conflict_id=note_id, **_choice(body)
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.get(
    "/encounters/{encounter_id}/notes", response_model=list[NoteResponse], dependencies=READ
)
def read_notes(
    encounter_id: uuid.UUID,
    current_staff: CurrentStaff,
    include_history: bool = False,
    session: Session = Depends(get_session),
):
    try:
        return list_encounter_notes(
            session,
            **_who(current_staff),
            encounter_id=encounter_id,
            include_history=include_history,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


# Prescriptions: doctors write and change them; nurses and doctors read them.


def _medicine(body: PrescriptionForm | RevisePrescription, **extra) -> PrescriptionDetails:
    return PrescriptionDetails(
        medicine=body.medicine,
        strength=body.strength,
        dose=body.dose,
        route=body.route,
        frequency=body.frequency,
        duration=body.duration,
        instructions=body.instructions,
        **extra,
    )


@router.post(
    "/encounters/{encounter_id}/prescriptions",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=PRESCRIBE,
)
def add_prescription(
    encounter_id: uuid.UUID,
    body: PrescriptionForm,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    try:
        return write_prescription(
            session,
            **_who(current_staff),
            encounter_id=encounter_id,
            details=_medicine(body),
            prescription_id=body.id,
            written_at=body.written_at,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/prescriptions/{prescription_id}/revisions",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=PRESCRIBE,
)
def change_prescription(
    prescription_id: uuid.UUID,
    body: RevisePrescription,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Stop or fix a prescription: a new version. Allowed after sign-off too."""
    try:
        return revise_prescription(
            session,
            **_who(current_staff),
            prescription_id=prescription_id,
            details=_medicine(body, clinical_status=body.clinical_status),
            revision_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.get(
    "/encounters/{encounter_id}/prescriptions",
    response_model=list[PrescriptionResponse],
    dependencies=READ,
)
def read_prescriptions(
    encounter_id: uuid.UUID,
    current_staff: CurrentStaff,
    include_history: bool = False,
    session: Session = Depends(get_session),
):
    try:
        return list_encounter_prescriptions(
            session,
            **_who(current_staff),
            encounter_id=encounter_id,
            include_history=include_history,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/prescriptions/{prescription_id}/resolve",
    response_model=PrescriptionResponse,
    dependencies=PRESCRIBE,
)
def choose_prescription(
    prescription_id: uuid.UUID,
    body: ResolveConflict,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    try:
        return resolve_prescription_conflict(
            session, **_who(current_staff), conflict_id=prescription_id, **_choice(body)
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None
