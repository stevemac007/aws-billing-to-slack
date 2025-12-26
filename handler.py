from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import os

import boto3
import requests

# It seems that the sparkline symbols don't line up (probably based on font?) so put them last
# Also, leaving out the full block because Slack doesn't like it: '█'
SPARKS = ['▁', '▂', '▃', '▄', '▅', '▆', '▇']


def sparkline(datapoints: List[float]) -> str:
    """Generate a sparkline visualization from a list of datapoints."""
    if not datapoints:
        return ""
    
    lower = min(datapoints)
    upper = max(datapoints)
    n_sparks = len(SPARKS) - 1

    line = ""
    for dp in datapoints:
        scaled = 1 if upper == 0 else dp / upper
        which_spark = round(scaled * n_sparks)
        which_spark = max(0, min(which_spark, len(SPARKS) - 1))
        line += SPARKS[which_spark]

    return line


def delta(costs: List[float]) -> float:
    """Calculate percentage change between the last two values."""
    if len(costs) > 1 and costs[-1] >= 1 and costs[-2] >= 1:
        # This only handles positive numbers
        return ((costs[-1] / costs[-2]) - 1) * 100.0
    return 0.0


def find_by_key(values: List[Dict[str, Any]], key: str, value: str) -> Optional[Dict[str, Any]]:
    """Find an item in a list of dictionaries by key-value pair."""
    return next((item for item in values if item.get(key) == value), None)


def lambda_handler(event: Dict[str, Any], context: Any) -> None:
    """AWS Lambda handler function."""
    group_type = os.environ.get("GROUP_TYPE", "DIMENSION")
    group_by = os.environ.get("GROUP_BY", "SERVICE")
    length = int(os.environ.get("LENGTH", "5"))
    cost_aggregation = os.environ.get("COST_AGGREGATION", "UnblendedCost")
    n_days = int(os.environ.get("DAYS", "7"))

    summary, buffer, data = report_cost(
        group_type=group_type,
        group_by=group_by,
        length=length,
        cost_aggregation=cost_aggregation,
        n_days=n_days
    )

    slack_hook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if slack_hook_url:
        publish_slack(slack_hook_url, summary, buffer)

    teams_hook_url = os.environ.get('TEAMS_WEBHOOK_URL')
    if teams_hook_url:
        publish_teams(teams_hook_url, summary, buffer)
    
    google_hook_url = os.environ.get('GOOGLE_WEBHOOK_URL')
    if google_hook_url:
        publish_google(google_hook_url, summary, buffer)

def report_cost(
    group_by: str = "SERVICE",
    length: int = 5,
    cost_aggregation: str = "UnblendedCost",
    result: Optional[Dict[str, Any]] = None,
    yesterday_str: Optional[str] = None,
    n_days: int = 7,
    group_type: str = "DIMENSION"
) -> Tuple[str, str, Dict[str, float]]:
    """Generate cost report from AWS Cost Explorer data."""
    
    today = datetime.today()
    start_period_date = today - timedelta(days=n_days)
    
    # Generate list of dates, so that even if our data is sparse,
    # we have the correct length lists of costs (len is n_days)
    list_of_dates = [
        (start_period_date + timedelta(days=x)).strftime('%Y-%m-%d')
        for x in range(n_days)
    ]

    # Get account name from env, or account id/account alias from boto3
    account_name = os.environ.get("AWS_ACCOUNT_NAME")
    if account_name is None:
        iam = boto3.client("iam")
        paginator = iam.get_paginator("list_account_aliases")
        for aliases in paginator.paginate(PaginationConfig={"MaxItems": 1}):
            if "AccountAliases" in aliases and len(aliases["AccountAliases"]) > 0:
                account_name = aliases["AccountAliases"][0]
                break

    if account_name is None:
        account_name = boto3.client("sts").get_caller_identity().get("Account")

    if account_name is None:
        account_name = "[NOT FOUND]"

    client = boto3.client('ce')

    query = {
        "TimePeriod": {
            "Start": start_period_date.strftime('%Y-%m-%d'),
            "End": today.strftime('%Y-%m-%d'),
        },
        "Granularity": "DAILY",
        "Filter": {
            "Not": {
                "Dimensions": {
                    "Key": "RECORD_TYPE",
                    "Values": [
                        "Credit",
                        "Refund",
                        "Upfront",
                        "Support",
                    ]
                }
            }
        },
        "Metrics": [cost_aggregation],
        "GroupBy": [
            {
                "Type": group_type,
                "Key": group_by,
            },
        ],
    }

    # Only run the query when on lambda, not when testing locally with example json
    api_response_time = None
    if result is None:
        result = client.get_cost_and_usage(**query)
        # Extract API response timestamp if available
        if 'ResponseMetadata' in result and 'HTTPHeaders' in result['ResponseMetadata']:
            api_response_time = result['ResponseMetadata']['HTTPHeaders'].get('date')

    cost_per_day_by_service: Dict[str, List[float]] = defaultdict(list)
    cost_per_week_by_service: Dict[str, float] = defaultdict(float)

    # New method, which first creates a dict of dicts
    # then loop over the services and loop over the list_of_dates
    # and this means even for sparse data we get a full list of costs
    cost_per_day_dict: Dict[str, Dict[str, float]] = defaultdict(dict)

    # Extract actual dates from the result data for more accurate reporting
    actual_dates = []
    for day in result['ResultsByTime']:
        start_date = day["TimePeriod"]["Start"]
        actual_dates.append(start_date)
        for group in day['Groups']:
            key = group['Keys'][0]
            if group_by == "LINKED_ACCOUNT":
                dimension = find_by_key(result["DimensionValueAttributes"], "Value", key)
                if dimension:
                    key += f" ({dimension['Attributes']['description']})"
            cost = float(group['Metrics'][cost_aggregation]['Amount'])
            cost_per_day_dict[key][start_date] = cost
            cost_per_week_by_service[key] += cost

    # Use actual dates from data if available, otherwise fall back to generated dates
    if actual_dates:
        list_of_dates = actual_dates
        # The "yesterday" date is the last date in our actual data
        yesterday_date = actual_dates[-1]
        # Update the date range for the summary
        start_period_date = datetime.strptime(actual_dates[0], '%Y-%m-%d')
        end_period_date = datetime.strptime(actual_dates[-1], '%Y-%m-%d') + timedelta(days=1)
    else:
        # Fallback to calculated yesterday date
        yesterday_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')

    for key in cost_per_day_dict:
        for start_date in list_of_dates:
            cost = cost_per_day_dict[key].get(start_date, 0.0)  # fallback for sparse data
            cost_per_day_by_service[key].append(cost)

    # Sort the map by yesterday's cost
    most_expensive_yesterday = sorted(
        cost_per_day_by_service.items(), 
        key=lambda item: item[1][-1], 
        reverse=True
    )

    service_names = [k for k, _ in most_expensive_yesterday[:length]]
    longest_name_len = len(max(service_names, key=len)) if service_names else 0

    buffer = f"{'Service':{longest_name_len}} ${'Yday':8} {'∆%':>5} $Last {n_days}{'d':6} {'Last '}{n_days}{'d':7} \n"

    for service_name, costs in most_expensive_yesterday[:length]:
        weekcost = cost_per_week_by_service[service_name]
        buffer += f"{service_name:{longest_name_len}} ${costs[-1]:8,.2f} {delta(costs):4.0f}% ${weekcost:12,.2f} {sparkline(costs):7}\n"

    other_costs = [0.0] * n_days
    other_weekly_costs = 0.0
    for service_name, costs in most_expensive_yesterday[length:]:
        for i, cost in enumerate(costs):
            if i < len(other_costs):
                other_costs[i] += cost
            other_weekly_costs += cost

    buffer += f"{'Other':{longest_name_len}} ${other_costs[-1]:8,.2f} {delta(other_costs):4.0f}% ${other_weekly_costs:12,.2f} {sparkline(other_costs):7} \n"

    total_costs = [0.0] * n_days
    for day_number in range(n_days):
        for service_name, costs in most_expensive_yesterday:
            if day_number < len(costs):
                total_costs[day_number] += costs[day_number]

    total_weekly = sum(cost_per_week_by_service.values())

    buffer += f"{'Total':{longest_name_len}} ${total_costs[-1]:8,.2f} {delta(total_costs):4.0f}% ${total_weekly:12,.2f} {sparkline(total_costs):7} \n"

    cost_per_day_by_service["total"] = total_costs[-1]

    # Get the date for yesterday's costs (the last day in our data)
    # Include timezone information
    utc_now = datetime.now(timezone.utc)
    report_timestamp = utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')
    
    # Add API response time info if available
    api_info = f" (AWS API response: {api_response_time})" if api_response_time else ""
    
    credits_expire_date_str = os.environ.get('CREDITS_EXPIRE_DATE')
    if credits_expire_date_str:
        credits_expire_date = datetime.strptime(credits_expire_date_str, "%m/%d/%Y")

        credits_remaining_as_of_str = os.environ.get('CREDITS_REMAINING_AS_OF')
        credits_remaining_as_of = datetime.strptime(credits_remaining_as_of_str, "%m/%d/%Y")

        credits_remaining = float(os.environ.get('CREDITS_REMAINING', '0'))

        days_left_on_credits = (credits_expire_date - credits_remaining_as_of).days
        allowed_credits_per_day = credits_remaining / days_left_on_credits if days_left_on_credits > 0 else 0

        relative_to_budget = (total_costs[-1] / allowed_credits_per_day * 100.0) if allowed_credits_per_day > 0 else 0

        if relative_to_budget < 60:
            emoji = ":white_check_mark:"
        elif relative_to_budget > 110:
            emoji = ":rotating_light:"
        else:
            emoji = ":warning:" 

        summary = (
            f"{emoji} {cost_aggregation} for {account_name} on {yesterday_date} (UTC) was ${total_costs[-1]:,.2f}\n"
            f"({relative_to_budget:.2f}% of credit budget ${allowed_credits_per_day:,.2f} for the day)\n"
            f"Report generated at {report_timestamp}{api_info}"
        )
    else:
        summary = (
            f"{cost_aggregation} for account {account_name} on {yesterday_date} (UTC) was ${total_costs[-1]:,.2f}\n"
            f"Report covering {start_period_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}\n"
        )

    return summary, buffer, cost_per_day_by_service


def publish_slack(hook_url: str, summary: str, buffer: str) -> None:
    """Publish cost report to Slack webhook."""
    try:
        resp = requests.post(   
            hook_url,
            json={
                "text": f"{summary}\n\n```\n{buffer}\n```",
            },
            timeout=30
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Slack webhook error: {e}")


def publish_teams(hook_url: str, summary: str, buffer: str) -> None:
    """Publish cost report to Microsoft Teams webhook."""
    try:
        resp = requests.post(
            hook_url,
            json={
                "text": f"{summary}\n\n```\n{buffer}\n```",
            },
            timeout=30
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Teams webhook error: {e}")


def publish_google(hook_url: str, summary: str, buffer: str) -> None:
    """Publish cost report to Google Chat webhook."""
    message = {
        "text": f"{summary}\n\n```\n{buffer}\n```"
    }
    
    try:
        resp = requests.post(hook_url, json=message, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Google Chat webhook error: {e}")

if __name__ == "__main__":
    """Test the cost reporting functionality with real AWS data."""
    print("=== Testing with real AWS Cost Explorer API ===")
    
    # Test with SERVICE grouping
    summary, buffer, cost_dict = report_cost(
        group_by="SERVICE", 
        length=10, 
        cost_aggregation="UnblendedCost", 
        n_days=7
    )
    print(f"UnblendedCost Summary: {summary}")
    print(f"Buffer:\n{buffer}")
    
    print("\n=== Testing with AmortizedCost ===")
    summary, buffer, cost_dict = report_cost(
        group_by="SERVICE", 
        length=10, 
        cost_aggregation="AmortizedCost", 
        n_days=7
    )
    print(f"AmortizedCost Summary: {summary}")
    print(f"Buffer:\n{buffer}")
