import os
from dotenv import load_dotenv
import tiktoken
from storage.models import ChatbotDocumentGroup
from registration.models import ChatbotTokenUsage, Chatbot, ChatbotConversation, ChatbotAPILog
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import json

load_dotenv()

# ChromaDB Configuration
CHROMA_DB_PATH = "./chroma_db"
embedding_endpoint = os.getenv('EMBEDDING_ENDPOINT')
embedding_api = os.getenv('EMBEDDING_API_KEY')
embeddings = AzureOpenAIEmbeddings(
    azure_deployment="text-embedding-3-large",
    openai_api_version="2023-05-15",
    azure_endpoint=embedding_endpoint,
    api_key=embedding_api
)

# Azure OpenAI Chat Client
llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("ENDPOINT_URL"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-05-01-preview",
    deployment_name=os.getenv("DEPLOYMENT_NAME"),
    max_tokens=512,
    temperature=0.7,  # Default, overridden by request
    top_p=0.95,
    frequency_penalty=0,
    presence_penalty=0
)

# Short-term context (in-memory, resets on restart)
session_history = []

# Token Counting Functions
def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens for a given text using the specified model's tokenizer."""
    encoder = tiktoken.encoding_for_model(model)
    return len(encoder.encode(text))

def count_message_tokens(messages: list, model: str = "gpt-4") -> int:
    """Count tokens in a list of messages."""
    encoder = tiktoken.encoding_for_model(model)
    total_tokens = 0
    for message in messages:
        total_tokens += len(encoder.encode(message["content"]))
        total_tokens += len(encoder.encode(message["role"]))
        total_tokens += 3  # Message overhead
    total_tokens += 3  # Conversation overhead
    return total_tokens

# Helper Functions
def get_chatbot_index_name(chatbot):
    """Get the consolidated index name for a chatbot."""
    try:
        doc_group = ChatbotDocumentGroup.objects.get(chatbot=chatbot)
        if doc_group.active_documents.exists():
            return doc_group.index_name
        return None
    except ChatbotDocumentGroup.DoesNotExist:
        return None

def get_file_list(chatbot):
    """Get list of filenames for the chatbot's documents."""
    try:
        doc_group = ChatbotDocumentGroup.objects.get(chatbot=chatbot)
        return ", ".join(doc.filename for doc in doc_group.active_documents.all())
    except ChatbotDocumentGroup.DoesNotExist:
        return "no files"

def format_history(history):
    """Format conversation history for the prompt."""
    return "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-5:]]) if history else "No prior conversation."

def query_assistant(user_input, chatbot, prompt='', temperature=0.7, user_id=None, platform=None):
    """
    Query assistant using RAG with ChromaDB, incorporating short-term and long-term context.
    """

    query_embedding = embeddings.embed_query(user_input)
    # print("query_embeddings:", query_embedding)

    log_entry = ChatbotAPILog.objects.create(
        chatbot = chatbot,
        platform = platform,
        user_id = user_id,
        query = user_input
    )
    log_entry.set_embedding(query_embedding)
    log_entry.save()

    # Check quota
    if hasattr(chatbot, 'quota') and not chatbot.quota.can_send_message():
        if chatbot.quota.is_trial:
            return "Your free trial has expired or you've reached your message limit. Please upgrade to continue using the chatbot."
        else:
            return "You've reached your message limit or your subscription has expired. Please renew your subscription to continue using the chatbot."

    # Get chatbot's collection
    index_name = get_chatbot_index_name(chatbot)
    if not index_name:
        return "No documents available to search. Please upload some documents first."

    # Initialize ChromaDB retriever
    vector_store = Chroma(
        collection_name=f"chatbot_{chatbot.id}",
        embedding_function=embeddings,
        persist_directory=CHROMA_DB_PATH
    )
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 7}
    )

    # Load long-term history if user_id and platform are provided
    long_term_history = []
    if user_id and platform:
        try:
            conversation = ChatbotConversation.objects.get(chatbot=chatbot, user_id=user_id, platform=platform)
            long_term_history = json.loads(conversation.history)  # SQLite TextField
            # Trim long-term history to 5 exchanges for token efficiency
            if len(long_term_history) > 5:
                long_term_history = long_term_history[-5:]
                conversation.history = json.dumps(long_term_history)
                conversation.save()
        except ChatbotConversation.DoesNotExist:
            conversation = ChatbotConversation.objects.create(
                chatbot=chatbot,
                user_id=user_id,
                platform=platform,
                history='[]'
            )

    # Combine short-term and long-term history
    combined_history = long_term_history + session_history

    # Custom system prompt
    file_list = get_file_list(chatbot)
    if not prompt or prompt == "":
        system_prompt_content = f"""
        ### Role
        - You are an AI chatbot designed to assist users based on their uploaded documents: {file_list}. You can also handle greetings and small talk politely.

        ### Capabilities
        1. Language: Respond in English if the query is in English. If the query is in Nepali or Romanized Nepali, respond in pure Nepali (never Romanized Nepali).
        2. Scope: If the query is unrelated to the document content, analyze the retrieved context and creatively redirect. Say something like: "I’m sorry, I don’t have info on your query, but I have knowledge about [document topic, e.g., robotics]. How can I assist with that?" (English) or "माफ गर्नुहोस्, मसँग तपाईंको प्रश्नको जानकारी छैन, तर म [document topic, e.g., रोबोटिक्स] बारे जानकार छु। त्यसमा कसरी मद्दत गर्न सक्छु?" (Nepali).
        3. Word Limit: Keep responses between 80-100 words.
        4. Greetings: Respond to greetings like "hello" or "नमस्ते" with a friendly reply, e.g., "Hello! How can I assist you today?" or "नमस्ते! म तपाईंलाई आज कसरी सहयोग गर्न सक्छु?"

        ### Constraints
        - Base answers on document content unless it’s a greeting or small talk. Use the context to infer the document topic for off-topic responses.

        ### Conversation History
        {format_history(combined_history)}
        """
    else:
        system_prompt_content = prompt  # Use provided prompt if available

    # Build RAG chain
    prompt_template = ChatPromptTemplate.from_template(
        """
        {system_prompt}
        
        Context from documents:
        {context}
        
        User query: {question}
        
        Answer:
        """
    )

    # Messages for token counting
    messages = [{"role": "system", "content": system_prompt_content}]
    messages.extend(combined_history[-5:])  # Limit to last 5 exchanges
    messages.append({"role": "user", "content": user_input})
    input_tokens = count_message_tokens(messages)
    print("Temperature:", temperature)

    try:
        # RAG chain
        chain = (
            {"context": retriever, "question": RunnablePassthrough(), "system_prompt": lambda x: system_prompt_content}
            | prompt_template
            | llm.bind(temperature=temperature)
            | StrOutputParser()
        )

        # Execute RAG
        assistant_response = chain.invoke(user_input)

        # Update histories
        session_history.append({"role": "user", "content": user_input})
        session_history.append({"role": "assistant", "content": assistant_response})
        if user_id and platform:
            updated_history = long_term_history
            updated_history.append({"role": "user", "content": user_input})
            updated_history.append({"role": "assistant", "content": assistant_response})
            # Trim to 5 exchanges
            if len(updated_history) > 5:
                updated_history = updated_history[-5:]
            conversation.history = json.dumps(updated_history)
            conversation.save()

        # Count context and output tokens
        retrieved_docs = retriever.invoke(user_input)
        context = "\n".join([doc.page_content for doc in retrieved_docs])
        context_tokens = count_tokens(context)
        total_input_tokens = input_tokens + context_tokens
        output_tokens = count_tokens(assistant_response)

        # Print token usage
        print("\n=== Token Usage ===")
        print(f"Input tokens (prompt): {input_tokens}")
        print(f"Context tokens: {context_tokens}")
        print(f"Total input tokens: {total_input_tokens}")
        print(f"Output tokens: {output_tokens}")
        print(f"Total tokens: {total_input_tokens + output_tokens}")
        print("=================\n")

        # Save token usage
        ChatbotTokenUsage.log_usage(
            chatbot=chatbot,
            input_tokens=total_input_tokens,
            output_tokens=output_tokens
        )

        # Update quota
        if hasattr(chatbot, 'quota'):
            chatbot.quota.messages_used += 1  # Increment by 1 per message, not 2
            chatbot.quota.save()

        print(assistant_response)
        return assistant_response

    except Exception as e:
        print(f"Error during conversation: {e}")
        return f"Error during conversation: {e}"