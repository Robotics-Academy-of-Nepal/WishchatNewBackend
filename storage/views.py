from django.http import JsonResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from .models import ChatbotDocument, ChatbotDocumentGroup
from .chroma_utils import (
    process_and_store_files,
    update_consolidated_content,
    delete_document_from_chroma,
    get_document_from_chroma,
    remove_document_content
)
import os
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from registration.models import Chatbot
from django.utils import timezone

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_file(request, chatbot_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method. Use POST.'}, status=405)
    
    organization = request.user.organization
    organization_name = organization.name.replace(" ", "-")
    print("organization_name: ", organization_name)
    
    try:
        chatbot = get_object_or_404(Chatbot, id=chatbot_id, organization=request.user.organization)
    except Exception as e:
        return JsonResponse({'error': f'Chatbot not found or not accessible: {str(e)}'}, status=404)

    doc_group, created = ChatbotDocumentGroup.objects.get_or_create(
        chatbot=chatbot,
        defaults={'index_name': f"{organization_name}-chatbot-{chatbot.id}"}
    )
    
    if not doc_group.can_add_document():
        return JsonResponse({'error': 'Maximum document limit (3) reached.'}, status=400)

    processed_files = []
    errors = []
    files_to_process = []

    # Check if request.FILES is empty
    if not request.FILES:
        return JsonResponse({'error': 'No files provided.'}, status=400)

    # Process each file in request.FILES where key is filename and value is file object
    for filename, file_object in request.FILES.items():
        files_to_process.append({'file': file_object, 'filename': filename})

    if not files_to_process:
        return JsonResponse({'error': 'No valid files provided.'}, status=400)
    
    # Check unique filenames and slots
    existing_docs = doc_group.active_documents.all()
    unique_filenames = {doc.filename for doc in existing_docs}  # Full filenames
    total_unique = len(unique_filenames)
    max_slots = 3

    new_filenames = {f['filename'] for f in files_to_process}  # Keep full filenames
    will_overwrite = new_filenames & unique_filenames  # Filenames to overwrite
    new_additions = new_filenames - unique_filenames  # New filenames

    if total_unique + len(new_additions) - len(will_overwrite) > max_slots:
        return JsonResponse({
            'error': f'Can only add {max_slots - total_unique + len(will_overwrite)} more unique document(s).'
        }, status=400)

    for file_data in files_to_process:
        uploaded_file = file_data['file']
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        allowed_extensions = ['.pdf', '.doc', '.docx', '.txt']
        if file_extension not in allowed_extensions:
            errors.append(f"Invalid file type for {file_data['filename']}. Only PDF, DOC, DOCX, or TXT allowed.")
            continue

    if errors:
        return JsonResponse({'errors': errors}, status=400)

    try:
        if not chatbot.azure_index_name:
            chatbot.azure_index_name = f"{organization_name}-chatbot-{chatbot.id}"
            chatbot.save()
        
        doc_group.index_name = chatbot.azure_index_name
        doc_group.save()
        
        has_existing_files = doc_group.active_documents.exists()

        # Process files and update database
        for file_data in files_to_process:
            filename = file_data['filename']  # Full filename with extension
            document, doc_created = ChatbotDocument.objects.get_or_create(
                chatbot=chatbot,
                filename=filename,  # Store full filename
                defaults={'uploaded_at': timezone.now()}
            )
            if not doc_created:
                document.uploaded_at = timezone.now()  # Update timestamp
                document.save()
            doc_group.active_documents.add(document)
            processed_files.append(filename)

        if has_existing_files:
            response_message = update_consolidated_content(files_to_process, chatbot_id, chatbot.name)
        else:
            response_message = process_and_store_files(files_to_process, chatbot_id)

        if "failed" in response_message:
            for filename in processed_files:
                doc = doc_group.active_documents.filter(filename=filename).first()
                if doc:
                    doc_group.active_documents.remove(doc)
                    doc.delete()
            return JsonResponse({'error': 'Failed to process files'}, status=400)

        unique_filenames = {doc.filename for doc in doc_group.active_documents.all()}
        response_data = {
            'success': True,
            'message': 'Files processed and uploaded successfully',
            'processed_files': processed_files,
            'total_files': len(unique_filenames),
            'remaining_slots': max_slots - len(unique_filenames),
            'consolidated_index': doc_group.index_name
        }
        return JsonResponse(response_data, status=200)

    except Exception as e:
        for filename in processed_files:
            doc = doc_group.active_documents.filter(filename=filename).first()
            if doc:
                doc_group.active_documents.remove(doc)
                doc.delete()
        return JsonResponse({
            'error': f"Error processing files: {str(e)}",
            'processed_files': [],
            'errors': errors
        }, status=400)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_file(request, chatbot_id, document_id=None):
    try:
        chatbot = get_object_or_404(Chatbot, id=chatbot_id, organization=request.user.organization)
    except Exception as e:
        return JsonResponse({'error': f'Chatbot not found or not accessible: {str(e)}'}, status=404)

    try:
        doc_group = ChatbotDocumentGroup.objects.get(chatbot=chatbot)
        if document_id:
            document = ChatbotDocument.objects.get(id=document_id, chatbot=chatbot)
            filename = document.filename
            
            success, message = delete_document_from_chroma(chatbot_id, filename)
            if not success:
                return Response({"error": "Failed to delete document from ChromaDB", "details": message}, status=500)
            
            consolidated_file = f"chatbot_{chatbot_id}_consolidated.txt"
            if os.path.exists(consolidated_file):
                with open(consolidated_file, "r", encoding="utf-8") as f:
                    content = f.read()
                updated_content = remove_document_content(content, filename)
                with open(consolidated_file, "w", encoding="utf-8") as f:
                    f.write(updated_content)
            
            doc_group.active_documents.remove(document)
            document.delete()
            unique_filenames = {doc.filename for doc in doc_group.active_documents.all()}
            return Response({
                "message": f"Document deleted successfully. {message}",
                "remaining_docs": len(unique_filenames)
            }, status=200)
            
        else:
            if doc_group.active_documents.exists():
                success, message = delete_document_from_chroma(chatbot_id)
                if not success:
                    return Response({"error": "Failed to delete all documents from ChromaDB", "details": message}, status=500)
                
                consolidated_file = f"chatbot_{chatbot_id}_consolidated.txt"
                if os.path.exists(consolidated_file):
                    os.remove(consolidated_file)
                
                for document in doc_group.active_documents.all():
                    document.delete()
                doc_group.active_documents.clear()
                # Always reset azure_index_name when deleting all documents
            chatbot.azure_index_name = None
            chatbot.save()
            return Response({"message": "All documents deleted successfully"}, status=200)
        
    except ChatbotDocumentGroup.DoesNotExist:
        # If no document group exists, reset azure_index_name and return success
        chatbot.azure_index_name = None
        chatbot.save()
        return Response({"message": "No documents exist, index reset"}, status=200)
    except ChatbotDocument.DoesNotExist:
        return Response({"error": "Document not found", "details": f"Document with id {document_id} not found"}, status=404)
    except Exception as e:
        return Response({"error": "Failed to delete document", "details": str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_documents(request, chatbot_id):
    try:
        chatbot = get_object_or_404(Chatbot, id=chatbot_id, organization=request.user.organization)
        doc_group = ChatbotDocumentGroup.objects.get(chatbot=chatbot)
        documents = doc_group.active_documents.all()
        
        # Deduplicate by filename, keeping the latest entry
        unique_docs = {}
        for doc in documents:
            if doc.filename not in unique_docs or doc.uploaded_at > unique_docs[doc.filename]['uploaded_at']:
                name, ext = os.path.splitext(doc.filename)
                unique_docs[doc.filename] = {
                    'id': doc.id,
                    'filename': doc.filename,  # Full filename
                    'extension': ext if ext else '',  # Extracted extension
                    'uploaded_at': doc.uploaded_at
                }
        
        unique_filenames = set(unique_docs.keys())
        return JsonResponse({
            'documents': [
                {
                    'id': doc['id'],
                    'filename': doc['filename'],
                    'extension': doc['extension'],
                    'uploaded_at': doc['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S')
                } for doc in unique_docs.values()
            ],
            'total_count': len(unique_filenames),
            'remaining_slots': 3 - len(unique_filenames)
        })
    except Chatbot.DoesNotExist:
        return JsonResponse({'error': 'Chatbot not found or not accessible'}, status=404)
    except ChatbotDocumentGroup.DoesNotExist:
        return JsonResponse({'documents': [], 'total_count': 0, 'remaining_slots': 3})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_document(request, chatbot_id, document_id):
    try:
        chatbot = get_object_or_404(Chatbot, id=chatbot_id, organization=request.user.organization)
        document = ChatbotDocument.objects.get(id=document_id, chatbot=chatbot)
        
        content = get_document_from_chroma(chatbot_id, document.filename)
        base_filename = os.path.splitext(document.filename)[0]  # Strip extension
        
        return JsonResponse({
            'document': {
                'id': document.id,
                'filename': base_filename,  # Return without extension
                'uploaded_at': document.uploaded_at.strftime('%Y-%m-%d %H:%M:%S'),
                'content': content
            }
        }, status=200)
        
            
    except (Chatbot.DoesNotExist, ChatbotDocument.DoesNotExist):
        return JsonResponse({'error': 'Document or chatbot not found or no permission'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Error retrieving document: {str(e)}'}, status=500)