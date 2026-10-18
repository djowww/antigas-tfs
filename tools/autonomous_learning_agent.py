"""Entry point for the optional, removable autonomous learner."""
import argparse
from .autonomous_players.learning_bridge import serve


def main(argv=None):
    parser = argparse.ArgumentParser(description='local autonomous learning companion')
    parser.add_argument('--socket', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--shadow', action='store_true')
    args = parser.parse_args(argv)
    serve(args.socket, args.state, args.shadow)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
