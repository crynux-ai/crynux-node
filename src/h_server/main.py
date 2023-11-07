import argparse

from h_server.run import run
from h_server.stop import stop


def main():
    parser = argparse.ArgumentParser(description="Crynux node")

    subparsers = parser.add_subparsers(help="Commands", dest="cmd")
    subparsers.add_parser("run", help="Start crynux node")
    subparsers.add_parser(
        "stop",
        help="Stop crynux node. Useful when node hasn't stop correctly in headless mode.",
    )

    args = parser.parse_args()
    if args.cmd == "run":
        run()
    if args.cmd == "stop":
        stop()


if __name__ == "__main__":
    main()
