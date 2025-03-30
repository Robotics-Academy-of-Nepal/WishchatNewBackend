from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication
from registration.models import Chatbot
from .chatbot import query_assistant

class APIKeyOrTokenAuthentication:
    """
    Custom authentication class that checks for API key in headers
    and falls back to TokenAuthentication
    """
    def __init__(self):
        self.token_auth = TokenAuthentication()
    
    def authenticate(self, request):
        # First try API key authentication
        api_key = request.headers.get('X-API-Key')
        if api_key:
            try:
                chatbot = Chatbot.objects.get(api_key=api_key)
                request.chatbot_from_api_key = chatbot
                return (None, None)
            except Chatbot.DoesNotExist:
                return None
        
        # Fall back to token authentication
        try:
            return self.token_auth.authenticate(request)
        except:
            return None

@api_view(['POST'])
@authentication_classes([APIKeyOrTokenAuthentication])
@permission_classes([AllowAny]) 
def handle_query(request):
    try:
        user_query = request.data.get('query')
        temperature = request.data.get('temperature', 0.7)  # Default temperature
        
        if not user_query:
            return JsonResponse({'error': 'No query provided.'}, status=400)
        
        # API key authentication path
        if hasattr(request, 'chatbot_from_api_key'):
            chatbot = request.chatbot_from_api_key
            system_prompt = getattr(chatbot, 'system_prompt', None)
            print("System Prompt being used is: ", system_prompt)
            
            # Optional: Warn if chatbot_id is provided and mismatches
            provided_chatbot_id = request.data.get('chatbot_id')
            if provided_chatbot_id and str(provided_chatbot_id) != str(chatbot.id):
                print(f"Warning: Provided chatbot_id {provided_chatbot_id} does not match API key chatbot {chatbot.id}")

            response = query_assistant(
                user_input=user_query,
                chatbot=chatbot,
                prompt=system_prompt,
                temperature=temperature
            )
            return JsonResponse({'response': response}, status=200)
        
        # Token authentication path
        else:
            if not request.user or not request.user.is_authenticated:
                return JsonResponse({'error': 'Authentication required.'}, status=401)
            
            chatbot_id = request.data.get('chatbot_id')
            if not chatbot_id:
                return JsonResponse({'error': 'No chatbot ID provided. Required for token authentication.'}, status=400)
            
            try:
                chatbot = Chatbot.objects.get(id=chatbot_id)
                if request.user.organization != chatbot.organization:
                    return JsonResponse({'error': 'You do not have permission to access this chatbot.'}, status=403)
                
                system_prompt = getattr(chatbot, 'system_prompt', None)
                response = query_assistant(
                    user_input=user_query,
                    chatbot=chatbot,
                    prompt=system_prompt,
                    temperature=temperature
                )
                return JsonResponse({'response': response}, status=200)
            
            except Chatbot.DoesNotExist:
                return JsonResponse({'error': 'Chatbot not found.'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_chatbot_prompt(request):
    try:
        chatbot_id = request.data.get('chatbot_id')
        prompt = request.data.get('prompt')
        
        if not chatbot_id:
            return JsonResponse({'error': 'No chatbot ID provided.'}, status=400)
        
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            if request.user.organization != chatbot.organization:
                return JsonResponse({'error': 'You do not have permission to modify this chatbot.'}, status=403)
            
            chatbot.system_prompt = prompt
            chatbot.save()
            return JsonResponse({'message': 'System Prompt saved successfully.'}, status=200)
        
        except Chatbot.DoesNotExist:
            return JsonResponse({'error': 'Chatbot not found.'}, status=404)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)