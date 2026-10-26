import os
import json
from datetime import datetime, timedelta, timezone
from garminconnect import Garmin

RUN_TYPES = {"running", "trail_running", "treadmill_running"}
WALK_TYPES = {"walking", "hiking"}

def format_duration(seconds):
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"

def format_pace(speed_mps):
    if not speed_mps or speed_mps <= 0:
        return "N/A"
    sec_per_mile = 1609.34 / speed_mps
    p_min = int(sec_per_mile // 60)
    p_sec = int(sec_per_mile % 60)
    return f"{p_min}'{p_sec:02d}\""

def build_category_metrics(activities, today, start_of_week, weekly_target):
    week_distance_meters = 0.0
    active_dates = set()

    for act in activities:
        start_str = act.get("startTimeGMT")
        if not start_str:
            continue
        act_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        act_date = act_dt.date()

        active_dates.add(act_date)

        if act_date >= start_of_week:
            week_distance_meters += act.get("distance", 0.0)

    # 14-day history array (oldest to newest)
    matrix = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        matrix.append({
            "date": day.isoformat(),
            "active": day in active_dates
        })

    # Consecutive streak count
    streak = 0
    check_day = today
    if check_day not in active_dates:
        check_day -= timedelta(days=1)
    while check_day in active_dates:
        streak += 1
        check_day -= timedelta(days=1)

    # Latest activity details
    latest = None
    if activities:
        recent = activities[0]
        dist_m = recent.get("distance", 0.0)
        dist_mi = dist_m / 1609.34
        dur_sec = recent.get("duration", 0.0)
        avg_speed = recent.get("averageSpeed", 0.0)
        avg_hr = recent.get("averageHR", 0)

        start_str = recent.get("startTimeGMT")
        act_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        diff_days = (today - act_dt.date()).days
        if diff_days == 0:
            rel_date = "Today"
        elif diff_days == 1:
            rel_date = "Yesterday"
        else:
            rel_date = f"{diff_days} days ago"

        type_raw = recent.get("activityType", {}).get("typeKey", "")
        clean_type = type_raw.replace("_", " ").title()

        latest = {
            "name": recent.get("activityName", clean_type),
            "type": clean_type,
            "relativeDate": rel_date,
            "distanceMiles": round(dist_mi, 1),
            "pace": format_pace(avg_speed),
            "duration": format_duration(dur_sec),
            "avgHr": int(avg_hr) if avg_hr else "N/A"
        }

    weekly_miles = round(week_distance_meters / 1609.34, 1)
    weekly_pct = min(100, int((weekly_miles / weekly_target) * 100)) if weekly_target > 0 else 0

    return {
        "streakDays": streak,
        "weeklyMiles": weekly_miles,
        "weeklyTarget": weekly_target,
        "weeklyPct": weekly_pct
