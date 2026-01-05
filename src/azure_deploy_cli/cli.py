import argparse
import sys

from .aca import aca_cli
from .identity import identity_cli
from .utils.logging import configure_logging, get_logger


def main() -> None:
    """
    Main CLI entry point

    Routes to different tool namespaces:
    - azid: Azure identity management (service principals, credentials, RBAC)
    - azaca: Azure Container Apps management (identity and role setup)
    """
    parser = argparse.ArgumentParser(
        description="Azure Deploy CLI",
        prog="azd",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Namespaces:
  azid      Azure identity management (service principals, credentials, roles)
  azaca       Azure Container Apps management (identity and role setup)
""",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["debug", "info", "warning", "error", "critical", "notset"],
        default="info",
        help="Set the logging level.",
    )

    subparsers = parser.add_subparsers(dest="namespace", help="Tool namespace")

    # Add identity namespace
    identity_cli.add_commands(subparsers)

    # Add ACA namespace
    aca_cli.add_commands(subparsers)

    args = parser.parse_args()

    configure_logging(level=args.log_level)
    logger = get_logger(__name__)

    if not args.namespace:
        parser.print_help()
        sys.exit(1)

    if not hasattr(args, "func"):
        logger.error("No command specified")
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
