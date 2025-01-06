# TeleTrack

TeleTrack monitors Telegram channels for specific keywords in channel descriptions and message content. It uses the Telethon library to interact with Telegram's API and stores relevant data in SQLite databases.

## Features

- Search for channels using user-defined keywords or default keywords.
- Monitor messages in channels for specific keywords.
- Save messages and channel information to SQLite databases.
- Rate-limited task execution to avoid exceeding Telegram's API limits.
- Uses spaCy and fuzzy matching for advanced keyword detection.

## Prerequisites

- Python 3.7+
- Telethon
- spaCy
- fuzzywuzzy
- SQLite

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/BAPPAYNE/TeleScan.git
   cd TeleTrack
   ```
2. **Install the required packages:**
   ```bash
   pip install telethon spacy fuzzywuzzy && python -m spacy download en_core_web_sm
   ```
   **Set up your Telegram API credentials:**

   Replace the placeholders in the script with your own telegram api_id, api_hash, and phone number.

   ```python
   api_id = 'YOUR_API'
   api_hash = 'YOUR_HASH'
   phone = 'YOUR_PHONE'
   ```

## Usage**:</br>
   You can run the script using the following command:
    ```bash
    python TeleTrack.py --message_keywords <keyword1> <keyword2> [--channel_keywords <keyword1> <keyword2>]
    ```
     `--message_keywords`: List of keywords to search for in messages (mandatory).
     `--channel_keywords`: List of keywords to search for channels (optional). If not provided, default keywords will be used.

   **Databases**

     telegram_messages.db: Stores extracted messages with columns for channel name, sender ID, sender name, and message content.
     telegram_channels.db: Stores channel information with columns for channel ID, name, and status.

   **Troubleshooting**
   
     Rate Limit Errors: If you encounter rate limit errors, the script will wait before retrying. Ensure you don't exceed the rate limits.
     Private Channels: If a channel is private or restricted, it will be skipped.

## Contributing
   Feel free to submit issues or pull requests if you have suggestions or improvements.

## License
   This project is licensed under the MIT License - see the LICENSE file for details.

