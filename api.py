"""
RESTful API for YouTube Comment Crawler with Swagger documentation
Exposes the crawler functionality through HTTP endpoints.
"""

import os
import sys
from waitress import serve
from flask import Flask
from flask_restx import Api, Resource, fields
from flask_cors import CORS
from main import YouTubeCommentCrawler, check_api_key
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Initialize Flask app and API
app = Flask(__name__)
api = Api(app, version='1.0', title='YouTube Comment Crawler API',
          description='API for crawling YouTube comments')

# Configure CORS properly
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
app.config['CORS_HEADERS'] = 'Content-Type, Authorization'

# Define namespaces
ns = api.namespace('api', description='YouTube crawler operations')

# Define models for request/response
crawl_request = api.model('CrawlRequest', {
    'channel_id': fields.String(required=True, description='YouTube channel ID'),
    'username': fields.String(required=False, description='Filter by username'),
    'keywords': fields.List(fields.String, required=False, description='Filter by keywords'),
    'max_videos': fields.Integer(required=False, default=50, description='Maximum number of videos to crawl'),
    'max_comments': fields.Integer(required=False, default=100, description='Maximum comments per video')
})

crawl_by_username_request = api.model('CrawlByUsernameRequest', {
    'channel_username': fields.String(required=True, description='YouTube channel username'),
    'username': fields.String(required=False, description='Filter by username'),
    'keywords': fields.List(fields.String, required=False, description='Filter by keywords'),
    'max_videos': fields.Integer(required=False, default=50, description='Maximum number of videos to crawl'),
    'max_comments': fields.Integer(required=False, default=100, description='Maximum comments per video')
})

comment_model = api.model('Comment', {
    'author': fields.String(description='Comment author'),
    'text': fields.String(description='Comment text'),
    'published_at': fields.String(description='Publication date'),
    'like_count': fields.Integer(description='Number of likes')
})

crawl_response = api.model('CrawlResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'video_count': fields.Integer(description='Number of videos processed'),
    'results': fields.Raw(description='Crawled comments by video')
})

# Get API key
try:
    api_key = check_api_key()
    crawler = YouTubeCommentCrawler(api_key)
except SystemExit:
    print("Error: YouTube API key not found. Please set the YOUTUBE_API_KEY environment variable.")
    sys.exit(1)


@ns.route('/health')
class Health(Resource):
    @api.doc(description='Health check endpoint')
    def get(self):
        """Check API health status"""
        return {'status': 'ok', 'service': 'YouTube Comment Crawler API'}


@ns.route('/crawl')
class CrawlComments(Resource):
    @api.doc(description='Crawl comments from a YouTube channel')
    @api.expect(crawl_request)
    @api.marshal_with(crawl_response)
    def post(self):
        """Crawl comments from specified YouTube channel"""
        data = api.payload

        if not data or 'channel_id' not in data:
            api.abort(400, 'Missing channel_id parameter')

        # Extract parameters
        channel_id = data.get('channel_id')
        username_filter = data.get('username')
        content_keywords = data.get('keywords')
        max_videos = data.get('max_videos', 50)
        max_comments_per_video = data.get('max_comments', 100)

        # Validate parameters
        if not isinstance(max_videos, int) or max_videos <= 0:
            api.abort(400, 'max_videos must be a positive integer')
        
        if not isinstance(max_comments_per_video, int) or max_comments_per_video <= 0:
            api.abort(400, 'max_comments must be a positive integer')

        try:
            results = crawler.crawl_channel_comments(
                channel_id=channel_id,
                username_filter=username_filter,
                content_keywords=content_keywords,
                max_videos=max_videos,
                max_comments_per_video=max_comments_per_video
            )
            
            # Format results for response
            formatted_results = {}
            for video_url, comments in results.items():
                formatted_comments = []
                for comment in comments:
                    snippet = comment["snippet"]["topLevelComment"]["snippet"]
                    formatted_comments.append({
                        'author': snippet["authorDisplayName"],
                        'text': snippet["textDisplay"],
                        'published_at': snippet["publishedAt"],
                        'like_count': snippet["likeCount"]
                    })
                formatted_results[video_url] = formatted_comments

            return {
                'success': True,
                'video_count': len(formatted_results),
                'results': formatted_results
            }
        
        except Exception as e:
            api.abort(500, str(e))

@ns.route('/by-username')
class CrawlCommentsByUsername(Resource):
    @api.doc(description='Crawl comments from a YouTube channel using channel username')
    @api.expect(crawl_by_username_request)
    @api.marshal_with(crawl_response)
    def post(self):
        """Crawl comments from YouTube channel specified by username"""
        data = api.payload

        if not data or 'channel_username' not in data:
            api.abort(400, 'Missing channel_username parameter')

        # Extract parameters
        channel_username = data.get('channel_username')
        username_filter = data.get('username')
        content_keywords = data.get('keywords')
        max_videos = data.get('max_videos', 50)
        max_comments_per_video = data.get('max_comments', 100)

        # Validate parameters
        if not isinstance(max_videos, int) or max_videos <= 0:
            api.abort(400, 'max_videos must be a positive integer')
        
        if not isinstance(max_comments_per_video, int) or max_comments_per_video <= 0:
            api.abort(400, 'max_comments must be a positive integer')

        try:
            # First, get the channel ID from the username
            channel_id = crawler.get_channel_id_from_username(channel_username)
            
            if not channel_id:
                api.abort(404, f'Channel not found for username: {channel_username}')
            
            # Then crawl using the channel ID
            results = crawler.crawl_channel_comments(
                channel_id=channel_id,
                username_filter=username_filter,
                content_keywords=content_keywords,
                max_videos=max_videos,
                max_comments_per_video=max_comments_per_video
            )
            
            # Format results for response
            formatted_results = {}
            for video_url, comments in results.items():
                formatted_comments = []
                for comment in comments:
                    snippet = comment["snippet"]["topLevelComment"]["snippet"]
                    formatted_comments.append({
                        'author': snippet["authorDisplayName"],
                        'text': snippet["textDisplay"],
                        'published_at': snippet["publishedAt"],
                        'like_count': snippet["likeCount"]
                    })
                formatted_results[video_url] = formatted_comments

            return {
                'success': True,
                'video_count': len(formatted_results),
                'results': formatted_results
            }
            
        except Exception as e:
            api.abort(500, str(e))

    def get_channel_id_from_username(self, username):
        """
        Get channel ID from a YouTube username/handle
        
        Args:
            username (str): YouTube channel username or handle
        
        Returns:
            str: Channel ID if found, None otherwise
        """
        try:
            # Remove @ symbol if present
            if username.startswith('@'):
                username = username[1:]
                
            # Try to find channel by username
            request = self.youtube.channels().list(
                part="id",
                forUsername=username
            )
            response = request.execute()
            
            # If found by username
            if response.get('items'):
                return response['items'][0]['id']
                
            # If not found by username, try to find by handle
            request = self.youtube.search().list(
                part="snippet",
                q=f"@{username}",
                type="channel",
                maxResults=1
            )
            response = request.execute()
            
            if response.get('items'):
                return response['items'][0]['snippet']['channelId']
                
            return None
        except Exception as e:
            print(f"Error getting channel ID for username {username}: {str(e)}")
            return None

            
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5000))

    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=False)
"""
RESTful API for YouTube Comment Crawler with Swagger documentation
Exposes the crawler functionality through HTTP endpoints.
"""

import os
import sys
from waitress import serve
from flask import Flask
from flask_restx import Api, Resource, fields
from flask_cors import CORS
from main import YouTubeCommentCrawler, check_api_key
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Initialize Flask app and API
app = Flask(__name__)
api = Api(app, version='1.0', title='YouTube Comment Crawler API',
          description='API for crawling YouTube comments')

# Configure CORS properly
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
app.config['CORS_HEADERS'] = 'Content-Type, Authorization'

# Define namespaces
ns = api.namespace('api', description='YouTube crawler operations')

# Define models for request/response
crawl_request = api.model('CrawlRequest', {
    'channel_id': fields.String(required=True, description='YouTube channel ID'),
    'username': fields.String(required=False, description='Filter by username'),
    'keywords': fields.List(fields.String, required=False, description='Filter by keywords'),
    'max_videos': fields.Integer(required=False, default=50, description='Maximum number of videos to crawl'),
    'max_comments': fields.Integer(required=False, default=100, description='Maximum comments per video')
})

crawl_by_username_request = api.model('CrawlByUsernameRequest', {
    'channel_username': fields.String(required=True, description='YouTube channel username'),
    'username': fields.String(required=False, description='Filter by username'),
    'keywords': fields.List(fields.String, required=False, description='Filter by keywords'),
    'max_videos': fields.Integer(required=False, default=50, description='Maximum number of videos to crawl'),
    'max_comments': fields.Integer(required=False, default=100, description='Maximum comments per video')
})

comment_model = api.model('Comment', {
    'author': fields.String(description='Comment author'),
    'text': fields.String(description='Comment text'),
    'published_at': fields.String(description='Publication date'),
    'like_count': fields.Integer(description='Number of likes')
})

crawl_response = api.model('CrawlResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'video_count': fields.Integer(description='Number of videos processed'),
    'results': fields.Raw(description='Crawled comments by video')
})

# Get API key
try:
    api_key = check_api_key()
    crawler = YouTubeCommentCrawler(api_key)
except SystemExit:
    print("Error: YouTube API key not found. Please set the YOUTUBE_API_KEY environment variable.")
    sys.exit(1)


@ns.route('/health')
class Health(Resource):
    @api.doc(description='Health check endpoint')
    def get(self):
        """Check API health status"""
        return {'status': 'ok', 'service': 'YouTube Comment Crawler API'}


@ns.route('/crawl')
class CrawlComments(Resource):
    @api.doc(description='Crawl comments from a YouTube channel')
    @api.expect(crawl_request)
    @api.marshal_with(crawl_response)
    def post(self):
        """Crawl comments from specified YouTube channel"""
        data = api.payload

        if not data or 'channel_id' not in data:
            api.abort(400, 'Missing channel_id parameter')

        # Extract parameters
        channel_id = data.get('channel_id')
        username_filter = data.get('username')
        content_keywords = data.get('keywords')
        max_videos = data.get('max_videos', 50)
        max_comments_per_video = data.get('max_comments', 100)

        # Validate parameters
        if not isinstance(max_videos, int) or max_videos <= 0:
            api.abort(400, 'max_videos must be a positive integer')
        
        if not isinstance(max_comments_per_video, int) or max_comments_per_video <= 0:
            api.abort(400, 'max_comments must be a positive integer')

        try:
            results = crawler.crawl_channel_comments(
                channel_id=channel_id,
                username_filter=username_filter,
                content_keywords=content_keywords,
                max_videos=max_videos,
                max_comments_per_video=max_comments_per_video
            )
            
            # Format results for response
            formatted_results = {}
            for video_url, comments in results.items():
                formatted_comments = []
                for comment in comments:
                    snippet = comment["snippet"]["topLevelComment"]["snippet"]
                    formatted_comments.append({
                        'author': snippet["authorDisplayName"],
                        'text': snippet["textDisplay"],
                        'published_at': snippet["publishedAt"],
                        'like_count': snippet["likeCount"]
                    })
                formatted_results[video_url] = formatted_comments

            return {
                'success': True,
                'video_count': len(formatted_results),
                'results': formatted_results
            }
        
        except Exception as e:
            api.abort(500, str(e))

@ns.route('/by-username')
class CrawlCommentsByUsername(Resource):
    @api.doc(description='Crawl comments from a YouTube channel using channel username')
    @api.expect(crawl_by_username_request)
    @api.marshal_with(crawl_response)
    def post(self):
        """Crawl comments from YouTube channel specified by username"""
        data = api.payload

        if not data or 'channel_username' not in data:
            api.abort(400, 'Missing channel_username parameter')

        # Extract parameters
        channel_username = data.get('channel_username')
        username_filter = data.get('username')
        content_keywords = data.get('keywords')
        max_videos = data.get('max_videos', 50)
        max_comments_per_video = data.get('max_comments', 100)

        # Validate parameters
        if not isinstance(max_videos, int) or max_videos <= 0:
            api.abort(400, 'max_videos must be a positive integer')
        
        if not isinstance(max_comments_per_video, int) or max_comments_per_video <= 0:
            api.abort(400, 'max_comments must be a positive integer')

        try:
            # First, get the channel ID from the username
            channel_id = crawler.get_channel_id_from_username(channel_username)
            
            if not channel_id:
                api.abort(404, f'Channel not found for username: {channel_username}')
            
            # Then crawl using the channel ID
            results = crawler.crawl_channel_comments(
                channel_id=channel_id,
                username_filter=username_filter,
                content_keywords=content_keywords,
                max_videos=max_videos,
                max_comments_per_video=max_comments_per_video
            )
            
            # Format results for response
            formatted_results = {}
            for video_url, comments in results.items():
                formatted_comments = []
                for comment in comments:
                    snippet = comment["snippet"]["topLevelComment"]["snippet"]
                    formatted_comments.append({
                        'author': snippet["authorDisplayName"],
                        'text': snippet["textDisplay"],
                        'published_at': snippet["publishedAt"],
                        'like_count': snippet["likeCount"]
                    })
                formatted_results[video_url] = formatted_comments

            return {
                'success': True,
                'video_count': len(formatted_results),
                'results': formatted_results
            }
            
        except Exception as e:
            api.abort(500, str(e))

if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5000))

    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=False)