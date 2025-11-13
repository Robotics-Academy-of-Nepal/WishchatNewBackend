import requests
from registration.models import Chatbot
from playground.chatbot import query_assistant
import re
from django.core.exceptions import ObjectDoesNotExist


def extract_youtube_urls(text):
    """Extract YouTube URLs from text"""
    youtube_patterns = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)",
        r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]+)",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)",
    ]

    urls = []
    for pattern in youtube_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            urls.append(match.group(0))

    return urls


def extract_video_info(text):
    """
    Extract video titles and URLs from formatted text.
    Handles formats like: ### Video Title [](url) or ### Video Title followed by URL
    """
    videos = []

    # Pattern 1: ### Title [optional_text](url)
    pattern1 = r"###\s*([^\n\[]+?)\s*\[([^\]]*)\]\(([^)]+)\)"
    matches = re.finditer(pattern1, text)

    for match in matches:
        title = match.group(1).strip()
        url = match.group(3).strip()
        if url and ("youtube.com" in url or "youtu.be" in url):
            videos.append({"title": title, "url": url, "full_match": match.group(0)})

    # Pattern 2: ### Title followed by a URL on next line or same line
    pattern2 = (
        r"###\s*([^\n]+)\s*\n?\s*(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s]+)"
    )
    matches = re.finditer(pattern2, text)

    for match in matches:
        title = match.group(1).strip()
        url = match.group(2).strip()
        # Only add if not already captured
        if not any(v["url"] == url for v in videos):
            videos.append({"title": title, "url": url, "full_match": match.group(0)})

    # Pattern 3: Plain YouTube URLs without titles
    youtube_pattern = r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+"
    for match in re.finditer(youtube_pattern, text):
        url = match.group(0)
        # Only add if not already captured with a title
        if not any(v["url"] == url for v in videos):
            videos.append({"title": None, "url": url, "full_match": url})

    return videos


def remove_video_sections(text, videos):
    """Remove video sections from text based on extracted video info"""
    for video in videos:
        text = text.replace(video["full_match"], "")

    # Remove common video section headers
    text = re.sub(
        r"(?:For more.*?helpful:|These resources.*?:|Watch these videos:)\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove lines that only contain "###" or are empty after video removal
    lines = text.split("\n")
    cleaned_lines = [line for line in lines if line.strip() and line.strip() != "###"]
    text = "\n".join(cleaned_lines)

    return text


def format_for_whatsapp(text):
    """
    Format text for natural WhatsApp display with proper spacing and formatting.
    Converts markdown to WhatsApp-friendly format.
    """
    # Convert markdown bold (**text**) to WhatsApp bold (*text*)
    text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)

    # Ensure proper spacing after numbered lists
    text = re.sub(r"(\d+\.)\s*(\*)", r"\1 \2", text)

    # Add line break after each numbered item for better readability
    text = re.sub(r"(\d+\.\s*\*[^*]+\*[^\n]+)", r"\1\n", text)

    # Clean up multiple spaces
    text = re.sub(r" +", " ", text)

    # Clean up excessive newlines (max 2 consecutive)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Ensure spacing around section headers (###)
    text = re.sub(r"(###[^\n]+)\n", r"\1\n\n", text)

    # Remove trailing spaces from lines
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip()


def clean_markdown_for_messaging(text):
    """
    Remove markdown formatting that doesn't work well in messaging platforms.
    Keeps text clean while preserving URLs for preview.
    """
    # Remove markdown image syntax: [![alt](image_url)](link_url) or ![alt](image_url)
    text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", "", text)

    # Remove empty markdown link wrappers: [text]()
    text = re.sub(r"\[([^\]]+)\]\(\)", r"\1", text)

    # Remove thumbnail URLs (img.youtube.com)
    text = re.sub(r"https?://img\.youtube\.com/[^\s]+", "", text)

    # Clean up extra whitespace and newlines
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)  # Max 2 newlines
    text = re.sub(r" +", " ", text)  # Multiple spaces to single
    text = text.strip()

    return text


def clean_text_content(text):
    """Final cleanup of text formatting"""
    # Remove extra whitespace
    text = re.sub(r" +", " ", text)

    # Clean up multiple newlines
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    # Remove leading/trailing whitespace from lines
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = "\n".join(lines)

    return text.strip()


def sendwhatsapp_messages(phoneNumber, message, whatsapp_id):
    try:
        chatbot = Chatbot.objects.filter(whatsapp_id=whatsapp_id).last()
    except ObjectDoesNotExist:
        print(f"Chatbot not found for whatsapp_id: {whatsapp_id}")
        return {"error": "Chatbot not found"}

    # Get bot response
    bot_response = query_assistant(
        user_input=message, chatbot=chatbot, user_id=phoneNumber, platform="whatsapp"
    )

    # Clean markdown formatting first
    bot_response = clean_markdown_for_messaging(bot_response)

    # Format for WhatsApp natural display
    bot_response = format_for_whatsapp(bot_response)

    headers = {"Authorization": f"Bearer {chatbot.whatsapp_token}"}

    try:
        # Extract video information (titles + URLs)
        video_info = extract_video_info(bot_response)

        if video_info:
            # Remove video sections from main text
            text_content = remove_video_sections(bot_response, video_info)

            # Final cleanup
            text_content = clean_text_content(text_content)

            # Send the main text message if there's content
            if text_content:
                text_payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": phoneNumber,
                    "type": "text",
                    "text": {"body": text_content},
                }
                requests.post(chatbot.whatsapp_url, headers=headers, json=text_payload)

            # Send each video with its title and thumbnail
            responses = []
            for video in video_info:
                # If we have a title, send it first with an emoji
                if video.get("title"):
                    title_payload = {
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": phoneNumber,
                        "type": "text",
                        "text": {"body": f"🎥 *{video['title']}*"},
                    }
                    requests.post(
                        chatbot.whatsapp_url, headers=headers, json=title_payload
                    )

                # Send URL with preview enabled (shows thumbnail)
                url_payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": phoneNumber,
                    "type": "text",
                    "text": {
                        "body": video["url"],
                        "preview_url": True,
                    },
                }
                response = requests.post(
                    chatbot.whatsapp_url, headers=headers, json=url_payload
                )
                responses.append(response.json())

            return {"status": "success", "responses": responses}

        else:
            # No videos, send formatted text message
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phoneNumber,
                "type": "text",
                "text": {"body": bot_response},
            }
            response = requests.post(
                chatbot.whatsapp_url, headers=headers, json=payload
            )
            return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error sending WhatsApp message: {str(e)}")
        return {"error": str(e)}
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {"error": str(e)}


def messenger_messages(sender_id, message_text, messenger_page_id):
    try:
        chatbot = Chatbot.objects.get(messenger_page_id=messenger_page_id)
    except ObjectDoesNotExist:
        print(f"Chatbot not found for messenger_page_id: {messenger_page_id}")
        return {"error": "Chatbot not found"}

    bot_response = query_assistant(
        user_input=message_text,
        chatbot=chatbot,
        user_id=sender_id,
        platform="messenger",
    )

    # Clean markdown formatting
    bot_response = clean_markdown_for_messaging(bot_response)

    # Format for natural display
    bot_response = format_for_whatsapp(
        bot_response
    )  # Same formatting works for Messenger

    headers = {"Authorization": f"Bearer {chatbot.messenger_token}"}

    try:
        # Extract video information
        video_info = extract_video_info(bot_response)

        if video_info:
            # Remove video sections from main text
            text_content = remove_video_sections(bot_response, video_info)
            text_content = clean_text_content(text_content)

            # Send text message if there's content
            if text_content:
                text_payload = {
                    "recipient": {"id": sender_id},
                    "message": {"text": text_content},
                }
                requests.post(chatbot.messenger_url, headers=headers, json=text_payload)

            # Send videos with titles
            responses = []
            for video in video_info:
                # Send title if available
                if video.get("title"):
                    title_payload = {
                        "recipient": {"id": sender_id},
                        "message": {"text": f"🎥 *{video['title']}*"},
                    }
                    requests.post(
                        chatbot.messenger_url, headers=headers, json=title_payload
                    )

                # Send URL (Messenger auto-generates preview)
                url_payload = {
                    "recipient": {"id": sender_id},
                    "message": {"text": video["url"]},
                }
                response = requests.post(
                    chatbot.messenger_url, headers=headers, json=url_payload
                )
                responses.append(response.json())

            return {"status": "success", "responses": responses}

        else:
            # No videos, send normal message
            payload = {
                "recipient": {"id": sender_id},
                "message": {"text": bot_response},
            }
            response = requests.post(
                chatbot.messenger_url, headers=headers, json=payload
            )
            return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error sending Messenger message: {str(e)}")
        return {"error": str(e)}
    except Exception as e:
        print(f"Unexpected error in messenger_messages: {str(e)}")
        return {"error": str(e)}


def instagram_messages(sender_id, message_text, instagram_page_id):
    try:
        chatbot = Chatbot.objects.get(instagram_page_id=instagram_page_id)
    except ObjectDoesNotExist:
        print(f"Chatbot not found for instagram_page_id: {instagram_page_id}")
        return {"error": "Chatbot not found"}

    bot_response = query_assistant(
        user_input=message_text,
        chatbot=chatbot,
        user_id=sender_id,
        platform="instagram",
    )

    # Clean markdown formatting
    bot_response = clean_markdown_for_messaging(bot_response)

    # Format for natural display
    bot_response = format_for_whatsapp(bot_response)

    headers = {"Authorization": f"Bearer {chatbot.instagram_token}"}

    try:
        # Extract video information
        video_info = extract_video_info(bot_response)

        if video_info:
            # Remove video sections from main text
            text_content = remove_video_sections(bot_response, video_info)
            text_content = clean_text_content(text_content)

            # Send text message if there's content
            if text_content:
                text_payload = {
                    "recipient": {"id": sender_id},
                    "message": {"text": text_content},
                }
                requests.post(chatbot.instagram_url, headers=headers, json=text_payload)

            # Send videos with titles
            responses = []
            for video in video_info:
                # Send title if available
                if video.get("title"):
                    title_payload = {
                        "recipient": {"id": sender_id},
                        "message": {"text": f"🎥 *{video['title']}*"},
                    }
                    requests.post(
                        chatbot.instagram_url, headers=headers, json=title_payload
                    )

                # Send URL
                url_payload = {
                    "recipient": {"id": sender_id},
                    "message": {"text": video["url"]},
                }
                response = requests.post(
                    chatbot.instagram_url, headers=headers, json=url_payload
                )
                response_data = response.json()
                print(f"Instagram YouTube URL Send Response: {response_data}")
                responses.append(response_data)

            return {"status": "success", "responses": responses}

        else:
            # No videos, send normal message
            payload = {
                "recipient": {"id": sender_id},
                "message": {"text": bot_response},
            }
            response = requests.post(
                chatbot.instagram_url, headers=headers, json=payload
            )
            response_data = response.json()
            print(f"Instagram Message Send Response: {response_data}")
            return response_data

    except requests.exceptions.RequestException as e:
        print(f"Error sending Instagram message: {str(e)}")
        return {"error": str(e)}
    except Exception as e:
        print(f"Unexpected error in instagram_messages: {str(e)}")
        return {"error": str(e)}
