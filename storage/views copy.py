# from django.http import JsonResponse
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.decorators import api_view, permission_classes
# from .models import ChatbotDocument, ChatbotDocumentGroup
# from .azure_upload import (
#     process_consolidated_files, 
#     update_consolidated_content, 
#     get_existing_content,
#     upload_to_search,
#     delete_document_from_azure_index
# )
# import os
# from rest_framework.response import Response
# from rest_framework import status
# from django.shortcuts import get_object_or_404
# from registration.models import Chatbot  
# from .delete_index import delete_index_files


# def remove_document_content(content, filename):
#     """
#     Remove specific document content from consolidated content.
#     Matches your content structure where each document starts with its filename.
    
#     Args:
#         content (str): The full consolidated content
#         filename (str): The filename without extension to match the header
    
#     Returns:
#         str: Updated content with the specified document removed
#     """
#     if not content:
#         return ""
        
#     # Split content into sections by double newlines
#     sections = content.split('\n\n')
#     # print("sections list: ", sections)
#     filtered_sections = []
    
#     # Remove file extension if present in the filename
#     filename = os.path.splitext(filename)[0]
    
#     for section in sections:
#         # Check if section starts with the filename
#         if not section.strip().startswith(filename):
#             filtered_sections.append(section)
    
#     # print("Filetered Sections: ", filtered_sections)
    
#     # Rejoin the content with double newlines
#     return '\n\n'.join(filtered_sections).strip()

# def extract_document_content(content, filename):
#     """
#     Extract specific document content from consolidated content.
#     Matches your content structure where each document starts with its filename.
    
#     Args:
#         content (str): The full consolidated content
#         filename (str): The filename without extension to match the header
    
#     Returns:
#         str: Updated content with the specified document extracted
#     """
#     if not content:
#         return ""
        
#     # Split content into sections by double newlines
#     sections = content.split('\n\n')
#     # print("sections list: ", sections)
#     filtered_sections = []
    
#     # Remove file extension if present in the filename
#     filename = os.path.splitext(filename)[0]
    
#     for section in sections:
#         # Check if section starts with the filename
#         if section.strip().startswith(filename):
#             filtered_sections.append(section)
    
#     # print("Filetered Sections: ", filtered_sections)
    
#     # Rejoin the content with double newlines
#     return '\n\n'.join(filtered_sections).strip()


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def upload_file(request, chatbot_id):
#     if request.method != 'POST':
#         return JsonResponse({'error': 'Invalid request method. Use POST.'}, status=405)
    
#     organization = request.user.organization
#     organization_name = organization.name
#     organization_name = organization_name.replace(" ", "-")
#     print("organiztion_name: ", organization_name)
    
#     # Get the chatbot and verify it belongs to the user's organization
#     try:
#         chatbot = get_object_or_404(Chatbot, 
#                                    id=chatbot_id, 
#                                    organization=request.user.organization)
#     except Exception as e:
#         return JsonResponse({'error': f'Chatbot not found or not accessible: {str(e)}'}, status=404)

#     # Get or create document group for chatbot
#     doc_group, created = ChatbotDocumentGroup.objects.get_or_create(
#         chatbot=chatbot,
#         defaults={'index_name': chatbot.azure_index_name or f"{organization_name}-chatbot-{chatbot.id}"}
#     )
    
#     # Check available slots
#     remaining_slots = 3 - doc_group.active_documents.count()
#     if remaining_slots <= 0:
#         return JsonResponse({'error': 'Maximum document limit (3) reached.'}, status=400)

#     # Initialize lists for tracking results
#     processed_files = []
#     errors = []
#     files_to_process = []

#     # Handle both single and multiple file uploads
#     if 'file' in request.FILES and 'filename' in request.POST:
#         files_to_process.append({
#             'file': request.FILES['file'],
#             'filename': request.POST['filename']
#         })
#     else:
#         for key in request.FILES.keys():
#             if key.startswith('file'):
#                 file_index = key.replace('file', '')
#                 filename_key = f'filename{file_index}'
                
#                 if filename_key in request.POST:
#                     files_to_process.append({
#                         'file': request.FILES[key],
#                         'filename': request.POST[filename_key]
#                     })
#                 else:
#                     errors.append(f'Filename missing for {key}')

#     if not files_to_process:
#         return JsonResponse({'error': 'No valid file/filename pairs provided.'}, status=400)

#     if len(files_to_process) > remaining_slots:
#         return JsonResponse({
#             'error': f'Can only add {remaining_slots} more document(s). Trying to add {len(files_to_process)}.'
#         }, status=400)

#     # Validate file types
#     for file_data in files_to_process:
#         uploaded_file = file_data['file']
#         file_extension = os.path.splitext(uploaded_file.name)[1].lower()
#         allowed_extensions = ['.pdf', '.doc', '.docx', '.txt']

#         if file_extension not in allowed_extensions:
#             errors.append(f"Invalid file type for {file_data['filename']}. Only PDF, DOC, DOCX, or TXT files are allowed.")
#             continue

#     if errors:
#         return JsonResponse({'errors': errors}, status=400)

#     try:
#         # Use chatbot's Azure index name or create one
#         if not chatbot.azure_index_name:
#             # Generate index name if not present
#             chatbot.azure_index_name = f"{organization_name}-chatbot-{chatbot.id}"
#             chatbot.save()
            
#         consolidated_index_name = chatbot.azure_index_name
#         doc_group.index_name = consolidated_index_name  # Ensure doc group has the same index name
#         doc_group.save()
        
#         has_existing_files = doc_group.active_documents.exists()

#         # Process individual files first
#         for file_data in files_to_process:
#             filename = file_data['filename']
#             newfilename = filename.replace(" ", "-").replace("(", "").replace(")", "").lower()

#             # Create individual document record for tracking
#             document = ChatbotDocument.objects.create(
#                 chatbot=chatbot,
#                 filename=filename,
#             )
            
#             doc_group.active_documents.add(document)
#             processed_files.append(filename)

#         # Handle consolidated content
#         if has_existing_files:
#             # Update existing consolidated content
#             response_message = update_consolidated_content(
#                 files_to_process,
#                 consolidated_index_name,
#                 chatbot.name
#             )
#         else:
#             # Create new consolidated content
#             response_message = process_consolidated_files(
#                 files_to_process,
#                 consolidated_index_name
#             )

#         if response_message == "failed":
#             # Rollback if Azure upload fails
#             for filename in processed_files:
#                 doc = doc_group.active_documents.filter(filename=filename).first()
#                 if doc:
#                     doc_group.active_documents.remove(doc)
#                     doc.delete()
#             return JsonResponse({'error': 'Failed to process consolidated content'}, status=400)

#         # Prepare response
#         response_data = {
#             'success': True,
#             'message': 'Files processed and uploaded successfully',
#             'processed_files': processed_files,
#             'total_files': doc_group.active_documents.count(),
#             'remaining_slots': 3 - doc_group.active_documents.count(),
#             'consolidated_index': consolidated_index_name
#         }

#         return JsonResponse(response_data, status=200)

#     except Exception as e:
#         # Rollback in case of error
#         for filename in processed_files:
#             doc = doc_group.active_documents.filter(filename=filename).first()
#             if doc:
#                 doc_group.active_documents.remove(doc)
#                 doc.delete()
        
#         return JsonResponse({
#             'error': f"Error processing files: {str(e)}",
#             'processed_files': [],
#             'errors': errors
#         }, status=400)

# @api_view(['DELETE'])
# @permission_classes([IsAuthenticated])
# def delete_file(request, chatbot_id, document_id=None):
#     # Get the chatbot and verify it belongs to the user's organization
#     try:
#         chatbot = get_object_or_404(Chatbot, 
#                                   id=chatbot_id, 
#                                   organization=request.user.organization)
#     except Exception as e:
#         return JsonResponse({'error': f'Chatbot not found or not accessible: {str(e)}'}, status=404)

#     try:
#         doc_group = ChatbotDocumentGroup.objects.get(chatbot=chatbot)
#         consolidated_index_name = doc_group.index_name

#         if document_id:
#             # Delete specific document
#             document = ChatbotDocument.objects.get(id=document_id, chatbot=chatbot)
#             filename = document.filename
            
#             # Delete from Azure Search index
#             success, message = delete_document_from_azure_index(consolidated_index_name, filename)
            
#             if not success and "Index not found" not in message:
#                 # If it failed for a reason other than the index not existing
#                 return Response({
#                     "error": "Failed to delete document from search index",
#                     "details": message
#                 }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
#             # If index was deleted because this was the last document
#             if success and "Index" in message and "deleted" in message:
#                 chatbot.azure_index_name = None
#                 chatbot.save()
            
#             # Remove from group and delete document from database
#             doc_group.active_documents.remove(document)
#             document.delete()
            
#             remaining_docs = doc_group.active_documents.count()
#             return Response({
#                 "message": f"Document deleted successfully. {message}",
#                 "remaining_docs": remaining_docs
#             }, status=status.HTTP_200_OK)
            
#         else:
#             # Delete all documents
#             if doc_group.active_documents.exists():
#                 try:
#                     delete_index_files(consolidated_index_name)
#                     chatbot.azure_index_name = None
#                     chatbot.save()
#                 except Exception as e:
#                     print(f"Error deleting Azure index: {str(e)}")
                
#                 for document in doc_group.active_documents.all():
#                     document.delete()
#                 doc_group.active_documents.clear()
            
#             return Response({
#                 "message": "All documents deleted successfully"
#             }, status=status.HTTP_200_OK)
        
#     except ChatbotDocumentGroup.DoesNotExist:
#         return Response({
#             "error": "Document group not found for chatbot",
#             "details": "No documents exist for this chatbot"
#         }, status=status.HTTP_404_NOT_FOUND)
#     except ChatbotDocument.DoesNotExist:
#         return Response({
#             "error": "Document not found",
#             "details": f"Document with id {document_id} does not exist"
#         }, status=status.HTTP_404_NOT_FOUND)
#     except Exception as e:
#         return Response({
#             "error": "Failed to delete document",
#             "details": str(e)
#         }, status=status.HTTP_400_BAD_REQUEST)

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def list_documents(request, chatbot_id):
#     """Get all documents for a specific chatbot"""
#     try:
#         # Get the chatbot and verify it belongs to the user's organization
#         chatbot = get_object_or_404(Chatbot, 
#                                    id=chatbot_id, 
#                                    organization=request.user.organization)
        
#         doc_group = ChatbotDocumentGroup.objects.get(chatbot=chatbot)
#         documents = doc_group.active_documents.all()
        
#         return JsonResponse({
#             'documents': [{
#                 'id': doc.id,
#                 'filename': doc.filename,
#                 'uploaded_at': doc.uploaded_at.strftime('%Y-%m-%d %H:%M:%S'),
#             } for doc in documents],
#             'total_count': documents.count(),
#             'remaining_slots': 3 - documents.count()
#         })
#     except Chatbot.DoesNotExist:
#         return JsonResponse({'error': 'Chatbot not found or not accessible'}, status=404)
#     except ChatbotDocumentGroup.DoesNotExist:
#         return JsonResponse({'documents': [], 'total_count': 0, 'remaining_slots': 3})

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def get_document(request, chatbot_id, document_id):
#     """Get a single document by ID for a specific chatbot"""
#     try:
#         # Get the chatbot and verify it belongs to the user's organization
#         chatbot = get_object_or_404(Chatbot, 
#                                    id=chatbot_id, 
#                                    organization=request.user.organization)
        
#         # Get the document and verify it belongs to this chatbot
#         document = ChatbotDocument.objects.get(
#             id=document_id,
#             chatbot=chatbot
#         )
        
#         doc_group = ChatbotDocumentGroup.objects.get(chatbot=chatbot)
#         filename = document.filename
#         consolidated_index_name = doc_group.index_name
        
#         # Fetch the consolidated content from Azure Search
#         full_content = get_existing_content(consolidated_index_name, filename)
        
#         # # Extract the content for this specific document
#         # document_content = extract_document_content(full_content, document.filename)

        
#         return JsonResponse({
#             'document': {
#                 'id': document.id,
#                 'filename': document.filename,
#                 'uploaded_at': document.uploaded_at.strftime('%Y-%m-%d %H:%M:%S'),
#                 'content': full_content
#             }
#         }, status=200)
            
#     except (Chatbot.DoesNotExist, ChatbotDocument.DoesNotExist):
#         return JsonResponse({
#             'error': 'Document or chatbot not found or you do not have permission to access it'
#         }, status=404)
#     except Exception as e:
#         return JsonResponse({
#             'error': f'Error retrieving document: {str(e)}'
#         }, status=500)
