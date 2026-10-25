"""The daily takings: one Lagos day's money, and what needs a second look (Week 10 Step 6).

Money in: payments received that day, by method and by the person who took them.
Money out: refunds approved that day, by method. Net per method: for cash, what should
be in the drawer at closing.

Things to look at (the brief asks reporting to surface unusual refunds):
- invoices paid beyond their total and not yet given back (overpaid);
- refunds still waiting for an admin;
- online payments that failed that day (declined, or the gateway's amount did not match);
- unusual refunds asked for that day: the whole payment back; asked by the same person
  who took the payment; or one person asking for many refunds in a day.

The export is the day's payments and refunds, one per line, with numbers and amounts
but no patient names, so it can go to an accountant.
"""
import csv
import io
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.billing.models import (
    Invoice,
    InvoiceStatus,
    OnlinePayment,
    OnlinePaymentStatus,
    Payment,
    Refund,
    RefundStatus,
)
from app.modules.billing.money import naira
from app.modules.identity.service import list_staff
from app.modules.scheduling.board import CLINIC_TIME, day_bounds

# One person asking for more refunds than this in a day is worth a look.
MANY_REFUNDS_A_DAY = 3
UNKNOWN = "(name not found)"


@dataclass(frozen=True)
class MethodTotal:
    method: str
    count: int
    amount_kobo: int


@dataclass(frozen=True)
class StaffTotal:
    staff_id: uuid.UUID
    name: str
    payments: int
    taken_kobo: int


@dataclass(frozen=True)
class Flag:
    kind: str  # overpaid, refund_waiting, online_failed, whole_refund, own_refund, many_refunds
    message: str
    invoice_number: str | None = None
    amount_kobo: int | None = None


@dataclass(frozen=True)
class Takings:
    day: date
    money_in: list[MethodTotal]
    money_out: list[MethodTotal]
    net_by_method: list[MethodTotal]
    by_staff: list[StaffTotal]
    invoices_issued: int
    billed_kobo: int
    flags: list[Flag] = field(default_factory=list)

    @property
    def total_in_kobo(self) -> int:
        return sum(row.amount_kobo for row in self.money_in)

    @property
    def total_out_kobo(self) -> int:
        return sum(row.amount_kobo for row in self.money_out)

    @property
    def net_kobo(self) -> int:
        return self.total_in_kobo - self.total_out_kobo


def _by_method(rows: list[Payment] | list[Refund]) -> dict[str, MethodTotal]:
    counts: dict[str, int] = defaultdict(int)
    amounts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row.method] += 1
        amounts[row.method] += row.amount_kobo
    return {m: MethodTotal(m, counts[m], amounts[m]) for m in sorted(counts)}


def _day_rows(session: Session, *, tenant_id: uuid.UUID, day: date):
    start, end = day_bounds(day)
    payments = list(
        session.exec(
            tenant_select(Payment, tenant_id)
            .where(col(Payment.received_at) >= start)
            .where(col(Payment.received_at) < end)
            .order_by(col(Payment.received_at), col(Payment.receipt_number))
        ).all()
    )
    refunds = list(
        session.exec(
            tenant_select(Refund, tenant_id)
            .where(col(Refund.status) == RefundStatus.APPROVED.value)
            .where(col(Refund.decided_at) >= start)
            .where(col(Refund.decided_at) < end)
            .order_by(col(Refund.decided_at), col(Refund.refund_number))
        ).all()
    )
    return payments, refunds


def _invoice_numbers(
    session: Session, *, tenant_id: uuid.UUID, invoice_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not invoice_ids:
        return {}
    rows = session.exec(
        tenant_select(Invoice, tenant_id).where(col(Invoice.id).in_(invoice_ids))
    ).all()
    return {row.id: row.number or "" for row in rows}


def _overpaid(session: Session, *, tenant_id: uuid.UUID) -> list[Flag]:
    """Issued invoices whose payments, less approved refunds, exceed their total."""
    paid = (
        select(Payment.invoice_id, func.sum(Payment.amount_kobo).label("paid"))
        .where(col(Payment.tenant_id) == tenant_id)
        .group_by(col(Payment.invoice_id))
        .subquery()
    )
    refunded = (
        select(Refund.invoice_id, func.sum(Refund.amount_kobo).label("refunded"))
        .where(col(Refund.tenant_id) == tenant_id)
        .where(col(Refund.status) == RefundStatus.APPROVED.value)
        .group_by(col(Refund.invoice_id))
        .subquery()
    )
    credit = paid.c.paid - func.coalesce(refunded.c.refunded, 0) - col(Invoice.total_kobo)
    statement = (
        select(Invoice.number, credit.label("credit"))
        .join(paid, paid.c.invoice_id == col(Invoice.id))
        .outerjoin(refunded, refunded.c.invoice_id == col(Invoice.id))
        .where(col(Invoice.tenant_id) == tenant_id)
        .where(col(Invoice.status) == InvoiceStatus.ISSUED.value)
        .where(credit > 0)
        .order_by(col(Invoice.number))
    )
    return [
        Flag(
            "overpaid",
            f"{number} was paid {naira(int(amount))} more than its total; give it back.",
            invoice_number=number,
            amount_kobo=int(amount),
        )
        for number, amount in session.exec(statement).all()
    ]


def _flags(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    day: date,
    names: dict[uuid.UUID, str],
) -> list[Flag]:
    start, end = day_bounds(day)
    flags = _overpaid(session, tenant_id=tenant_id)

    waiting = session.exec(
        tenant_select(Refund, tenant_id).where(col(Refund.status) == RefundStatus.REQUESTED.value)
    ).all()
    if waiting:
        total = sum(refund.amount_kobo for refund in waiting)
        flags.append(
            Flag(
                "refund_waiting",
                f"{len(waiting)} refund(s) for {naira(total)} are waiting for an admin.",
                amount_kobo=total,
            )
        )

    failed = session.exec(
        tenant_select(OnlinePayment, tenant_id)
        .where(col(OnlinePayment.status) == OnlinePaymentStatus.FAILED.value)
        .where(col(OnlinePayment.completed_at) >= start)
        .where(col(OnlinePayment.completed_at) < end)
    ).all()
    asked_today = list(
        session.exec(
            tenant_select(Refund, tenant_id)
            .where(col(Refund.requested_at) >= start)
            .where(col(Refund.requested_at) < end)
            .order_by(col(Refund.requested_at))
        ).all()
    )
    numbers = _invoice_numbers(
        session,
        tenant_id=tenant_id,
        invoice_ids={row.invoice_id for row in failed} | {r.invoice_id for r in asked_today},
    )
    for row in failed:
        flags.append(
            Flag(
                "online_failed",
                f"An online payment of {naira(row.amount_kobo)} failed: {row.failure_reason}",
                invoice_number=numbers.get(row.invoice_id),
                amount_kobo=row.amount_kobo,
            )
        )

    payments: dict[uuid.UUID, Payment] = {}
    payment_ids = {refund.payment_id for refund in asked_today}
    if payment_ids:
        statement = tenant_select(Payment, tenant_id).where(col(Payment.id).in_(payment_ids))
        payments = {p.id: p for p in session.exec(statement).all()}
    per_person: dict[uuid.UUID, int] = defaultdict(int)
    for refund in asked_today:
        per_person[refund.requested_by_id] += 1
        payment = payments.get(refund.payment_id)
        number = numbers.get(refund.invoice_id)
        asker = names.get(refund.requested_by_id, UNKNOWN)
        if payment is not None and refund.amount_kobo == payment.amount_kobo:
            flags.append(
                Flag(
                    "whole_refund",
                    f"{asker} asked for the whole {naira(refund.amount_kobo)} back "
                    f"({refund.status}).",
                    invoice_number=number,
                    amount_kobo=refund.amount_kobo,
                )
            )
        if payment is not None and payment.received_by_id == refund.requested_by_id:
            flags.append(
                Flag(
                    "own_refund",
                    f"{asker} asked to refund a payment they took themselves "
                    f"({naira(refund.amount_kobo)}, {refund.status}).",
                    invoice_number=number,
                    amount_kobo=refund.amount_kobo,
                )
            )
    for person, count in sorted(per_person.items(), key=lambda item: -item[1]):
        if count > MANY_REFUNDS_A_DAY:
            flags.append(
                Flag(
                    "many_refunds",
                    f"{names.get(person, UNKNOWN)} asked for {count} refunds on {day:%d %b}.",
                )
            )
    return flags


def daily_takings(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, day: date
) -> Takings:
    """One Lagos day's money and the things to look at. Written in the diary."""
    names = {staff.id: staff.full_name for staff in list_staff(session, tenant_id=tenant_id)}
    payments, refunds = _day_rows(session, tenant_id=tenant_id, day=day)
    money_in = _by_method(payments)
    money_out = _by_method(refunds)
    net = [
        MethodTotal(
            method,
            money_in.get(method, MethodTotal(method, 0, 0)).count
            + money_out.get(method, MethodTotal(method, 0, 0)).count,
            money_in.get(method, MethodTotal(method, 0, 0)).amount_kobo
            - money_out.get(method, MethodTotal(method, 0, 0)).amount_kobo,
        )
        for method in sorted(set(money_in) | set(money_out))
    ]

    taken: dict[uuid.UUID, list[Payment]] = defaultdict(list)
    for payment in payments:
        taken[payment.received_by_id].append(payment)
    by_staff = sorted(
        (
            StaffTotal(
                staff_id,
                names.get(staff_id, UNKNOWN),
                len(rows),
                sum(row.amount_kobo for row in rows),
            )
            for staff_id, rows in taken.items()
        ),
        key=lambda row: (-row.taken_kobo, row.name),
    )

    start, end = day_bounds(day)
    issued = session.exec(
        tenant_select(Invoice, tenant_id)
        .where(col(Invoice.status) == InvoiceStatus.ISSUED.value)
        .where(col(Invoice.issued_at) >= start)
        .where(col(Invoice.issued_at) < end)
    ).all()

    result = Takings(
        day=day,
        money_in=list(money_in.values()),
        money_out=list(money_out.values()),
        net_by_method=net,
        by_staff=by_staff,
        invoices_issued=len(issued),
        billed_kobo=sum(invoice.total_kobo for invoice in issued),
        flags=_flags(session, tenant_id=tenant_id, day=day, names=names),
    )
    add_audit_event(
        session, tenant_id=tenant_id, actor_id=actor_id, action=AuditAction.TAKINGS_VIEW
    )
    session.commit()
    return result


def _clock(moment: datetime) -> str:
    return moment.astimezone(CLINIC_TIME).strftime("%H:%M")


def takings_csv(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, day: date
) -> tuple[str, str]:
    """The day's payments and refunds as CSV, for an accountant. No patient names.
    Answers (file name, CSV text). Written in the diary."""
    names = {staff.id: staff.full_name for staff in list_staff(session, tenant_id=tenant_id)}
    payments, refunds = _day_rows(session, tenant_id=tenant_id, day=day)
    numbers = _invoice_numbers(
        session,
        tenant_id=tenant_id,
        invoice_ids={p.invoice_id for p in payments} | {r.invoice_id for r in refunds},
    )
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["time", "kind", "number", "invoice", "method", "amount_naira", "staff", "reference"]
    )
    for p in payments:
        writer.writerow(
            [
                _clock(p.received_at),
                "payment",
                p.receipt_number,
                numbers.get(p.invoice_id, ""),
                p.method,
                f"{p.amount_kobo / 100:.2f}",
                names.get(p.received_by_id, UNKNOWN),
                p.reference or "",
            ]
        )
    for r in refunds:
        writer.writerow(
            [
                _clock(r.decided_at) if r.decided_at else "",
                "refund",
                r.refund_number or "",
                numbers.get(r.invoice_id, ""),
                r.method,
                f"{-r.amount_kobo / 100:.2f}",
                names.get(r.decided_by_id, UNKNOWN) if r.decided_by_id else "",
                "",
            ]
        )
    add_audit_event(
        session, tenant_id=tenant_id, actor_id=actor_id, action=AuditAction.TAKINGS_EXPORT
    )
    session.commit()
    return f"takings-{day.isoformat()}.csv", out.getvalue()
