#!/usr/bin/env python3
"""
Main runner for the Discord Music Bot
Runs both the Discord bot and web server simultaneously
"""

import threading
import time
import json
import os
import sys
import signal
from datetime import datetime

# Import the bot and server modules
try:
    from discord_bot import bot, config as bot_config
    from web_server import app, socketio, config as server_config
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    print("Make sure discord_bot.py and web_server.py are in the same directory")
    sys.exit(1)

class MusicBotManager:
    def __init__(self):
        self.discord_thread = None
        self.web_thread = None
        self.running = False
        
    def start_discord_bot(self):
        """Start the Discord bot in a separate thread"""
        try:
            print(f"🤖 Starting Discord bot...")
            bot.run(bot_config['discord']['token'])
        except Exception as e:
            print(f"❌ Discord bot error: {e}")
    
    def start_web_server(self):
        """Start the web server in a separate thread"""
        try:
            print(f"🌐 Starting web server on {server_config['server']['host']}:{server_config['server']['port']}")
            socketio.run(
                app, 
                host=server_config['server']['host'], 
                port=server_config['server']['port'], 
                debug=False,  # Set to False to avoid conflicts
                use_reloader=False  # Disable reloader to prevent issues with threading
            )
        except Exception as e:
            print(f"❌ Web server error: {e}")
    
    def start(self):
        """Start both services"""
        print("🎵 Starting Music Bot Manager...")
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        # Validate config
        if not self.validate_config():
            return
        
        self.running = True
        
        # Start web server in a separate thread
        self.web_thread = threading.Thread(target=self.start_web_server, daemon=True)
        self.web_thread.start()
        
        # Give web server time to start
        time.sleep(2)
        
        # Start Discord bot in a separate thread
        self.discord_thread = threading.Thread(target=self.start_discord_bot, daemon=True)
        self.discord_thread.start()
        
        print("✅ Both services started successfully!")
        print("=" * 50)
        print("🎵 Music Bot is now running!")
        print(f"🌐 Web interface: http://{server_config['server']['host']}:{server_config['server']['port']}")
        print(f"🤖 Discord bot: Ready to accept commands")
        print("💡 Press Ctrl+C to stop")
        print("=" * 50)
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop both services"""
        print("\n🛑 Stopping Music Bot Manager...")
        self.running = False
        
        # Note: Discord.py and Flask-SocketIO handle cleanup automatically
        # when the main process exits
        
        print("✅ Music Bot Manager stopped")
        sys.exit(0)
    
    def validate_config(self):
        """Validate configuration"""
        try:
            # Check if config.json exists
            if not os.path.exists('config.json'):
                print("❌ config.json not found!")
                print("Please create a config.json file with the required settings.")
                return False
            
            # Check Discord token
            if not bot_config.get('discord', {}).get('token'):
                print("❌ Discord token not found in config.json!")
                print("Please add your Discord bot token to config.json")
                return False
            
            # Check required directories
            download_folder = server_config.get('music', {}).get('download_folder', 'downloads')
            if not os.path.exists(download_folder):
                os.makedirs(download_folder, exist_ok=True)
                print(f"📁 Created download folder: {download_folder}")
            
            print("✅ Configuration validated")
            return True
            
        except Exception as e:
            print(f"❌ Configuration validation error: {e}")
            return False

def signal_handler(signum, frame):
    """Handle system signals"""
    print(f"\n🔄 Received signal {signum}")
    manager.stop()

def main():
    """Main entry point"""
    print("🎵 Discord Music Bot Manager")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ is required")
        sys.exit(1)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start manager
    global manager
    manager = MusicBotManager()
    manager.start()

if __name__ == "__main__":
    main()