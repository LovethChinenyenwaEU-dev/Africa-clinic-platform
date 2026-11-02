import argparse
import getpass
import sys
from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from app.core.db import engine
from app.demo_data import DemoNotAllowedError, reset_demo_passwords, seed_demo
from app.modules.identity.service import EmailAlreadyUsedError
from app.modules.outreach.service import interest_csv
from app.provisioning import provision_clinic


def _create_clinic(args: argparse.Namespace) -> int:
    password = getpass.getpass("Admin password (typing is hidden): ")
    again = getpass.getpass("Type it again: ")
    if password != again:
        print("The two passwords did not match. Nothing was created.")
        return 1

    try:
        with Session(engine) as session:
            tenant, admin = provision_clinic(
                session,
                clinic_name=args.clinic_name,
                admin_name=args.admin_name,
                admin_email=args.admin_email,
                admin_password=password,
            )
    except (ValueError, EmailAlreadyUsedError) as error:
        print(f"Could not create the clinic: {error}")
        return 1

    print(f"Created clinic '{tenant.name}' (id {tenant.id}).")
    print(f"First admin: {admin.email}")
    return 0


def _seed_demo(args: argparse.Namespace) -> int:
    print("Creates a demo clinic with clearly fake people. Development machines only.")
    password = getpass.getpass("Password for every demo login (typing is hidden): ")
    again = getpass.getpass("Type it again: ")
    if password != again:
        print("The two passwords did not match. Nothing was created.")
        return 1

    try:
        with Session(engine) as session:
            logins = seed_demo(session, password=password)
    except (ValueError, EmailAlreadyUsedError, DemoNotAllowedError) as error:
        print(f"Could not create the demo data: {error}")
        return 1

    print("Demo clinic created. Sign in with any of these (same password for all):")
    for login in logins:
        print(f"  {login.role:<11} {login.email}")
    return 0


def _reset_demo_passwords(args: argparse.Namespace) -> int:
    print("Sets a new password for the demo logins only. Development machines only.")
    password = getpass.getpass("New password for every demo login (typing is hidden): ")
    again = getpass.getpass("Type it again: ")
    if password != again:
        print("The two passwords did not match. Nothing was changed.")
        return 1

    try:
        with Session(engine) as session:
            changed = reset_demo_passwords(session, password=password)
    except (ValueError, DemoNotAllowedError) as error:
        print(f"Could not reset the passwords: {error}")
        return 1

    if changed == 0:
        print("No demo logins found. Run seed-demo first.")
        return 1
    print(f"New password set for {changed} demo logins.")
    return 0


def _list_interest(args: argparse.Namespace) -> int:
    """The landing page's Register interest requests, as CSV on the screen. They hold
    people's contact details: do not save the output anywhere shared."""
    since = datetime.now(UTC) - timedelta(days=args.days)
    with Session(engine) as session:
        print(interest_csv(session, since=since), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="Clinic Platform admin tools")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-clinic", help="Create a clinic and its first admin")
    create.add_argument("--clinic-name", required=True)
    create.add_argument("--admin-name", required=True)
    create.add_argument("--admin-email", required=True)

    interest = commands.add_parser(
        "list-interest", help="Register interest requests from the landing page, as CSV"
    )
    interest.add_argument("--days", type=int, default=30, help="How far back (default 30)")

    commands.add_parser("seed-demo", help="Development only: a demo clinic with fake people")
    commands.add_parser(
        "reset-demo-passwords", help="Development only: a new password for the demo logins"
    )

    args = parser.parse_args(argv)
    if args.command == "create-clinic":
        return _create_clinic(args)
    if args.command == "list-interest":
        return _list_interest(args)
    if args.command == "seed-demo":
        return _seed_demo(args)
    if args.command == "reset-demo-passwords":
        return _reset_demo_passwords(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())