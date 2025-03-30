# # chatbot.py
# import os
# from openai import AzureOpenAI
# from dotenv import load_dotenv
# import tiktoken
# from storage.models import ChatbotDocumentGroup
# from registration.models import ChatbotTokenUsage  





# load_dotenv()


# def initialize_client():
#     """Initializes the Azure OpenAI client."""
#     endpoint = os.getenv("ENDPOINT_URL")
#     subscription_key = os.getenv("AZURE_OPENAI_API_KEY")

#     return AzureOpenAI(
#         azure_endpoint=endpoint,
#         api_key=subscription_key,
#         api_version="2024-05-01-preview",
#     )

# client = initialize_client()
# last_response = None

# def count_tokens(text: str, model: str = "gpt-4") -> int:
#     """Count tokens for a given text using the specified model's tokenizer."""
#     encoder = tiktoken.encoding_for_model(model)
#     return len(encoder.encode(text))

# def count_message_tokens(messages: list, model: str = "gpt-4") -> int:
#     """Count tokens in a list of messages."""
#     encoder = tiktoken.encoding_for_model(model)
#     total_tokens = 0
    
#     for message in messages:
#         total_tokens += len(encoder.encode(message["content"]))
#         total_tokens += len(encoder.encode(message["role"]))
#         total_tokens += 3  # message overhead
    
#     total_tokens += 3  # conversation overhead
#     return total_tokens

# def get_chatbot_index_name(chatbot):
#     """Get the consolidated index name for a chatbot."""
#     try:
#         doc_group = ChatbotDocumentGroup.objects.get(chatbot=chatbot)
#         if doc_group.active_documents.exists():
#             # Return the index name from the document group
#             return doc_group.index_name
#         return None
#     except ChatbotDocumentGroup.DoesNotExist:
#         return None

# def validate_index_exists(index_name, search_endpoint, search_key):
#     """Validate that the index exists before querying."""
#     import requests
    
#     headers = {
#         'api-key': search_key,
#         'Content-Type': 'application/json'
#     }
    
#     url = f"{search_endpoint}/indexes/{index_name}?api-version=2024-03-01-preview"
    
#     try:
#         response = requests.get(url, headers=headers)
#         return response.status_code == 200
#     except Exception:
#         return False

# def query_assistant(user_input, chatbot, prompt='', temperature=0.7):
#     """
#     Query assistant using the chatbot's index
#     """
#     global last_response
#     deployment = os.getenv("DEPLOYMENT_NAME")
#     search_endpoint = os.getenv("SEARCH_ENDPOINT")
#     search_key = os.getenv("SEARCH_KEY")

#     # Get chatbot's index name
#     index_name = get_chatbot_index_name(chatbot)
    
#     if not index_name:
#         return "No documents available to search. Please upload some documents first."
    
#     # Check if the chatbot can send messages (quota)
#     if hasattr(chatbot, 'quota') and not chatbot.quota.can_send_message():
#         if chatbot.quota.is_trial:
#             return "Your free trial has expired or you've reached your message limit. Please upgrade to continue using the chatbot."
#         else:
#             return "You've reached your message limit or your subscription has expired. Please renew your subscription to continue using the chatbot."

#     if prompt == '' or prompt is None:
#         system_prompt = {
#             "role": "system",
#             "content": """
#                 ### Role
#                 - Primary Function: You are an AI chatbot who helps users understand their documents. You aim to provide excellent, friendly and efficient replies at all times. Your role is to listen attentively to the user, understand their needs, and synthesize information from their documents to provide comprehensive answers. If a question is not clear, ask clarifying questions.
                        
#                 ### Constraints
#                 1. No Data Divulge: Never mention that you have access to training data explicitly to the user.
#                 2. Maintaining Focus: Stay focused on the user's query and provide relevant information from their documents.
#                 3. Information Integration: When answering queries, consider all relevant information and integrate it coherently.
#                 4. Source Attribution: While you shouldn't mention the documents explicitly, ensure your responses accurately reflect the knowledge from the sources.
#                 5. Comprehensive Coverage: For each query, analyze all available information to provide the most complete and accurate response possible.
#                 6. Word Limitations: Always answer within 40 words , do not exceed that word limit.
#                 7. Language selection: If query is in Nepali or Romanized Nepali only answer in Nepali language, answer in english language if query is in English or explicitly asked to. Never Answer in Romanized Nepali.
#                 """   
#         }
#     else:
#         system_prompt = {
#             "role": "system",
#             "content": prompt
#         }

#     messages = [
#         {"role": "system", "content": system_prompt["content"]}
#     ]
    
#     if last_response and isinstance(last_response, str):
#         messages.append({"role": "assistant", "content": last_response})
    
#     messages.append({"role": "user", "content": user_input})

#     # Count input tokens
#     input_tokens = count_message_tokens(messages)
#     print("Temperature:", temperature)

#     try:
#         data_sources = [{
#             "type": "azure_search",
#             "parameters": {
#                 "endpoint": search_endpoint,
#                 "index_name": index_name,
#                 "semantic_configuration": "semantic",
#                 "query_type": "vector_semantic_hybrid",  
#                 "role_information": system_prompt["content"],
#                 "in_scope": True,
#                 "filter": None,
#                 "strictness": 5,
#                 "top_n_documents": 10,
#                 "authentication": {
#                     "type": "api_key",
#                     "key": search_key
#                 },
#                 "embedding_dependency": {
#                     "type": "deployment_name",
#                     "deployment_name": "text-embedding-3-large"
#                 }
#             }
#         }]
    

#         completion = client.chat.completions.create(
#             model=deployment,
#             messages=messages,
#             max_tokens=512,
#             temperature=temperature,
#             top_p=0.95,
#             frequency_penalty=0,
#             presence_penalty=0,
#             stop=None,
#             stream=False,
#             extra_body={
#                 "data_sources": data_sources
#             }
#         )


#         assistant_response = completion.choices[0].message.content
        
#         # Count output tokens
#         output_tokens = count_tokens(assistant_response)
        
#         # Print token usage
#         print("\n=== Token Usage ===")
#         print(f"Input tokens: {input_tokens}")
#         print(f"Output tokens: {output_tokens}")
#         print(f"Total tokens: {input_tokens + output_tokens}")
#         print("=================\n")

#         # Save token usage in the database
#         ChatbotTokenUsage.log_usage(
#             chatbot=chatbot,
#             input_tokens=input_tokens,
#             output_tokens=output_tokens
#         )

#         # Update message quota if successful
#         if hasattr(chatbot, 'quota'):
#             chatbot.quota.messages_used += 2
#             chatbot.quota.save()

#         last_response = assistant_response

#         # Clean up response
#         assistant_response = assistant_response.replace("**", "")
#         assistant_response = assistant_response.replace("[", "")
#         assistant_response = assistant_response.replace("]", "")
#         assistant_response = assistant_response.replace("doc1", "")
#         assistant_response = assistant_response.replace("(", "")
#         assistant_response = assistant_response.replace(")", "")

#         return assistant_response

#     except Exception as e:
#         print(f"Error during conversation: {e}")
#         return f"Error during conversation: {e}"