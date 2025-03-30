import requests
from registration.models import Chatbot

def sendwhatsapp_messages(phoneNumber, message, whatsapp_id):

    print("whatsapp id:", whatsapp_id)
    chatbot = Chatbot.objects.get(whatsapp_id=whatsapp_id)
    whatsappurl = chatbot.whatsapp_url
    whatsapptoken = chatbot.whatsapp_token 
    apiKey = chatbot.api_key
    query = message

    print("API key is: ", apiKey)

    payload = {
    'query': query,
    'temperature': 0.7 
    }
    
    headers = {
    'X-API-Key': apiKey,
    'Content-Type': 'application/json'
    }

    # Send POST request
    chatbot_response = requests.post('http://127.0.0.1:8000/api/query/', json=payload, headers=headers)

    bot_response = "No response generated"
    if chatbot_response.status_code == 200:
        response_data = chatbot_response.json()  # Properly parse the JSON response
        bot_response = response_data.get('response', bot_response)
        print("bot response:", bot_response)

    try:
        headers = {"Authorization":f"Bearer {whatsapptoken}" }
        payload = {
            "messaging_product": 'whatsapp',
            "recipient_type": "individual",
            "to": phoneNumber,
            "type": "text",
            "text": {"body": bot_response}
        }

        response = requests.post(whatsappurl, headers=headers, json=payload)
        ans = response.json()
        return ans
    except Exception as e:
        print(f"Error sending WhatsApp message: {str(e)}")
        return {"error": str(e)}
    

def messenger_messages(sender_id, message_text, messenger_page_id):

    print("whatsapp id:", messenger_page_id)
    chatbot = Chatbot.objects.get(messenger_page_id=messenger_page_id)
    messengerurl = chatbot.messenger_url
    messengertoken = chatbot.messenger_token 
    apiKey = chatbot.api_key
    query = message_text

    print("API key is: ", apiKey)

    payload = {
    'query': query,
    'temperature': 0.7 
    }
    
    headers = {
    'X-API-Key': apiKey,
    'Content-Type': 'application/json'
    }

    # Send POST request
    chatbot_response = requests.post('http://127.0.0.1:8000/api/query/', json=payload, headers=headers)

    bot_response = "No response generated"
    if chatbot_response.status_code == 200:
        response_data = chatbot_response.json()  # Properly parse the JSON response
        bot_response = response_data.get('response', bot_response)
        print("bot response:", bot_response)

    try:
        headers = {"Authorization":f"Bearer {messengertoken}" }
        payload = {
        "recipient": {
            "id": sender_id
        },
        "message": {
            "text": bot_response
        }
    }

        response = requests.post(messengerurl, headers=headers, json=payload)
        ans = response.json()
        return ans
    except Exception as e:
        print(f"Error sending WhatsApp message: {str(e)}")
        return {"error": str(e)}