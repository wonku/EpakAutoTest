# -*- coding: utf-8 -*-
"""Calculate N working days before a date using China statutory calendar."""
from datetime import date, timedelta

HOLIDAYS = set()
WORKDAYS = set()  # makeup workdays on weekends


def add_range(start, end):
    d = start
    while d <= end:
        HOLIDAYS.add(d)
        d += timedelta(days=1)


# === 2025 (State Council notice) ===
add_range(date(2025, 1, 1), date(2025, 1, 1))       # New Year
add_range(date(2025, 1, 28), date(2025, 2, 4))      # Spring Festival
add_range(date(2025, 4, 4), date(2025, 4, 6))       # Qingming
add_range(date(2025, 5, 1), date(2025, 5, 5))       # Labour Day
add_range(date(2025, 5, 31), date(2025, 6, 2))      # Dragon Boat
add_range(date(2025, 10, 1), date(2025, 10, 8))     # National + Mid-Autumn

for d in [
    date(2025, 1, 26), date(2025, 2, 8), date(2025, 4, 27),
    date(2025, 9, 28), date(2025, 10, 11),
]:
    WORKDAYS.add(d)

# === 2026 (State Council notice) ===
add_range(date(2026, 1, 1), date(2026, 1, 3))       # New Year
add_range(date(2026, 2, 15), date(2026, 2, 23))     # Spring Festival
add_range(date(2026, 4, 4), date(2026, 4, 6))       # Qingming
add_range(date(2026, 5, 1), date(2026, 5, 5))       # Labour Day
add_range(date(2026, 6, 19), date(2026, 6, 21))     # Dragon Boat
add_range(date(2026, 9, 25), date(2026, 9, 27))     # Mid-Autumn
add_range(date(2026, 10, 1), date(2026, 10, 7))     # National Day

for d in [
    date(2026, 1, 4), date(2026, 2, 14), date(2026, 2, 28),
    date(2026, 5, 9), date(2026, 9, 20), date(2026, 10, 10),
]:
    WORKDAYS.add(d)

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def is_workday(d):
    if d in WORKDAYS:
        return True
    if d in HOLIDAYS:
        return False
    return d.weekday() < 5


def workdays_before(end_date, n, inclusive_end=True):
    """Return start date such that [start, end] contains n workdays."""
    count = 0
    d = end_date
    days = []
    while count < n:
        if is_workday(d):
            count += 1
            days.append(d)
        if count < n:
            d -= timedelta(days=1)
    return days[-1], days


if __name__ == "__main__":
    end = date(2026, 7, 10)
    n = 101

    # Inclusive: Jul 10 is the 101st workday counting back
    result, workdays_list = workdays_before(end, n)

    print(f"End date: {end} ({WEEKDAY_CN[end.weekday()]})")
    print(f"Is workday: {is_workday(end)}")
    print()
    print(f"Start date (101 workdays inclusive): {result} ({WEEKDAY_CN[result.weekday()]})")
    print(f"Calendar span: {(end - result).days + 1} days")
    print(f"Workdays in range: {len(workdays_list)}")
    print()
    print("First 5 workdays in range:")
    for x in workdays_list[-5:][::-1]:
        tag = ""
        if x in HOLIDAYS:
            tag = " [holiday override?]"
        elif x in WORKDAYS:
            tag = " [makeup workday]"
        print(f"  {x} {WEEKDAY_CN[x.weekday()]}{tag}")
    print("  ...")
    print("Last 5 workdays in range:")
    for x in workdays_list[:5]:
        print(f"  {x} {WEEKDAY_CN[x.weekday()]}")

    # Also show exclusive interpretation
    if is_workday(end):
        result_excl, _ = workdays_before(end - timedelta(days=1), n)
        print()
        print(f"Alternative (101 workdays BEFORE today, exclusive): {result_excl} ({WEEKDAY_CN[result_excl.weekday()]})")
