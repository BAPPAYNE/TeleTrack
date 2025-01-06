import asyncio
import sqlite3
from telethon import TelegramClient, functions, types, errors
import re
import spacy
from fuzzywuzzy import fuzz
import argparse

# Messages Database setup
conn_messages = sqlite3.connect('telegram_messages.db')
cursor_messages = conn_messages.cursor()
cursor_messages.execute('''CREATE TABLE IF NOT EXISTS messages
                           (id INTEGER PRIMARY KEY, channel TEXT, sender_id INTEGER, sender_name TEXT, message TEXT)''')

# Channels Database setup
conn_channels = sqlite3.connect('telegram_channels.db')
cursor_channels = conn_channels.cursor()
cursor_channels.execute('''CREATE TABLE IF NOT EXISTS channels
                           (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id INTEGER UNIQUE, channel_name TEXT, status TEXT)''')

# Replace these with your own values
api_id = 'YOUR_API'
api_hash = 'YOUR_HASH'
phone = 'YOUR_PHONE'
client = TelegramClient('session_name', api_id, api_hash)

# Load the spaCy model for NLP
nlp = spacy.load("en_core_web_sm")

# Default keywords for initial search
DEFAULT_CHANNEL_KEYWORDS = [
    'party', 'supplies', 'research chemicals', 'pharma', 'meds',
    'buy drugs', 'sell drugs', 'LSD', 'MDMA', 'cocaine', 'heroin',
    'ecstasy', 'meth', 'drugstore', 'online pharmacy', 'illegal drugs',
    'psychedelics', 'narcotics', 'recreational drugs', 'drug deals',
    'fashion', 'music', 'sports', 'news', 'tech', 'gaming',
    'movies', 'travel', 'food', 'lifestyle', 'fitness', 'education'
]

# Fuzzy matching threshold
FUZZY_MATCH_THRESHOLD = 70

def contains_keywords(text, keywords):
    return any(keyword.lower() in text.lower() for keyword in keywords)

def fuzzy_contains_keywords(text, keywords):
    return any(fuzz.partial_ratio(keyword.lower(), text.lower()) > FUZZY_MATCH_THRESHOLD for keyword in keywords)

def analyze_message_content(text):
    doc = nlp(text)
    return any(ent.label_ for ent in doc.ents)

class RateLimitQueue:
    def __init__(self, rate_limit, interval):
        self.queue = asyncio.Queue()
        self.rate_limit = rate_limit
        self.interval = interval

    async def add_task(self, task):
        await self.queue.put(task)

    async def worker(self):
        while True:
            task = await self.queue.get()
            await task()
            self.queue.task_done()
            await asyncio.sleep(self.interval)

    def start(self):
        for _ in range(self.rate_limit):
            asyncio.create_task(self.worker())

async def monitor_channel(channel, message_keywords):
    try:
        print(f"Attempting to join channel: {channel.title}")
        await client(functions.channels.JoinChannelRequest(channel))
        print(f"Joined channel: {channel.title}")

        contains_keyword_content = False

        async for message in client.iter_messages(channel, limit=100):
            if contains_keywords(message.text or '', message_keywords) or fuzzy_contains_keywords(message.text or '', message_keywords) or analyze_message_content(message.text or ''):
                contains_keyword_content = True
                sender_id = message.sender_id
                sender_name = ''
                if sender_id:
                    sender = await client.get_entity(sender_id)
                    if isinstance(sender, types.User):
                        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                    else:
                        sender_name = sender.title if hasattr(sender, 'title') else ''
                cursor_messages.execute("INSERT INTO messages (channel, sender_id, sender_name, message) VALUES (?, ?, ?, ?)",
                                        (channel.title, sender_id, sender_name, message.text))
                conn_messages.commit()
                print(f"Saved message from channel: {channel.title}, sender: {sender_name}")

            # Extract mentions and links to other channels
            if message.entities:
                for entity in message.entities:
                    if isinstance(entity, types.MessageEntityMention):
                        mention = message.text[entity.offset:entity.offset + entity.length]
                        if mention.startswith('@'):
                            mentioned_channel = mention[1:]
                            try:
                                mentioned_channel_entity = await client.get_entity(mentioned_channel)
                                if isinstance(mentioned_channel_entity, types.Channel):
                                    await rate_limit_queue.add_task(lambda: monitor_channel(mentioned_channel_entity, message_keywords))
                                    print(f"Found and added mentioned channel: {mentioned_channel_entity.title}")
                            except Exception as e:
                                print(f"Failed to get entity for mention {mention}: {e}")

            # Extract links to other channels from text
            links = re.findall(r'(https?://t\.me/[\w_]+)', message.text or '')
            for link in links:
                try:
                    linked_channel_entity = await client.get_entity(link)
                    if isinstance(linked_channel_entity, types.Channel):
                        await rate_limit_queue.add_task(lambda: monitor_channel(linked_channel_entity, message_keywords))
                        print(f"Found and added linked channel: {linked_channel_entity.title}")
                except Exception as e:
                    print(f"Failed to get entity for link {link}: {e}")

        # Leaving channel after processing
        await client(functions.channels.LeaveChannelRequest(channel))
        print(f"Left channel: {channel.title}")

        # Correctly setting status
        status = 'involved' if contains_keyword_content else 'clean'
        cursor_channels.execute('''INSERT INTO channels (channel_id, channel_name, status) 
                                   VALUES (?, ?, ?) 
                                   ON CONFLICT(channel_id) DO UPDATE SET status = ?''',
                                (channel.id, channel.title, status, status))
        conn_channels.commit()
        print(f"Channel status updated: {channel.title} - {status}")

    except errors.ChannelPrivateError:
        print(f"Channel {channel.title} is private or restricted. Skipping.")
    except errors.PeerIdInvalidError:
        print(f"Invalid channel ID for {channel.title}. Skipping.")
    except errors.FloodWaitError as e:
        print(f"Rate limit exceeded. Waiting for {e.seconds} seconds.")
        await asyncio.sleep(e.seconds)
    except errors.RPCError as e:
        print(f"RPC Error while processing channel {channel.title}: {e}")

async def main():
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Process keywords for searching channels and messages.")
    parser.add_argument(
        '--channel_keywords', 
        type=str, 
        nargs='+', 
        help='Keywords to search for channels', 
        default=[]
    )
    parser.add_argument(
        '--message_keywords', 
        type=str, 
        nargs='+', 
        required=True, 
        help='Keywords to search for in messages'
    )
    
    args = parser.parse_args()
    channel_keywords = args.channel_keywords if args.channel_keywords else DEFAULT_CHANNEL_KEYWORDS
    global message_keywords
    message_keywords = set(args.message_keywords)

    await client.start(phone)

    global rate_limit_queue 
    rate_limit_queue = RateLimitQueue(rate_limit=20, interval=3)
    rate_limit_queue.start()

    while True:
        for keyword in channel_keywords:
            try:
                result = await client(functions.contacts.SearchRequest(
                    q=keyword,  # Search keyword
                    limit=10  # Number of channels to search in each iteration
                ))

                for chat in result.chats:
                    if isinstance(chat, types.Channel):
                        channel = chat

                        cursor_channels.execute("SELECT status FROM channels WHERE channel_id = ?", (channel.id,))
                        row = cursor_channels.fetchone()
                        if row:
                            print(f"Channel {channel.title} already processed with status: {row[0]}")
                            continue

                        print(f'Found channel: {channel.title}')
                        await rate_limit_queue.add_task(lambda: monitor_channel(channel, message_keywords))

            except errors.FloodWaitError as e:
                print(f"Rate limit exceeded during search. Waiting for {e.seconds} seconds.")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"Unexpected error during search: {e}")

        await asyncio.sleep(60)  # Wait for 1 minute before the next search iteration

    print("Finished collecting messages.")

    cursor_messages.execute("SELECT channel, sender_id, sender_name, message FROM messages")
    rows = cursor_messages.fetchall()
    for row in rows:
        channel, sender_id, sender_name, message = row
        print(f'\nChannel: {channel}')
        print(f'Sender ID: {sender_id}, Sender Name: {sender_name}')
        print(f'Message: {message}')

with client:
    client.loop.run_until_complete(main())
