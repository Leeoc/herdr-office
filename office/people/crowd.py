import re
from typing import Iterable, Optional

from office.people.person import BLOCKED, DONE, RESTING_STATUSES, WORKING, Look, Person
from office.people.timing import ticks
from office.people.venue import NAPS, Activity, Game, Point, Venue

MEETING_EVERY, MEETING_LENGTH = ticks(180), ticks(19)
DESK_PRIORITY = {BLOCKED: 0, WORKING: 1, DONE: 2}


class Crowd:
    """Everyone in the office, and the decisions that involve more than one of them."""

    def __init__(self, palette: dict, ticket_pattern: str, nap_after: float, closed: Iterable[str] = ()):
        self.palette = palette
        self.ticket_pattern = re.compile(ticket_pattern)
        self.usual_nap_after = nap_after
        self.closed = set(closed)
        self.people: dict[str, Person] = {}

    @property
    def nap_after(self) -> float:
        return float("inf") if NAPS in self.closed else self.usual_nap_after

    def sync(self, agents: Iterable, venue: Venue, t: int, newcomers: bool) -> None:
        """Bring the crowd in line with the agents herdr reports; `newcomers` marks arrivals as brand new."""
        agents = list(agents)
        present = {a.key for a in agents}
        for person in self.people.values():
            person.leaving = person.key not in present
        for agent in agents:
            person = self.people.get(agent.key) or self.arrive(agent.key, venue, t, newcomers)
            person.update(agent, self.ticket_of(agent.label), t)

    def arrive(self, key: str, venue: Venue, t: int, first_day: bool) -> Person:
        person = Person(key, Look.for_key(key, self.palette), venue.entrance(), t, first_day)
        self.people[key] = person
        return person

    def ticket_of(self, label: str) -> Optional[str]:
        match = self.ticket_pattern.search(label or "")
        return match.group(1).lower() if match else None

    def tick(self, venue: Venue, t: int, now: float) -> None:
        self.assign_desks(venue.desk_count())
        self.schedule_meetings(t)
        self.give_out_beds(now, venue)
        self.schedule_games(venue.games(), t, now)
        for person in list(self.people.values()):
            person.tick(venue, t, lambda activity, asker=person: self.free_spot(activity, asker))
            if person.leaving and person.arrived():
                del self.people[person.key]

    def relocate(self) -> None:
        for person in self.people.values():
            person.forget_places()

    def assign_desks(self, desk_count: int) -> None:
        """Desks go to whoever needs one most; when the room is short, an idle agent gives theirs up to a busy one.

        Within the same need, whoever already has a desk keeps it, so nobody is shuffled about for no reason.
        """
        def need(person: Person) -> tuple:
            settled = person.desk is not None and person.desk < desk_count
            return DESK_PRIORITY.get(person.status, len(DESK_PRIORITY)), not settled, person.key

        seated = {p.key for p in sorted(self.present(), key=need)[:desk_count]}
        for person in self.people.values():
            if person.key not in seated or person.desk is not None and person.desk >= desk_count:
                person.desk = None
        free = [d for d in range(desk_count) if d not in {p.desk for p in self.people.values()}]
        for person in sorted((p for p in self.people.values() if p.key in seated and p.desk is None), key=need):
            person.desk = free.pop(0)

    def schedule_meetings(self, t: int) -> None:
        for person in self.people.values():
            person.meeting = None
        if t % MEETING_EVERY >= MEETING_LENGTH:
            return
        seat = 0
        for group in self.ticket_groups().values():
            if len(group) > 1:
                for person in sorted(group, key=lambda p: p.key):
                    person.meeting, seat = seat, seat + 1

    def ticket_groups(self) -> dict[str, list[Person]]:
        groups: dict[str, list[Person]] = {}
        for person in self.present():
            if person.ticket and person.status == WORKING:
                groups.setdefault(person.ticket, []).append(person)
        return groups

    def schedule_games(self, games: tuple[Game, ...], t: int, now: float) -> None:
        """Idle people who are awake take turns at each open game; the line-up rotates every round."""
        for person in self.people.values():
            person.game = None
        playing: set[str] = set()
        for game in games:
            every = ticks(game.every_seconds)
            if game.name in self.closed or t % every >= ticks(game.length_seconds):
                continue
            free = [p for p in self.idle_and_awake() if p.key not in playing]
            if len(free) < len(game.spots):
                continue
            first = (t // every * len(game.spots)) % len(free)
            for place in range(len(game.spots)):
                player = free[(first + place) % len(free)]
                player.game = (game, place)
                playing.add(player.key)

    def idle_and_awake(self) -> list[Person]:
        return sorted((p for p in self.present()
                       if p.status in RESTING_STATUSES and p.nap_index is None and p.meeting is None),
                      key=lambda p: p.key)

    def give_out_beds(self, now: float, venue: Venue) -> None:
        """Nappers keep their bed; free beds go to whoever has been idle longest, and the rest stay up."""
        beds = len(venue.nap_spots())
        sleepy = sorted((p for p in self.present() if p.sleepy(now, self.nap_after)), key=lambda p: (p.since, p.key))
        sleepy_keys = {p.key for p in sleepy}
        for person in self.people.values():
            if person.key not in sleepy_keys or person.nap_index is not None and person.nap_index >= beds:
                person.nap_index = None
        free = [bed for bed in range(beds) if bed not in {p.nap_index for p in sleepy}]
        for person in sleepy:
            if person.nap_index is None and free:
                person.nap_index = free.pop(0)

    def free_spot(self, activity: Activity, asker: Person) -> Optional[Point]:
        if activity.name in self.closed:
            return None
        taken = {p.leisure_spot for p in self.people.values()
                 if p is not asker and p.activity is not None and p.activity.name == activity.name}
        return next((spot for spot in activity.spots if spot not in taken), None)

    def present(self) -> list[Person]:
        return [p for p in self.people.values() if not p.leaving]

    def anyone_moving(self) -> bool:
        return any(p.moving() for p in self.people.values())

    def alarm(self) -> bool:
        return any(p.status == BLOCKED for p in self.present())

    def counts(self) -> dict[str, int]:
        tally = {BLOCKED: 0, WORKING: 0, DONE: 0, "idle": 0}
        for person in self.people.values():
            tally[person.status if person.status in tally else "idle"] += 1
        return tally
