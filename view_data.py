import argparse
import pymysql
from tabulate import tabulate
import sys

class DataViewer:
    def __init__(self, db_config):
        self.db_config = db_config
        self.connection = None
        
    def connect(self):
        """Connect to the database"""
        try:
            self.connection = pymysql.connect(**self.db_config)
            self.connection.cursor().execute("USE telescrape")
            return True
        except Exception as e:
            print(f"Error connecting to database: {e}")
            return False
    
    def get_summary(self):
        """Get overall summary statistics"""
        cursor = self.connection.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Total channels
        cursor.execute("SELECT COUNT(*) FROM channels")
        total_channels = cursor.fetchone()[0]
        
        # Total user-channel relationships
        cursor.execute("SELECT COUNT(*) FROM user_channel")
        total_relationships = cursor.fetchone()[0]
        
        # Users with username
        cursor.execute("SELECT COUNT(*) FROM users WHERE username IS NOT NULL")
        users_with_username = cursor.fetchone()[0]
        
        # Bots
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_bot = TRUE")
        bot_count = cursor.fetchone()[0]
        
        # Verified users
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_verified = TRUE")
        verified_count = cursor.fetchone()[0]
        
        print("\n=== SUMMARY ===")
        print(f"Total unique users: {total_users}")
        print(f"Total channels scraped: {total_channels}")
        print(f"Total user-channel relationships: {total_relationships}")
        print(f"Users with username: {users_with_username}")
        print(f"Bot accounts: {bot_count}")
        print(f"Verified accounts: {verified_count}")
    
    def list_channels(self):
        """List all channels with user counts"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            SELECT 
                c.title,
                c.username,
                c.participants_count,
                COUNT(uc.user_id) as scraped_users,
                c.is_megagroup,
                c.scraped_at
            FROM channels c
            LEFT JOIN user_channel uc ON c.id = uc.channel_id
            GROUP BY c.id
            ORDER BY scraped_users DESC
        """)
        
        channels = cursor.fetchall()
        
        print("\n=== CHANNELS ===")
        headers = ["Title", "Username", "Total Members", "Scraped Users", "Type", "Scraped At"]
        table_data = []
        
        for channel in channels:
            table_data.append([
                channel[0][:30] + "..." if len(channel[0]) > 30 else channel[0],
                f"@{channel[1]}" if channel[1] else "N/A",
                channel[2] if channel[2] else "N/A",
                channel[3],
                "Megagroup" if channel[4] else "Channel",
                channel[5].strftime("%Y-%m-%d %H:%M")
            ])
        
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    def search_users(self, query):
        """Search for users by username or name"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            SELECT 
                u.user_id,
                u.username,
                u.first_name,
                u.last_name,
                u.is_bot,
                u.is_verified,
                COUNT(uc.channel_id) as channel_count
            FROM users u
            LEFT JOIN user_channel uc ON u.id = uc.user_id
            WHERE u.username LIKE %s 
               OR u.first_name LIKE %s 
               OR u.last_name LIKE %s
            GROUP BY u.id
            LIMIT 50
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))
        
        users = cursor.fetchall()
        
        print(f"\n=== SEARCH RESULTS FOR '{query}' ===")
        if not users:
            print("No users found.")
            return
            
        headers = ["User ID", "Username", "First Name", "Last Name", "Bot", "Verified", "Channels"]
        table_data = []
        
        for user in users:
            table_data.append([
                user[0],
                f"@{user[1]}" if user[1] else "N/A",
                user[2] if user[2] else "N/A",
                user[3] if user[3] else "N/A",
                "Yes" if user[4] else "No",
                "Yes" if user[5] else "No",
                user[6]
            ])
        
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    def show_channel_users(self, channel_name):
        """Show users from a specific channel"""
        cursor = self.connection.cursor()
        
        # First find the channel
        cursor.execute("""
            SELECT id, title FROM channels 
            WHERE title LIKE %s OR username LIKE %s
            LIMIT 1
        """, (f"%{channel_name}%", f"%{channel_name}%"))
        
        channel = cursor.fetchone()
        if not channel:
            print(f"Channel '{channel_name}' not found.")
            return
        
        channel_id, channel_title = channel
        
        cursor.execute("""
            SELECT 
                u.user_id,
                u.username,
                u.first_name,
                u.last_name,
                u.is_bot,
                u.is_verified,
                uc.scraped_at
            FROM users u
            JOIN user_channel uc ON u.id = uc.user_id
            WHERE uc.channel_id = %s
            LIMIT 100
        """, (channel_id,))
        
        users = cursor.fetchall()
        
        print(f"\n=== USERS IN '{channel_title}' (showing first 100) ===")
        headers = ["User ID", "Username", "First Name", "Last Name", "Bot", "Verified", "Scraped At"]
        table_data = []
        
        for user in users:
            table_data.append([
                user[0],
                f"@{user[1]}" if user[1] else "N/A",
                user[2] if user[2] else "N/A",
                user[3] if user[3] else "N/A",
                "Yes" if user[4] else "No",
                "Yes" if user[5] else "No",
                user[6].strftime("%Y-%m-%d %H:%M")
            ])
        
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    def export_users(self, output_file):
        """Export all users to CSV"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            SELECT 
                u.user_id,
                u.access_hash,
                u.username,
                u.first_name,
                u.last_name,
                u.phone,
                u.is_bot,
                u.is_verified,
                u.is_restricted,
                u.is_scam,
                u.is_fake,
                GROUP_CONCAT(c.title SEPARATOR '; ') as channels
            FROM users u
            LEFT JOIN user_channel uc ON u.id = uc.user_id
            LEFT JOIN channels c ON c.id = uc.channel_id
            GROUP BY u.id
        """)
        
        users = cursor.fetchall()
        
        import csv
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'User ID', 'Access Hash', 'Username', 'First Name', 'Last Name',
                'Phone', 'Is Bot', 'Is Verified', 'Is Restricted', 'Is Scam', 
                'Is Fake', 'Channels'
            ])
            writer.writerows(users)
        
        print(f"Exported {len(users)} users to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='View Telegram scraper data')
    
    # Commands
    parser.add_argument('--summary', action='store_true', help='Show summary statistics')
    parser.add_argument('--channels', action='store_true', help='List all channels')
    parser.add_argument('--search', type=str, help='Search for users')
    parser.add_argument('--channel', type=str, help='Show users from specific channel')
    parser.add_argument('--export', type=str, help='Export users to CSV file')
    
    args = parser.parse_args()
    
    # Hardcoded database configuration
    db_config = {
        'host': '89.28.236.32',
        'user': 'hedinn',
        'password': 'Fxp.123456',
        'port': 3306,
        'charset': 'utf8mb4'
    }
    
    viewer = DataViewer(db_config)
    
    if not viewer.connect():
        sys.exit(1)
    
    # Execute requested command
    if args.summary or not any([args.channels, args.search, args.channel, args.export]):
        viewer.get_summary()
    
    if args.channels:
        viewer.list_channels()
    
    if args.search:
        viewer.search_users(args.search)
    
    if args.channel:
        viewer.show_channel_users(args.channel)
    
    if args.export:
        viewer.export_users(args.export)
    
    if viewer.connection:
        viewer.connection.close()

if __name__ == '__main__':
    main()
