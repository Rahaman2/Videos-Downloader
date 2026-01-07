from flask import Flask, request, render_template, jsonify, Response, stream_with_context
import os
import requests
import yt_dlp
import static_ffmpeg
import subprocess
from werkzeug.utils import secure_filename
from urllib.parse import quote

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-social-downloader-key'

# Initialize FFmpeg - Crucial for YouTube playback fix
static_ffmpeg.add_paths()

class UniversalDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
    def detect_platform(self, url):
        url = url.lower()
        if 'youtube.com' in url or 'youtu.be' in url: return 'youtube'
        if 'instagram.com' in url: return 'instagram'
        if 'facebook.com' in url or 'fb.watch' in url: return 'facebook'
        return 'generic'

    def get_info(self, url):
        ydl_opts = {
            # YouTube needs the + merge, others just take 'best'
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
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

    platform = downloader.detect_platform(url)

    try:
        info = downloader.get_info(url)
        filename = secure_filename(f"{info.get('title', 'video')}.mp4")

        # ==========================================
        # ENGINE A: YOUTUBE (Merging Audio/Video)
        # ==========================================
        if platform == 'youtube':
            def generate_yt():
                # We use -o - to pipe the output through stdout
                # We use --merge-output-format mp4 to ensure it's playable
                proc = subprocess.Popen(
                    [
                        'yt-dlp', 
                        '-o', '-', 
                        '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                        '--merge-output-format', 'mp4',
                        '--no-playlist',
                        url
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )
                while True:
                    chunk = proc.stdout.read(1024 * 64) # 64KB chunks
                    if not chunk:
                        break
                    yield chunk
                proc.terminate()

            return Response(stream_with_context(generate_yt()), headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Content-Type": "video/mp4"
            })

        # ==========================================
        # ENGINE B: FB / INSTA (Direct Pipe)
        # ==========================================
        else:
            # Re-run the URL hunting logic to ensure we don't get 'None'
            media_url = info.get('url')
            if not media_url and info.get('entries'):
                media_url = info['entries'][0].get('url')
            elif not media_url and info.get('requested_formats'):
                media_url = info['requested_formats'][0].get('url')

            # We use the same headers that yt-dlp uses to satisfy security checks
            request_headers = info.get('http_headers', {})
            req = requests.get(media_url, stream=True, headers=request_headers, timeout=60)
            
            def generate_direct():
                for chunk in req.iter_content(chunk_size=65536):
                    if chunk: yield chunk

            response = Response(stream_with_context(generate_direct()), headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Content-Type": "video/mp4"
            })
            
            # Carry over the file size so the browser can show a progress bar
            if req.headers.get('Content-Length'):
                response.headers["Content-Length"] = req.headers.get('Content-Length')
            
            return response

    except Exception as e:
        return f"Streaming Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)