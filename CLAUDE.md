# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a standalone statistics generator for MultiQC with two main analysis tools:

**Git Repository Analysis** (`generate_plots.py`):
- Number of MultiQC modules over time
- Number of contributors over time (including co-authors from commit messages)

**GitHub API Analysis** (`generate_github_stats.py`):
- Issues created over time (cumulative)
- Open issues over time
- New issues per month
- Pull requests created over time (cumulative)
- Open pull requests over time
- New pull requests per month

Both scripts use PyDriller/PyGithub respectively and Plotly for chart generation.

## Running the Scripts

Both scripts use PEP 723 script format with inline dependencies. Use `uv` to run them:

**Git Repository Analysis:**
```bash
# Run with a path to the MultiQC repository using uv
uv run generate_plots.py /path/to/multiqc/repo
```

**GitHub API Analysis:**
```bash
# Run with repository name and GitHub token
uv run generate_github_stats.py MultiQC/MultiQC --token $(gh auth token)
```

Both scripts require Python 3.8+ and automatically install dependencies:
- plotly, kaleido (for chart generation)
- pydriller (for git analysis) / pygithub (for GitHub API)
- typer (for CLI interface)

## Testing

To test the script, clone the MultiQC repository into a temporary location and run the script on it:

```bash
# Clone MultiQC repository to a temporary location
git clone https://github.com/MultiQC/MultiQC.git /tmp/multiqc-test

# Run the script on the cloned repository using uv
uv run generate_plots.py /tmp/multiqc-test

# Verify that both dark and light mode SVG files are generated
ls -la *_dark.svg *_light.svg
```

This will generate the statistics plots based on the actual MultiQC repository history and verify that the script works correctly with real data.

## Architecture

### Core Components

1. **extract_coauthors()**: Parses commit messages to find "Co-authored-by:" lines, filtering out bot accounts and invalid names. This is crucial for post-2025 MultiQC data when squash-merge strategy was adopted.

2. **generate_plots()**: Main CLI function that:
   - Validates the provided repository path
   - Iterates through all Git commits using PyDriller
   - Tracks new MultiQC modules by watching for new files in `multiqc/modules/` directory
   - Counts unique contributors from both commit authors and co-authors
   - Generates both dark and light mode SVG charts with transparent backgrounds

### Chart Generation

The script creates both visual and data outputs:

**SVG Charts:**
- `modules_over_time_dark.svg` / `modules_over_time_light.svg`
- `contributors_over_time_dark.svg` / `contributors_over_time_light.svg`
- `issues_created_dark.svg` / `issues_created_light.svg`
- `issues_open_dark.svg` / `issues_open_light.svg`
- `issues_monthly_dark.svg` / `issues_monthly_light.svg`
- `prs_created_dark.svg` / `prs_created_light.svg`
- `prs_open_dark.svg` / `prs_open_light.svg`
- `prs_monthly_dark.svg` / `prs_monthly_light.svg`

Charts use different font colors (#ffffff for dark mode, #000000 for light mode) but identical transparent backgrounds.

**CSV Data Files:**
- `modules_over_time.csv` - Chronological module data with dates and cumulative counts
- `contributors_over_time.csv` - Contributor data with GitHub usernames (when available) and full names in brackets
- `issues_created_over_time.csv` - Cumulative issues created data
- `issues_open_over_time.csv` - Open issues count over time
- `issues_monthly_new.csv` - New issues created per month
- `prs_created_over_time.csv` - Cumulative PRs created data
- `prs_open_over_time.csv` - Open PRs count over time
- `prs_monthly_new.csv` - New PRs created per month

### README Integration

The README.md uses HTML `<picture>` elements with media queries to display the appropriate chart based on the user's color scheme preference, following the same pattern as the MultiQC logo.

## Key Implementation Details

- Module detection looks specifically for files matching `multiqc/modules/[module_name]` pattern
- Co-author extraction is case-insensitive and handles various email formats
- Bot filtering excludes "bot", "github-actions", and "multiqc bot" from contributor counts
- All chart backgrounds are transparent (rgba(0,0,0,0)) for better integration
- GitHub username extraction from noreply emails (`username@users.noreply.github.com` format)
- CSV contributor format: `username (Full Name)` when GitHub username differs from commit name

## Automation

The repository includes a GitHub Actions workflow (`.github/workflows/update-plots.yml`) that:
- Runs weekly on Sundays at 2 AM UTC
- Can be manually triggered via `workflow_dispatch`
- Clones the MultiQC repository and regenerates all plots and CSV files
- Commits changes back to this repository only if CSV files have changed (SVG files are ignored since Plotly generates slightly different output each time)

## GitHub API Caching System

The `generate_github_stats.py` script implements an intelligent caching system:

**Cache Location**: `.cache/` directory (committed to git for GitHub Actions)
**Cache Format**: JSON files named `{owner}_{repo}_cache.json`
**Incremental Updates**: Only fetches new items since last cached item number
**Resilience**: Saves cache every 100 items to prevent data loss on interruption
**Performance**: Dramatically reduces API calls on subsequent runs

## File Structure

- `generate_plots.py` - Git repository analysis script (PEP 723 format)
- `generate_github_stats.py` - GitHub API analysis script (PEP 723 format)
- `README.md` - Documentation with responsive image display using `<picture>` elements
- `*.svg` - Generated chart files (dark/light variants for both scripts)
- `*.csv` - Raw data files for further analysis (both git and GitHub data)
- `.cache/` - GitHub API cache files (committed to enable GitHub Actions incremental updates)
- `.github/workflows/update-plots.yml` - Automated update workflow