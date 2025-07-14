# Telegram Channel Scraper

A Python-based Telegram scraper that uses Telethon and PyMySQL to scrape user information from all channels/groups you are a member of.

## Features

- Scrapes all channels and groups you're a member of
- Stores user information including:
  - User ID and access hash
  - Username, first name, and last name
  - Bot status, verification status, restriction status
  - Scam/fake indicators
- Tracks which channel each user was scraped from
- Skips channels that require admin permissions
- Handles rate limiting with built-in delays
- Comprehensive logging

## Database Structure

The scraper creates a MySQL database called `telescrape` with three tables:

1. **users** - Stores user information
2. **channels** - Stores channel/group information
3. **user_channel** - Links users to the channels they were found in

## Prerequisites

1. Python 3.7+
2. MySQL Server
3. Telegram API credentials (api_id and api_hash)
4. An existing Telegram session file (already logged in)

## Installation

1. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

Run the scraper with:

```bash
python telegram_scraper.py --name YOUR_SESSION_NAME --api_id YOUR_API_ID --api_hash YOUR_API_HASH
```

### Command line arguments:

- `--name` (required): The session file name (without .session extension)
- `--api_id` (optional): Your Telegram API ID
- `--api_hash` (optional): Your Telegram API hash

### Example:

```bash
python telegram_scraper.py --name myaccount --api_id 12345 --api_hash abcdef123456
```

Note: The MySQL server connection is hardcoded and will automatically:
- Connect to the remote server at 89.28.236.32
- Use credentials (user: hedinn, password: Fxp.123456)
- Create the `telescrape` database if it doesn't exist
- Create all necessary tables with proper columns

## Important Notes

1. **Session Files**: The script expects an existing session file. You need to be already logged in with that session.

2. **Rate Limits**: The scraper includes delays to avoid hitting Telegram's rate limits, but excessive use may still result in temporary restrictions.

3. **Privacy**: Some channels restrict member visibility. The scraper will skip these channels and log a warning.

4. **Admin-Only Channels**: Channels that only show admins will be skipped automatically.

## Logs

The scraper creates a `scraper.log` file with detailed information about the scraping process, including:
- Successful connections
- Channels being processed
- Number of users scraped
- Any errors or warnings

## Data Viewer Utility

A separate `view_data.py` script is included to easily view and export the scraped data:

```bash
# Show summary statistics (uses pre-configured database)
python view_data.py --summary

# List all channels with user counts
python view_data.py --channels

# Search for users by name or username
python view_data.py --search "john"

# Show users from a specific channel
python view_data.py --channel "ChannelName"

# Export all users to CSV
python view_data.py --export users.csv
```

## Database Queries

You can also use these SQL queries directly:

```sql
-- Use the database
USE telescrape;

-- Count total unique users
SELECT COUNT(*) FROM users;

-- Count users per channel
SELECT c.title, COUNT(uc.user_id) as user_count 
FROM channels c 
JOIN user_channel uc ON c.id = uc.channel_id 
GROUP BY c.id 
ORDER BY user_count DESC;

-- Find users in multiple channels
SELECT u.username, u.first_name, u.last_name, COUNT(uc.channel_id) as channel_count 
FROM users u 
JOIN user_channel uc ON u.id = uc.user_id 
GROUP BY u.id 
HAVING channel_count > 1 
ORDER BY channel_count DESC;

-- Get all info for a specific channel
SELECT u.* 
FROM users u 
JOIN user_channel uc ON u.id = uc.user_id 
JOIN channels c ON c.id = uc.channel_id 
WHERE c.title LIKE '%ChannelName%';
```

## Safety and Legal Considerations

- Only scrape channels you have legitimate access to
- Respect Telegram's Terms of Service
- Be mindful of user privacy
- Use the data responsibly and in compliance with applicable laws
