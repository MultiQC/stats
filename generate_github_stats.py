#!/usr/bin/env python

# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "plotly",
#     "typer",
#     "kaleido",
#     "pygithub",
#     "python-dateutil",
# ]
# ///

import csv
import json
import os
from datetime import datetime
from pathlib import Path
import plotly.graph_objects as go
import typer
from typing import Dict, List, Tuple, Optional
from github import Github
from collections import defaultdict


def get_github_client(token: str = None) -> Github:
    """Get authenticated GitHub client."""
    if token:
        from github import Auth
        auth = Auth.Token(token)
        return Github(auth=auth)
    else:
        # Try to use unauthenticated client (lower rate limits)
        return Github()


def get_cache_path(repo_name: str) -> Path:
    """Get cache file path for a repository."""
    cache_dir = Path(".cache")
    cache_dir.mkdir(exist_ok=True)
    safe_repo_name = repo_name.replace("/", "_")
    return cache_dir / f"{safe_repo_name}_cache.json"


def load_cache(repo_name: str) -> Dict:
    """Load cached data for a repository."""
    cache_path = get_cache_path(repo_name)
    if cache_path.exists():
        typer.echo(f"Loading cached data from {cache_path}")
        with open(cache_path, 'r') as f:
            return json.load(f)
    return {"issues": [], "prs": [], "last_updated": None}


def save_cache(repo_name: str, cache_data: Dict):
    """Save data to cache."""
    cache_path = get_cache_path(repo_name)
    typer.echo(f"Saving cache to {cache_path}")
    with open(cache_path, 'w') as f:
        json.dump(cache_data, f, indent=2, default=str)


def collect_all_data(repo, repo_name: str, use_cache: bool = True) -> Tuple[List[Dict], List[Dict]]:
    """Collect all issues and PRs data efficiently with incremental caching."""
    cache_data = load_cache(repo_name) if use_cache else {"issues": [], "prs": [], "last_updated": None}

    # Convert cached items back to proper format
    cached_issues = []
    cached_prs = []
    last_number = 0

    if cache_data["issues"]:
        for item in cache_data["issues"]:
            if isinstance(item['created_at'], str):
                item['created_at'] = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
            if item['closed_at'] and isinstance(item['closed_at'], str):
                item['closed_at'] = datetime.fromisoformat(item['closed_at'].replace('Z', '+00:00'))
            cached_issues.append(item)
            last_number = max(last_number, item['number'])

    if cache_data["prs"]:
        for item in cache_data["prs"]:
            if isinstance(item['created_at'], str):
                item['created_at'] = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
            if item['closed_at'] and isinstance(item['closed_at'], str):
                item['closed_at'] = datetime.fromisoformat(item['closed_at'].replace('Z', '+00:00'))
            cached_prs.append(item)
            last_number = max(last_number, item['number'])

    typer.echo(f"Found {len(cached_issues)} cached issues and {len(cached_prs)} cached PRs")
    typer.echo(f"Fetching new items since #{last_number}...")

    # Fetch all items (GitHub API returns both issues and PRs together)
    issues = repo.get_issues(state='all')

    new_issues = []
    new_prs = []
    count = 0
    new_items = 0
    save_interval = 100  # Save cache every 100 items

    for issue in issues:
        count += 1

        # Skip items we already have cached
        if issue.number <= last_number:
            continue

        new_items += 1

        item_data = {
            'number': issue.number,
            'title': issue.title,
            'created_at': issue.created_at,
            'closed_at': issue.closed_at,
            'state': issue.state,
            'is_pr': issue.pull_request is not None
        }

        if issue.pull_request:
            new_prs.append(item_data)
        else:
            new_issues.append(item_data)

        # Save cache incrementally
        if new_items % save_interval == 0:
            typer.echo(f"Processed {count} items, found {new_items} new items... Saving cache...")
            current_cache = {
                "issues": cached_issues + new_issues,
                "prs": cached_prs + new_prs,
                "last_updated": datetime.now().isoformat()
            }
            if use_cache:
                save_cache(repo_name, current_cache)

    # Combine cached and new data
    all_issues = cached_issues + new_issues
    all_prs = cached_prs + new_prs

    typer.echo(f"Total: {len(all_issues)} issues, {len(all_prs)} PRs ({new_items} new items)")

    # Final cache update
    if use_cache:
        cache_data = {
            "issues": all_issues,
            "prs": all_prs,
            "last_updated": datetime.now().isoformat()
        }
        save_cache(repo_name, cache_data)

    return all_issues, all_prs


def calculate_cumulative_stats(items_data: List[Dict], item_type: str) -> Tuple[List[datetime], List[int], List[datetime], List[int]]:
    """Calculate cumulative statistics for items (issues or PRs)."""
    typer.echo(f"Calculating cumulative statistics for {item_type}...")

    # Sort by creation date
    items_data.sort(key=lambda x: x['created_at'])

    # Track cumulative created count
    created_dates = []
    created_counts = []

    # Track open count over time
    open_dates = []
    open_counts = []

    # Events: (date, event_type, count_change)
    events = []

    # Add creation events
    for item in items_data:
        events.append((item['created_at'], 'created', 1))
        if item['closed_at']:
            events.append((item['closed_at'], 'closed', -1))

    # Sort events by date
    events.sort(key=lambda x: x[0])

    # Calculate cumulative created
    total_created = 0
    for item in items_data:
        total_created += 1
        created_dates.append(item['created_at'])
        created_counts.append(total_created)

    # Calculate open count over time
    current_open = 0
    for event_date, event_type, change in events:
        if event_type == 'created':
            current_open += change
        elif event_type == 'closed':
            current_open += change

        open_dates.append(event_date)
        open_counts.append(current_open)

    return created_dates, created_counts, open_dates, open_counts


def calculate_monthly_stats(items_data: List[Dict], item_type: str) -> Tuple[List[datetime], List[int]]:
    """Calculate monthly creation statistics for items (issues or PRs)."""
    typer.echo(f"Calculating monthly statistics for {item_type}...")

    if not items_data:
        return [], []

    # Sort by creation date
    items_data.sort(key=lambda x: x['created_at'])

    # Group items by month (first day of month)
    monthly_counts = defaultdict(int)

    for item in items_data:
        # Get first day of the month for this item
        item_date = item['created_at']
        month_start = item_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        monthly_counts[month_start] += 1

    # Convert to sorted lists
    months = sorted(monthly_counts.keys())
    counts = [monthly_counts[month] for month in months]

    return months, counts


def generate_plots_and_csv(
    repo_name: str,
    issues_created_dates: List[datetime],
    issues_created_counts: List[int],
    issues_open_dates: List[datetime],
    issues_open_counts: List[int],
    prs_created_dates: List[datetime],
    prs_created_counts: List[int],
    prs_open_dates: List[datetime],
    prs_open_counts: List[int],
    issues_monthly_dates: List[datetime],
    issues_monthly_counts: List[int],
    prs_monthly_dates: List[datetime],
    prs_monthly_counts: List[int]
):
    """Generate plots and CSV files for all statistics."""
    typer.echo("Generating plots and CSV files...")

    # Generate CSV files
    # Issues created
    with open("issues_created_over_time.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["date", "cumulative_issues_created"])
        for date, count in zip(issues_created_dates, issues_created_counts):
            writer.writerow([date.isoformat(), count])

    # Issues open
    with open("issues_open_over_time.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["date", "issues_open"])
        for date, count in zip(issues_open_dates, issues_open_counts):
            writer.writerow([date.isoformat(), count])

    # PRs created
    with open("prs_created_over_time.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["date", "cumulative_prs_created"])
        for date, count in zip(prs_created_dates, prs_created_counts):
            writer.writerow([date.isoformat(), count])

    # PRs open
    with open("prs_open_over_time.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["date", "prs_open"])
        for date, count in zip(prs_open_dates, prs_open_counts):
            writer.writerow([date.isoformat(), count])

    # Issues created per month
    with open("issues_monthly_new.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["month_start", "new_issues"])
        for date, count in zip(issues_monthly_dates, issues_monthly_counts):
            writer.writerow([date.isoformat(), count])

    # PRs created per month
    with open("prs_monthly_new.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["month_start", "new_prs"])
        for date, count in zip(prs_monthly_dates, prs_monthly_counts):
            writer.writerow([date.isoformat(), count])

    # Generate plots for both dark and light modes
    for mode in ["dark", "light"]:
        font_color = "#ffffff" if mode == "dark" else "#000000"

        # Issues created over time
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=issues_created_dates,
            y=issues_created_counts,
            fill="tozeroy",
            name="Issues Created",
            line=dict(color="rgb(255, 127, 14)")
        ))
        fig.update_layout(
            title=f"{repo_name} - Issues Created Over Time",
            xaxis_title="Date",
            yaxis_title="Cumulative Issues Created",
            font=dict(family="Open Sans", size=18, color=font_color),
            plot_bgcolor="rgba(0, 0, 0, 0)",
            paper_bgcolor="rgba(0, 0, 0, 0)",
        )
        fig.write_image(f"issues_created_{mode}.svg")

        # Issues open over time
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=issues_open_dates,
            y=issues_open_counts,
            fill="tozeroy",
            name="Issues Open",
            line=dict(color="rgb(255, 127, 14)")
        ))
        fig.update_layout(
            title=f"{repo_name} - Open Issues Over Time",
            xaxis_title="Date",
            yaxis_title="Number of Open Issues",
            font=dict(family="Open Sans", size=18, color=font_color),
            plot_bgcolor="rgba(0, 0, 0, 0)",
            paper_bgcolor="rgba(0, 0, 0, 0)",
        )
        fig.write_image(f"issues_open_{mode}.svg")

        # PRs created over time
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=prs_created_dates,
            y=prs_created_counts,
            fill="tozeroy",
            name="PRs Created",
            line=dict(color="rgb(44, 160, 44)")
        ))
        fig.update_layout(
            title=f"{repo_name} - Pull Requests Created Over Time",
            xaxis_title="Date",
            yaxis_title="Cumulative PRs Created",
            font=dict(family="Open Sans", size=18, color=font_color),
            plot_bgcolor="rgba(0, 0, 0, 0)",
            paper_bgcolor="rgba(0, 0, 0, 0)",
        )
        fig.write_image(f"prs_created_{mode}.svg")

        # PRs open over time
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=prs_open_dates,
            y=prs_open_counts,
            fill="tozeroy",
            name="PRs Open",
            line=dict(color="rgb(44, 160, 44)")
        ))
        fig.update_layout(
            title=f"{repo_name} - Open Pull Requests Over Time",
            xaxis_title="Date",
            yaxis_title="Number of Open PRs",
            font=dict(family="Open Sans", size=18, color=font_color),
            plot_bgcolor="rgba(0, 0, 0, 0)",
            paper_bgcolor="rgba(0, 0, 0, 0)",
        )
        fig.write_image(f"prs_open_{mode}.svg")

        # Issues created per month
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=issues_monthly_dates,
            y=issues_monthly_counts,
            mode='lines+markers',
            name="New Issues per Month",
            line=dict(color="rgb(255, 127, 14)"),
            marker=dict(size=4)
        ))
        fig.update_layout(
            title=f"{repo_name} - New Issues Per Month",
            xaxis_title="Month",
            yaxis_title="New Issues Created",
            font=dict(family="Open Sans", size=18, color=font_color),
            plot_bgcolor="rgba(0, 0, 0, 0)",
            paper_bgcolor="rgba(0, 0, 0, 0)",
        )
        fig.write_image(f"issues_monthly_{mode}.svg")

        # PRs created per month
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=prs_monthly_dates,
            y=prs_monthly_counts,
            mode='lines+markers',
            name="New PRs per Month",
            line=dict(color="rgb(44, 160, 44)"),
            marker=dict(size=4)
        ))
        fig.update_layout(
            title=f"{repo_name} - New Pull Requests Per Month",
            xaxis_title="Month",
            yaxis_title="New PRs Created",
            font=dict(family="Open Sans", size=18, color=font_color),
            plot_bgcolor="rgba(0, 0, 0, 0)",
            paper_bgcolor="rgba(0, 0, 0, 0)",
        )
        fig.write_image(f"prs_monthly_{mode}.svg")


def generate_github_stats(
    repo_name: str = typer.Argument(..., help="GitHub repository in format 'owner/repo'"),
    token: str = typer.Option(None, "--token", "-t", help="GitHub personal access token for higher rate limits")
):
    """Generate GitHub statistics plots from a GitHub repository.

    Note: This script requires GitHub API access. For large repositories or frequent use,
    you should provide a personal access token to avoid rate limits:

    uv run generate_github_stats.py owner/repo --token YOUR_TOKEN
    """

    typer.echo(f"Analyzing GitHub repository: {repo_name}")

    if not token:
        typer.echo("Warning: No token provided. You may hit rate limits quickly.")
        typer.echo("Consider using --token flag with a GitHub personal access token.")

    # Initialize GitHub client
    github_client = get_github_client(token)

    try:
        repo = github_client.get_repo(repo_name)
        typer.echo(f"Successfully connected to repository: {repo.full_name}")
    except Exception as e:
        typer.echo(f"Error: Could not access repository {repo_name}: {e}", err=True)
        raise typer.Exit(1)

    # Collect data efficiently
    issues_data, prs_data = collect_all_data(repo, repo_name)

    typer.echo(f"Found {len(issues_data)} issues and {len(prs_data)} pull requests")

    # Calculate statistics
    issues_created_dates, issues_created_counts, issues_open_dates, issues_open_counts = calculate_cumulative_stats(issues_data, "issues")
    prs_created_dates, prs_created_counts, prs_open_dates, prs_open_counts = calculate_cumulative_stats(prs_data, "PRs")

    # Calculate monthly statistics
    issues_monthly_dates, issues_monthly_counts = calculate_monthly_stats(issues_data, "issues")
    prs_monthly_dates, prs_monthly_counts = calculate_monthly_stats(prs_data, "PRs")

    # Generate plots and CSV files
    generate_plots_and_csv(
        repo_name,
        issues_created_dates, issues_created_counts,
        issues_open_dates, issues_open_counts,
        prs_created_dates, prs_created_counts,
        prs_open_dates, prs_open_counts,
        issues_monthly_dates, issues_monthly_counts,
        prs_monthly_dates, prs_monthly_counts
    )

    typer.echo("\nGenerated files:")
    typer.echo("Charts:")
    typer.echo(f"- issues_created_dark.svg and issues_created_light.svg ({len(issues_data)} issues)")
    typer.echo("- issues_open_dark.svg and issues_open_light.svg")
    typer.echo(f"- issues_monthly_dark.svg and issues_monthly_light.svg ({len(issues_monthly_counts)} months)")
    typer.echo(f"- prs_created_dark.svg and prs_created_light.svg ({len(prs_data)} PRs)")
    typer.echo("- prs_open_dark.svg and prs_open_light.svg")
    typer.echo(f"- prs_monthly_dark.svg and prs_monthly_light.svg ({len(prs_monthly_counts)} months)")
    typer.echo("Raw data:")
    typer.echo(f"- issues_created_over_time.csv ({len(issues_data)} issues)")
    typer.echo("- issues_open_over_time.csv")
    typer.echo(f"- issues_monthly_new.csv ({len(issues_monthly_counts)} months)")
    typer.echo(f"- prs_created_over_time.csv ({len(prs_data)} PRs)")
    typer.echo("- prs_open_over_time.csv")
    typer.echo(f"- prs_monthly_new.csv ({len(prs_monthly_counts)} months)")


if __name__ == "__main__":
    typer.run(generate_github_stats)