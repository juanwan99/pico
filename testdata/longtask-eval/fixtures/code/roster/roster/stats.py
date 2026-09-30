"""Score statistics. ``None`` means the student was absent."""


def mean(scores):
    """Mean of the present scores; ``None`` when nobody is present."""
    present = [s for s in scores if s is not None]
    return sum(present) / len(present)


def median(scores):
    """Median of the present scores; ``None`` when nobody is present."""
    present = sorted(s for s in scores if s is not None)
    if not present:
        return None
    mid = len(present) // 2
    return present[mid]


def group_means(students):
    """``{group: mean rounded to 1 decimal}``; a group with nobody present maps to ``None``."""
    by_group = {}
    for st in students:
        by_group.setdefault(st["group"], []).append(st["score"])
    return {g: round(mean(v), 1) for g, v in sorted(by_group.items())}
