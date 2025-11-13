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

    # Clean markdown formatting
    bot_response = clean_markdown_for_messaging(bot_response)

    headers = {"Authorization": f"Bearer {chatbot.whatsapp_token}"}

    try:
        # Check if response contains YouTube URLs
        youtube_urls = extract_youtube_urls(bot_response)

        if youtube_urls:
            # Remove URLs from main text
            text_without_urls = bot_response
            for url in youtube_urls:
                text_without_urls = text_without_urls.replace(url, "").strip()

            # Clean up extra whitespace
            text_without_urls = re.sub(r"\s+", " ", text_without_urls).strip()
            text_without_urls = re.sub(r"\n\s*\n\s*\n+", "\n\n", text_without_urls)

            # Send the text message if there's content
            if text_without_urls:
                text_payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": phoneNumber,
                    "type": "text",
                    "text": {"body": text_without_urls},
                }
                requests.post(chatbot.whatsapp_url, headers=headers, json=text_payload)

            # Send each YouTube URL as a separate message for preview
            responses = []
            for url in youtube_urls:
                url_payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": phoneNumber,
                    "type": "text",
                    "text": {
                        "body": url,
                        "preview_url": True,  # This enables link preview
                    },
                }
                response = requests.post(
                    chatbot.whatsapp_url, headers=headers, json=url_payload
                )
                responses.append(response.json())

            return {"status": "success", "responses": responses}

        else:
            # No YouTube URLs, send normal text message
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

    headers = {"Authorization": f"Bearer {chatbot.messenger_token}"}

    try:
        # Check if response contains YouTube URLs
        youtube_urls = extract_youtube_urls(bot_response)

        if youtube_urls:
            # Send text without URLs first (if there's text content)
            text_without_urls = bot_response
            for url in youtube_urls:
                text_without_urls = text_without_urls.replace(url, "").strip()

            text_without_urls = re.sub(r"\s+", " ", text_without_urls).strip()
            text_without_urls = re.sub(r"\n\s*\n\s*\n+", "\n\n", text_without_urls)

            # Send text message if there's content
            if text_without_urls:
                text_payload = {
                    "recipient": {"id": sender_id},
                    "message": {"text": text_without_urls},
                }
                requests.post(chatbot.messenger_url, headers=headers, json=text_payload)

            # Send YouTube URLs as separate messages (Messenger auto-generates preview)
            responses = []
            for url in youtube_urls:
                url_payload = {"recipient": {"id": sender_id}, "message": {"text": url}}
                response = requests.post(
                    chatbot.messenger_url, headers=headers, json=url_payload
                )
                responses.append(response.json())

            return {"status": "success", "responses": responses}

        else:
            # No YouTube URLs, send normal message
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

    headers = {"Authorization": f"Bearer {chatbot.instagram_token}"}

    try:
        # Check if response contains YouTube URLs
        youtube_urls = extract_youtube_urls(bot_response)

        if youtube_urls:
            # Send text without URLs first (if there's text content)
            text_without_urls = bot_response
            for url in youtube_urls:
                text_without_urls = text_without_urls.replace(url, "").strip()

            text_without_urls = re.sub(r"\s+", " ", text_without_urls).strip()
            text_without_urls = re.sub(r"\n\s*\n\s*\n+", "\n\n", text_without_urls)

            # Send text message if there's content
            if text_without_urls:
                text_payload = {
                    "recipient": {"id": sender_id},
                    "message": {"text": text_without_urls},
                }
                requests.post(chatbot.instagram_url, headers=headers, json=text_payload)

            # Send YouTube URLs separately
            responses = []
            for url in youtube_urls:
                url_payload = {"recipient": {"id": sender_id}, "message": {"text": url}}
                response = requests.post(
                    chatbot.instagram_url, headers=headers, json=url_payload
                )
                response_data = response.json()
                print(f"Instagram YouTube URL Send Response: {response_data}")
                responses.append(response_data)

            return {"status": "success", "responses": responses}

        else:
            # No YouTube URLs, send normal message
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
