# Daily Financial News - Briefing 

A simple Python + GitHub Actions starter project for generating a daily financial markets and geopolitical briefing news.

## What this does
- Pulls recent financial market news from Finnhub.
- Applies a basic rules-based risk-on / risk-off / neutral classification.
- Writes a markdown briefing file.
- Runs manually or on a daily GitHub Actions schedule.

## Files
- `src/briefing.py` - main script
- `.github/workflows/daily-briefing.yml` - GitHub Actions workflow
- `requirements.txt` - Python dependencies

## Setup
1. Create a new GitHub repository.
2. Copy Python, Workflow and Requirements.txt "Files" into the repo.
3. Create a Finnhub API key (3rd party API provider who connnects to financial websites).
4. In GitHub, go to Settings > Secrets and variables > Actions.
5. Add a new repository secret called `FINNHUB_API_KEY`.
6. Push the repo to GitHub.
7. Run the workflow manually first using `workflow_dispatch`.

## Schedule
The starter workflow uses:
- `0 7 * * *`

That is 07:00 UTC, which is 08:00 UK time during BST. In winter, if you want true 08:00 UK local time, change it to `0 8 * * *` or move to a scheduler that supports Europe/London timezone handling.

## Next upgrades / Enhancements
- Add indices, oil, FX, crypto and UK bond markets data.
- Add better summarisation logic including 3 to 4 point summary from the website link.
- Email or Teams/Slack delivery - Included Global Data Office - DL delivery.
- Persist daily archives.
