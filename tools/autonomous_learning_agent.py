"""Entry point for the optional, removable autonomous learner."""
import argparse
from .autonomous_players.learning_bridge import serve


def main(argv=None):
    parser = argparse.ArgumentParser(description='local autonomous learning companion')
    parser.add_argument('--socket', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--status')
    parser.add_argument('--shadow', action='store_true')
    parser.add_argument('--neural-mode', choices=('off','shadow','active'), default='off')
    parser.add_argument('--neural-agent', action='append', help='limit neural decisions to a named canary; repeatable')
    args = parser.parse_args(argv)
    try:
        serve(args.socket, args.state, args.shadow, args.status, args.neural_mode,
              neural_agents=args.neural_agent)
    except KeyboardInterrupt:
        # systemd uses SIGINT so serve's finally persists the latest model.
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
