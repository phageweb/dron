"""Which agents the coordinator may plan with, and which it must leave alone.

Two mechanisms from `spec/roj/04_rozhrani.md`, and they answer different
questions. Staleness answers "is what I know about this agent recent enough to
plan with": a state older than the age limit is not a position, it is a guess
about where something was. The mission epoch answers "is this agent still in
the same mission I am": after a coordinator restart the machines may still be
carrying commands from a previous life, and without an epoch the only way that
shows up is in the map.

Neither is a watchdog for the agent itself. `GUID_TIMEOUT` is - it lives on the
autopilot and stops the vehicle when commands stop arriving, which is the
guarantee G3 that makes the rest of this safe to get wrong.
"""

from typing import Dict, Iterable, List, Optional, Tuple


class SwarmState:
    """Last known state per agent, with the epoch each was reported under."""

    def __init__(self, epoch: int = 0, max_age_s: float = 0.2):
        self.epoch = epoch
        self.max_age_s = max_age_s
        self._seen: Dict[str, Tuple[float, int, object]] = {}

    def update(self, name: str, when_s: float, payload: object,
               epoch: Optional[int] = None) -> bool:
        """Record a state. Returns False if it was rejected, and why matters.

        A message from an older epoch is not merely ignored: accepting one
        would let a machine that missed the restart keep steering the mission
        that replaced it.
        """
        epoch = self.epoch if epoch is None else epoch
        if epoch < self.epoch:
            return False
        if epoch > self.epoch:
            # An agent that has moved on to a newer mission than the
            # coordinator knows about means the coordinator is the stale one.
            raise ValueError(
                f"Agent {name} reported epoch {epoch}, ahead of the "
                f"coordinator's {self.epoch}. Something else is commanding "
                "this swarm.")
        self._seen[name] = (when_s, epoch, payload)
        return True

    def fresh(self, now_s: float) -> Dict[str, object]:
        """The agents whose state is recent enough to plan with."""
        return {name: payload
                for name, (when, _, payload) in self._seen.items()
                if now_s - when <= self.max_age_s}

    def stale(self, now_s: float) -> List[str]:
        """The agents whose state is too old, in the order they went quiet."""
        overdue = [(when, name)
                   for name, (when, _, _) in self._seen.items()
                   if now_s - when > self.max_age_s]
        return [name for _, name in sorted(overdue)]

    def age(self, name: str, now_s: float) -> Optional[float]:
        entry = self._seen.get(name)
        return None if entry is None else now_s - entry[0]

    def start_new_epoch(self) -> int:
        """Begin a new mission. Everything from the old one stops counting."""
        self.epoch += 1
        self._seen.clear()
        return self.epoch


def widen_for_stale(
    d_safe_m: float,
    stale_names: Iterable[str],
    agent_names: Iterable[str],
    widen_by_m: float,
) -> Dict[str, float]:
    """A bigger bubble around an agent nobody has heard from lately.

    `spec/roj/03_vrstva_roje.md` section 5: an agent whose state has gone stale
    keeps flying - its own failsafe decides what it does - so the rest of the
    swarm has to assume it is somewhere other than where it was last seen. The
    separation to it grows; the separation between the healthy ones does not.
    """
    stale = set(stale_names)
    return {name: d_safe_m + (widen_by_m if name in stale else 0.0)
            for name in agent_names}
