#!/usr/bin/env python3
"""
Generate hour_partition values for Grafana Cassandra queries

This script helps create the list of hour_partition values needed for
querying Cassandra aggregate tables efficiently.

Usage:
    python generate_partitions.py --hours 24
    python generate_partitions.py --days 7
    python generate_partitions.py --current
"""
import argparse
from datetime import datetime, timedelta


def generate_hour_partitions(hours_back=24, format_style='grafana'):
    """
    Generate hour_partition values for the last N hours

    Args:
        hours_back: Number of hours to go back from now
        format_style: 'grafana' (quoted, comma-separated) or 'python' (list)

    Returns:
        String with formatted partition values
    """
    now = datetime.utcnow()
    partitions = []

    for i in range(hours_back):
        hour = now - timedelta(hours=hours_back - i - 1)
        partition = hour.strftime("%Y-%m-%d-%H")
        partitions.append(partition)

    if format_style == 'grafana':
        # Format for CQL: '2025-10-11-00', '2025-10-11-01', ...
        return ",\n  ".join([f"'{p}'" for p in partitions])
    elif format_style == 'python':
        # Format for Python: ['2025-10-11-00', '2025-10-11-01', ...]
        return partitions
    elif format_style == 'cql':
        # Format for inline CQL: ('2025-10-11-00', '2025-10-11-01', ...)
        return "(" + ", ".join([f"'{p}'" for p in partitions]) + ")"
    else:
        return partitions


def get_current_hour_partition():
    """Get the current hour partition value"""
    return datetime.utcnow().strftime("%Y-%m-%d-%H")


def generate_complete_query(query_type='global_trend', hours=24):
    """
    Generate complete Grafana query with current time partitions

    Args:
        query_type: Type of query to generate
        hours: Number of hours to include

    Returns:
        Complete CQL query string
    """
    partitions = generate_hour_partitions(hours, 'grafana')
    current_hour = get_current_hour_partition()

    queries = {
        'global_trend': f"""
SELECT
  toTimestamp(hour_start) as time,
  pct_stress as "Stress %"
FROM reddit_rt.agg_global_hour
WHERE hour_partition IN (
  {partitions}
)
ORDER BY hour_start ASC
""",
        'global_current': f"""
SELECT
  pct_stress as "Stress %",
  total_cnt as "Total Posts",
  stress_cnt as "Stressed Posts",
  avg_score as "Avg Score"
FROM reddit_rt.agg_global_hour
WHERE hour_partition = '{current_hour}'
ORDER BY hour_start DESC
LIMIT 1
""",
        'top_subreddits': f"""
SELECT
  subreddit as "Subreddit",
  pct_stress as "Stress %",
  total_cnt as "Posts",
  stress_cnt as "Stressed"
FROM reddit_rt.agg_subreddit_hour
WHERE hour_partition = '{current_hour}'
ORDER BY pct_stress DESC
LIMIT 10
ALLOW FILTERING
""",
        'hourly_volume': f"""
SELECT
  toTimestamp(hour_start) as time,
  total_cnt as "Posts"
FROM reddit_rt.agg_global_hour
WHERE hour_partition IN (
  {partitions}
)
ORDER BY hour_start ASC
""",
        'subreddit_trend': f"""
SELECT
  toTimestamp(hour_start) as time,
  pct_stress as value
FROM reddit_rt.agg_subreddit_hour
WHERE subreddit = 'depression'
  AND hour_partition IN (
  {partitions}
)
ORDER BY hour_start ASC
"""
    }

    return queries.get(query_type, "Unknown query type")


def print_dashboard_update_instructions(hours=24):
    """Print instructions for updating Grafana dashboard"""
    print("=" * 80)
    print("GRAFANA DASHBOARD UPDATE INSTRUCTIONS")
    print("=" * 80)
    print()
    print(f"Generated for: Last {hours} hours")
    print(f"Current UTC time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Current hour partition: {get_current_hour_partition()}")
    print()
    print("-" * 80)
    print("1. HOUR PARTITION LIST (for WHERE clauses)")
    print("-" * 80)
    print(generate_hour_partitions(hours, 'grafana'))
    print()
    print("-" * 80)
    print("2. COMPLETE QUERIES")
    print("-" * 80)
    print()

    query_types = [
        ('global_trend', 'Global Stress Trend (Time Series)'),
        ('global_current', 'Current Hour Stats (Stat Panel)'),
        ('top_subreddits', 'Top 10 Subreddits (Bar Chart)'),
        ('hourly_volume', 'Hourly Post Volume (Time Series)'),
        ('subreddit_trend', 'Subreddit Trend (Time Series)')
    ]

    for qtype, description in query_types:
        print(f"\n### {description}")
        print(f"```sql")
        print(generate_complete_query(qtype, hours).strip())
        print(f"```\n")

    print("-" * 80)
    print("3. UPDATE STEPS")
    print("-" * 80)
    print("""
1. Open Grafana: http://localhost:3000
2. Navigate to your dashboard
3. For each panel:
   a. Click panel title → Edit
   b. Replace the WHERE hour_partition IN (...) clause
   c. Paste the partition list generated above
   d. Click "Apply" to save

4. For "Current Hour" queries:
   - Replace hour_partition value with: '{}'

5. Test each panel to ensure data loads correctly

6. Save dashboard (Ctrl+S or Cmd+S)
""".format(get_current_hour_partition()))

    print("-" * 80)
    print("4. AUTOMATION TIP")
    print("-" * 80)
    print("""
For automatic updates, consider:
- Creating a dashboard variable that queries recent hour_partitions
- Using Grafana's query templating if supported by Cassandra plugin
- Scheduling this script to run daily and update dashboard JSON
- Creating a dashboard refresh DAG in Airflow
""")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Generate hour_partition values for Grafana Cassandra queries',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate partitions for last 24 hours
  python generate_partitions.py --hours 24

  # Generate partitions for last 7 days
  python generate_partitions.py --days 7

  # Get current hour partition
  python generate_partitions.py --current

  # Generate complete dashboard update instructions
  python generate_partitions.py --dashboard-update

  # Generate specific query type
  python generate_partitions.py --query global_trend --hours 48
        """
    )

    parser.add_argument('--hours', type=int, help='Number of hours back')
    parser.add_argument('--days', type=int, help='Number of days back')
    parser.add_argument('--current', action='store_true', help='Print current hour partition')
    parser.add_argument('--format', choices=['grafana', 'python', 'cql'], default='grafana',
                        help='Output format (default: grafana)')
    parser.add_argument('--query', choices=['global_trend', 'global_current', 'top_subreddits',
                                           'hourly_volume', 'subreddit_trend'],
                        help='Generate complete query of specified type')
    parser.add_argument('--dashboard-update', action='store_true',
                        help='Print complete dashboard update instructions')

    args = parser.parse_args()

    # Determine hours
    if args.days:
        hours = args.days * 24
    elif args.hours:
        hours = args.hours
    else:
        hours = 24  # Default

    # Execute requested action
    if args.current:
        print(get_current_hour_partition())

    elif args.dashboard_update:
        print_dashboard_update_instructions(hours)

    elif args.query:
        print(generate_complete_query(args.query, hours))

    else:
        # Default: print partition list
        partitions = generate_hour_partitions(hours, args.format)
        print(partitions)


if __name__ == '__main__':
    main()
