# 1. Row 1: Two weeks ago Monday -> Sunday (7 days)
    # 2. Row 2: Last week Monday -> Sunday (7 days)
    # 3. Row 3: Current week Monday -> Today (1 to 7 days)
    current_week_monday = today - timedelta(days=today.weekday())
    two_weeks_ago_monday = current_week_monday - timedelta(days=14)

    # Total days to render = 14 days (previous two full weeks) + (days passed this week + 1 for today)
    days_to_show = 14 + (today.weekday() + 1)

    matrix = []
    for i in range(days_to_show):
        day = two_weeks_ago_monday + timedelta(days=i)
        matrix.append({
            "date": day.isoformat(),
            "active": (day in active_dates),
            "isToday": (day == today)
        })
