from flask import Flask, request, render_template, jsonify, send_file
import os
import requests
import re
from datetime import datetime
import yt_dlp
import instaloader
from werkzeug.utils import secure_filename



DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)


class UniversalDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def detect_platform(self, url):
        """Detect the platform from URL and return the platform name"""
        url = url.lower()
        if 'youtube.com' in url or 'youtu.be' in url:
            return 'youtube'
        elif 'instagram.com' in url:
            return 'instagram'
        elif 'facebook.com' in url or 'fb.watch' in url:
            return 'facebook'
        elif 'twitter.com' in url or 'x.com' in url:
            return 'twitter'
        elif 'tiktok.com' in url:
            return 'tiktok'
        elif 'pinterest.com' in url:
            return 'pinterest'
        elif 'linkedin.com' in url:
            return 'linkedin'
        elif 'snapchat.com' in url:
            return 'snapchat'
        elif 'reddit.com' in url:
            return 'reddit'
        elif 'twitch.tv' in url:
            return 'twitch'
        else:
            return 'unknown'
    
    def create_safe_filename(self, filename, max_length=100):
        """Create a safe filename"""
        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip()
        if len(filename) > max_length:
            filename = filename[:max_length]
        return filename
    
    def download_youtube_content(self, url, path):
        """Download YouTube videos, shorts, playlists"""
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, '%(uploader)s - %(title)s.%(ext)s'),
                'format': 'best[height<=1080]',
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
                'ignoreerrors': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if 'entries' in info:  # Playlist
                    titles = [entry.get('title', 'Unknown') for entry in info['entries'] if entry]
                    return {
                        'status': 'success',
                        'message': f'Downloaded {len(titles)} videos from playlist',
                        'titles': titles[:5],  # Show first 5 titles
                        'type': 'playlist'
                    }
                else:  # Single video
                    return {
                        'status': 'success',
                        'message': 'YouTube content downloaded successfully!',
                        'title': info.get('title', 'Unknown'),
                        'uploader': info.get('uploader', 'Unknown'),
                        'type': 'video'
                    }
        except Exception as e:
            return {'status': 'error', 'message': f'YouTube error: {str(e)}'}
    
    def download_instagram_content(self, url, path):
        """Download Instagram posts, reels, stories, IGTV"""
        try:
            loader = instaloader.Instaloader(
                dirname_pattern=path,
                filename_pattern='{profile}_{mediaid}_{date_utc}',
                download_videos=True,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=True,
                compress_json=False
            )
            
            # Handle different Instagram URL types
            if '/stories/' in url:
                # Story URL
                username = self.extract_instagram_username(url)
                if username:
                    profile = instaloader.Profile.from_username(loader.context, username)
                    for story in loader.get_stories([profile.userid]):
                        for item in story.get_items():
                            loader.download_storyitem(item, target=username)
                    return {
                        'status': 'success',
                        'message': f'Instagram stories downloaded for {username}',
                        'type': 'stories'
                    }
            elif '/reel/' in url or '/p/' in url or '/tv/' in url:
                # Post, Reel, or IGTV
                shortcode = self.extract_instagram_shortcode(url)
                post = instaloader.Post.from_shortcode(loader.context, shortcode)
                
                loader.download_post(post, target=post.owner_username)
                
                content_type = 'reel' if post.is_video else 'post'
                if post.typename == 'GraphSidecar':
                    content_type = 'carousel'
                
                return {
                    'status': 'success',
                    'message': f'Instagram {content_type} downloaded successfully!',
                    'username': post.owner_username,
                    'caption': post.caption[:100] + '...' if post.caption and len(post.caption) > 100 else post.caption,
                    'type': content_type
                }
            else:
                # Profile URL - download recent posts
                username = self.extract_instagram_username(url)
                profile = instaloader.Profile.from_username(loader.context, username)
                
                count = 0
                for post in profile.get_posts():
                    if count >= 10:  # Limit to 10 recent posts
                        break
                    loader.download_post(post, target=username)
                    count += 1
                
                return {
                    'status': 'success',
                    'message': f'Downloaded {count} recent posts from {username}',
                    'type': 'profile'
                }
                
        except Exception as e:
            return {'status': 'error', 'message': f'Instagram error: {str(e)}'}
    
    def download_tiktok_content(self, url, path):
        """Download TikTok videos"""
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, 'TikTok_%(uploader)s_%(title)s.%(ext)s'),
                'format': 'best',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {
                    'status': 'success',
                    'message': 'TikTok video downloaded successfully!',
                    'title': info.get('title', 'TikTok Video'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'type': 'video'
                }
        except Exception as e:
            return {'status': 'error', 'message': f'TikTok error: {str(e)}'}
    
    def download_twitter_content(self, url, path):
        """Download Twitter/X videos, images, threads"""
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, 'Twitter_%(uploader)s_%(title)s.%(ext)s'),
                'writesubtitles': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {
                    'status': 'success',
                    'message': 'Twitter content downloaded successfully!',
                    'title': info.get('title', 'Twitter Content'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'type': 'tweet'
                }
        except Exception as e:
            return {'status': 'error', 'message': f'Twitter error: {str(e)}'}
    
    def download_facebook_content(self, url, path):
        """Download Facebook videos, posts"""
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, 'Facebook_%(title)s.%(ext)s'),
                'format': 'best',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {
                    'status': 'success',
                    'message': 'Facebook content downloaded successfully!',
                    'title': info.get('title', 'Facebook Content'),
                    'type': 'video'
                }
        except Exception as e:
            return {'status': 'error', 'message': f'Facebook error: {str(e)}'}
    
    def download_reddit_content(self, url, path):
        """Download Reddit videos, images, gifs"""
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, 'Reddit_%(title)s.%(ext)s'),
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {
                    'status': 'success',
                    'message': 'Reddit content downloaded successfully!',
                    'title': info.get('title', 'Reddit Post'),
                    'type': 'post'
                }
        except Exception as e:
            return {'status': 'error', 'message': f'Reddit error: {str(e)}'}
    
    def download_generic_content(self, url, path):
        """Download from any supported platform using yt-dlp"""
        try:
            ydl_opts = {
                'outtmpl': os.path.join(path, '%(extractor)s_%(title)s.%(ext)s'),
                'format': 'best',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {
                    'status': 'success',
                    'message': 'Content downloaded successfully!',
                    'title': info.get('title', 'Unknown'),
                    'extractor': info.get('extractor', 'Unknown'),
                    'type': 'media'
                }
        except Exception as e:
            return {'status': 'error', 'message': f'Download error: {str(e)}'}
    
    def extract_instagram_shortcode(self, url):
        """Extract shortcode from Instagram URL"""
        patterns = [
            r'/p/([^/?]+)',
            r'/reel/([^/?]+)',
            r'/tv/([^/?]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def extract_instagram_username(self, url):
        """Extract username from Instagram URL"""
        match = re.search(r'instagram\.com/([^/?]+)', url)
        if match:
            return match.group(1)
        return None
    
    def download_content(self, url, custom_path=None):
        """Main download function"""
        path = custom_path or DOWNLOAD_DIR
        platform = self.detect_platform(url)
        
        # Create timestamped folder for this download
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        download_folder = os.path.join(path, f"{platform}_{timestamp}")
        os.makedirs(download_folder, exist_ok=True)
        
        try:
            if platform == 'youtube':
                return self.download_youtube_content(url, download_folder)
            elif platform == 'instagram':
                return self.download_instagram_content(url, download_folder)
            elif platform == 'tiktok':
                return self.download_tiktok_content(url, download_folder)
            elif platform == 'twitter':
                return self.download_twitter_content(url, download_folder)
            elif platform == 'facebook':
                return self.download_facebook_content(url, download_folder)
            elif platform == 'reddit':
                return self.download_reddit_content(url, download_folder)
            else:
                # Try generic download for other platforms
                return self.download_generic_content(url, download_folder)
                
        except Exception as e:
            return {'status': 'error', 'message': f'Unexpected error: {str(e)}'}
