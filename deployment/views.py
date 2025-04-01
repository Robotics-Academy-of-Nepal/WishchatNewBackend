from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated 
# from playground.chatbot import query_assistant
from registration.models import Chatbot
import json
from .functions import sendwhatsapp_messages, messenger_messages, instagram_messages

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def whatsapp_credentials(request):
    try:
        whatsapp_url = request.data.get("whatsapp_url")
        whatsapp_token = request.data.get("whatsapp_token")
        whatsapp_id = request.data.get("whatsapp_id")
        chatbot_id = request.data.get("chatbot_id")

        chatbot = Chatbot.objects.get(id=chatbot_id)
        chatbot.whatsapp_url = whatsapp_url
        chatbot.whatsapp_token = whatsapp_token
        chatbot.whatsapp_id = whatsapp_id
        chatbot.save()

        # Return dynamic webhook URL and verify token
        webhook_url = f"https://kfwsdw58-8000.inc1.devtunnels.ms/api/webhook/{chatbot.id}/whatsapp/"
        return JsonResponse({
            "webhookurl": webhook_url,
            "verify_token": chatbot.verify_token
        }, status=200)

    except Chatbot.DoesNotExist:
        return JsonResponse({"error": "Chatbot not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=403)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def messenger_credentials(request):
    try:
        messenger_url = request.data.get("messenger_url")
        messenger_token = request.data.get("messenger_token")
        messenger_id = request.data.get("messenger_page_id")
        chatbot_id = request.data.get("chatbot_id")

        chatbot = Chatbot.objects.get(id=chatbot_id)
        chatbot.messenger_url = messenger_url
        chatbot.messenger_token = messenger_token
        chatbot.messenger_page_id = messenger_id
        chatbot.save()

        # Return dynamic webhook URL and verify token
        webhook_url = f"https://kfwsdw58-8000.inc1.devtunnels.ms/api/webhook/{chatbot.id}/messenger/"
        return JsonResponse({
            "webhookurl": webhook_url,
            "verify_token": chatbot.verify_token
        }, status=200)

    except Chatbot.DoesNotExist:
        return JsonResponse({"error": "Chatbot not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=403)
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def instagram_credentials(request):
    try:
        instagram_url = request.data.get("instagram_url")
        instagram_token = request.data.get("instagram_token")
        instagram_id = request.data.get("instagram_page_id")
        chatbot_id = request.data.get("chatbot_id")

        chatbot = Chatbot.objects.get(id=chatbot_id)
        chatbot.instagram_url = instagram_url
        chatbot.instagram_token = instagram_token
        chatbot.instagram_page_id = instagram_id
        chatbot.save()

        # Return dynamic webhook URL and verify token
        webhook_url = f"https://kfwsdw58-8000.inc1.devtunnels.ms/api/webhook/{chatbot.id}/instagram/"
        return JsonResponse({
            "webhookurl": webhook_url,
            "verify_token": chatbot.verify_token
        }, status=200)

    except Chatbot.DoesNotExist:
        return JsonResponse({"error": "Chatbot not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=403)
    


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def unified_webhook(request, chatbot_id, platform):
    try:
        chatbot = Chatbot.objects.get(id=chatbot_id)
    except Chatbot.DoesNotExist:
        return HttpResponse("Invalid chatbot ID", status=404)
    
    if request.method == 'GET':
        # Webhook verification
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == chatbot.verify_token:
            return HttpResponse(challenge, status=200)
        return HttpResponse("Invalid verification token", status=403)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else request.data
            print(f"Webhook data for {platform}/{chatbot_id}:", data)

            if platform == 'whatsapp':
                entries = data.get('entry', [])
                if not entries:
                    return JsonResponse({"status": "success", "message": "No entries"}, status=200)
                
                changes = entries[0].get('changes', [])
                if not changes:
                    return JsonResponse({"status": "success", "message": "No changes"}, status=200)
                
                value = changes[0].get('value', {})
                whatsapp_id = value.get('metadata', {}).get('phone_number_id')
                messages = value.get('messages', [])
                if not messages:
                    return JsonResponse({"status": "success", "message": "No messages"}, status=200)
                
                message = messages[0]
                sender_wa_id = message.get('from')
                message_body = message.get('text', {}).get('body')

                if sender_wa_id and message_body:
                    print(f"WhatsApp message from {sender_wa_id}: {message_body}")
                    response = sendwhatsapp_messages(sender_wa_id, message_body, whatsapp_id)
                    return JsonResponse({"status": "success", "message": "Message processed", "response": response}, status=200)

            elif platform == 'messenger':
                for entry in data.get('entry', []):
                    messenger_id = entry.get('id')
                    for messaging_event in entry.get('messaging', []):
                        if 'message' in messaging_event:
                            sender_id = messaging_event['sender']['id']
                            message_text = messaging_event['message']['text']
                            response = messenger_messages(sender_id, message_text, messenger_id)
                            return JsonResponse({"status": "success", "message": "Message processed", "response": response}, status=200)

            elif platform == 'instagram':
                for entry in data.get('entry', []):
                    instagram_id = entry.get('id')
                    for messaging_event in entry.get('messaging', []):
                        if 'message' in messaging_event:
                            sender_id = messaging_event['sender']['id']
                            message_text = messaging_event['message']['text']
                            response = instagram_messages(sender_id, message_text, instagram_id)
                            return JsonResponse({"status": "success", "message": "Message processed", "response": response}, status=200)


            return JsonResponse({"status": "success", "message": "No actionable data"}, status=200)

        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {str(e)}")
            return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
        except Exception as e:
            print(f"Webhook Error: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)