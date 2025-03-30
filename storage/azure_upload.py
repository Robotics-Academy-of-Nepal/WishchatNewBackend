import os  
from openai import AzureOpenAI
from azure.search.documents import SearchClient  
from azure.search.documents.indexes import SearchIndexClient  
from azure.core.credentials import AzureKeyCredential  
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    VectorSearchAlgorithmKind,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)
from dotenv import load_dotenv
import fitz


load_dotenv()


# Azure configuration  
service_name = os.getenv('SERVICE_NAME') 
admin_key = os.getenv('ADMIN_KEY')   
endpoint = os.getenv('SEARCH_ENDPOINT') 
doc_intelligent_endpoint = os.getenv('DOC_INTELLIGENT_ENDPOINT')   
doc_intelligent_key = os.getenv('DOC_INTELLIGENT_KEY') 
embedding_endpoint = os.getenv('EMBEDDING_ENDPOINT') 
embedding_api = os.getenv('EMBEDDING_API_KEY') 


  
# Create clients  
index_client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(admin_key))  



def extract_text_from_pdf(uploaded_file):
    """
    Extracts text from an uploaded PDF file using PyMuPDF.
    Args:
        uploaded_file: InMemoryUploadedFile object from Django request.FILES
    Returns:
        str: Extracted text from the PDF
    """
    try:
        # Open the file directly from memory (no need to save it)
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        all_text = []

        for page_num, page in enumerate(doc):
            text = page.get_text("text")  # Extract text
            all_text.append(f"--- Page {page_num + 1} ---\n{text}")

        return "\n".join(all_text)
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return ""


def extract_text_from_docx(uploaded_file):
    """
    Extracts text from an uploaded DOCX file.
    Args:
        uploaded_file: InMemoryUploadedFile object from Django request.FILES
    Returns:
        str: Extracted text from the DOCX
    """
    try:
        import docx
        # Save to a temporary file since python-docx doesn't work directly with file objects
        import tempfile
        temp = tempfile.NamedTemporaryFile(delete=False)
        temp.write(uploaded_file.read())
        temp.close()
        
        # Open with python-docx
        doc = docx.Document(temp.name)
        
        # Extract text
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
            
        # Remove temp file
        import os
        os.unlink(temp.name)
        
        return '\n'.join(full_text)
    except Exception as e:
        print(f"Error extracting text from DOCX: {str(e)}")
        return ""



def generate_embeddings(text):

    client = AzureOpenAI(
        api_key=embedding_api,
        api_version="2023-05-15",
        azure_endpoint=embedding_endpoint
    )

    """Generate embeddings using text-embedding-3 model"""
    response = client.embeddings.create(
        model="text-embedding-3-large",  
        input=text
    )
    embedding = response.data[0].embedding
    return embedding

def create_index_if_not_exists(index_name):  
    """Create Azure Search index if it doesn't exist"""
    try:  
        existing_index = index_client.get_index(index_name)  
        print(f"Index '{index_name}' already exists.")  
    except Exception as e:  
        print("Creating new index")

        # Define fields for the index
        fields = [
            SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="standard.lucene", retrievable=True),
            SearchableField(name="table_content", type=SearchFieldDataType.String, analyzer_name="standard.lucene", retrievable=True),
            SearchableField(name="id", type=SearchFieldDataType.String, key=True, filterable=True, retrievable=True),
            SearchableField(name="filename", type=SearchFieldDataType.String, filterable=True, retrievable=True),
            SimpleField(name="filepath", type=SearchFieldDataType.String),
            SimpleField(name="page_number", type=SearchFieldDataType.Int32),

            # Add vector field for embeddings
            SearchField(
                name="contentVector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=3072,  
                vector_search_profile_name="my-vector-profile",
            ),
        ]

        # Define vector search configuration
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="my-hnsw", 
                    kind=VectorSearchAlgorithmKind.HNSW,
                    parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine"
                    }
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="my-vector-profile", 
                    algorithm_configuration_name="my-hnsw"
                )
            ],
        )

        # Define semantic configuration
        semantic_config = SemanticConfiguration(
            name="semantic",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="filename"),
                content_fields=[
                    SemanticField(field_name="content"),
                    SemanticField(field_name="table_content")
                ]
            )
        )

        # Create semantic search settings
        semantic_search = SemanticSearch(configurations=[semantic_config])

        # Create the search index with vector and semantic search
        index = SearchIndex(
            name=index_name, 
            fields=fields, 
            vector_search=vector_search,
            semantic_search=semantic_search
        )

        index_client.create_or_update_index(index=index)
        print(f"Index '{index_name}' created successfully")



def create_consolidated_content(files_data, chatbot_name):
    """
    Creates a consolidated content string from multiple uploaded files.

    Args:
        files_data: List of dictionaries with 'file' and 'filename'.
        chatbot_name: The chatbot name for indexing.

    Returns:
        str: Consolidated text content from all files.
    """
    consolidated_content = ""

    for file_data in files_data:
        uploaded_file = file_data['file']
        filename = os.path.splitext(file_data['filename'])[0]  # Remove extension

        # Add filename as header
        consolidated_content += f"{filename}\n"

        # Read and add file content based on file type
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()

        if file_extension == '.pdf':
            print(f"Processing PDF file: {filename}")
            text = extract_text_from_pdf(uploaded_file)
            if not text:
                text = f"Error extracting content from {filename}"
            consolidated_content += text
        elif file_extension == '.docx':
            print(f"Processing DOCX file: {filename}")
            text = extract_text_from_docx(uploaded_file)
            if not text:
                text = f"Error extracting content from {filename}"
            consolidated_content += text
        else:
            # For text-based files
            content = uploaded_file.read().decode('utf-8')
            consolidated_content += content

        consolidated_content += "\n\n"  # Add separation between files
        uploaded_file.seek(0)  # Reset file pointer

    return consolidated_content


def split_text_into_chunks(text, max_tokens=400):  
    """
    Splits text into smaller chunks to avoid exceeding Azure AI Search token limits.

    Args:
        text (str): The full text to split.
        max_tokens (int): Maximum tokens per chunk (adjust as needed).

    Returns:
        list: List of text chunks.
    """
    words = text.split()  
    chunks = []  
    current_chunk = []  
    current_length = 0  

    for word in words:  
        current_length += len(word)  
        current_chunk.append(word)  

        if current_length >= max_tokens:  
            chunks.append(" ".join(current_chunk))  
            current_chunk = []  
            current_length = 0  

    if current_chunk:  
        chunks.append(" ".join(current_chunk))  

    return chunks  



def process_consolidated_files(files_data, index_name):
    """
    Process multiple files with each file being exactly one chunk in Azure Search.
    
    Args:
        files_data: List of dictionaries containing file objects and filenames.
        index_name: Name for the Azure Search index.

    Returns:
        str: Status message indicating success or failure.
    """
    print(f"Processing files for index: {index_name}")
    create_index_if_not_exists(index_name)

    try:
        # For holding all documents to upload
        all_documents = []
        doc_id = 1
        
        # Also create a consolidated file for reference
        all_text = ""
        
        for file_data in files_data:
            uploaded_file = file_data['file']
            filename = os.path.splitext(file_data['filename'])[0]

            print(f"Processing: {filename}")
            if uploaded_file.name.lower().endswith('.pdf'):
                text = extract_text_from_pdf(uploaded_file)
            elif uploaded_file.name.lower().endswith('.docx'):
                text = extract_text_from_docx(uploaded_file)
            else:
                text = uploaded_file.read().decode('utf-8')
            
            # Add file content to consolidated text (for reference file)
            all_text += f"\n\n--- File: {filename} ---\n\n{text}"
            
            # Create a document for this specific file
            document = {
                "id": f"{index_name}-{doc_id}",
                "filename": filename,
                "filepath": "file_chunk",
                "content": text,
                "table_content": "",
                "page_number": doc_id
            }
            
            # Generate embedding for this file
            document["contentVector"] = generate_embeddings(text)
            all_documents.append(document)
            doc_id += 1
        
        # Save consolidated content to a file for reference
        with open(f"{index_name}_consolidated.txt", "w", encoding="utf-8") as f:
            f.write(all_text)
        print(f"Saved consolidated content to {index_name}_consolidated.txt")
        
        # Upload all documents to Azure AI Search
        message = upload_to_search(all_documents, index_name)
        return message

    except Exception as e:
        print(f"Error in process_consolidated_files: {str(e)}")
        return f"failed: {str(e)}"
    


def upload_to_search(documents, index_name):
    """Upload documents to Azure Search"""
    print(f"Using index: {index_name}")
    # print("documents: ", documents)
    try:  
        # Generate embeddings for each document
        for doc in documents:
            doc["contentVector"] = generate_embeddings(doc["content"])
        
        # print("documents: ", documents)
        search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(admin_key)
        )  
        result = search_client.upload_documents(documents)  
        return f"Uploaded {len(documents)} documents. Result:", result 
    except Exception as e:  
        print(f"Error uploading documents: {str(e)}")
        return "failed"

    
def get_existing_content(index_name, filename):
    """
    Retrieve existing content from Azure Search index
    """
    print("index_name: ", index_name)
    try:
        search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(admin_key)
        )
        
        results = search_client.search(
            search_text="*",  # Search all documents
            filter=f"filename eq '{filename}'",
            select=["content"]
        )
        for result in results:
            print("Found Content: ", result["content"])
            return result['content']
        
        return ""
    except Exception as e:
        print(f"Error retrieving existing content: {str(e)}")
        return ""


def update_consolidated_content(files_data, index_name, chatbot_name, regenerate=False):
    """
    Update content with each file as its own chunk.
    If regenerate is True, delete existing content and add only new files.
    
    Args:
        files_data: List of dictionaries containing file objects and filenames.
        index_name: Name of the Azure Search index.
        chatbot_name: Chatbot name for the index name.
        regenerate: Whether to regenerate all content (used when deleting files).
        
    Returns:
        str: Status message indicating success or failure.
    """
    print(f"Updating content for index: {index_name}")
    
    try:
        # For tracking documents
        all_documents = []
        
        # If regenerating, delete existing documents
        if regenerate:
            search_client = SearchClient(
                endpoint=endpoint,
                index_name=index_name,
                credential=AzureKeyCredential(admin_key)
            )
            
            # Query all documents to get their IDs
            results = search_client.search(search_text="*", select=["id"])
            doc_ids = [result["id"] for result in results]
            
            # Delete existing documents if there are any
            if doc_ids:
                for doc_id in doc_ids:
                    search_client.delete_documents([{"id": doc_id}])
                print(f"Deleted {len(doc_ids)} existing documents")
        
        # Create documents for new files
        doc_id = 1  # Start with ID 1 if regenerating
        
        # If not regenerating, find the highest existing ID to avoid conflicts
        if not regenerate:
            search_client = SearchClient(
                endpoint=endpoint,
                index_name=index_name,
                credential=AzureKeyCredential(admin_key)
            )
            
            results = search_client.search(search_text="*", select=["id"], top=1000)
            existing_ids = [int(result["id"].split('-')[1]) for result in results if len(result["id"].split('-')) > 1]
            doc_id = max(existing_ids) + 1 if existing_ids else 1
            
        # Save all text for consolidated reference file
        all_text = ""
        
        # Process each new file
        for file_data in files_data:
            uploaded_file = file_data['file']
            filename = os.path.splitext(file_data['filename'])[0]

            print(f"Processing: {filename}")
            if uploaded_file.name.lower().endswith('.pdf'):
                text = extract_text_from_pdf(uploaded_file)
            elif uploaded_file.name.lower().endswith('.docx'):
                text = extract_text_from_docx(uploaded_file)
            else:
                text = uploaded_file.read().decode('utf-8')
            
            # Add to consolidated text
            all_text += f"\n\n--- File: {filename} ---\n\n{text}"
            
            # Create document for this file
            document = {
                "id": f"{index_name}-{doc_id}",
                "filename": filename,
                "filepath": "file_chunk",
                "content": text,
                "table_content": "",
                "page_number": doc_id
            }
            
            document["contentVector"] = generate_embeddings(text)
            all_documents.append(document)
            doc_id += 1
            
        # Update the consolidated reference file
        if not regenerate:
            # Get existing consolidated content if any
            try:
                with open(f"{index_name}_consolidated.txt", "r", encoding="utf-8") as f:
                    existing_text = f.read()
                all_text = existing_text + "\n\n" + all_text
            except FileNotFoundError:
                pass
                
        # Save consolidated content
        with open(f"{index_name}_consolidated.txt", "w", encoding="utf-8") as f:
            f.write(all_text)
        print(f"Saved consolidated content to {index_name}_consolidated.txt")
        
        # Upload to Azure Search
        message = upload_to_search(all_documents, index_name)
        return message
        
    except Exception as e:
        print(f"Error in update_consolidated_content: {str(e)}")
        return f"failed: {str(e)}"
    
def delete_document_from_azure_index(index_name, filename):
    """
    Delete a document with the specified filename from the Azure Search index.
    If it's the last document, delete the entire index.
    
    Args:
        index_name (str): The name of the Azure Search index
        filename (str): The filename to delete
        
    Returns:
        tuple: (success, message) where success is a boolean and message is an explanation
    """
    try:
        search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(admin_key)
        )
        
        # First, check how many documents are in the index
        result_count = 0
        results = search_client.search(search_text="*", include_total_count=True)
        result_count = results.get_count()
        
        # Find the document ID for this filename
        # Since we can't filter by filename if it's not filterable, we'll use search
        doc_results = search_client.search(
            filter=f"filename eq '{filename}'",  # Search for exact filename
            select=["id", "filename"]
        )
        
        # Find documents with matching filename
        documents_to_delete = []
        for doc in doc_results:
            # Double-check exact match since search can return partial matches
            if doc.get("filename") == filename:
                documents_to_delete.append({"id": doc["id"]})
        
        if not documents_to_delete:
            return False, f"No documents found with filename: {filename}"
        
        # If this is the last document and we need to delete the index
        if result_count <= len(documents_to_delete):
            # Delete the entire index
            index_client = SearchIndexClient(
                endpoint=endpoint,
                credential=AzureKeyCredential(admin_key)
            )
            index_client.delete_index(index_name)
            return True, f"Index {index_name} deleted as it contained only the document(s) to be deleted"
        
        # Otherwise, just delete the specific document(s)
        result = search_client.delete_documents(documents=documents_to_delete)
        
        # Check if all deletes were successful
        all_succeeded = all(status.succeeded for status in result)
        
        if all_succeeded:
            return True, f"Successfully deleted {len(documents_to_delete)} document(s) with filename: {filename}"
        else:
            # Collect error messages
            errors = [f"ID: {status.key}, Error: {status.error_message}" 
                     for status in result if not status.succeeded]
            return False, f"Partial failure deleting documents: {'; '.join(errors)}"
            
    except Exception as e:
        return False, f"Error deleting document(s): {str(e)}"