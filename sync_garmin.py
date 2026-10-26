import os
import json
from datetime import datetime, timedelta, timezone
from garminconnect import Garmin

def format_duration(seconds):
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"

def format_pace(speed_mps):
    if not speed_mps or speed_mps <= 0:
        return "N/A"
    # Convert m/s to min/mile (1 mile = 1609.34 m)
    sec_per_mile = 1609.34 / speed_mps
    p_min = int(sec_per_mile // 60)
    p_sec = int(sec_per_mile % 60)
    return f"{p_min}'{p_sec:02d}\""

def main():
    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    token_dir = os.environ.get("GARMIN_TOKEN_DIR", "~/.garminconnect")
    
    weekly_target = float(os.environ.get("WEEKLY_TARGET_MILES", 15.0))

    if not email or not password:
        raise ValueError("Missing GARMIN_EMAIL or GARMIN_PASSWORD environment variables.")

    # 1. Authenticate with Garmin
    garmin = Garmin(email, password)
    try:
        garmin.login(token_dir)
    except Exception:
        # Initial login or token refresh
        garmin.login()

    # 2. Fetch last 30 activities
    activities = garmin.get_activities(0, 30)

    # Filter running activities (running, trail_running, treadmill_running)
    running_activities = [
        act for act in activities 
        if "running" in act.get("activityType", {}).get("typeKey", "").lower()
    ]

    now = datetime.now(timezone.utc)
    today = now.date()

    # Determine start of current week (Monday)
    start_of_week = today - timedelta(days=today.weekday())

    week_distance_meters = 0.0
    active_dates = set()

    for act in running_activities:
        start_str = act.get("startTimeGMT")
        if not start_str:
            continue
        act_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        act_date = act_dt.date()

        # Track active days
        active_dates.add(act_date)

        # Tally miles for current week (Mon -> Sun)
        if act_date >= start_of_week:
            week_distance_meters += act.get("distance", 0.0)

    # 3. Calculate 14-day history array (oldest to newest)
    matrix = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        matrix.append({
            "date": day.isoformat(),
            "active": day in active_dates
        })

    # Count consecutive active streak up to today
    streak = 0
    check_day = today
    # Allow 1 rest day window if today's run has not happened yet
    if check_day not in active_dates:
        check_day -= timedelta(days=1)
    while check_day in active_dates:
        streak += 1
        check_day -= timedelta(days=1)

    # 4. Extract latest run metrics
    latest_run = None
    if running_activities:
        recent = running_activities[0]
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

        latest_run = {
            "name": recent.get("activityName", "Outdoor Run"),
            "relativeDate": rel_date,
            "distanceMiles": round(dist_mi, 1),
            "pace": format_pace(avg_speed),
            "duration": format_duration(dur_sec),
            "avgHr": int(avg_hr) if avg_hr else "N/A"
        }

    weekly_miles = round(week_distance_meters / 1609.34, 1)
    weekly_pct = min(100, int((weekly_miles / weekly_target) * 100)) if weekly_target > 0 else 0

    stats_payload = {
        "streakDays": streak,
        "weeklyMiles": weekly_miles,
        "weeklyTarget": weekly_target,
        "weeklyPct": weekly_pct,
        "streakMatrix": matrix,
        "latestRun": latest_run,
        "lastSynced": now.isoformat()
    }

    # Write output to garmin-stats.json
    output_path = os.environ.get("OUTPUT_PATH", "garmin-stats.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stats_payload, f, indent=2)

    print(f"Stats written to {output_path} successfully.")

if __name__ == "__main__":
    main()
