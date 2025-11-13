import os
import tempfile
from io import BytesIO
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from django.conf import settings
from .views import upload_file
from django.core.files.uploadedfile import InMemoryUploadedFile


def extract_channel_id_from_url(api_key, url):
    """
    Converts YouTube channel, user, or handle URL into a proper channel ID.
    """
    youtube = build("youtube", "v3", developerKey=api_key)

    # Direct channel URL
    if "channel/" in url:
        return url.split("channel/")[-1].split("/")[0]

    # User URL (legacy)
    elif "user/" in url:
        username = url.split("user/")[-1].split("/")[0]
        request = youtube.channels().list(forUsername=username, part="id")
        response = request.execute()
        if response.get("items"):
            return response["items"][0]["id"]

    # Handle URL (@username)
    elif "@" in url:
        handle = url.split("@")[-1].strip("/").split("?")[0]  # Remove query params
        request = youtube.search().list(
            q=handle, type="channel", part="snippet", maxResults=1
        )
        response = request.execute()
        if response.get("items"):
            return response["items"][0]["snippet"]["channelId"]

    return None


def get_all_video_ids(api_key, channel_id, max_videos=50):
    """
    Fetch video IDs from a channel using YouTube Data API.
    """
    youtube = build("youtube", "v3", developerKey=api_key)
    videos = []
    next_page_token = None

    while len(videos) < max_videos:
        try:
            request = youtube.search().list(
                part="id",
                channelId=channel_id,
                maxResults=min(50, max_videos - len(videos)),
                order="date",
                type="video",
                pageToken=next_page_token,
            )
            response = request.execute()

            for item in response.get("items", []):
                if "videoId" in item["id"]:
                    videos.append(item["id"]["videoId"])

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        except Exception as e:
            print(f"Error fetching videos: {e}")
            break

    return videos


def get_video_details(api_key, video_ids):
    """
    Fetch video titles and metadata for better context.
    """
    youtube = build("youtube", "v3", developerKey=api_key)
    video_details = {}

    # Process in batches of 50 (API limit)
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        try:
            request = youtube.videos().list(part="snippet", id=",".join(batch))
            response = request.execute()

            for item in response.get("items", []):
                video_id = item["id"]
                video_details[video_id] = {
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"][
                        :200
                    ],  # First 200 chars
                    "channel": item["snippet"]["channelTitle"],
                }
        except Exception as e:
            print(f"Error fetching video details: {e}")

    return video_details


def format_youtube_transcripts(video_data):
    """
    Format YouTube transcripts in RAG-friendly format matching the YouTube scraper output.
    """
    output = "=" * 80 + "\n"
    output += "YOUTUBE CHANNEL TRANSCRIPT KNOWLEDGE BASE\n"
    output += f"Total Videos: {len(video_data)}\n"
    if video_data:
        output += f"Channel: {list(video_data.values())[0].get('channel', 'Unknown')}\n"
    output += "=" * 80 + "\n\n"

    for idx, (video_id, data) in enumerate(video_data.items(), 1):
        output += f"[VIDEO {idx}]\n"
        output += f"Title: {data['title']}\n"
        output += f"URL: https://www.youtube.com/watch?v={video_id}\n"

        if data.get("description"):
            output += f"\nDescription:\n{data['description']}\n"

        output += f"\nTranscript:\n"
        output += data["transcript"]
        output += "\n\n" + "-" * 80 + "\n\n"

    return output


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_youtube_channel(request, chatbot_id):
    """
    Takes a YouTube channel link, fetches transcripts of videos, generates a .txt file,
    and uploads it using existing upload_file() logic.
    """
    channel_url = request.data.get("channel_url")
    max_videos = int(request.data.get("max_videos", 20))  # Default 20 videos

    if not channel_url:
        return JsonResponse({"error": "channel_url is required"}, status=400)

    if max_videos > 50:
        return JsonResponse({"error": "max_videos cannot exceed 50"}, status=400)

    api_key = getattr(settings, "YOUTUBE_API_KEY", None)
    if not api_key:
        return JsonResponse({"error": "YouTube API key not configured."}, status=500)

    try:
        # 1️⃣ Get channel ID
        print(f"Extracting channel ID from: {channel_url}")
        channel_id = extract_channel_id_from_url(api_key, channel_url)
        if not channel_id:
            return JsonResponse(
                {
                    "error": "Invalid or unsupported channel URL. Use format: youtube.com/@ChannelName or youtube.com/channel/UC..."
                },
                status=400,
            )
        print(f"Channel ID: {channel_id}")

        # 2️⃣ Get video IDs
        print(f"Fetching up to {max_videos} video IDs...")
        video_ids = get_all_video_ids(api_key, channel_id, max_videos=max_videos)
        if not video_ids:
            return JsonResponse(
                {"error": "No videos found for this channel."}, status=400
            )
        print(f"Found {len(video_ids)} videos")

        # 3️⃣ Get video details (titles, descriptions)
        print("Fetching video details...")
        video_details = get_video_details(api_key, video_ids)

        # 4️⃣ Fetch transcripts (with fallback to title/description)
        print("Fetching transcripts...")
        video_data = {}
        successful_transcripts = 0
        fallback_count = 0

        for vid in video_ids:
            try:
                transcript = None
                has_transcript = False

                # Try multiple language options
                language_options = [
                    ["en"],  # English
                    ["en-US"],  # US English
                    ["en-GB"],  # UK English
                    ["a.en"],  # Auto-generated English
                ]

                for lang_codes in language_options:
                    try:
                        transcript = YouTubeTranscriptApi.get_transcript(
                            vid, languages=lang_codes
                        )
                        if transcript:
                            has_transcript = True
                            break
                    except:
                        continue

                # If still no transcript, try without language specification
                if not transcript:
                    try:
                        transcript = YouTubeTranscriptApi.get_transcript(vid)
                        has_transcript = True
                    except:
                        pass

                # Get video details
                title = video_details.get(vid, {}).get("title", "Unknown Title")
                description = video_details.get(vid, {}).get("description", "")
                channel = video_details.get(vid, {}).get("channel", "Unknown Channel")

                if has_transcript and transcript:
                    # Use actual transcript
                    video_text = " ".join([x["text"] for x in transcript])
                    video_data[vid] = {
                        "title": title,
                        "description": description,
                        "channel": channel,
                        "transcript": video_text,
                        "has_transcript": True,
                    }
                    successful_transcripts += 1
                    print(f"✓ Transcript fetched for: {title}")
                else:
                    # Fallback: Use title and description as content
                    fallback_content = f"Video Title: {title}\n\n"
                    if description:
                        fallback_content += f"Description: {description}\n\n"
                    fallback_content += (
                        "Note: Full transcript not available for this video."
                    )

                    video_data[vid] = {
                        "title": title,
                        "description": description,
                        "channel": channel,
                        "transcript": fallback_content,
                        "has_transcript": False,
                    }
                    fallback_count += 1
                    print(f"⚠ Using title/description fallback for: {title}")

            except Exception as e:
                print(f"✗ Failed to process {vid}: {e}")
                continue

        if not video_data:
            return JsonResponse(
                {
                    "error": f"Could not process any videos from {len(video_ids)} videos found.",
                    "details": "Unable to fetch video information. Please check the channel URL and try again.",
                    "videos_checked": len(video_ids),
                },
                status=400,
            )

        print(f"Successfully processed {len(video_data)} videos:")
        print(f"  - {successful_transcripts} with full transcripts")
        print(f"  - {fallback_count} using title/description only")

        # 5️⃣ Format content in RAG-friendly format
        formatted_content = format_youtube_transcripts(video_data)

        # 6️⃣ Create in-memory file
        filename = f"{channel_id}_transcripts.txt"
        file_content = formatted_content.encode("utf-8")
        file_obj = BytesIO(file_content)

        uploaded_file = InMemoryUploadedFile(
            file=file_obj,
            field_name="file",
            name=filename,
            content_type="text/plain",
            size=len(file_content),
            charset="utf-8",
        )

        # 7️⃣ Call upload_file with the underlying Django request
        # Get the underlying Django HttpRequest
        django_request = request._request

        # Add our generated file to FILES (don't replace, just add)
        django_request.FILES[filename] = uploaded_file

        # Call the existing upload_file function with Django request
        response = upload_file(django_request, chatbot_id)

        # Clean up: remove our added file from FILES
        if filename in django_request.FILES:
            del django_request.FILES[filename]

        # 8️⃣ Enhance response with YouTube-specific info
        if response.status_code == 200:
            response_data = response.json() if hasattr(response, "json") else {}
            if isinstance(response_data, dict):
                response_data["youtube_info"] = {
                    "channel_id": channel_id,
                    "total_videos_found": len(video_ids),
                    "transcripts_fetched": successful_transcripts,
                    "fallback_videos": fallback_count,
                    "total_processed": len(video_data),
                    "filename": filename,
                }
                return JsonResponse(response_data, status=200)

        return response

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse(
            {"error": f"Failed to process YouTube channel: {str(e)}"}, status=500
        )
