SigmundBOT: Mastodon Personality Bot
🔍 Features
Responds to Mastodon followers and mentions

Offers multiple personality tests:

Big Five

MBTI

Stoicism

HEXACO (optional to mention if implemented)

Saves results to CSV and uploads to Google Sheets for logging

Deployable via GitHub Actions, Replit, Railway, or Render

🛠 Setup Guide
Create a Mastodon account & register a developer application to get your API keys.

Create a Google Cloud project and enable the Google Sheets API.

Clone this repository.

Copy .env.example to .env and fill in all required credentials.

Install dependencies via pip install -r requirements.txt.

Run locally or deploy using your preferred platform.

For GitHub Actions, configure the workflow (deploy.yml) to automate deployment.

✅ Included Psychometric Tests
Big Five Personality

MBTI Personality Type

Stoicism Level

HEXACO Personality (if included)

🛡 Security
Keep all sensitive keys and tokens in .env

Never commit .env to GitHub or public repositories

Regularly revoke and regenerate API tokens for safety

For detailed instructions, see the documentation folder.
