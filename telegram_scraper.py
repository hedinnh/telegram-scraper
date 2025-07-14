import argparse
import asyncio
import pymysql
from telethon import TelegramClient
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
from telethon.errors import ChatAdminRequiredError, UserPrivacyRestrictedError
from datetime import datetime
import logging
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramScraper:
    def __init__(self, session_name, api_id, api_hash, db_config):
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        self.db_config = db_config
        self.client = None
        self.db_connection = None
        
    async def connect_telegram(self):
        """Connect to Telegram using existing session file"""
        try:
            # Use the session name provided
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.error(f"Session {self.session_name} is not authorized. Please login first.")
                return False
                
            me = await self.client.get_me()
            logger.info(f"Connected as {me.first_name} {me.last_name or ''} (@{me.username})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            return False
    
    def connect_database(self):
        """Connect to MySQL database"""
        try:
            self.db_connection = pymysql.connect(**self.db_config)
            logger.info("Connected to MySQL database")
            self.setup_database()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False
    
    def setup_database(self):
        """Create database and tables if they don't exist"""
        cursor = self.db_connection.cursor()
        
        # Create database if not exists
        cursor.execute("CREATE DATABASE IF NOT EXISTS telescrape")
        cursor.execute("USE telescrape")
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                access_hash BIGINT,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                phone VARCHAR(50),
                is_bot BOOLEAN DEFAULT FALSE,
                is_verified BOOLEAN DEFAULT FALSE,
                is_restricted BOOLEAN DEFAULT FALSE,
                is_scam BOOLEAN DEFAULT FALSE,
                is_fake BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id)
            )
        """)
        
        # Create channels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id BIGINT PRIMARY KEY,
                channel_id BIGINT NOT NULL,
                access_hash BIGINT,
                title VARCHAR(255),
                username VARCHAR(255),
                participants_count INT,
                is_megagroup BOOLEAN DEFAULT FALSE,
                is_broadcast BOOLEAN DEFAULT FALSE,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_channel_id (channel_id)
            )
        """)
        
        # Create user_channel table (many-to-many relationship)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_channel (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_channel (user_id, channel_id),
                INDEX idx_user (user_id),
                INDEX idx_channel (channel_id)
            )
        """)
        
        self.db_connection.commit()
        logger.info("Database tables created/verified")
    
    def save_user(self, user, channel_id):
        """Save user to database"""
        cursor = self.db_connection.cursor()
        
        try:
            # Insert or update user
            cursor.execute("""
                INSERT INTO users (
                    id, user_id, access_hash, username, first_name, last_name, 
                    phone, is_bot, is_verified, is_restricted, is_scam, is_fake
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    access_hash = VALUES(access_hash),
                    username = VALUES(username),
                    first_name = VALUES(first_name),
                    last_name = VALUES(last_name),
                    phone = VALUES(phone),
                    is_bot = VALUES(is_bot),
                    is_verified = VALUES(is_verified),
                    is_restricted = VALUES(is_restricted),
                    is_scam = VALUES(is_scam),
                    is_fake = VALUES(is_fake)
            """, (
                user.id,
                user.id,
                user.access_hash if hasattr(user, 'access_hash') else None,
                user.username,
                user.first_name,
                user.last_name if hasattr(user, 'last_name') else None,
                user.phone if hasattr(user, 'phone') else None,
                user.bot if hasattr(user, 'bot') else False,
                user.verified if hasattr(user, 'verified') else False,
                user.restricted if hasattr(user, 'restricted') else False,
                user.scam if hasattr(user, 'scam') else False,
                user.fake if hasattr(user, 'fake') else False
            ))
            
            # Link user to channel
            cursor.execute("""
                INSERT IGNORE INTO user_channel (user_id, channel_id)
                VALUES (%s, %s)
            """, (user.id, channel_id))
            
            self.db_connection.commit()
            
        except Exception as e:
            logger.error(f"Error saving user {user.id}: {e}")
            self.db_connection.rollback()
    
    def save_channel(self, channel):
        """Save channel information to database"""
        cursor = self.db_connection.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO channels (
                    id, channel_id, access_hash, title, username, 
                    participants_count, is_megagroup, is_broadcast
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    access_hash = VALUES(access_hash),
                    title = VALUES(title),
                    username = VALUES(username),
                    participants_count = VALUES(participants_count),
                    scraped_at = CURRENT_TIMESTAMP
            """, (
                channel.id,
                channel.id,
                channel.access_hash if hasattr(channel, 'access_hash') else None,
                channel.title,
                channel.username if hasattr(channel, 'username') else None,
                channel.participants_count if hasattr(channel, 'participants_count') else None,
                channel.megagroup if hasattr(channel, 'megagroup') else False,
                channel.broadcast if hasattr(channel, 'broadcast') else False
            ))
            
            self.db_connection.commit()
            
        except Exception as e:
            logger.error(f"Error saving channel {channel.id}: {e}")
            self.db_connection.rollback()
    
    async def scrape_channel(self, channel):
        """Scrape all members from a channel"""
        try:
            # Get channel entity
            channel_entity = await self.client.get_entity(channel)
            
            # Save channel info
            self.save_channel(channel_entity)
            
            logger.info(f"Scraping channel: {channel_entity.title} (ID: {channel_entity.id})")
            
            # Try to get participants
            offset = 0
            limit = 100
            all_participants = []
            
            while True:
                try:
                    participants = await self.client(GetParticipantsRequest(
                        channel_entity,
                        ChannelParticipantsSearch(''),
                        offset,
                        limit,
                        hash=0
                    ))
                    
                    if not participants.users:
                        break
                    
                    all_participants.extend(participants.users)
                    offset += len(participants.users)
                    
                    # Save users in batches
                    for user in participants.users:
                        self.save_user(user, channel_entity.id)
                    
                    logger.info(f"Scraped {offset} users from {channel_entity.title}")
                    
                    # Avoid hitting rate limits
                    await asyncio.sleep(1)
                    
                except ChatAdminRequiredError:
                    logger.warning(f"Admin rights required for {channel_entity.title}. Skipping...")
                    break
                    
            logger.info(f"Finished scraping {channel_entity.title}. Total users: {len(all_participants)}")
            return len(all_participants)
            
        except Exception as e:
            logger.error(f"Error scraping channel {channel}: {e}")
            return 0
    
    async def scrape_all_channels(self):
        """Scrape all channels the user is a member of"""
        try:
            # Get all dialogs (conversations)
            dialogs = await self.client.get_dialogs()
            
            channels = []
            for dialog in dialogs:
                entity = dialog.entity
                
                # Check if it's a channel or supergroup
                if hasattr(entity, 'megagroup') or hasattr(entity, 'broadcast'):
                    channels.append(entity)
            
            logger.info(f"Found {len(channels)} channels/groups to scrape")
            
            total_users = 0
            for i, channel in enumerate(channels, 1):
                logger.info(f"Processing channel {i}/{len(channels)}")
                users_count = await self.scrape_channel(channel)
                total_users += users_count
                
                # Add delay between channels
                await asyncio.sleep(2)
            
            logger.info(f"Scraping completed. Total users scraped: {total_users}")
            
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
    
    async def run(self):
        """Main execution method"""
        # Connect to Telegram
        if not await self.connect_telegram():
            return
        
        # Connect to database
        if not self.connect_database():
            await self.client.disconnect()
            return
        
        try:
            # Start scraping
            await self.scrape_all_channels()
            
        finally:
            # Clean up
            if self.db_connection:
                self.db_connection.close()
            if self.client:
                await self.client.disconnect()
            
            logger.info("Scraper finished")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', type=str, required=True, help='The username of the telegram user')
    parser.add_argument('--api_id', type=int, required=False, help='The user_id of the telegram user')
    parser.add_argument('--api_hash', type=str, required=False, help='The api_hash of the telegram user')
    
    args = parser.parse_args()
    
    # Hardcoded database configuration
    db_config = {
        'host': '89.28.236.32',
        'user': 'hedinn',
        'password': 'Fxp.123456',
        'port': 3306,
        'charset': 'utf8mb4',
        'autocommit': False
    }
    
    # Create scraper instance
    scraper = TelegramScraper(
        session_name=args.name,
        api_id=args.api_id,
        api_hash=args.api_hash,
        db_config=db_config
    )
    
    # Run the scraper
    await scraper.run()

if __name__ == '__main__':
    asyncio.run(main())
