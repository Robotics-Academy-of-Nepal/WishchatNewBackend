from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated 
from rest_framework.response import Response
from rest_framework import status
from registration.models import Chatbot
import json
from .functions import sendwhatsapp_messages, messenger_messages, instagram_messages
import urllib.parse
from dotenv import load_dotenv
import os


load_dotenv()

meta_client_id = os.getenv("META_CLIENT_ID")
meta_client_secret = os.getenv("META_CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URI")

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def whatsapp_oauth(request):
    """
    Initiate the OAuth flow for WhatsApp by returning the Meta authorization URL as a JSON response.
    """
    try:
        # Get chatbot_id from query parameters
        chatbot_id = request.GET.get('chatbot_id')
        if not chatbot_id:
            return Response(
                {"error": "chatbot_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Store chatbot_id in session for use in the callback
        request.session['chatbot_id'] = chatbot_id

        # Construct the Meta OAuth authorization URL
        auth_url = 'https://www.facebook.com/v20.0/dialog/oauth'
        params = {
            'client_id': meta_client_id,
            'redirect_uri': redirect_uri,
            'scope': 'whatsapp_business_management,whatsapp_business_messaging',
            'response_type': 'code',
            'state': 'whatsapp'  # Optional: to verify the callback
        }
        auth_url = f"{auth_url}?{urllib.parse.urlencode(params)}"

        # Return the authorization URL as a JSON response
        return Response(
            {"authorization_url": auth_url},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['GET'])
@permission_classes([AllowAny])

def whatsapp_oauth_callback(request):
    """
    Handle the callback from Meta/WhatsApp OAuth process and store the access token.
    """
    try:
        # Get authorization code and state from the callback
        code = request.GET.get('code')
        state = request.GET.get('state')
        
        if not code:
            return Response(
                {"error": "Authorization failed. No code was received."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Verify state if applicable (security check)
        if state != 'whatsapp':
            return Response(
                {"error": "Invalid state parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Retrieve the chatbot_id from session
        chatbot_id = request.session.get('chatbot_id')
        if not chatbot_id:
            return Response(
                {"error": "No chatbot_id found in session"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Exchange code for access token
        token_url = "https://graph.facebook.com/v20.0/oauth/access_token"
        token_params = {
            'client_id': meta_client_id,
            'client_secret': meta_client_secret,
            'redirect_uri': redirect_uri,
            'code': code
        }
        
        # Make the request to exchange code for token
        import requests
        token_response = requests.post(token_url, params=token_params)
        token_data = token_response.json()
        
        if 'access_token' not in token_data:
            return Response(
                {"error": "Failed to obtain access token", "details": token_data},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        access_token = token_data['access_token']
        
        try:
            # Example API call to get accounts the user has access to
            accounts_url = "https://graph.facebook.com/v20.0/me/accounts"
            headers = {'Authorization': f'Bearer {access_token}'}
            accounts_response = requests.get(accounts_url, headers=headers)
            accounts_data = accounts_response.json()
            
            whatsapp_business_url = "https://graph.facebook.com/v20.0/me/whatsapp_business_account"
            whatsapp_response = requests.get(whatsapp_business_url, headers=headers)
            whatsapp_data = whatsapp_response.json()
            
            # Extract WhatsApp Business Account ID
            # Note: This is a simplified approach - actual implementation depends on Meta's API response structure
            whatsapp_business_id = whatsapp_data.get('data', [{}])[0].get('id') if 'data' in whatsapp_data else None
            
            if not whatsapp_business_id:
                return Response(
                    {"error": "Failed to retrieve WhatsApp Business Account ID", "details": whatsapp_data},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Update the chatbot with WhatsApp credentials
            chatbot = Chatbot.objects.get(id=chatbot_id)
            chatbot.whatsapp_token = access_token
            chatbot.whatsapp_id = whatsapp_business_id
            chatbot.save()
            
            # Clear the session data
            if 'chatbot_id' in request.session:
                del request.session['chatbot_id']
                
            return Response(
                {"success": True, "message": "WhatsApp integration successful"},
                status=status.HTTP_200_OK
            )
            
        except Chatbot.DoesNotExist:
            return Response(
                {"error": f"Chatbot with ID {chatbot_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to update chatbot with WhatsApp credentials: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        return Response(
            {"error": f"OAuth callback failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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