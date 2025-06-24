from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import yt_dlp
import os
import json
import threading
import time
from collections import deque
import hashlib

# Load config
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'music_server_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
music_queue = deque()
current_song = None
is_playing = False
is_paused = False
volume = config['music']['default_volume']
downloaded_songs = {}  # Cache for downloaded songs

# Ensure download folder exists
os.makedirs(config['music']['download_folder'], exist_ok=True)

class MusicManager:
    def __init__(self):
        self.ydl_opts = {
            'format': config['youtube']['quality'],
            'outtmpl': os.path.join(config['music']['download_folder'], '%(id)s.%(ext)s'),
            'noplaylist': True,
        }
    
    def get_video_id(self, url):
        """Extract video ID from YouTube URL"""
        ydl = yt_dlp.YoutubeDL({'quiet': True})
        try:
            info = ydl.extract_info(url, download=False)
            return info['id']
        except:
            return None
    
    def get_song_info(self, url):
        """Get song information without downloading"""
        ydl = yt_dlp.YoutubeDL({'quiet': True})
        try:
            info = ydl.extract_info(url, download=False)
            return {
                'id': info['id'],
                'title': info['title'],
                'duration': info.get('duration', 0),
                'url': url
            }
        except Exception as e:
            raise Exception(f"Cannot get video info: {str(e)}")
    
    def download_song(self, song_info):
        """Download song if not already downloaded"""
        video_id = song_info['id']
        
        # Check if already downloaded
        for ext in ['mp3', 'webm', 'm4a', 'mp4']:
            file_path = os.path.join(config['music']['download_folder'], f"{video_id}.{ext}")
            if os.path.exists(file_path):
                song_info['file_path'] = file_path
                downloaded_songs[video_id] = song_info
                return song_info
        
        # Download the song
        ydl = yt_dlp.YoutubeDL(self.ydl_opts)
        try:
            ydl.download([song_info['url']])
            
            # Find the downloaded file
            for ext in ['mp3', 'webm', 'm4a', 'mp4']:
                file_path = os.path.join(config['music']['download_folder'], f"{video_id}.{ext}")
                if os.path.exists(file_path):
                    song_info['file_path'] = file_path
                    downloaded_songs[video_id] = song_info
                    self.manage_storage()
                    return song_info
            
            raise Exception("Downloaded file not found")
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")
    
    def manage_storage(self):
        """Manage storage by removing old files if exceeds max_preload"""
        if len(downloaded_songs) > config['music']['max_preload']:
            # Remove oldest files
            to_remove = len(downloaded_songs) - config['music']['max_preload']
            oldest_songs = list(downloaded_songs.keys())[:to_remove]
            
            for video_id in oldest_songs:
                song = downloaded_songs[video_id]
                if 'file_path' in song and os.path.exists(song['file_path']):
                    os.remove(song['file_path'])
                del downloaded_songs[video_id]

music_manager = MusicManager()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/add_song', methods=['POST'])
def add_song_web():
    """Add song via web interface"""
    return add_song()

@app.route('/add_song', methods=['POST'])
def add_song():
    """Add song to queue"""
    global music_queue
    
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        # Get song info
        song_info = music_manager.get_song_info(url)
        
        # Check if already in queue
        for song in music_queue:
            if song['id'] == song_info['id']:
                return jsonify({'error': 'Song already in queue'}), 400
        
        # Add to queue
        music_queue.append(song_info)
        
        # ถ้ายังไม่มีเพลงกำลังเล่น ให้ดึงเพลงจากคิวมาเล่นทันที
        global current_song, is_playing
        if current_song is None and len(music_queue) > 0:
            current_song = music_queue.popleft()
            is_playing = True
            # ถ้าไฟล์ถูกดาวน์โหลดแล้ว ให้เติม file_path
            if current_song['id'] in downloaded_songs:
                current_song = downloaded_songs[current_song['id']]
            socketio.emit('status_updated', get_status_data())
        
        # Notify clients
        socketio.emit('queue_updated', get_status_data())
        
        # Download in background
        threading.Thread(target=download_and_notify, args=(song_info,)).start()
        
        return jsonify({
            'success': True,
            'title': song_info['title'],
            'message': f'Added to queue: {song_info["title"]}'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def download_and_notify(song_info):
    """Download song and notify when ready"""
    try:
        music_manager.download_song(song_info)
        socketio.emit('song_ready', {'id': song_info['id'], 'title': song_info['title']})
    except Exception as e:
        socketio.emit('download_error', {'id': song_info['id'], 'error': str(e)})

@app.route('/skip', methods=['POST'])
def skip_song():
    """Skip current song"""
    global current_song, is_playing
    
    current_song = None
    is_playing = False
    
    socketio.emit('skip')
    socketio.emit('status_updated', get_status_data())
    
    return jsonify({'success': True})

@app.route('/pause', methods=['POST'])
def pause_song():
    """Pause current song"""
    global is_paused
    
    is_paused = True
    socketio.emit('pause')
    socketio.emit('status_updated', get_status_data())
    
    return jsonify({'success': True})

@app.route('/resume', methods=['POST'])
def resume_song():
    """Resume current song"""
    global is_paused
    
    is_paused = False
    socketio.emit('resume')
    socketio.emit('status_updated', get_status_data())
    
    return jsonify({'success': True})

@app.route('/volume', methods=['POST'])
def set_volume():
    """Set volume"""
    global volume
    
    try:
        data = request.get_json()
        new_volume = data.get('volume')
        
        if new_volume < 0 or new_volume > 100:
            return jsonify({'error': 'Volume must be between 0-100'}), 400
        
        volume = new_volume
        socketio.emit('volume_changed', {'volume': volume})
        socketio.emit('status_updated', get_status_data())
        
        return jsonify({'success': True, 'volume': volume})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def get_status():
    """Get current status"""
    return jsonify(get_status_data())

@app.route('/next_song')
def get_next_song():
    """Get next song in queue"""
    global music_queue, current_song, is_playing
    
    if music_queue:
        current_song = music_queue.popleft()
        is_playing = True
        
        # Check if song is downloaded
        if current_song['id'] in downloaded_songs:
            current_song = downloaded_songs[current_song['id']]
        
        socketio.emit('status_updated', get_status_data())
        
        return jsonify({
            'success': True,
            'song': current_song,
            'file_path': current_song.get('file_path')
        })
    
    return jsonify({'success': False, 'message': 'No songs in queue'})

@app.route('/audio/<video_id>')
def serve_audio(video_id):
    """Serve audio file"""
    if video_id in downloaded_songs:
        song = downloaded_songs[video_id]
        if 'file_path' in song and os.path.exists(song['file_path']):
            return send_file(song['file_path'])
    
    return jsonify({'error': 'File not found'}), 404

@app.route('/song_ended', methods=['POST'])
def song_ended():
    """Handle when song ended naturally"""
    global current_song, is_playing

    current_song = None
    is_playing = False

    # Try to play next song in queue
    if music_queue:
        current_song = music_queue.popleft()
        is_playing = True
        if current_song['id'] in downloaded_songs:
            current_song = downloaded_songs[current_song['id']]
        socketio.emit('status_updated', get_status_data())
        return jsonify({'success': True, 'song': current_song})
    else:
        socketio.emit('status_updated', get_status_data())
        return jsonify({'success': False, 'message': 'No songs in queue'})

def get_status_data():
    """Get current status data"""
    return {
        'current_song': current_song,
        'queue': list(music_queue),
        'is_playing': is_playing,
        'is_paused': is_paused,
        'volume': volume,
        'queue_length': len(music_queue)
    }

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('status_updated', get_status_data())

if __name__ == '__main__':
    socketio.run(app, host=config['server']['host'], port=config['server']['port'], debug=True)