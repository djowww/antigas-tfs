"""Offline validation for configured autonomous hunting routes."""
import argparse
import json
from pathlib import Path

from .routes import RouteGraph
from .world import Position


def audit_runtime_routes(runtime_path, routes_path, sources):
    """Check that every configured hunting point has an in-and-out static route."""
    config = json.loads(Path(runtime_path).read_text(encoding='utf-8'))
    raw_targets = config.get('hunting_points')
    if not isinstance(raw_targets, list) or not raw_targets:
        raise ValueError('runtime config has no hunting_points')
    if len(raw_targets) > 64:
        raise ValueError('runtime config exceeds the 64 hunting point limit')

    targets = []
    for row in raw_targets:
        if (not isinstance(row, list) or len(row) != 3 or
                any(type(value) is not int for value in row)):
            raise ValueError('each hunting point must be an integer [x, y, z]')
        target = Position(*row)
        if target in targets:
            raise ValueError('duplicate hunting point')
        targets.append(target)

    sources = tuple(sources)
    if not sources:
        raise ValueError('at least one source position is required')
    graph = RouteGraph.load(routes_path)
    routes, unreachable = [], []
    for target in targets:
        def has_route(start, goal):
            return start == goal or graph.next_step(start, goal) is not None

        roundtrip_sources = [source for source in sources
                             if has_route(source, target) and has_route(target, source)]
        outbound_sources = [source for source in sources if has_route(source, target)]
        row = {
            'target': [target.x, target.y, target.z],
            'outbound': bool(outbound_sources),
            'return': bool(roundtrip_sources),
            'source': ([roundtrip_sources[0].x, roundtrip_sources[0].y,
                        roundtrip_sources[0].z] if roundtrip_sources else None),
        }
        routes.append(row)
        if not row['return']:
            unreachable.append(row)

    return {'total': len(targets), 'reachable': len(targets) - len(unreachable),
            'unreachable': unreachable, 'routes': routes}


def _position(value):
    try:
        parts = value.split(',')
        if len(parts) != 3:
            raise ValueError
        return Position(*(int(part) for part in parts))
    except ValueError as exc:
        raise argparse.ArgumentTypeError('source must be x,y,z') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, help='private runtime JSON path')
    parser.add_argument('--routes', required=True, help='static route graph JSON path')
    parser.add_argument('--source', required=True, action='append', type=_position,
                        help='known starting/return position x,y,z; may be repeated')
    args = parser.parse_args(argv)
    result = audit_runtime_routes(args.runtime, args.routes, args.source)
    print(json.dumps(result, separators=(',', ':')))
    return 0 if not result['unreachable'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
