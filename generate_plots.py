#!/usr/bin/env python

# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "plotly",
#     "pydriller",
#     "typer",
#     "kaleido",
# ]
# ///

import csv
import fnmatch
import os
import plotly.graph_objects as go
from pydriller import Repository, ModificationType
import re
import typer
from pathlib import Path


def extract_coauthors(commit_msg):
    """Extract co-authors from commit message"""
    coauthors = []
    # Look for Co-authored-by: Name <email>
    coauthor_pattern = r"Co-authored-by:\s*([^<\n\r]+?)(?:\s*<[^>]+>)?\s*$"
    matches = re.findall(coauthor_pattern, commit_msg, re.MULTILINE | re.IGNORECASE)

    for match in matches:
        # Clean up the name
        name = match.strip()
        # Skip bot accounts, empty names, and single character names
        if (
            name
            and len(name) > 2
            and not any(
                bot in name.lower() for bot in ["bot", "github-actions", "multiqc bot"]
            )
            and not name.startswith("Co-authored-by")
        ):
            coauthors.append(name)

    return coauthors


def generate_plots(repo_path: Path = typer.Argument(..., help="Path to the GitHub repository to analyze")):
    """Generate MultiQC statistics plots from a GitHub repository."""

    # Validate that the path exists and is a directory
    if not repo_path.exists():
        typer.echo(f"Error: Path {repo_path} does not exist", err=True)
        raise typer.Exit(1)

    if not repo_path.is_dir():
        typer.echo(f"Error: Path {repo_path} is not a directory", err=True)
        raise typer.Exit(1)

    # Find when each new module was added to MultiQC
    modules = {}
    mods_plot_x = []
    mods_plot_y = []

    # Track both committers and co-authors
    contributors = {}
    contributor_details = {}  # Store GitHub username and full name mapping
    contributors_plot_x = []
    contributors_plot_y = []

    for commit in Repository(str(repo_path)).traverse_commits():
        # Count new modules
        for modification in commit.modified_files:
            if modification.change_type == ModificationType.ADD:
                if fnmatch.fnmatch(modification.new_path, "multiqc/*"):
                    mod_match = re.match(
                        r"multiqc/modules/([^/\.]+)", modification.new_path
                    )
                    if mod_match:
                        mod = mod_match.group(1)
                        if mod not in modules:
                            modules[mod] = str(commit.committer_date)
                            # Plotting data points
                            mods_plot_x.append(commit.committer_date)
                            mods_plot_y.append(len(modules))

        # Count new contributors (main committer)
        if commit.committer.name not in contributors:
            contributors[commit.committer.name] = str(commit.committer_date)

            # Extract GitHub username from email if possible
            github_username = None
            if commit.committer.email and commit.committer.email.endswith('@users.noreply.github.com'):
                # Format: username@users.noreply.github.com or 123456+username@users.noreply.github.com
                email_part = commit.committer.email.replace('@users.noreply.github.com', '')
                if '+' in email_part:
                    github_username = email_part.split('+')[-1]
                else:
                    github_username = email_part

            # Store contributor details
            if github_username and github_username != commit.committer.name:
                contributor_details[commit.committer.name] = f"{github_username} ({commit.committer.name})"
            else:
                contributor_details[commit.committer.name] = commit.committer.name

            # Plotting data points
            contributors_plot_x.append(commit.committer_date)
            contributors_plot_y.append(len(contributors))

        # Count co-authors from commit message
        coauthors = extract_coauthors(commit.msg)
        for coauthor in coauthors:
            if coauthor not in contributors:
                contributors[coauthor] = str(commit.committer_date)

                # For co-authors, just use the name as-is since we don't have email info
                contributor_details[coauthor] = coauthor

                # Plotting data points
                contributors_plot_x.append(commit.committer_date)
                contributors_plot_y.append(len(contributors))

    typer.echo(f"Total modules found: {len(modules)}")
    typer.echo(f"Total contributors found (including co-authors): {len(contributors)}")

    # Create output directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("plots", exist_ok=True)

    # Save raw data to CSV files
    # Modules CSV
    with open("data/modules_over_time.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["date", "cumulative_modules", "module_name"])

        # Sort modules by date for proper CSV output
        sorted_modules = sorted(modules.items(), key=lambda x: x[1])
        for i, (module_name, date_str) in enumerate(sorted_modules, 1):
            writer.writerow([date_str, i, module_name])

    # Contributors CSV
    with open("data/contributors_over_time.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["date", "cumulative_contributors", "contributor_name"])

        # Sort contributors by date for proper CSV output
        sorted_contributors = sorted(contributors.items(), key=lambda x: x[1])
        for i, (contributor_name, date_str) in enumerate(sorted_contributors, 1):
            # Use the detailed name format (GitHub username with full name in brackets if available)
            detailed_name = contributor_details.get(contributor_name, contributor_name)
            writer.writerow([date_str, i, detailed_name])

    # Generate both dark and light mode versions
    for mode in ["dark", "light"]:
        font_color = "#ffffff" if mode == "dark" else "#000000"

        # Modules over time
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=mods_plot_x, y=mods_plot_y, fill="tozeroy", name="Modules"))
        fig.update_layout(
            title="MultiQC modules over time",
            xaxis_title="Date",
            yaxis_title="Number of modules",
            font=dict(family="Open Sans", size=18, color=font_color),
            plot_bgcolor="rgba(0, 0, 0, 0)",
            paper_bgcolor="rgba(0, 0, 0, 0)",
        )
        filename = f"modules_over_time_{mode}.svg"
        fig.write_image(f"plots/{filename}")

        # Contributors over time (including co-authors from squash merges)
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=contributors_plot_x,
                y=contributors_plot_y,
                fill="tozeroy",
                name="Contributors",
            )
        )
        fig.update_layout(
            title="MultiQC code contributors over time",
            xaxis_title="Date",
            yaxis_title="Number of contributors",
            font=dict(family="Open Sans", size=18, color=font_color),
            plot_bgcolor="rgba(0, 0, 0, 0)",
            paper_bgcolor="rgba(0, 0, 0, 0)",
        )
        filename = f"contributors_over_time_{mode}.svg"
        fig.write_image(f"plots/{filename}")

    typer.echo("\nGenerated files:")
    typer.echo("Charts:")
    typer.echo(f"- modules_over_time_dark.svg and modules_over_time_light.svg ({len(modules)} modules)")
    typer.echo(
        f"- contributors_over_time_dark.svg and contributors_over_time_light.svg ({len(contributors)} contributors, including co-authors from squash merges)"
    )
    typer.echo("Raw data:")
    typer.echo(f"- modules_over_time.csv ({len(modules)} modules with dates)")
    typer.echo(f"- contributors_over_time.csv ({len(contributors)} contributors with dates)")


if __name__ == "__main__":
    typer.run(generate_plots)
