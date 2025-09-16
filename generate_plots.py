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

import fnmatch
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
            # Plotting data points
            contributors_plot_x.append(commit.committer_date)
            contributors_plot_y.append(len(contributors))

        # Count co-authors from commit message
        coauthors = extract_coauthors(commit.msg)
        for coauthor in coauthors:
            if coauthor not in contributors:
                contributors[coauthor] = str(commit.committer_date)
                # Plotting data points
                contributors_plot_x.append(commit.committer_date)
                contributors_plot_y.append(len(contributors))

    typer.echo(f"Total modules found: {len(modules)}")
    typer.echo(f"Total contributors found (including co-authors): {len(contributors)}")

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
        fig.write_image(filename)

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
        fig.write_image(filename)

    typer.echo("\nGenerated charts:")
    typer.echo(f"- modules_over_time_dark.svg and modules_over_time_light.svg ({len(modules)} modules)")
    typer.echo(
        f"- contributors_over_time_dark.svg and contributors_over_time_light.svg ({len(contributors)} contributors, including co-authors from squash merges)"
    )


if __name__ == "__main__":
    typer.run(generate_plots)
