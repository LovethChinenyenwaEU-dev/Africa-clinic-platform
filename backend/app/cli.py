import argparse
import getpass
import sys

from sqlmodel import Session

from app.core.db import engine
from app.modules.identity.service import EmailAlreadyUsedError
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="Clinic Platform admin tools")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-clinic", help="Create a clinic and its first admin")
    create.add_argument("--clinic-name", required=True)
    create.add_argument("--admin-name", required=True)
    create.add_argument("--admin-email", required=True)

    args = parser.parse_args(argv)
    if args.command == "create-clinic":
        return _create_clinic(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())