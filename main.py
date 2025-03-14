"""
YouTube Comment Crawler
A tool to crawl and filter comments from a specific YouTube channel.
"""

import os
import argparse
from typing import List, Dict, Any, Optional
import googleapiclient.discovery
import googleapiclient.errors
from dotenv import load_dotenv

load_dotenv()

class YouTubeAPI:
    """Class to handle YouTube API requests."""
    
    def __init__(self, api_key: str):
        """Initialize the YouTube API client."""
        self.youtube = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=api_key
        )
    
    def get_channel_videos(self, channel_id: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Get videos from a specific channel."""
        # Get upload playlist ID for the channel
        channel_response = self.youtube.channels().list(
            part="contentDetails",
            id=channel_id
        ).execute()
        
        if not channel_response.get("items"):
            return []
        
        uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        # Get videos from the uploads playlist
        videos = []
        next_page_token = None
        
        while len(videos) < max_results:
            playlist_items_response = self.youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=min(50, max_results - len(videos)),
                pageToken=next_page_token
            ).execute()
            
            videos.extend(playlist_items_response["items"])
            
            next_page_token = playlist_items_response.get("nextPageToken")
            if not next_page_token:
                break
                
        return videos[:max_results]
    
    def get_video_comments(self, video_id: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """Get comments for a specific video."""
        comments = []
        next_page_token = None
        
        try:
            while len(comments) < max_results:
                comments_response = self.youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=min(100, max_results - len(comments)),
                    pageToken=next_page_token
                ).execute()
                
                comments.extend(comments_response["items"])
                
                next_page_token = comments_response.get("nextPageToken")
                if not next_page_token or len(comments) >= max_results:
                    break
        except googleapiclient.errors.HttpError as e:
            # Comments might be disabled for the video
            print(f"Não foi possível obter comentários para o vídeo {video_id}: {e}")
            
        return comments[:max_results]


class CommentFilter:
    """Class to filter comments based on different criteria."""
    
    @staticmethod
    def filter_by_username(comments: List[Dict[str, Any]], username: str) -> List[Dict[str, Any]]:
        """Filter comments by username (case insensitive)."""
        username = username.lower()
        return [
            comment for comment in comments
            if username in comment["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"].lower()
        ]
    
    @staticmethod
    def filter_by_content(comments: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
        """Filter comments by content keywords (case insensitive)."""
        keywords = [keyword.lower() for keyword in keywords]
        filtered_comments = []
        
        for comment in comments:
            comment_text = comment["snippet"]["topLevelComment"]["snippet"]["textDisplay"].lower()
            if any(keyword in comment_text for keyword in keywords):
                filtered_comments.append(comment)
                
        return filtered_comments


class YouTubeCommentCrawler:
    """Main class to handle the comment crawling process."""
    
    def __init__(self, api_key: str):
        """Initialize the crawler with API access."""
        self.api = YouTubeAPI(api_key)
    
    @staticmethod
    def get_video_url(video_id: str) -> str:
        """Generate YouTube video URL from video ID."""
        return f"https://www.youtube.com/watch?v={video_id}"
    
    def crawl_channel_comments(
        self, 
        channel_id: str,
        username_filter: Optional[str] = None,
        content_keywords: Optional[List[str]] = None,
        max_videos: int = 50,
        max_comments_per_video: int = 100
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Crawl and filter comments from a specific channel.
        Returns a dictionary mapping video URLs to matching comments.
        """
        results = {}
        
        # Get videos from the channel
        videos = self.api.get_channel_videos(channel_id, max_videos)
        
        for video in videos:
            video_id = video["contentDetails"]["videoId"]
            
            # Get comments for the video
            comments = self.api.get_video_comments(video_id, max_comments_per_video)
            
            # Apply filters if provided
            filtered_comments = comments
            
            if username_filter:
                filtered_comments = CommentFilter.filter_by_username(filtered_comments, username_filter)
                
            if content_keywords:
                filtered_comments = CommentFilter.filter_by_content(filtered_comments, content_keywords)
                
            # Add to results if there are matching comments
            if filtered_comments:
                video_url = self.get_video_url(video_id)
                results[video_url] = filtered_comments
                
        return results

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
            request = self.api.youtube.channels().list(
                part="id",
                forUsername=username
            )
            response = request.execute()

            # If found by username
            if response.get('items'):
                return response['items'][0]['id']

            # If not found by username, try to find by handle
            request = self.api.youtube.search().list(
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


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Crawler de Comentários do YouTube")
    
    parser.add_argument("--channel_id", required=True, help="ID do canal do YouTube")
    parser.add_argument("--username", help="Filtrar comentários por nome de usuário")
    parser.add_argument("--keywords", nargs="+", help="Filtrar comentários por palavras-chave")
    parser.add_argument("--max_videos", type=int, default=50, help="Número máximo de vídeos para verificar")
    parser.add_argument("--max_comments", type=int, default=100, help="Número máximo de comentários por vídeo")
    
    return parser.parse_args()


def display_results(results: Dict[str, List[Dict[str, Any]]]):
    """Display the crawling results in a formatted way."""
    if not results:
        print("Nenhum comentário correspondente encontrado.")
        return
    
    print(f"Encontrados comentários correspondentes em {len(results)} vídeos:")
    print("-" * 80)
    
    for video_url, comments in results.items():
        print(f"Vídeo: {video_url}")
        print(f"Comentários correspondentes: {len(comments)}")
        
        for comment in comments[:3]:  # Mostrar os primeiros 3 comentários como amostra
            author = comment["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"]
            text = comment["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            
            # Truncar comentários longos para exibição
            if len(text) > 100:
                text = text[:97] + "..."
                
            print(f"  - {author}: {text}")
            
        if len(comments) > 3:
            print(f"  ... e mais {len(comments) - 3}")
            
        print("-" * 80)

def check_api_key():
    """Verifica e retorna a chave da API do YouTube."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    
    if not api_key:
        print("Erro: Chave da API do YouTube não encontrada.")
        print("\nPara definir a chave da API, você pode:")
        print("1. Definir a variável de ambiente YOUTUBE_API_KEY:")
        print("   - No Linux/Mac: export YOUTUBE_API_KEY='sua_chave_api'")
        print("   - No Windows (cmd): set YOUTUBE_API_KEY=sua_chave_api")
        print("   - No Windows (PowerShell): $env:YOUTUBE_API_KEY='sua_chave_api'")
        print("\n2. Ou criar um arquivo .env no diretório do projeto com o seguinte conteúdo:")
        print("   YOUTUBE_API_KEY=sua_chave_api")
        sys.exit(1)
    
    return api_key

def main():
    """Main function to run the crawler."""
    args = parse_arguments()
    
    # Obter chave da API dos argumentos ou variável de ambiente
    api_key = check_api_key()
    
    args = parse_arguments()
    
    # Inicializar e executar o crawler
    crawler = YouTubeCommentCrawler(api_key)
    results = crawler.crawl_channel_comments(
        channel_id=args.channel_id,
        username_filter=args.username,
        content_keywords=args.keywords,
        max_videos=args.max_videos,
        max_comments_per_video=args.max_comments
    )
    
    # Exibir resultados
    display_results(results)


if __name__ == "__main__":
    main()