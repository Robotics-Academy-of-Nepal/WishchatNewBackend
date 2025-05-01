import requests
from registration.models import Chatbot
from playground.chatbot import query_assistant

# def sendwhatsapp_messages(phoneNumber, message, whatsapp_id):

#     print("whatsapp id:", whatsapp_id)
    
#     duplicate_chatbots = Chatbot.objects.filter(whatsapp_id=whatsapp_id)
#     chatbot_names = [chatbot.name for chatbot in duplicate_chatbots]
#     print(f"Duplicate chatbots with ID {whatsapp_id}: {chatbot_names}")
#     for chatbot in duplicate_chatbots:
#         print(f"ID: {chatbot.id}, Name: {chatbot.name}")

#     chatbot = Chatbot.objects.get(whatsapp_id=whatsapp_id)
    
#     whatsappurl = chatbot.whatsapp_url
#     whatsapptoken = chatbot.whatsapp_token 
#     apiKey = chatbot.api_key
#     query = message

#     print("API key is: ", apiKey)

#     payload = {
#     'query': query,
#     'temperature': 0.7 
#     }
    
#     headers = {
#     'X-API-Key': apiKey,
#     'Content-Type': 'application/json'
#     }

#     # Send POST request
#     chatbot_response = requests.post('http://127.0.0.1:8000/api/query/', json=payload, headers=headers)

#     bot_response = "No response generated"
#     if chatbot_response.status_code == 200:
#         response_data = chatbot_response.json()  # Properly parse the JSON response
#         bot_response = response_data.get('response', bot_response)
#         print("bot response:", bot_response)

#     try:
#         headers = {"Authorization":f"Bearer {whatsapptoken}" }
#         payload = {
#             "messaging_product": 'whatsapp',
#             "recipient_type": "individual",
#             "to": phoneNumber,
#             "type": "text",
#             "text": {"body": bot_response}
#         }

#         response = requests.post(whatsappurl, headers=headers, json=payload)
#         ans = response.json()
#         return ans
#     except Exception as e:
#         print(f"Error sending WhatsApp message: {str(e)}")
#         return {"error": str(e)}
    

# def messenger_messages(sender_id, message_text, messenger_page_id):

#     print("messenger id:", messenger_page_id)

#     duplicate_chatbots = Chatbot.objects.filter(messenger_page_id=messenger_page_id)
#     chatbot_names = [chatbot.name for chatbot in duplicate_chatbots]
#     print(f"Duplicate chatbots with ID {messenger_page_id}: {chatbot_names}")

#     chatbot = Chatbot.objects.get(messenger_page_id=messenger_page_id)
#     messengerurl = chatbot.messenger_url
#     messengertoken = chatbot.messenger_token 
#     apiKey = chatbot.api_key
#     query = message_text

#     print("API key is: ", apiKey)

#     payload = {
#     'query': query,
#     'temperature': 0.7 
#     }
    
#     headers = {
#     'X-API-Key': apiKey,
#     'Content-Type': 'application/json'
#     }

#     # Send POST request
#     chatbot_response = requests.post('http://127.0.0.1:8000/api/query/', json=payload, headers=headers)

#     bot_response = "No response generated"
#     if chatbot_response.status_code == 200:
#         response_data = chatbot_response.json()  # Properly parse the JSON response
#         bot_response = response_data.get('response', bot_response)
#         print("bot response:", bot_response)

#     try:
#         headers = {"Authorization":f"Bearer {messengertoken}" }
#         payload = {
#         "recipient": {
#             "id": sender_id
#         },
#         "message": {
#             "text": bot_response
#         }
#     }

#         response = requests.post(messengerurl, headers=headers, json=payload)
#         ans = response.json()
#         return ans
#     except Exception as e:
#         print(f"Error sending messenger message: {str(e)}")
#         return {"error": str(e)}
    

# def instagram_messages(sender_id, message_text, instagram_page_id):
#     print("instagram id:", instagram_page_id)

#     duplicate_chatbots = Chatbot.objects.filter(instagram_page_id=instagram_page_id)
#     chatbot_names = [chatbot.name for chatbot in duplicate_chatbots]
#     print(f"Duplicate chatbots with ID {instagram_page_id}: {chatbot_names}")

#     chatbot = Chatbot.objects.get(instagram_page_id=instagram_page_id)
#     instagramurl = chatbot.instagram_url
#     instagramtoken = chatbot.instagram_token 
#     apiKey = chatbot.api_key
#     query = message_text

#     print("API key is: ", apiKey)

#     payload = {
#     'query': query,
#     'temperature': 0.7 
#     }
    
#     headers = {
#     'X-API-Key': apiKey,
#     'Content-Type': 'application/json'
#     }

#     # Send POST request
#     chatbot_response = requests.post('http://127.0.0.1:8000/api/query/', json=payload, headers=headers)

#     bot_response = "No response generated"
#     if chatbot_response.status_code == 200:
#         response_data = chatbot_response.json()  # Properly parse the JSON response
#         bot_response = response_data.get('response', bot_response)
#         print("bot response:", bot_response)

#     try:
#         headers = {"Authorization":f"Bearer {instagramtoken}" }
#         payload = {
#         "recipient": {
#             "id": sender_id
#         },
#         "message": {
#             "text": bot_response
#         }
#     }

#         response = requests.post(instagramurl, headers=headers, json=payload)
#         ans = response.json()
#         return ans
#     except Exception as e:
#         print(f"Error sending instagram message: {str(e)}")
#         return {"error": str(e)}

def sendwhatsapp_messages(phoneNumber, message, whatsapp_id):
    chatbot = Chatbot.objects.get(whatsapp_id=whatsapp_id)
    
    # Use query_assistant directly
    bot_response = query_assistant(
        user_input=message,
        chatbot=chatbot,
        user_id=phoneNumber,  # sender_wa_id
        platform='whatsapp'
    )

    try:
        headers = {"Authorization": f"Bearer {chatbot.whatsapp_token}"}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phoneNumber,
            "type": "text",
            "text": {"body": bot_response}
        }
        response = requests.post(chatbot.whatsapp_url, headers=headers, json=payload)
        return response.json()
    except Exception as e:
        print(f"Error sending WhatsApp message: {str(e)}")
        return {"error": str(e)}

def messenger_messages(sender_id, message_text, messenger_page_id):
    chatbot = Chatbot.objects.get(messenger_page_id=messenger_page_id)
    
    bot_response = query_assistant(
        user_input=message_text,
        chatbot=chatbot,
        user_id=sender_id,
        platform='messenger'
    )
    
    try:
        headers = {"Authorization": f"Bearer {chatbot.messenger_token}"}
        payload = {
            "recipient": {"id": sender_id},
            "message": {"text": bot_response}
        }
        response = requests.post(chatbot.messenger_url, headers=headers, json=payload)
        return response.json()
    except Exception as e:
        print(f"Error sending Messenger message: {str(e)}")
        return {"error": str(e)}

def instagram_messages(sender_id, message_text, instagram_page_id):
    chatbot = Chatbot.objects.get(instagram_page_id=instagram_page_id)
    
    bot_response = query_assistant(
        user_input=message_text,
        chatbot=chatbot,
        user_id=sender_id,
        platform='instagram'
    )
    
    try:
        headers = {"Authorization": f"Bearer {chatbot.instagram_token}"}
        payload = {
            "recipient": {"id": sender_id},
            "message": {"text": bot_response}
        }
        response = requests.post(chatbot.instagram_url, headers=headers, json=payload)
        response_data = response.json()
        print(f"Instagram Message Send Response: {response_data}")  # Log the response
        return response_data
    except Exception as e:
        print(f"Error sending Instagram message: {str(e)}")
        return {"error": str(e)}