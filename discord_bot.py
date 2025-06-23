import discord
from discord.ext import commands
import requests
import json
import re
from urllib.parse import urlparse, parse_qs

# Load config
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=config['discord']['command_prefix'], intents=intents)

API_BASE = f"http://{config['server']['host']}:{config['server']['port']}"

def is_youtube_url(url):
    """Check if URL is a valid YouTube URL"""
    youtube_regex = re.compile(
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    return youtube_regex.match(url) is not None

@bot.event
async def on_ready():
    print(f'🎵 {bot.user} is ready to rock! 🎵')

@bot.command(name='play')
async def play(ctx, *, url):
    """Add a song to the queue"""
    if not is_youtube_url(url):
        await ctx.send("❌ กรุณาใส่ลิงก์ YouTube ที่ถูกต้อง")
        return
    
    try:
        # Send processing message
        processing_msg = await ctx.send(f"⏳ Processing...")
        
        # Add to queue via API
        response = requests.post(f"{API_BASE}/add_song", json={"url": url})
        data = response.json()
        
        if response.status_code == 200:
            await processing_msg.edit(content=f"✅ Added to queue: **{data['title']}**")
        else:
            await processing_msg.edit(content=f"❌ Error: {data.get('error', 'Unknown error')}")
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name='skip')
async def skip(ctx):
    """Skip the current song"""
    try:
        response = requests.post(f"{API_BASE}/skip")
        if response.status_code == 200:
            await ctx.send("⏭️ เพลงถัดไป!")
        else:
            await ctx.send("❌ ไม่สามารถข้ามเพลงได้")
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name='pause')
async def pause(ctx):
    """Pause the current song"""
    try:
        response = requests.post(f"{API_BASE}/pause")
        if response.status_code == 200:
            await ctx.send("⏸️ พักเพลง")
        else:
            await ctx.send("❌ ไม่สามารถพักเพลงได้")
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name='resume')
async def resume(ctx):
    """Resume the current song"""
    try:
        response = requests.post(f"{API_BASE}/resume")
        if response.status_code == 200:
            await ctx.send("▶️ เล่นต่อ")
        else:
            await ctx.send("❌ ไม่สามารถเล่นต่อได้")
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name='volume')
async def volume(ctx, vol: int):
    """Set volume (0-100)"""
    if not 0 <= vol <= 100:
        await ctx.send("❌ ระดับเสียงต้องอยู่ระหว่าง 0-100")
        return
    
    try:
        response = requests.post(f"{API_BASE}/volume", json={"volume": vol})
        if response.status_code == 200:
            await ctx.send(f"🔊 ตั้งระดับเสียงเป็น {vol}%")
        else:
            await ctx.send("❌ ไม่สามารถปรับระดับเสียงได้")
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name='np')
async def now_playing(ctx):
    """Show current playing and queue"""
    try:
        response = requests.get(f"{API_BASE}/status")
        data = response.json()
        
        if response.status_code == 200:
            msg = "🎵 **Now Playing:**\n"
            if data['current_song']:
                msg += f"▶️ {data['current_song']['title']}\n\n"
            else:
                msg += "ไม่มีเพลงที่กำลังเล่น\n\n"
            
            if data['queue']:
                msg += "📋 **Queue:**\n"
                for i, song in enumerate(data['queue'][:5], 1):
                    msg += f"{i}. {song['title']}\n"
                if len(data['queue']) > 5:
                    msg += f"...และอีก {len(data['queue']) - 5} เพลง"
            else:
                msg += "📋 **Queue:** ว่าง"
            
            await ctx.send(msg)
        else:
            await ctx.send("❌ ไม่สามารถดึงข้อมูลได้")
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

if __name__ == "__main__":
    bot.run(config['discord']['token'])