from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication
from registration.models import Chatbot, ChatbotAPILog, ChatbotQuota
from registration.serializers import ChatbotQuotaSerializer
from .chatbot import query_assistant
from django.db.models import Count
from django.db.models.functions import TruncHour
from sklearn.cluster import KMeans
import numpy as np
from datetime import datetime, timedelta, timezone
from django.utils import timezone as tz
from django.utils.timezone import get_current_timezone


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
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chatbot_traffic_stats(request, chatbot_id):
    try:
        chatbot = Chatbot.objects.get(id=chatbot_id)
        if request.user.organization != chatbot.organization:
            return JsonResponse({'error': 'You do not have permission to access this chatbot.'}, status=403)
        
        registration_date = chatbot.created_at
        today_date = tz.now()
        local_tz = get_current_timezone()

        filter_month = request.GET.get('month')
        filter_year = request.GET.get('year')

        logs = ChatbotAPILog.objects.filter(chatbot=chatbot)
        if filter_year:
            year = int(filter_year)
            start_date = max(registration_date, datetime(year, 1, 1, tzinfo=timezone.utc))
            end_date = min(today_date, datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
            logs = logs.filter(timestamp__range=(start_date, end_date))
        
        elif filter_month:
            month_map = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            month_num = month_map.get(filter_month.lower())
            if not month_num:
                return JsonResponse({'error': 'Invalid month name.'}, status=400)
            year = today_date.year if month_num <= today_date.month else today_date.year - 1
            start_date = max(registration_date, datetime(year, month_num, 1, tzinfo=timezone.utc))
            next_month = month_num + 1 if month_num < 12 else 1
            next_year = year if month_num < 12 else year + 1
            end_day = (datetime(next_year, next_month, 1, tzinfo=timezone.utc) - timedelta(days=1)).day
            end_date = min(datetime(year, month_num, end_day, 23, 59, 59, tzinfo=timezone.utc), today_date)
            logs = logs.filter(timestamp__range=(start_date, end_date))
        
        else:
            start_date = datetime(today_date.year, today_date.month, 1, tzinfo=timezone.utc)
            end_date = today_date
            logs = logs.filter(timestamp__range=(start_date, end_date))

        if not logs.exists():
            return JsonResponse({
                'top_peak_traffic_hours': [],
                # 'traffic_data': [],
                'top_searched_queries': []
            }, status=200)

        # Peak traffic hours (Top 5)
        hourly_traffic = (logs.annotate(hour=TruncHour('timestamp'))
                         .values('hour')
                         .annotate(hits=Count('id'))
                         .order_by('-hits')[:5])
        top_peak_traffic_hours = [
            {'time': entry['hour'].astimezone(local_tz).strftime('%Y-%m-%d %H:00'), 'hits': entry['hits']}
            for entry in hourly_traffic
        ]

        # Traffic data for graph (all hours in the period)
        all_hours_traffic = (logs.annotate(hour=TruncHour('timestamp'))
                            .values('hour')
                            .annotate(hits=Count('id'))
                            .order_by('hour'))
        traffic_data = [
            {'time': entry['hour'].astimezone(local_tz).strftime('%Y-%m-%d %H:00'), 'hits': entry['hits']}
            for entry in all_hours_traffic
        ]

        # Filter out conversational queries
        conversational_keywords = {'hello', 'hi', 'hey', 'namaste', 'नमस्ते', 'how are you', 'कस्तो छ', 'bye', 'goodbye'}
        logs_with_queries = logs.filter(query__isnull=False).exclude(query='')
        filtered_logs = [log for log in logs_with_queries if log.query.lower() and not any(kw in log.query.lower() for kw in conversational_keywords)]

        if not filtered_logs:
            top_searched_queries = []
            print("Top searched queries list-1: ",top_searched_queries )
        else:
            # Collect queries, embeddings, and timestamps
            valid_data = [
                (log.query.strip().replace('\n', '').replace('\\', ''), log.get_embedding(), log.timestamp)
                for log in filtered_logs
                if log.get_embedding() is not None and not np.any(np.isnan(log.get_embedding()))
            ]

            if len(valid_data) >= 2:
                # Cluster queries using embeddings
                embedding_array = np.array([data[1] for data in valid_data])
                num_clusters = min(5, len(embedding_array))
                kmeans = KMeans(n_clusters=num_clusters, random_state=42)
                clusters = kmeans.fit_predict(embedding_array)
                cluster_counts = np.bincount(clusters)
                
                # Group queries by cluster
                cluster_data = {}
                for i, (query, _, timestamp) in enumerate(valid_data):
                    cluster = clusters[i]
                    if cluster not in cluster_data:
                        cluster_data[cluster] = []
                    cluster_data[cluster].append((query, timestamp))
                
                # Select top clusters and first query by timestamp
                top_clusters = sorted(range(len(cluster_counts)), key=lambda x: cluster_counts[x], reverse=True)[:5]
                top_searched_queries = []
                print("Top searched queries list-2: ",top_searched_queries )
                for cluster in top_clusters:
                    cluster_queries = cluster_data[cluster]
                    if cluster_queries:
                        # Sort by timestamp to get the earliest query
                        earliest_query = min(cluster_queries, key=lambda x: x[1])[0]
                        count = len(cluster_queries)
                        top_searched_queries.append({'query': earliest_query, 'count': count})
            else:
                # Fallback to frequency count (rare case)
                query_counts = {}
                for query, _, _ in valid_data:
                    normalized_query = query.strip().replace('\n', '').replace('\\', '')
                    query_counts[normalized_query] = query_counts.get(normalized_query, 0) + 1
                top_searched_queries = [{'query': q, 'count': c} for q, c in sorted(query_counts.items(), key=lambda x: x[1], reverse=True)[:5]]


        print("Top searched queries list-3: ",top_searched_queries )

        return JsonResponse({
            'top_peak_traffic_hours': top_peak_traffic_hours,
            # 'traffic_data': traffic_data,
            'top_searched_queries': top_searched_queries
        }, status=200)
    
    except Chatbot.DoesNotExist:
        return JsonResponse({'error': 'Chatbot not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chatbot_quota_data(request, chatbot_id):
    try:
        chatbot = Chatbot.objects.get(id=chatbot_id)
        if request.user.organization != chatbot.organization:
            return JsonResponse({'error': 'You do not have permission to access this chatbot.'}, status=403)
        
        quota = ChatbotQuota.objects.get(chatbot=chatbot)

        serializer = ChatbotQuotaSerializer(quota)

        return JsonResponse({'quota': serializer.data}, status=200)
    
    except Chatbot.DoesNotExist:
        return JsonResponse({'error': 'Chatbot not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)