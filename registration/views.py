from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from google.oauth2 import id_token
from google.auth.transport import requests
from django.conf import settings
from .serializers import (GoogleAuthSerializer, 
                          GoogleUserSerializer, 
                          OrganizationInvitationSerializer, 
                          CustomUserSerializer,
                          OrganizationSerializer,
                          ChatbotSerializer,
                          ChatbotFAQSerializer,
                          ChatbotColorSerializer,
                          GracePeriodUpdateSerializer,
                          SendingStatusUpdateSerializer,
                          MessageLimitUpdateSerializer)
from .models import (CustomUser,
                    OrganizationInvitation,
                    Organization,
                    Chatbot,
                    ChatbotFAQ,
                    ChatbotColor,
                    ChatbotTokenUsage)
from rest_framework import status , permissions , viewsets, decorators
from rest_framework.authtoken.models import Token
from django.core.exceptions import ValidationError
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .utils import send_invitation_email, process_invitation_code
from storage.models import ChatbotDocumentGroup, ChatbotDocument
from storage.delete_index import delete_index_files
from django.db import transaction
from django.db.models import Sum
from datetime import datetime




class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        print("\n=== Starting Google Login Process ===")
        print("Received request data:", request.data)
        
        serializer = GoogleAuthSerializer(data=request.data)
        
        if not serializer.is_valid():
            print("Serializer validation failed:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        google_token = serializer.validated_data['auth_token']
        print("Retrieved token from request:", google_token[:20] + "..." if google_token else "None")
        
        try:
            print("Attempting to verify Google token with client ID:", settings.GOOGLE_OAUTH2_CLIENT_ID)
            # Verify the Google token
            idinfo = id_token.verify_oauth2_token(
                google_token, 
                requests.Request(), 
                settings.GOOGLE_OAUTH2_CLIENT_ID
            )
            print("Token verification successful. User info:", idinfo)

            # Extract user info from Google response
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            print(f"Extracted user info - Email: {email}, First Name: {first_name}, Last Name: {last_name}")
            
            # Check if user exists
            try:
                print("Checking if user exists with email:", email)
                user = CustomUser.objects.get(email=email)
                print("Existing user found:", user.username)
                is_new_user = False
            except CustomUser.DoesNotExist:
                print("User does not exist. Creating new user...")
                # Create new user if doesn't exist
                username = email.split('@')[0]  # Use email prefix as username
                base_username = username
                counter = 1
                
                # Handle username uniqueness
                while CustomUser.objects.filter(username=username).exists():
                    print(f"Username {username} already exists, trying {base_username}{counter}")
                    username = f"{base_username}{counter}"
                    counter += 1

                print("Creating new user with username:", username)
                user = CustomUser.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=None,  
                    phone_number="",  
                )
                user.set_unusable_password()
                user.save()
                print("New user created successfully")
                is_new_user = True

            # Generate or get auth token
            print("Generating auth token for user:", user.username)
            token, _ = Token.objects.get_or_create(user=user)
            
            # Serialize user data
            user_serializer = GoogleUserSerializer(user)

            has_organization = user.organization is not None

            response_data = {
                "message": "Successfully logged in with Google",
                "token": token.key,
                "user": user_serializer.data,
                "has_organization": has_organization,
                "is_new_user": is_new_user and not has_organization,  # Flag for frontend to show org creation form
                "google_data": {
                    "email": idinfo['email'],
                    "full_name": idinfo.get('name', ''),
                    "picture": idinfo.get('picture', ''),
                    "given_name": idinfo.get('given_name', ''),
                    "family_name": idinfo.get('family_name', ''),
                    "locale": idinfo.get('locale', '')
                }
            }
            
            # Add organization information if user has one
            if has_organization:
                response_data["organization"] = {
                    "id": user.organization.id,
                    "name": user.organization.name,
                    "is_owner": user.is_owner
                }
            
            # Check for invitation code in request or session
            invitation_code = request.data.get('invitation_code') or request.session.get('pending_invitation_code')
            
            # Clear the session variable if it exists
            if request.session and 'pending_invitation_code' in request.session:
                del request.session['pending_invitation_code']
            
            # Process invitation if code exists
            if invitation_code:
                print(f"Processing invitation code: {invitation_code}")
                try:
                    invitation = OrganizationInvitation.objects.get(
                        invitation_code=invitation_code,
                        status='pending'
                    )
                    
                    # Check that the authenticated user's email matches the invitation email
                    if invitation.email.lower() != email.lower():
                        print(f"Email mismatch: invitation sent to {invitation.email}, but authenticated with {email}")
                        response_data["invitation_error"] = f"This invitation was sent to {invitation.email}. Please log in with that email address."
                    # Check if invitation is still valid
                    elif invitation.is_valid():
                        print(f"Valid invitation found for organization: {invitation.organization.name}")
                        # Accept the invitation
                        if invitation.accept(user):
                            print(f"User successfully joined organization: {invitation.organization.name}")
                            response_data["joined_organization"] = invitation.organization.name
                            response_data["has_organization"] = True
                            
                            # Update organization information since user now has one
                            response_data["organization"] = {
                                "id": user.organization.id,
                                "name": user.organization.name,
                                "is_owner": user.is_owner  # Will be False for invited users
                            }
                            
                            # Reset is_new_user flag since they don't need to create an org
                            response_data["is_new_user"] = False
                        else:
                            print("Failed to accept invitation")
                            response_data["invitation_error"] = "Failed to accept invitation"
                    else:
                        print("Invitation has expired")
                        response_data["invitation_error"] = "Invitation has expired"
                        
                except OrganizationInvitation.DoesNotExist:
                    print(f"No valid invitation found with code: {invitation_code}")
                    response_data["invitation_error"] = "Invalid invitation"
            
            print("=== Google Login Process Completed Successfully ===\n")
            return Response(response_data, status=status.HTTP_200_OK)

        except ValidationError as ve:
            print("Validation Error occurred:", str(ve))
            return Response({
                "error": "Invalid token",
                "detail": str(ve)
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            print("Unexpected error occurred:", str(e))
            print("Error type:", type(e).__name__)
            import traceback
            print("Full traceback:", traceback.format_exc())
            return Response({
                "error": str(e),
                "error_type": type(e).__name__
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        

class IsOrganizationOwner(permissions.BasePermission):
    """Custom permission to only allow organization owners to perform actions."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_owner
    
    def has_object_permission(self, request, view, obj):
        # Check if the user is the owner of the organization related to the object
        return request.user.is_owner and request.user.organization == obj.organization 
    

class DeleteOrganizationMemberView(APIView):
    """View for organization owners to remove members."""
    permission_classes = [IsOrganizationOwner]
    
    def delete(self, request, member_id):
        try:
            # Get the member to delete
            member = CustomUser.objects.get(id=member_id)
            
            # Check if member is in the same organization as the requesting user
            if member.organization != request.user.organization:
                return Response(
                    {"error": "This user is not a member of your organization"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Prevent owners from deleting themselves through this endpoint
            if member.id == request.user.id:
                return Response(
                    {"error": "You cannot remove yourself using this endpoint"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Prevent deleting other owners (optional, remove if owners should be able to delete other owners)
            if member.is_owner:
                return Response(
                    {"error": "You cannot remove other organization owners"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Remove the user from the organization
            member.organization = None
            member.save()
            
            return Response(
                {"message": f"User {member.email} has been removed from your organization"},
                status=status.HTTP_200_OK
            )
            
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class OrganizationInvitationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # If user is an organization owner, return all invitations for their org
        if user.is_owner:
            return OrganizationInvitation.objects.filter(organization=user.organization)
        
        # For regular users, only show invitations sent to their email
        return OrganizationInvitation.objects.filter(email=user.email)
    
    def get_permissions(self):
        """
        Custom permissions:
        - Organization owners can create/list/delete invitations
        - Anyone can retrieve/accept/decline invitations sent to them
        """
        if self.action in ['create', 'destroy', 'list', 'bulk_invite']:
            self.permission_classes = [IsOrganizationOwner]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.organization,
            invited_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept an invitation and join the organization."""
        try:
            invitation = self.get_object()
            
            # For users who are already logged in
            if request.user.is_authenticated:
                # Check if invitation is for this user
                if invitation.email.lower() != request.user.email.lower():
                    return Response(
                        {"error": "This invitation is not for you. It was sent to " + invitation.email},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Check if invitation is valid (not expired, still pending)
                if not invitation.is_valid():
                    return Response(
                        {"error": "This invitation has expired or is no longer valid."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Accept invitation
                if invitation.accept(request.user):
                    return Response(
                        {"message": f"You have joined {invitation.organization.name}."},
                        status=status.HTTP_200_OK
                    )
                
                return Response(
                    {"error": "Could not accept invitation."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # For new users (via Google login)
            else:
                # Store invitation code AND expected email in session for after login
                request.session['pending_invitation_code'] = invitation.invitation_code
                request.session['pending_invitation_email'] = invitation.email
                
                # Return response with redirect information
                return Response({
                    "status": "redirect",
                    "redirect_to": "google_login",
                    "invitation_code": invitation.invitation_code,
                    "expected_email": invitation.email,  # Also include the expected email in the response
                    "message": f"Please login with Google using {invitation.email} to accept this invitation."
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response(
                {"error": f"Error processing invitation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """List only pending invitations."""
        queryset = self.get_queryset().filter(status='pending')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
        
    @action(detail=False, methods=['post'])
    def bulk_invite(self, request):
        """
        Create invitations and send invitation emails for multiple recipients at once.
        
        Expected request format:
        {
            "emails": ["user1@example.com", "user2@example.com", ...]
        }
        """
        emails = request.data.get('emails', [])
        if not emails or not isinstance(emails, list):
            return Response(
                {"error": "A list of emails is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        user = request.user
        if not user.organization or not user.is_owner:
            return Response(
                {"error": "You must be an organization owner to send invitations"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        results = {
            "successful": [],
            "failed": []
        }
        
        frontend_url = settings.FRONTEND_URL
        
        for email in emails:
            try:
                # Create invitation
                invitation = OrganizationInvitation.objects.create(
                    organization=user.organization,
                    invited_by=user,
                    email=email.lower(),  # Store email in lowercase for consistent matching
                    status='pending',
                    expires_at=timezone.now() + timezone.timedelta(days=7)
                )
                
                # Send invitation email
                try:
                    send_invitation_email(invitation, frontend_url)
                    results["successful"].append({
                        "email": email,
                        "invitation_code": invitation.invitation_code,
                        "message": "Invitation created and email sent successfully"
                    })
                except Exception as email_error:
                    # If email fails, keep the invitation but report the error
                    results["failed"].append({
                        "email": email,
                        "invitation_code": invitation.invitation_code,
                        "error": f"Invitation created but email failed: {str(email_error)}"
                    })
                    
            except Exception as invitation_error:
                results["failed"].append({
                    "email": email,
                    "error": f"Failed to create invitation: {str(invitation_error)}"
                })
                
        return Response({
            "message": f"Processed {len(emails)} invitations",
            "results": results
        }, status=status.HTTP_200_OK)

class OrganizationMemberViewSet(viewsets.ModelViewSet):
    """ViewSet for listing organization members."""
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.organization:
            return CustomUser.objects.none()
        return CustomUser.objects.filter(organization=user.organization)

    @decorators.action(detail=False, methods=['get'])
    def owners(self, request):
        """List only organization owners."""
        queryset = self.get_queryset().filter(is_owner=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @decorators.action(detail=False, methods=['get'])
    def members(self, request):
        """List only regular members (non-owners)."""
        queryset = self.get_queryset().filter(is_owner=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """Delete an organization member."""
        user = self.request.user
        
        # Ensure the user is an organization owner
        if not user.is_owner:
            return Response({"detail": "Only organization owners can remove members."}, 
                        status=status.HTTP_403_FORBIDDEN)
        
        # Get the specific user by ID
        try:
            # Use get() instead of filter() to ensure we get exactly one user
            target_user = CustomUser.objects.get(pk=pk, organization=user.organization)
            
            # Prevent self-deletion
            if target_user.id == user.id:
                return Response({"detail": "You cannot remove yourself."}, 
                            status=status.HTTP_400_BAD_REQUEST)
            
            # Store the ID for logging
            target_id = target_user.id
            
            # Delete the specific user
            target_user.delete()

            print(f"Member with ID {target_id} deleted successfully.")
            
            return Response({"detail": f"Member with ID {target_id} deleted successfully."}, 
                status=status.HTTP_200_OK)
            
        except CustomUser.DoesNotExist:
            return Response({"detail": "User not found in your organization."}, 
                        status=status.HTTP_404_NOT_FOUND)
    
        
class CreateOrganizationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        # Check if user already has an organization
        user = request.user
        if user.organization:
            return Response(
                {"error": "User already belongs to an organization"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get organization name from request
        organization_name = request.data.get('name')
        if not organization_name:
            return Response(
                {"error": "Organization name is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if organization with this name already exists
        if Organization.objects.filter(name=organization_name).exists():
            return Response(
                {"error": "An organization with this name already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create the organization
        organization = Organization.objects.create(name=organization_name)
        
        # Associate user with organization as owner
        user.organization = organization
        user.is_owner = True
        user.save()
        
        # Return response with organization data
        serializer = OrganizationSerializer(organization)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    

class ChatbotViewSet(viewsets.ModelViewSet):
    """ViewSet for managing chatbots within an organization."""
    serializer_class = ChatbotSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return chatbots for the user's organization."""
        user = self.request.user
        if not user.organization:
            return Chatbot.objects.none()
        
        # Return all chatbots associated with the user's organization
        return Chatbot.objects.filter(organization=user.organization)
    
    def perform_create(self, serializer):
        """Assign the chatbot to the user's organization when creating."""
        if not self.request.user.organization:
            raise ValidationError("User must belong to an organization to create a chatbot.")
        
        serializer.save(organization=self.request.user.organization)
    
    def list(self, request, *args, **kwargs):
        """Override list method to include chatbot count and handle empty response."""
        queryset = self.get_queryset()
        
        # Get the total count of chatbots
        chatbot_count = queryset.count()
        
        # Serialize the data
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            "count": chatbot_count,
            "chatbots": serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        chatbot = self.get_object()
        chatbot_name = chatbot.name
        
        # Check if chatbot has a document group in the storage app
        try:
            doc_group = ChatbotDocumentGroup.objects.get(chatbot=chatbot)
            consolidated_index_name = doc_group.index_name
            
            # Delete Azure Search index if it exists
            try:
                delete_index_files(consolidated_index_name)
                print(f"Successfully deleted Azure index: {consolidated_index_name}")
            except Exception as e:
                print(f"Error deleting Azure index: {str(e)}")
                # Continue with deletion even if Azure index deletion fails
            
            # Delete all documents associated with this chatbot
            for document in doc_group.active_documents.all():
                document.delete()
            
            # Clear and delete the document group
            doc_group.active_documents.clear()
            doc_group.delete()
            
        except ChatbotDocumentGroup.DoesNotExist:
            # No document group, so no index to delete
            print(f"No document group found for chatbot {chatbot_name}")
        except Exception as e:
            print(f"Error handling document group deletion: {str(e)}")
        
        # Proceed with standard deletion
        response = super().destroy(request, *args, **kwargs)
        
        # Customize the response message
        if response.status_code == status.HTTP_204_NO_CONTENT:
            return Response({
                "message": f"Chatbot '{chatbot_name}' and all associated resources deleted successfully"
            }, status=status.HTTP_200_OK)
        
        return response
    
class DeleteOrganizationView(APIView):
    """View for organization owners to delete their entire organization."""
    permission_classes = [IsOrganizationOwner]
    
    def delete(self, request):
        user = request.user
        organization = user.organization
        
        if not organization:
            return Response(
                {"error": "You are not part of any organization"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Get all organization members
                members = CustomUser.objects.filter(organization=organization)
                
                # Get all organization chatbots (to clean up related resources)
                chatbots = Chatbot.objects.filter(organization=organization)
                
                # Delete all chatbots and their related resources
                for chatbot in chatbots:
                    
                    try:
                        doc_group = ChatbotDocumentGroup.objects.get(chatbot=chatbot)
                        consolidated_index_name = doc_group.index_name
                        
                        # Delete Azure Search index if it exists
                        try:
                            delete_index_files(consolidated_index_name)
                        except Exception as e:
                            print(f"Error deleting Azure index: {str(e)}")
                        
                        # Delete all documents associated with this chatbot
                        doc_group.active_documents.all().delete()
                        doc_group.delete()
                        
                    except ChatbotDocumentGroup.DoesNotExist:
                        pass
                    
                    # Now delete the chatbot itself
                    chatbot.delete()
                
                # Remove organization link from all members
                for member in members:
                    member.organization = None
                    member.is_owner = False
                    member.save()
                
                # Get organization name for the response
                org_name = organization.name
                
                # Delete the organization
                organization.delete()
                
                return Response(
                    {"message": f"Organization '{org_name}' and all its resources have been deleted successfully"},
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            return Response(
                {"error": f"Error deleting organization: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class LogoutView(APIView):
    """View for user logout by invalidating their auth token."""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # Delete the user's auth token
            Token.objects.filter(user=request.user).delete()
            
            return Response(
                {"message": "Successfully logged out"},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": f"Error during logout: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class ChatbotFAQViewSet(viewsets.ModelViewSet):
    serializer_class = ChatbotFAQSerializer
    permission_classes = [IsAuthenticated]  # Require authentication

    def get_queryset(self):
        """Filter FAQs to the chatbot specified in the URL."""
        chatbot_id = self.kwargs['chatbot_id']
        return ChatbotFAQ.objects.filter(chatbot__id=chatbot_id)

    def get_chatbot(self):
        """Helper to retrieve the chatbot from the URL parameter."""
        chatbot_id = self.kwargs['chatbot_id']
        return get_object_or_404(Chatbot, id=chatbot_id)

    def perform_create(self, serializer):
        """Associate the FAQ with the chatbot during creation."""
        chatbot = self.get_chatbot()
        serializer.save(chatbot=chatbot)

    def create(self, request, *args, **kwargs):
        """Override create to handle multiple FAQs in one request."""
        chatbot = self.get_chatbot()
        data = request.data

        # Check if data is a list (bulk create) or a single object
        if isinstance(data, list):
            serializer = self.get_serializer(data=data, many=True)
        else:
            serializer = self.get_serializer(data=data)

        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=False, methods=['delete'], url_path='delete-all')
    def delete_all(self, request, chatbot_id=None):
        """Custom action to delete all FAQs for the chatbot."""
        chatbot = self.get_chatbot()
        deleted_count, _ = ChatbotFAQ.objects.filter(chatbot=chatbot).delete()
        return Response(
            {'message': f'Deleted {deleted_count} FAQs for chatbot {chatbot.name}'},
            status=status.HTTP_204_NO_CONTENT
        )

    def update(self, request, *args, **kwargs):
        """Allow partial updates (e.g., edit only the answer)."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def perform_update(self, serializer):
        """Ensure the chatbot association isn't changed during updates."""
        serializer.save()

    # Optional: Add permission check
    def check_permissions(self, request):
        super().check_permissions(request)
        chatbot = self.get_chatbot()
        # Example: Ensure the user is part of the chatbot's organization
        if chatbot.organization not in [request.user.organization]:
            self.permission_denied(request, message="You do not have permission to modify this chatbot's FAQs.")

class ChatbotColorViewSet(viewsets.ViewSet):
    """ViewSet for managing chatbot color settings with only POST and GET."""
    serializer_class = ChatbotColorSerializer
    permission_classes = [IsAuthenticated]

    def get_chatbot(self):
        """Helper to retrieve the chatbot from the URL parameter."""
        chatbot_id = self.kwargs.get('chatbot_id')
        return get_object_or_404(Chatbot, id=chatbot_id)

    def create(self, request, *args, **kwargs):
        """Handle POST to create or update chatbot color settings."""
        chatbot = self.get_chatbot()
        existing_colors = ChatbotColor.objects.filter(chatbot=chatbot).first()
        
        if existing_colors:
            serializer = self.serializer_class(
                existing_colors,
                data=request.data,
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            serializer = self.serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(chatbot=chatbot)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """Handle GET to retrieve chatbot color settings."""
        chatbot = self.get_chatbot()
        color_settings = get_object_or_404(ChatbotColor, chatbot=chatbot)
        serializer = self.serializer_class(color_settings)
        return Response(serializer.data)

    def check_permissions(self, request):
        super().check_permissions(request)
        chatbot = self.get_chatbot()
        if chatbot.organization != request.user.organization:
            self.permission_denied(
                request,
                message="You do not have permission to access this chatbot's color settings."
            )

class AdminOrganizationView(APIView):

    permission_classes = [IsAdminUser]
    def get(self, request):
        try:
            total_organizations = Organization.objects.count()
            organizations = Organization.objects.all()
            serializer = OrganizationSerializer(organizations, many=True)
            return Response({
                "total organizations": total_organizations,
                "organizations": serializer.data
            }, status=200)
        
        except Exception as e:
            return Response({
                "status": "Failed",
                "error": e
            }, status=400)
        
    

class AdminChatbotlistView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, org_id):
        try:
            organization = Organization.objects.get(id=org_id)
            chatbots = organization.chatbots.all()
            serializer = ChatbotSerializer(chatbots, many=True)
            return Response({
                "Status":"OK",
                "Chatbots": serializer.data
            }, status= 200)
        
        except Organization.DoesNotExist:
            return Response({
                "status": "Failed",
                "response": "Invalid request, organization with given id does not exist"
            }, status=404)
        
class TotalTokenUsageView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        
        month_param = request.query_params.get('month', None)

        if month_param:
            try:
                year, month = map(int, month_param.split('-'))
                tokenusage = ChatbotTokenUsage.objects.filter(
                    timestamp__year=year,
                    timestamp__month=month
                ).aggregate(
                    total=Sum('total_tokens'),
                    input=Sum('input_tokens'),
                    output=Sum('output_tokens')
                )

                total_tokens = tokenusage['total'] or 0
                input_tokens = tokenusage['input'] or 0
                output_tokens = tokenusage['output'] or 0

                response_data = {
                    "status" : "ok",
                    "month": month_param,
                    "total_tokens": total_tokens,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                }

                return Response(response_data, status=200)
            
            except (ValueError, TypeError):
                return Response({
                    "staus": "Failed",
                    "error": "Invalid month format. Use YYYY-MM (e.g., 2025-03)",
                },
                status=400
                )
            
        else:
            try:
                token_usage = ChatbotTokenUsage.objects.aggregate(
                    total=Sum('total_tokens'),
                    input=Sum('input_tokens'),
                    output=Sum('output_tokens')
                )

                total_tokens = token_usage['total'] or 0
                input_tokens = token_usage['input'] or 0
                output_tokens = token_usage['output'] or 0

                response_data = {
                    "status": "OK",
                    "total_tokens": total_tokens,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                }

                return Response(response_data, status=200)
            
            except (ValueError, TypeError):
                return Response({
                    "staus": "Failed",
                    "error": "Invalid month format. Use YYYY-MM (e.g., 2025-03)",
                },
                status=400
                )
            

class OrganizationTokenCountView(APIView):
    
    permission_classes= [IsAdminUser]

    def get(self,request, org_id):
        try:
            organization = Organization.objects.get(id=org_id)

        except Organization.DoesNotExist:
            return Response({
                "status": "Failed",
                "response": "Invalid request, organization with given id does not exist"
            }, status=404)
        
        month_param = request.query_params.get('month', None)
        print("month_param", month_param)

        if month_param:
            
            try:
                year , month = map(int, month_param.split('-'))

                print(year, month)

                token_usage = organization.total_tokens_used_by_month(year, month)  # Get dict
                total_tokens = token_usage['total'] or 0
                input_tokens = token_usage['input'] or 0
                output_tokens = token_usage['output'] or 0

                response_data = {
                    "status": "OK",
                    "total_tokens": total_tokens,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                }

                return Response(response_data, status=200)
            
            except (ValueError, TypeError):
                return Response({
                    "staus": "Failed",
                    "error": "Invalid month format. Use YYYY-MM (e.g., 2025-03)",
                },
                status=400
                )
            
        else:

            try:
                

                token_usage = organization.total_tokens_used()  # Get dict
                total_tokens = token_usage['total'] or 0
                input_tokens = token_usage['input'] or 0
                output_tokens = token_usage['output'] or 0

                response_data = {
                    "status": "OK",
                    "total_tokens": total_tokens,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                }

                return Response(response_data, status=200)
            
            except (ValueError, TypeError):
                return Response({
                    "staus": "Failed",
                    "error": "Invalid month format. Use YYYY-MM (e.g., 2025-03)",
                },
                status=400
                )

class ChatbotTokenCountView(APIView):
    permission_classes = [IsAdminUser]  # Adjust permissions as needed

    def get(self, request, chatbot_id):
        # Try to fetch the chatbot by ID
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
        except Chatbot.DoesNotExist:
            return Response({
                "status": "Failed",
                "response": "Invalid request, chatbot with given ID does not exist"
            }, status=404)

        # Get the optional 'month' query parameter (e.g., '2025-03')
        month_param = request.query_params.get('month', None)

        if month_param:
            # Handle monthly token usage
            try:
                year, month = map(int, month_param.split('-'))
                
                # Filter token usage by year and month
                token_usage = ChatbotTokenUsage.objects.filter(
                    chatbot=chatbot,
                    timestamp__year=year,
                    timestamp__month=month
                ).aggregate(
                    total=Sum('total_tokens'),
                    input=Sum('input_tokens'),
                    output=Sum('output_tokens')
                )

                total_tokens = token_usage['total'] or 0
                input_tokens = token_usage['input'] or 0
                output_tokens = token_usage['output'] or 0

                response_data = {
                    "status": "OK",
                    "chatbot_id": chatbot.id,
                    "chatbot_name": chatbot.name,
                    "total_tokens": total_tokens,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "year": year,
                    "month": month
                }

                return Response(response_data, status=200)

            except (ValueError, TypeError):
                return Response({
                    "status": "Failed",
                    "error": "Invalid month format. Use YYYY-MM (e.g., 2025-03)"
                }, status=400)

        else:
            # Handle total token usage (no month filter)
            try:
                token_usage = ChatbotTokenUsage.objects.filter(
                    chatbot=chatbot
                ).aggregate(
                    total=Sum('total_tokens'),
                    input=Sum('input_tokens'),
                    output=Sum('output_tokens')
                )

                total_tokens = token_usage['total'] or 0
                input_tokens = token_usage['input'] or 0
                output_tokens = token_usage['output'] or 0

                response_data = {
                    "status": "OK",
                    "chatbot_id": chatbot.id,
                    "chatbot_name": chatbot.name,
                    "total_tokens": total_tokens,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                }

                return Response(response_data, status=200)

            except (ValueError, TypeError):
                return Response({
                    "status": "Failed",
                    "error": "An unexpected error occurred"
                }, status=400)
            
class GracePeriodModificationView(APIView):
    permission_classes = [IsAdminUser]

    def post(self,request,chatbot_id):
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            quota = chatbot.quota

            serializer = GracePeriodUpdateSerializer(quota, data= request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "message": "Grace Period updated successfully",
                    "grace period": serializer.data["grace_period_days"]
                }, status=200)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Chatbot.DoesNotExist:
            return Response({"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND)

class UpdateSendingStatusView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, chatbot_id):
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            quota = chatbot.quota

            serializer = SendingStatusUpdateSerializer(quota, data = request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "message": "Message sending status successfully changed.",
                    "sending_status": serializer.data["is_sending_enabled"]
                }, status=200)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Chatbot.DoesNotExist:
            return Response({"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND)
        
class UpdateMessageLimitView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, chatbot_id):
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            quota = chatbot.quota

            serializer = MessageLimitUpdateSerializer(quota, data = request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "message": "Message limit successfully changed.",
                    "sending_status": serializer.data["message_limit"]
                }, status=200)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Chatbot.DoesNotExist:
            return Response({"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND)
        