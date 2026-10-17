"""Pure admission control. Persist snapshot after every observation before login.

Times are wall-clock seconds so suspension survives process restarts. Clock
regressions and invalid measurements fail closed rather than resetting timers.
"""
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class HealthSample:
    now: float
    measured_at: float
    memory_mib: float
    cpu_percent: float
    latency_ms: float
    server_pid: int
    sql_age_seconds: float = 0
    dispatcher_queued: int = 0
    counter_anomaly: bool = False
    oom: bool = False


@dataclass(frozen=True)
class Decision:
    target: int
    suspended: bool
    reason: str


class Supervisor:
    TIERS = (0, 1, 5, 10, 25, 50)

    def __init__(self, state=None):
        self.state = dict(state) if state else dict(target=0, suspended=False, reason='baseline',
            started=None, tier_at=None, healthy_at=None, pid=None, last=None,
            violations={}, recoveries=[], baseline=[])

    def snapshot(self):
        import copy
        return copy.deepcopy(self.state)

    def _suspend(self, reason):
        self.state.update(target=0, suspended=True, reason=reason, healthy_at=None)

    def observe(self, sample, functional=False):
        s, t = self.state, sample.now
        values = asdict(sample)
        if any(not math.isfinite(v) for v in values.values() if isinstance(v, (int, float))):
            self._suspend('invalid metrics')
            return Decision(s['target'], s['suspended'], s['reason'])
        if s['last'] is not None and t < s['last']:
            self._suspend('clock regression')
        s['last'] = t
        if s['started'] is None:
            s.update(started=t, tier_at=t, pid=sample.server_pid)
        critical = None
        if t - sample.measured_at > 120 or sample.measured_at > t + 5:
            critical = 'stale metrics'
        elif sample.memory_mib < 384 or sample.memory_mib < 0:
            critical = 'critical memory'
        elif sample.oom:
            critical = 'OOM'
        elif sample.server_pid != s['pid'] or sample.server_pid <= 0:
            critical = 'server restart'
        elif sample.sql_age_seconds > 2:
            critical = 'SQL delay'
        elif sample.latency_ms > 1000 or sample.latency_ms < 0:
            critical = 'critical latency'
        elif sample.counter_anomaly:
            critical = 'queue counter anomaly'
        if critical:
            self._suspend(critical)
            # Observe a new stable identity; recovery still needs five healthy minutes.
            s['pid'] = sample.server_pid
            return Decision(0, True, critical)
        baseline = s['baseline']
        if t - s['started'] < 300 and not s['suspended']:
            baseline.append(sample.latency_ms)
            del baseline[:-60]
        sorted_baseline = sorted(baseline)
        p95 = sorted_baseline[min(len(sorted_baseline)-1, int(len(sorted_baseline)*.95))] if baseline else 50
        delayed = dict(memory=(sample.memory_mib < 512, 30), cpu=(sample.cpu_percent > 85, 60),
                       latency=(sample.latency_ms > max(250, 3*p95), 60),
                       dispatcher=(sample.dispatcher_queued > 200, 5))
        for name, (bad, duration) in delayed.items():
            if bad:
                since = s['violations'].setdefault(name, t)
                if t - since >= duration:
                    self._suspend(name)
            else:
                s['violations'].pop(name, None)
        healthy = (sample.memory_mib >= 768 and sample.cpu_percent <= 85 and
                   sample.latency_ms <= max(250, 3*p95) and sample.dispatcher_queued <= 200)
        s['recoveries'] = [r for r in s['recoveries'] if t-r < 3600]
        if s['suspended']:
            if healthy:
                if s['healthy_at'] is None:
                    s['healthy_at'] = t
                if t-s['healthy_at'] >= 300 and len(s['recoveries']) < 3:
                    s.update(suspended=False, target=1, tier_at=t, reason='recovered', violations={})
                    s['recoveries'].append(t)
            else:
                s['healthy_at'] = None
        elif healthy:
            wait = 300 if s['target'] == 0 else (1200 if s['target'] == 25 else 600)
            if t-s['tier_at'] >= wait and (s['target'] == 0 or functional):
                index = self.TIERS.index(s['target'])
                s.update(target=self.TIERS[min(index+1, len(self.TIERS)-1)], tier_at=t, reason='healthy tier')
        return Decision(s['target'], s['suspended'], s['reason'])
