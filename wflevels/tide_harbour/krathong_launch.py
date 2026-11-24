"""Reference scheduler for krathongs launched gradually from the riverbank.

The level director must implement the same transitions with persistent cells.
Positions are normalized along the river; actors are reused only after exit.
"""
from dataclasses import dataclass, field


@dataclass
class Launches:
    capacity: int
    interval: float = 1.2
    journey: float = 180.0
    elapsed: float = 0.0
    ages: list = field(default_factory=list)
    was_enabled: bool = False

    def step(self, seconds: float, enabled: bool, count: int) -> tuple:
        if seconds < 0:
            raise ValueError('elapsed time must be nonnegative')
        count = max(0, min(self.capacity, count))
        if not enabled or count == 0:
            self.ages.clear()
            self.elapsed = 0.0
            self.was_enabled = False
            return ()
        # Begin a fresh sequence with an empty river after enabling.
        if not self.was_enabled:
            self.was_enabled = True
            self.elapsed = 0.0
        # Process events in order, including departures between launches.
        remaining = seconds
        while remaining > 0:
            until_launch = max(0.0, self.interval - self.elapsed)
            dt = min(remaining, until_launch)
            self.ages = [age + dt for age in self.ages if age + dt < self.journey]
            self.elapsed += dt
            remaining -= dt
            if self.elapsed >= self.interval:
                self.elapsed = 0.0
                if len(self.ages) < count:
                    self.ages.append(0.0)
        return tuple(age / self.journey for age in self.ages)
