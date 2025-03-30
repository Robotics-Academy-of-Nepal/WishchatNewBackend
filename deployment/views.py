from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated 
# from playground.chatbot import query_assistant
from registration.models import Chatbot
import json
from .functions import sendwhatsapp_messages, messenger_messages

VERIFY_TOKEN = 'd27260f9-0e18-4d9d-9a76-8039b5baa7c7'


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def whatsapp_credentials(request):
    try:
        # Extract data from request
        whatsappurl = request.data.get("whatsapp_url")
        whatsapptoken = request.data.get("whatsapp_token")
        whatsappid = request.data.get("whatsapp_id")
        chatbot_id = request.data.get("chatbot_id")

        # Fetch the Chatbot instance (raise error if not found)
        chatbot = Chatbot.objects.get(id=chatbot_id)

        # Update the chatbot fields
        chatbot.whatsapp_url = whatsappurl
        chatbot.whatsapp_token = whatsapptoken
        chatbot.whatsapp_id = whatsappid
        chatbot.save()

        # Success response
        return JsonResponse({
            "webhookurl": "https://kfwsdw58-8000.inc1.devtunnels.ms/api/1dfb88d7-85fb-4e62-ba34-2446150ad8e5",
            "verify_token": "d27260f9-0e18-4d9d-9a76-8039b5baa7c7"
        }, status=200)

    except Chatbot.DoesNotExist:
        return JsonResponse({"error": "Chatbot not found"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=403)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def messenger_credentials(request):
    try:
        # Extract data from request
        messengerurl = request.data.get("messenger_url")
        messengertoken = request.data.get("messenger_token")
        messengerid = request.data.get("messenger_page_id")
        chatbot_id = request.data.get("chatbot_id")

        # Fetch the Chatbot instance (raise error if not found)
        chatbot = Chatbot.objects.get(id=chatbot_id)

        # Update the chatbot fields
        chatbot.messenger_url = messengerurl
        chatbot.messenger_token = messengertoken
        chatbot.messenger_page_id = messengerid
        chatbot.save()

        # Success response
        return JsonResponse({
            "webhookurl": "https://kfwsdw58-8000.inc1.devtunnels.ms/api/facebook",
            "verify_token": "d27260f9-0e18-4d9d-9a76-8039b5baa7c7"
        }, status=200)

    except Chatbot.DoesNotExist:
        return JsonResponse({"error": "Chatbot not found"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=403)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def whatsAppWebhook(request):
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        else:
            return HttpResponse('error', status=403)

    elif request.method == 'POST':
        try:
            # Load request body
            data = json.loads(request.body)
            print("data:", data)
            
            # Safely extract entries
            entries = data.get('entry', [])
            if not entries:
                return JsonResponse({"status": "success", "message": "No entries found"}, status=200)
            
            # Extract changes
            changes = entries[0].get('changes', [])
            if not changes:
                return JsonResponse({"status": "success", "message": "No changes found"}, status=200)
            
            # Extract value
            value = changes[0].get('value', {})
            
            
            whatsapp_id = value.get('metadata', {}).get('phone_number_id')
            print("Phone Number ID:", whatsapp_id)
            
            # Extract messages
            messages = value.get('messages', [])
            if not messages:
                return JsonResponse({"status": "success", "message": "No messages found"}, status=200)
            
            # Extract message data
            message = messages[0]
            print("Message:", message)
            
            sender_wa_id = message.get('from')
            message_text = message.get('text', {})
            message_body = message_text.get('body') if message_text else None
            
            if not sender_wa_id or not message_body:
                return JsonResponse({"status": "success", "message": "Invalid message format"}, status=200)
            
            # Log the received message
            print(f"Message received from {sender_wa_id}: {message_body}")


            
            whatsapp_message = sendwhatsapp_messages(sender_wa_id, message_body,whatsapp_id)
            # print("whatsapp_message:", whatsapp_message)
            return JsonResponse({"status": "success", "message": "Message processed"}, status=200)

        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {str(e)}")
            return JsonResponse({"status": "success", "message": "Invalid JSON"}, status=200)
            
        except Exception as e:
            print(f"Webhook Error: {str(e)}")
            return JsonResponse({"status": "success", "message": "Message received"}, status=200)
        
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def facebook_messenger_webhook(request):
    """
    Facebook Messenger Webhook endpoint for verification and message handling
    """
    if request.method == 'GET':
        # Handle webhook verification
        verify_token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if verify_token == VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse("Invalid verification token", status=403)

    elif request.method == 'POST':
        try:
            # Parse the incoming webhook data
            data = request.data
            print("data is: ", data)
            # Process each entry in the webhook payload
            for entry in data.get('entry', []):
                print("entry is :", entry)
                messenger_id = entry.get('id')
                print("messenger_id is: ", messenger_id)
                for messaging_event in entry.get('messaging', []):
                    if 'message' in messaging_event:
                        sender_id = messaging_event['sender']['id']
                        message_text = messaging_event['message']['text']
                        messenger_messages(sender_id, message_text,messenger_id)
                        
            
            return HttpResponse("EVENT_RECEIVED", status=200)
            
        except Exception as e:
            print(f"Error processing webhook: {str(e)}")
            return HttpResponse(f"Error: {str(e)}", status=400)