from flask import Flask, request, render_template, jsonify, Response, stream_with_context
import os
import requests
import yt_dlp
import static_ffmpeg
from werkzeug.utils import secure_filename
from urllib.parse import quote

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Initialize FFmpeg
static_ffmpeg.add_paths()

class UniversalDownloader:
    def __init__(self):
        self.session = requests.Session()
        # Modern User-Agent to prevent "damaged file" blocks from Meta/Instagram
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
    def get_info(self, url):
        """Extracts metadata with a deep-search for the best MP4 stream."""
        ydl_opts = {
            # Priority: 1. Merged MP4, 2. Best Video + Best Audio, 3. Any best format
            'format': 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            # 'cookiefile': 'cookies.txt', # Highly recommended for Instagram/FB
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

downloader = UniversalDownloader()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def handle_ui_request():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'status': 'error', 'message': 'URL is required'}), 400

        info = downloader.get_info(url)
        
        return jsonify({
            'status': 'success',
            'title': info.get('title', 'Video'),
            'download_url': f"/stream?url={quote(url)}" 
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stream', methods=['GET'])
def stream_to_client():
    url = request.args.get('url')
    if not url:
        return "URL Required", 400

    try:
        info = downloader.get_info(url)
        
        # --- THE FIX: URL HUNTING LOGIC ---
        media_url = None
        
        # 1. Check direct URL
        if info.get('url'):
            media_url = info['url']
        # 2. Check entries (common for FB/Insta)
        elif info.get('entries'):
            media_url = info['entries'][0].get('url')
        # 3. Check requested_formats (common for YT)
        elif info.get('requested_formats'):
            # If YouTube separates them, we pick the one that contains both or the first video
            media_url = info['requested_formats'][0].get('url')
        
        if not media_url:
            return "Could not find a valid streamable URL for this media.", 404

        filename = secure_filename(f"{info.get('title', 'video')}.mp4")
        
        # Setup headers for the outbound request to the platform
        request_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        if info.get('http_headers'):
            request_headers.update(info['http_headers'])

        # Start the stream from the platform
        platform_req = requests.get(media_url, stream=True, headers=request_headers, timeout=60)
        platform_req.raise_for_status()

        def generate():
            # Use 64KB chunks to keep the pipe active and prevent timeouts
            for chunk in platform_req.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk

        # Build the response back to the user's browser
        response = Response(
            stream_with_context(generate()),
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Content-Type": "video/mp4",
                "X-Content-Type-Options": "nosniff"
            }
        )

        # Content-Length is vital so the browser doesn't think the file is "damaged"
        if platform_req.headers.get('Content-Length'):
            response.headers["Content-Length"] = platform_req.headers.get('Content-Length')

        return response

    except Exception as e:
        return f"Streaming Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)