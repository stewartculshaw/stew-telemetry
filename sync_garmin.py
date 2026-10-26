import os
import json
from datetime import datetime, timedelta, timezone
from garminconnect import Garmin

RUN_TYPES = {"running", "trail_running", "treadmill_running"}
WALK_TYPES = {"walking", "hiking"}

def format_duration(seconds):
    if not seconds or seconds <= 0:
        return "0:00"
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
        try:
            act_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            act_date = act_dt.date()
        except Exception:
            continue

        active_dates.add(act_date)

        if act_date >= start_of_week:
            week_distance_meters += act.get("distance", 0.0)

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
        rel_date = "Recent"
        if start_str:
            try:
                act_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                diff_days = (today - act_dt.date()).days
                if diff_days == 0:
                    rel_date = "Today"
                elif diff_days == 1:
                    rel_date = "Yesterday"
                else:
                    rel_date = f"{diff_days} days ago"
            except Exception:
                pass

        type_raw = recent.get("activityType", {}).get("typeKey", "")
        clean_type = type_raw.replace("_", " ").title() if type_raw else "Activity"

        latest = {
            "activityId": str(recent.get("activityId", "")),
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
        "weeklyPct": weekly_pct,
        "streakMatrix": matrix,
        "latest": latest
    }

def build_activity_index(activities):
    index = {}
    for act in activities:
        act_id = str(act.get("activityId", ""))
        if not act_id:
            continue

        dist_m = act.get("distance", 0.0)
        dist_mi = dist_m / 1609.34
        dur_sec = act.get("duration", 0.0)
        avg_speed = act.get("averageSpeed", 0.0)
        avg_hr = act.get("averageHR", 0)
        elev_m = act.get("elevationGain", 0.0)
        elev_ft = int(elev_m * 3.28084) if elev_m else 0

        type_raw = act.get("activityType", {}).get("typeKey", "")
        clean_type = type_raw.replace("_", " ").title() if type_raw else "Run"

        start_str = act.get("startTimeGMT", "")
        formatted_date = start_str
        if start_str:
            try:
                dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                formatted_date = dt.strftime("%d %b %Y")
            except Exception:
                pass

        index[act_id] = {
            "id": act_id,
            "name": act.get("activityName", clean_type),
            "type": clean_type,
            "date": formatted_date,
            "distanceMiles": round(dist_mi, 2),
            "pace": format_pace(avg_speed),
            "duration": format_duration(dur_sec),
            "avgHr": int(avg_hr) if avg_hr else "N/A",
            "elevationGainFt": elev_ft
        }
    return index

def main():
    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    token_dir = os.environ.get("GARMIN_TOKEN_DIR", "~/.garminconnect")
    
    run_target = float(os.environ.get("RUN_TARGET_MILES", 15.0))
    walk_target = float(os.environ.get("WALK_TARGET_MILES", 20.0))

    if not email or not password:
        raise ValueError("Missing GARMIN_EMAIL or GARMIN_PASSWORD environment variables.")

    garmin = Garmin(email, password)
    try:
        garmin.login(token_dir)
    except Exception:
        garmin.login()

    activities = garmin.get_activities(0, 50)

    # Filter into the two distinct buckets
    runs = [
        act for act in activities 
        if act.get("activityType", {}).get("typeKey", "").lower() in RUN_TYPES
    ]
    walks = [
        act for act in activities 
        if act.get("activityType", {}).get("typeKey", "").lower() in WALK_TYPES
    ]

    now = datetime.now(timezone.utc)
    today = now.date()
    start_of_week = today - timedelta(days=today.weekday())

    output_path = os.environ.get("OUTPUT_PATH", "garmin-stats.json")

    # Load existing archive so older blog-linked workouts persist
    archived_activities = {}
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_payload = json.load(f)
                archived_activities = existing_payload.get("activities", {})
        except Exception:
            archived_activities = {}

    # Merge newly fetched activities into the permanent index
    fresh_activities = build_activity_index(activities)
    archived_activities.update(fresh_activities)

    stats_payload = {
        "runs": build_category_metrics(runs, today, start_of_week, run_target),
        "walks": build_category_metrics(walks, today, start_of_week, walk_target),
        "activities": archived_activities,
        "lastSynced": now.isoformat()
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stats_payload, f, indent=2)

    print(f"Stats and {len(archived_activities)} activities written to {output_path} successfully.")

if __name__ == "__main__":
    main()
