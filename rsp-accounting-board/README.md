# RSP Accounting Status Board

Auto-updating dashboard for Restaurant Systems Pro's accounting team. Mirrors the Wally's automation pattern: GitHub Actions pulls fresh data daily, GitHub Pages serves the board.

## How it works
1. Every weekday at 6:00 AM Arizona, the workflow reads the last two days of Manager Log dispatch emails and any team reply emails from the Gmail inbox (IMAP).
2. The email text goes to Claude, which extracts structured updates (reconciled-through dates, over/short amounts, payroll dates, blockers) keyed to exact entity names.
3. Updates merge into `data/board.json`, the commit triggers a Pages deploy, and the board at the Pages URL reflects the new state.
4. Scoring on the board: red means someone said no, an over/short is above $20, or a checkpoint went silent past its cadence. Silence rots red on its own.

## One-time setup (Fred does this, about 10 minutes)
1. Create the repo (private) under the RestaurantSystemsPro org and push this folder.
2. Settings > Secrets and variables > Actions > New repository secret, add three:
   - `GMAIL_ADDRESS`: the inbox receiving the dispatches
   - `GMAIL_APP_PASSWORD`: create at myaccount.google.com > Security > 2-Step Verification > App passwords. This is NOT your Gmail password.
   - `ANTHROPIC_API_KEY`: from console.anthropic.com
3. Settings > Pages > Source: GitHub Actions.
4. Actions tab > Daily board update > Run workflow, to test once manually.
5. Bookmark the Pages URL. That is the board.

## Manual mode (works today, before secrets exist)
Open `index.html` locally, or drag a `board.json` onto the Load answers file button. The morning Claude session can generate that file from the emails until the automation is live.

## Files
- `index.html`: the dashboard (self-contained, also works opened locally)
- `data/board.json`: current board state, written by the workflow
- `scripts/parse_dispatch.py`: email fetch + Claude extraction + merge
- `.github/workflows/daily.yml`: schedule, commit, deploy

## Security notes
- Secrets live only in GitHub Actions secrets. Never in code, never in this repo's files.
- The Gmail App Password only grants mail access, and can be revoked in one click without touching the account password.
- When SETA delivers the read-only RSP API, `parse_dispatch.py` gets a sibling script that reads system truth directly and the email parse becomes a supplement for judgment notes. Same board, better data.

## Open items
- Melinda's five former clients (Atlas Group, Brakeman's Burgers, both Ola Juice Bars, Piglatin Cochino) sit in an "Oversight (Melinda)" lane pending reassignment to a team.
- Setup Schedule Notification in RSP must be configured or no dispatch emails exist for the parser to read.
