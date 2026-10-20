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
    TIERS = (0, 1, 5, 10, 20)
    ADMISSION_MEMORY_MIB = 1024

    @classmethod
    def from_preflight(cls,samples,current):
        """First installation only: a complete recent independent baseline.

        The <=120s handoff is checked with a new current healthy observation.
        This never restores existing state or clears a suspension/restart latch.
        All subsequent tier/recovery coverage still requires <=15s sample gaps.
        """
        if len(samples)<61 or not 0<=current.now-samples[-1].now<=120:
            raise ValueError('preflight coverage missing or stale')
        guard=cls()
        for sample in samples:
            decision=guard.observe(sample)
            if decision.suspended or sample.memory_mib<cls.ADMISSION_MEMORY_MIB or sample.cpu_percent>85:
                raise ValueError('preflight not continuously healthy')
        check=cls()
        decision=check.observe(current)
        if (decision.suspended or current.memory_mib<cls.ADMISSION_MEMORY_MIB or current.cpu_percent>85 or
            current.latency_ms>250 or current.server_pid!=guard.state['pid'] or guard.state['target']!=1):
            raise ValueError('current preflight handoff unhealthy')
        guard.state.update(last=current.now,tier_at=current.now,healthy_at=current.now,
                           reason='recent independent preflight verified')
        return guard

    def __init__(self, state=None, *, immediate_target=None):
        if immediate_target is not None and (type(immediate_target) is not int or immediate_target not in (10,20)):
            raise ValueError('direct admission requires explicit target ten or twenty')
        self.immediate_target = immediate_target
        self.state = dict(state) if state else dict(target=0, suspended=False, reason='baseline',
            started=None, tier_at=None, healthy_at=None, pid=None, last=None,
            violations={}, recoveries=[], baseline=[])
        if state:
            required = {'target','suspended','started','tier_at','healthy_at','pid','last','violations','recoveries','baseline','reason'}
            if not required.issubset(state) or state['target'] not in self.TIERS:
                raise ValueError('invalid supervisor checkpoint')
            reason='controller restart verification'
            if immediate_target and state['suspended'] and state['reason'] not in ('cpu',reason):
                reason=state['reason']
            self.state.update(target=0,suspended=True,healthy_at=None,reason=reason)
            if immediate_target and reason == 'controller restart verification':
                # A new process establishes its cadence from a fresh lease;
                # graceful combat logout can exceed the in-process 15s limit.
                self.state['last'] = None

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
        if (not 0 <= sample.cpu_percent <= 100 or sample.sql_age_seconds < 0 or
            sample.dispatcher_queued < 0 or sample.now < 0 or sample.measured_at < 0 or
            not isinstance(sample.server_pid,int)):
            self._suspend('invalid metrics')
            return Decision(0,True,s['reason'])
        if s['last'] is not None and t < s['last']:
            self._suspend('clock regression')
        if s['last'] is not None and t-s['last'] > 15:
            self._suspend('observation gap')
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
        delayed = dict(memory=(sample.memory_mib < 768, 15), cpu=(sample.cpu_percent > 85 and not self.immediate_target, 60),
                       latency=(sample.latency_ms > max(250, 3*p95), 60),
                       dispatcher=(sample.dispatcher_queued > 200, 5))
        for name, (bad, duration) in delayed.items():
            if bad:
                since = s['violations'].setdefault(name, t)
                if t - since >= duration:
                    self._suspend(name)
            else:
                s['violations'].pop(name, None)
        required_memory = self.ADMISSION_MEMORY_MIB if s['suspended'] or s['target'] == 0 else 768
        healthy = (sample.memory_mib >= required_memory and (sample.cpu_percent <= 85 or self.immediate_target is not None) and
                   sample.latency_ms <= max(250, 3*p95) and sample.dispatcher_queued <= 200)
        # Operator-authorized direct admission skips CPU/tier waiting, never a
        # non-CPU suspension, stale observation or any critical check above.
        if self.immediate_target and healthy and sample.memory_mib >= self.ADMISSION_MEMORY_MIB and (not s['suspended'] or
                s['reason'] in ('cpu','controller restart verification')):
            s.update(target=self.immediate_target,suspended=False,reason=f'operator direct {self.immediate_target}',tier_at=t)
            return Decision(s['target'],False,s['reason'])
        if not healthy:
            s['healthy_at'] = None
        elif s['healthy_at'] is None:
            s['healthy_at'] = t
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
            wait = 300 if s['target'] == 0 else 600
            if t-max(s['tier_at'],s['healthy_at']) >= wait and (s['target'] == 0 or functional):
                index = self.TIERS.index(s['target'])
                s.update(target=self.TIERS[min(index+1, len(self.TIERS)-1)], tier_at=t, reason='healthy tier')
        return Decision(s['target'], s['suspended'], s['reason'])
