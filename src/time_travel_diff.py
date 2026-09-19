from src.diff_engine import diff_snapshots

def time_travel_diff(resolver, environment, at_timestamp):
    snapshot_before = resolver.get_snapshot_at(environment, at_timestamp)
    snapshot_now = resolver.get_latest_snapshot(environment)
    return diff_snapshots(snapshot_before, snapshot_now)