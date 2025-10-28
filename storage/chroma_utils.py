import os
import tempfile
from dotenv import load_dotenv
import fitz
import docx
from langchain_openai import AzureOpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

load_dotenv()

embedding_endpoint = os.getenv("EMBEDDING_ENDPOINT")
embedding_api = os.getenv("EMBEDDING_API_KEY")
embeddings = AzureOpenAIEmbeddings(
    azure_deployment="text-embedding-3-large",
    openai_api_version="2023-05-15",
    azure_endpoint=embedding_endpoint,
    api_key=embedding_api,
)

CHROMA_DB_PATH = "./chroma_db"


def extract_text_from_pdf(uploaded_file):
    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        all_text = []
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            all_text.append(f"--- Page {page_num + 1} ---\n{text}")
        return "\n".join(all_text)
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return ""


def extract_text_from_docx(uploaded_file):
    try:
        temp = tempfile.NamedTemporaryFile(delete=False)
        temp.write(uploaded_file.read())
        temp.close()
        doc = docx.Document(temp.name)
        full_text = [para.text for para in doc.paragraphs]
        os.unlink(temp.name)
        return "\n".join(full_text)
    except Exception as e:
        print(f"Error extracting text from DOCX: {str(e)}")
        return ""


def extract_text_from_txt(uploaded_file):
    try:
        return uploaded_file.read().decode("utf-8")
    except Exception as e:
        print(f"Error extracting text from TXT: {str(e)}")
        return ""


def process_and_store_files(files_data, chatbot_id):
    try:
        collection_name = f"chatbot_{chatbot_id}"
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=CHROMA_DB_PATH,
        )
        all_text = ""
        documents = []
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )

        for doc_id, file_data in enumerate(files_data, start=1):
            uploaded_file = file_data["file"]
            filename = os.path.splitext(file_data["filename"])[0]
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()

            if file_extension == ".pdf":
                print(f"Processing PDF: {filename}")
                text = extract_text_from_pdf(uploaded_file)
            elif file_extension == ".docx":
                print(f"Processing DOCX: {filename}")
                text = extract_text_from_docx(uploaded_file)
            elif file_extension == ".txt":
                print(f"Processing TXT: {filename}")
                text = extract_text_from_txt(uploaded_file)
            else:
                print(f"Unsupported file type: {filename}{file_extension}")
                continue

            if not text:
                text = f"Error extracting content from {filename}"

            all_text += f"\n\n--- File: {filename} ---\n\n{text}"
            chunks = text_splitter.split_text(text)
            for chunk_id, chunk in enumerate(chunks):
                document = Document(
                    page_content=chunk,
                    metadata={
                        "id": f"{chatbot_id}-{doc_id}-{chunk_id}",
                        "filename": filename,
                        "filepath": "file_chunk",
                        "page_number": doc_id,
                        "chunk_id": chunk_id,
                    },
                )
                documents.append(document)
            uploaded_file.seek(0)

        vector_store.add_documents(documents)
        consolidated_file = f"chatbot_{chatbot_id}_consolidated.txt"
        with open(consolidated_file, "w", encoding="utf-8") as f:
            f.write(all_text)
        print(f"Saved consolidated content to {consolidated_file}")
        return f"Uploaded {len(documents)} documents successfully"
    except Exception as e:
        print(f"Error processing files: {str(e)}")
        return f"failed: {str(e)}"


def update_consolidated_content(files_data, chatbot_id, chatbot_name):
    """
    Safely update a chatbot's documents by fully rebuilding the Chroma collection.
    Prevents lingering invalid docs with None page_content.
    """
    try:
        collection_name = f"chatbot_{chatbot_id}"
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=CHROMA_DB_PATH,
        )

        # Delete the existing collection completely
        vector_store.delete_collection()
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=CHROMA_DB_PATH,
        )

        consolidated_file = f"chatbot_{chatbot_id}_consolidated.txt"
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )

        all_text = ""
        documents = []

        for doc_id, file_data in enumerate(files_data, start=1):
            uploaded_file = file_data["file"]
            filename = os.path.splitext(file_data["filename"])[0]
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()

            # Extract text safely
            if file_extension == ".pdf":
                text = extract_text_from_pdf(uploaded_file) or ""
            elif file_extension == ".docx":
                text = extract_text_from_docx(uploaded_file) or ""
            elif file_extension == ".txt":
                text = extract_text_from_txt(uploaded_file) or ""
            else:
                print(f"Unsupported file type: {uploaded_file.name}")
                continue

            if not text.strip():
                text = f"Error extracting content from {filename}"

            all_text += f"\n\n--- File: {filename} ---\n\n{text}"

            # Split text into safe chunks
            chunks = text_splitter.split_text(text)
            for chunk_id, chunk in enumerate(chunks):
                if not chunk or not isinstance(chunk, str):
                    continue  # skip invalid chunks

                document = Document(
                    page_content=chunk.strip(),
                    metadata={
                        "id": f"{chatbot_id}-{doc_id}-{chunk_id}",
                        "filename": filename,
                        "filepath": "file_chunk",
                        "page_number": doc_id,
                        "chunk_id": chunk_id,
                    },
                )
                documents.append(document)

            uploaded_file.seek(0)

        # Add documents to Chroma
        if documents:
            vector_store.add_documents(documents)

        # Update consolidated text file
        with open(consolidated_file, "w", encoding="utf-8") as f:
            f.write(all_text)

        print(
            f"Updated consolidated content to {consolidated_file}, {len(documents)} documents added"
        )
        return f"Uploaded {len(documents)} documents successfully"

    except Exception as e:
        print(f"Error updating content: {e}")
        return f"failed: {str(e)}"


def delete_document_from_chroma(chatbot_id, filename=None):
    try:
        collection_name = f"chatbot_{chatbot_id}"
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=CHROMA_DB_PATH,
        )
        collection = vector_store._collection
        existing_docs = collection.get(include=["metadatas"])

        if not existing_docs["metadatas"]:
            return False, "No documents found in ChromaDB for this chatbot"

        if filename:
            filename = os.path.splitext(filename)[0]
            doc_ids_to_delete = [
                existing_docs["ids"][i]
                for i, doc in enumerate(existing_docs["metadatas"])
                if doc["filename"] == filename
            ]
            if not doc_ids_to_delete:
                return False, f"No documents found with filename: {filename}"
            collection.delete(ids=doc_ids_to_delete)
            return (
                True,
                f"Successfully deleted {len(doc_ids_to_delete)} document(s) with filename: {filename}",
            )
        else:
            vector_store.delete_collection()
            vector_store = Chroma(
                collection_name=collection_name,
                embedding_function=embeddings,
                persist_directory=CHROMA_DB_PATH,
            )
            return True, "All documents deleted successfully"
    except Exception as e:
        return False, f"Error deleting from ChromaDB: {str(e)}"


def get_document_from_chroma(chatbot_id, filename):
    try:
        collection_name = f"chatbot_{chatbot_id}"
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=CHROMA_DB_PATH,
        )
        results = vector_store._collection.get(include=["documents", "metadatas"])
        filename = os.path.splitext(filename)[0]

        # Collect all chunks for the filename
        chunks = []
        for doc_content, metadata in zip(results["documents"], results["metadatas"]):
            if metadata["filename"] == filename:
                chunks.append((metadata["chunk_id"], doc_content))

        if not chunks:
            return ""

        # Sort by chunk_id and concatenate
        chunks.sort(key=lambda x: x[0])  # Sort by chunk_id
        full_content = "\n".join(chunk[1] for chunk in chunks)
        return full_content
    except Exception as e:
        print(f"Error retrieving from ChromaDB: {str(e)}")
        return ""


def remove_document_content(content, filename):
    if not content:
        return ""
    sections = content.split("\n\n")
    filename = os.path.splitext(filename)[0]
    # Filter out sections starting with exact file header
    filtered_sections = [
        section
        for section in sections
        if not section.strip().startswith(f"--- File: {filename} ---")
    ]
    return "\n\n".join(filtered_sections).strip()
