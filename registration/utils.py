from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import os
from .models import OrganizationInvitation


def send_invitation_email(invitation, frontend_url):
    """
    Send invitation email to the invitee.

    Args:
        invitation: OrganizationInvitation instance
        frontend_url: Base URL of your frontend application
    """
    subject = f"Invitation to join {invitation.organization.name}"

    # Create invitation link with the invitation code
    invitation_link = f"{frontend_url}/login/{invitation.invitation_code}"
    print("invitation_link: ", invitation_link)
    # Email context
    context = {
        "organization_name": invitation.organization.name,
        "invited_by": f"{invitation.invited_by.first_name} {invitation.invited_by.last_name}",
        "invitation_link": invitation_link,
        "expires_at": invitation.expires_at,
    }

    html_message_path = "emails/invitation_email.html"
    plain_message_path = "emails/invitation_email.txt"

    # Render email content from template
    html_message = render_to_string(html_message_path, context)
    plain_message = render_to_string(plain_message_path, context)

    # Send email
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        html_message=html_message,
        fail_silently=False,
    )


def process_invitation_code(request, user):
    """
    Process pending invitation code stored in session after user login.

    Args:
        request: The HTTP request object
        user: The authenticated user

    Returns:
        dict: Result of the invitation processing
    """
    # Check if there's a pending invitation code in the session
    invitation_code = request.session.get("pending_invitation_code")
    expected_email = request.session.get("pending_invitation_email")

    # Clear the session data
    if "pending_invitation_code" in request.session:
        del request.session["pending_invitation_code"]
    if "pending_invitation_email" in request.session:
        del request.session["pending_invitation_email"]

    # If no invitation code, nothing to do
    if not invitation_code:
        return {"success": False, "message": "No pending invitation found."}

    try:
        # Find the invitation
        invitation = OrganizationInvitation.objects.get(invitation_code=invitation_code)

        # Verify the email matches the invitation
        # Use lowercase for case-insensitive comparison
        if invitation.email.lower() != user.email.lower():
            # Email doesn't match - reject
            return {
                "success": False,
                "message": f"This invitation was sent to {invitation.email}, but you're logged in with {user.email}.",
            }

        # Check if invitation is still valid
        if not invitation.is_valid():
            return {
                "success": False,
                "message": "This invitation has expired or is no longer valid.",
            }

        # Accept the invitation
        if invitation.accept(user):
            return {
                "success": True,
                "message": f"You have joined {invitation.organization.name}.",
            }
        else:
            return {"success": False, "message": "Could not accept invitation."}

    except OrganizationInvitation.DoesNotExist:
        return {"success": False, "message": "Invalid invitation code."}
    except Exception as e:
        return {"success": False, "message": f"Error processing invitation: {str(e)}"}
