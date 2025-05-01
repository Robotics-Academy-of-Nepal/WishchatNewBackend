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
import requests


load_dotenv()

meta_client_id = os.getenv("META_CLIENT_ID")
meta_client_secret = os.getenv("META_CLIENT_SECRET")
messenger_redirect_uri = os.getenv("MESSENGER_REDIRECT_URI")
instagram_redirect_uri = os.getenv("INSTAGRAM_REDIRECT_URI")
base_webhook_url = os.getenv("BASE_WEBHOOK_URL")

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

        # Construct the Meta OAuth authorization URL
        auth_url = 'https://www.facebook.com/v20.0/dialog/oauth'
        # Encode chatbot_id into the state parameter (you can use a delimiter or JSON for more complex data)
        state = f"whatsapp_{chatbot_id}"  # Combine a prefix with chatbot_id
        params = {
            'client_id': meta_client_id,
            'redirect_uri': messenger_redirect_uri,
            'scope': 'whatsapp_business_management,whatsapp_business_messaging',
            'response_type': 'code',
            'state': state  # Pass chatbot_id in state
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
            
        # Parse the state parameter to extract chatbot_id
        if not state or not state.startswith('whatsapp_'):
            return Response(
                {"error": "Invalid state parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Extract chatbot_id from state (remove the 'whatsapp_' prefix)
        chatbot_id = state[len('whatsapp_'):]
        if not chatbot_id:
            return Response(
                {"error": "No chatbot_id found in state"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Exchange code for access token
        token_url = "https://graph.facebook.com/v20.0/oauth/access_token"
        token_params = {
            'client_id': meta_client_id,
            'client_secret': meta_client_secret,
            'redirect_uri': messenger_redirect_uri,
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
            
            print("Accounts Data: ", accounts_data)


            whatsapp_business_url = "https://graph.facebook.com/v20.0/me/whatsapp_business_account"
            whatsapp_response = requests.get(whatsapp_business_url, headers=headers)
            whatsapp_data = whatsapp_response.json()
            
            # Extract WhatsApp Business Account ID
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def messenger_oauth(request):
    """
    Initiate the OAuth flow for Messenger by returning the Facebook authorization URL as a JSON response.
    """
    try:
        # Get chatbot_id from query parameters
        chatbot_id = request.GET.get('chatbot_id')
        if not chatbot_id:
            return Response(
                {"error": "chatbot_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Construct the Facebook OAuth authorization URL
        auth_url = 'https://www.facebook.com/v20.0/dialog/oauth'
        state = f"messenger_{chatbot_id}"  # Encode chatbot_id in state
        params = {
            'client_id': meta_client_id,
            'redirect_uri': messenger_redirect_uri,
            'scope': 'pages_messaging,pages_manage_metadata,pages_show_list',  # Required permissions
            'response_type': 'code',
            'state': state  # Pass chatbot_id in state
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
def messenger_oauth_callback(request):
    """
    Handle the callback from Facebook Messenger OAuth process, store the credentials,
    set up the webhook in Meta Developer App, and subscribe the Page for events.
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
            
        # Parse the state parameter to extract chatbot_id
        if not state or not state.startswith('messenger_'):
            return Response(
                {"error": "Invalid state parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Extract chatbot_id from state (remove the 'messenger_' prefix)
        chatbot_id = state[len('messenger_'):]
        if not chatbot_id:
            return Response(
                {"error": "No chatbot_id found in state"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Exchange code for access token
        token_url = "https://graph.facebook.com/v20.0/oauth/access_token"
        token_params = {
            'client_id': meta_client_id,
            'client_secret': meta_client_secret,
            'redirect_uri': messenger_redirect_uri,
            'code': code
        }
        
        # Make the request to	via the Graph API
        token_response = requests.post(token_url, params=token_params)
        token_data = token_response.json()
        
        if 'access_token' not in token_data:
            return Response(
                {"error": "Failed to obtain access token", "details": token_data},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_access_token = token_data['access_token']
        
        try:
            # Get accounts (Pages) the user has access to
            accounts_url = "https://graph.facebook.com/v20.0/me/accounts"
            headers = {'Authorization': f'Bearer {user_access_token}'}
            accounts_response = requests.get(accounts_url, headers=headers)
            accounts_data = accounts_response.json()
            
            print("Accounts Data: ", accounts_data)

            # Check if accounts_data contains data
            if 'data' not in accounts_data or not accounts_data['data']:
                return Response(
                    {"error": "No accounts found for this user", "details": accounts_data},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Use the first Page (you can modify this to let the user choose a Page)
            page = accounts_data['data'][0]  # e.g., 'Tees Heaven' with ID '119744001222118'
            page_id = page['id']
            page_access_token = page['access_token']  # Page-specific access token
            
            # Verify that the Page has Messenger enabled (optional, for debugging)
            messenger_profile_url = f"https://graph.facebook.com/v20.0/{page_id}/messenger_profile"
            messenger_response = requests.get(messenger_profile_url, headers=headers)
            messenger_data = messenger_response.json()
            
            print("Messenger Profile Data: ", messenger_data)

            # Update the chatbot with Messenger credentials
            chatbot = Chatbot.objects.get(id=chatbot_id)
            messenger_api_url = f"https://graph.facebook.com/v20.0/{page_id}/messages"  # The API endpoint for sending messages
            chatbot.messenger_token = page_access_token  # Store the Page Access Token
            chatbot.messenger_page_id = page_id  # Store the Page ID
            chatbot.messenger_url = messenger_api_url  # Store the Messenger API endpoint for sending messages

            print("Messenger URL: ", chatbot.messenger_url)
            
            chatbot.save()

            # Step 1: Set the webhook URL and verify token in the Meta Developer App
            app_access_token = f"{meta_client_id}|{meta_client_secret}"  # Client Credentials Flow (simplified)
            dynamic_webhook_url = f"{base_webhook_url}{chatbot.id}/messenger/"  # Dynamic webhook URL for receiving events
            webhook_setup_url = f"https://graph.facebook.com/v20.0/{meta_client_id}/subscriptions"
            webhook_params = {
                'object': 'page',
                'callback_url': dynamic_webhook_url,
                'fields': 'messages,messaging_postbacks',
                'verify_token': str(chatbot.verify_token),  # Use the chatbot's verify_token
                'access_token': app_access_token
            }
            webhook_response = requests.post(webhook_setup_url, params=webhook_params)
            webhook_data = webhook_response.json()
            
            print("Webhook Setup Response: ", webhook_data)

            if 'success' not in webhook_data or not webhook_data['success']:
                return Response(
                    {"error": "Failed to set up webhook in Meta Developer App", "details": webhook_data},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Step 2: Subscribe the app to the Page for Messenger webhooks
            subscribe_url = f"https://graph.facebook.com/v20.0/{page_id}/subscribed_apps"
            subscribe_params = {
                'subscribed_fields': 'messages,messaging_postbacks',  # Events to subscribe to
                'access_token': page_access_token
            }
            subscribe_response = requests.post(subscribe_url, params=subscribe_params)
            subscribe_data = subscribe_response.json()
            
            print("Page Subscription Response: ", subscribe_data)

            if 'success' not in subscribe_data or not subscribe_data['success']:
                return Response(
                    {"error": "Failed to subscribe to Messenger webhooks for the Page", "details": subscribe_data},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(
                {"success": True, "message": "Messenger integration and webhook setup fully automated"},
                status=status.HTTP_200_OK
            )
            
        except Chatbot.DoesNotExist:
            return Response(
                {"error": f"Chatbot with ID {chatbot_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to update chatbot or set up webhook: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        return Response(
            {"error": f"OAuth callback failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instagram_oauth(request):
    """
    Initiate the OAuth flow for Instagram using the Facebook Page-based approach.
    """
    try:
        # Get chatbot_id from query parameters
        chatbot_id = request.GET.get('chatbot_id')
        if not chatbot_id:
            return Response(
                {"error": "chatbot_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Construct the Facebook OAuth authorization URL
        auth_url = 'https://www.facebook.com/v20.0/dialog/oauth'
        state = f"instagram_{chatbot_id}"  # Encode chatbot_id in state
        params = {
            'client_id': meta_client_id,
            'redirect_uri': instagram_redirect_uri,
            'scope': 'instagram_basic,instagram_manage_messages,pages_show_list,pages_manage_metadata',  # Required permissions
            'response_type': 'code',
            'state': state  # Pass chatbot_id in state
        }
        full_auth_url = f"{auth_url}?{urllib.parse.urlencode(params)}"

        # Log the full OAuth URL for debugging
        print("Instagram OAuth URL (via Facebook): ", full_auth_url)

        # Return the authorization URL as a JSON response
        return Response(
            {"authorization_url": full_auth_url},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def instagram_oauth_callback(request):
    """
    Handle the callback from Facebook/Instagram OAuth process, store the credentials,
    set up the webhook in Meta Developer App, and subscribe the Page for events.
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
            
        # Parse the state parameter to extract chatbot_id
        if not state or not state.startswith('instagram_'):
            return Response(
                {"error": "Invalid state parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Extract chatbot_id from state (remove the 'instagram_' prefix)
        chatbot_id = state[len('instagram_'):]
        if not chatbot_id:
            return Response(
                {"error": "No chatbot_id found in state"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Exchange code for access token
        token_url = "https://graph.facebook.com/v20.0/oauth/access_token"
        token_params = {
            'client_id': meta_client_id,
            'client_secret': meta_client_secret,
            'redirect_uri': instagram_redirect_uri,
            'code': code
        }
        
        # Make the request to exchange code for token
        token_response = requests.post(token_url, params=token_params)
        token_data = token_response.json()
        
        if 'access_token' not in token_data:
            return Response(
                {"error": "Failed to obtain access token", "details": token_data},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_access_token = token_data['access_token']
        print("The function reached here.")
        # user_id = token_data['user_id']

        try:
            # Get the Instagram Business Account details
            accounts_url = "https://graph.facebook.com/v20.0/me/accounts"
            headers = {'Authorization': f'Bearer {user_access_token}'}
            accounts_response = requests.get(accounts_url, headers=headers)
            accounts_data = accounts_response.json()
            
            print("Accounts Data: ", accounts_data)

            if 'data' not in accounts_data or not accounts_data['data']:
                return Response(
                    {"error": "No accounts found for this user", "details": accounts_data},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Use the first Page (you can modify this to let the user choose a Page)
            page = accounts_data['data'][0]  # e.g., 'Tees Heaven' with ID '119744001222118'
            page_id = page['id']
            page_access_token = page['access_token']  # Page-specific access token
            
            # Get the Instagram Business Account linked to this Page
            ig_business_url = f"https://graph.facebook.com/v20.0/{page_id}?fields=instagram_business_account"
            ig_response = requests.get(ig_business_url, headers=headers)
            ig_data = ig_response.json()
            
            print("Instagram Business Account Data: ", ig_data)

            # Check if an Instagram Business Account is linked
            if 'instagram_business_account' not in ig_data or not ig_data['instagram_business_account']:
                return Response(
                    {"error": "No Instagram Business Account linked to this Page", "details": ig_data},
                    status=status.HTTP_400_BAD_REQUEST
                )

            ig_business_account_id = ig_data['instagram_business_account']['id']
            
            # Update the chatbot with Instagram credentials
            chatbot = Chatbot.objects.get(id=chatbot_id)
            instagram_api_url = f"https://graph.facebook.com/v20.0/{ig_business_account_id}/messages"  # The API endpoint for sending messages
            chatbot.instagram_token = page_access_token  # Store the Instagram Access Token
            chatbot.instagram_page_id = ig_business_account_id  # Store the Instagram Business Account ID
            chatbot.instagram_url = instagram_api_url  # Store the Instagram API endpoint for sending messages
            chatbot.save()

            # Step 1: Set the webhook URL and verify token in the Meta Developer App
            app_access_token = f"{meta_client_id}|{meta_client_secret}"  # Client Credentials Flow (simplified)
            dynamic_webhook_url = f"{base_webhook_url}{chatbot.id}/instagram/"  # Dynamic webhook URL for receiving events
            webhook_setup_url = f"https://graph.facebook.com/v20.0/{meta_client_id}/subscriptions"
            webhook_params = {
                'object': 'instagram',
                'callback_url': dynamic_webhook_url,
                'fields': 'messages,messaging_postbacks',
                'verify_token': str(chatbot.verify_token),  # Use the chatbot's verify_token
                'access_token': app_access_token
            }
            webhook_response = requests.post(webhook_setup_url, params=webhook_params)
            webhook_data = webhook_response.json()
            
            print("Webhook Setup Response: ", webhook_data)

            if 'success' not in webhook_data or not webhook_data['success']:
                return Response(
                    {"error": "Failed to set up webhook in Meta Developer App", "details": webhook_data},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Step 2: Attempt to subscribe the app to the Instagram Business Account for webhooks
            subscribe_url = f"https://graph.facebook.com/v20.0/{ig_business_account_id}/subscribed_apps"
            subscribe_params = {
                'subscribed_fields': 'messages,messaging_postbacks',  # Events to subscribe to
                'access_token': user_access_token
            }
            subscribe_response = requests.post(subscribe_url, params=subscribe_params)
            subscribe_data = subscribe_response.json()
            
            print("Instagram Subscription Response: ", subscribe_data)

            # If subscription fails, log the error but allow the integration to proceed
            if 'success' not in subscribe_data or not subscribe_data['success']:
                print("Warning: Failed to subscribe to Instagram webhooks. You may need to complete App Review or manually subscribe in the Meta Developer Portal.")
                return Response(
                    {
                        "success": True,
                        "message": "Instagram integration completed, but webhook subscription failed. You may need to complete App Review or manually subscribe in the Meta Developer Portal.",
                        "details": subscribe_data
                    },
                    status=status.HTTP_200_OK
                )

            return Response(
                {"success": True, "message": "Instagram integration and webhook setup fully automated"},
                status=status.HTTP_200_OK
            )
            
        except Chatbot.DoesNotExist:
            return Response(
                {"error": f"Chatbot with ID {chatbot_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to update chatbot or set up webhook: {str(e)}"},
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