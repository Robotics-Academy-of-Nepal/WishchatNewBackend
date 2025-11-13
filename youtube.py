import re
import requests
import googleapiclient.discovery
import os
import sys

# Force UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

os.environ["PYTHONUTF8"] = "1"

# ========================
# CONFIGURATION
# ========================
API_KEY = (
    "AIzaSyBgr4d5ztFkNhQb6yWkWUmjcVhExtVMVk0"  # Replace with your YouTube Data API key
)
CHANNEL_URL = "https://www.youtube.com/@HowToInsider"  # Replace with any channel URL
OUTPUT_FILE = "youtube_videos_context.txt"


# ========================
# EXTRACT CHANNEL ID FROM URL
# ========================
def get_channel_id(channel_url):
    if "/channel/" in channel_url:
        return channel_url.split("/channel/")[1].split("/")[0]
    else:
        res = requests.get(channel_url)
        match = re.search(r'"channelId":"(UC[-_A-Za-z0-9]{22,})"', res.text)
        if match:
            return match.group(1)
        else:
            match = re.search(r'"browseId":"(UC[-_A-Za-z0-9]{22,})"', res.text)
            if match:
                return match.group(1)
            raise ValueError("Could not extract channel ID from URL")


# ========================
# INITIALIZE YOUTUBE API CLIENT
# ========================
def get_youtube_client():
    return googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)


# ========================
# GET ALL VIDEO IDS FROM CHANNEL
# ========================
def get_video_ids(youtube, channel_id):
    video_ids = []
    request = youtube.search().list(
        part="id", channelId=channel_id, maxResults=50, order="date", type="video"
    )

    while request:
        response = request.execute()
        for item in response["items"]:
            video_ids.append(item["id"]["videoId"])
        request = youtube.search().list_next(request, response)

    return video_ids


# ========================
# GET VIDEO DETAILS
# ========================
def get_video_details(youtube, video_ids):
    all_video_details = []

    for i in range(0, len(video_ids), 50):
        request = youtube.videos().list(
            part="snippet,contentDetails,statistics", id=",".join(video_ids[i : i + 50])
        )
        response = request.execute()
        for video in response["items"]:
            details = {
                "title": video["snippet"]["title"],
                "description": video["snippet"]["description"],
                "url": f"https://www.youtube.com/watch?v={video['id']}",
                "published_at": video["snippet"]["publishedAt"],
                "channel_title": video["snippet"]["channelTitle"],
                "tags": video["snippet"].get("tags", []),
            }
            all_video_details.append(details)

    return all_video_details


# ========================
# EXTRACT KEYWORDS FROM TITLE AND DESCRIPTION
# ========================
def extract_keywords(text):
    """Extract relevant keywords for better RAG retrieval"""
    keywords = set()

    # Common health/fitness topics
    topics = [
        "weight loss",
        "fat loss",
        "diet",
        "fasting",
        "calories",
        "nutrition",
        "exercise",
        "workout",
        "fitness",
        "health",
        "muscle",
        "protein",
        "carbs",
        "keto",
        "carnivore",
        "metabolism",
        "blood sugar",
        "insulin",
        "diabetes",
        "cholesterol",
        "heart health",
        "brain",
        "energy",
        "motivation",
        "habits",
        "tips",
        "how to",
        "lose weight",
        "burn fat",
    ]

    text_lower = text.lower()
    for topic in topics:
        if topic in text_lower:
            keywords.add(topic)

    return keywords


# ========================
# SAVE TO OPTIMIZED RAG FORMAT
# ========================
def save_to_rag_format(video_list, filename):
    if not video_list:
        print("No videos to save.")
        return

    with open(filename, "w", encoding="utf-8") as f:
        # Write channel overview
        if video_list:
            f.write(f"CHANNEL: {video_list[0]['channel_title']}\n")
            f.write(f"TOTAL VIDEOS: {len(video_list)}\n\n")

        # Write each video in a dense, keyword-rich format
        for idx, video in enumerate(video_list, 1):
            title = video["title"]
            description = video["description"].strip()
            url = video["url"]

            # Extract keywords
            all_text = f"{title} {description}"
            keywords = extract_keywords(all_text)

            # Write video entry
            f.write(f"VIDEO_{idx}\n")
            f.write(f"TITLE: {title}\n")

            # Add keywords for better retrieval
            if keywords:
                f.write(f"TOPICS: {', '.join(sorted(keywords))}\n")

            # Write content in a Q&A style for better RAG matching
            if description:
                # Clean description
                description = description.replace("\n", " ").strip()

                # Generate natural language content
                f.write(f"CONTENT: This video covers {title}. ")
                f.write(f"{description} ")
                f.write(f"Watch the full video at {url}\n")
            else:
                f.write(f"CONTENT: This video is about {title}. ")
                f.write(f"Watch at {url}\n")

            f.write("\n" + "=" * 100 + "\n\n")

    print(f"Saved {len(video_list)} videos to {filename}")
    print("File optimized for RAG/chatbot retrieval")


# ========================
# ALSO CREATE A SUMMARY FILE
# ========================
def create_summary_file(video_list, filename="channel_summary.txt"):
    """Create a summary file with aggregated topics"""
    if not video_list:
        return

    all_keywords = set()
    topic_videos = {}

    for video in video_list:
        all_text = f"{video['title']} {video['description']}"
        keywords = extract_keywords(all_text)
        all_keywords.update(keywords)

        for keyword in keywords:
            if keyword not in topic_videos:
                topic_videos[keyword] = []
            topic_videos[keyword].append({"title": video["title"], "url": video["url"]})

    with open(filename, "w", encoding="utf-8") as f:
        f.write("CHANNEL KNOWLEDGE BASE SUMMARY\n")
        f.write(f"Channel: {video_list[0]['channel_title']}\n\n")

        f.write("TOPICS COVERED:\n")
        for topic in sorted(all_keywords):
            f.write(f"- {topic.title()} ({len(topic_videos[topic])} videos)\n")

        f.write("\n" + "=" * 100 + "\n\n")

        # Group videos by topic
        for topic in sorted(topic_videos.keys()):
            f.write(f"TOPIC: {topic.upper()}\n")
            f.write(f"Related videos ({len(topic_videos[topic])}):\n")
            for vid in topic_videos[topic][:5]:  # Show top 5
                f.write(f"  - {vid['title']}\n")
                f.write(f"    {vid['url']}\n")
            f.write("\n")

    print(f"Created summary file: {filename}")


# ========================
# MAIN
# ========================
def main():
    try:
        print("Extracting channel ID...")
        channel_id = get_channel_id(CHANNEL_URL)
        print(f"Channel ID: {channel_id}")
    except ValueError as e:
        print(f"Error: {e}")
        return
    except Exception as e:
        print(f"Unexpected error: {e}")
        return

    youtube = get_youtube_client()
    print("Fetching video IDs...")
    video_ids = get_video_ids(youtube, channel_id)
    print(f"Found {len(video_ids)} videos. Fetching details...")

    videos = get_video_details(youtube, video_ids)
    save_to_rag_format(videos, OUTPUT_FILE)
    create_summary_file(videos)


if __name__ == "__main__":
    main()
