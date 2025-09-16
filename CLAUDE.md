# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a standalone statistics generator for MultiQC, designed to analyze Git repositories and create visual plots showing:
- Number of MultiQC modules over time
- Number of contributors over time (including co-authors from commit messages)

The repository contains a single Python script that uses PyDriller for Git analysis and Plotly for chart generation.

## Running the Script

The main script is `generate_plots.py` and uses a PEP 723 script format with inline dependencies. Use `uv` to run the script:

```bash
# Run the script with a path to the MultiQC repository using uv
uv run generate_plots.py /path/to/multiqc/repo
```

The script requires Python 3.8+ and will automatically install dependencies:
- plotly (for chart generation)
- pydriller (for Git repository analysis)
- typer (for CLI interface)
- kaleido (for SVG image export)

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

Charts use different font colors (#ffffff for dark mode, #000000 for light mode) but identical transparent backgrounds.

**CSV Data Files:**
- `modules_over_time.csv` - Chronological module data with dates and cumulative counts
- `contributors_over_time.csv` - Contributor data with GitHub usernames (when available) and full names in brackets

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

## File Structure

- `generate_plots.py` - Main script (PEP 723 format with inline dependencies)
- `README.md` - Documentation with responsive image display using `<picture>` elements
- `*.svg` - Generated chart files (dark/light variants)
- `*.csv` - Raw data files for further analysis
- `.github/workflows/update-plots.yml` - Automated update workflow