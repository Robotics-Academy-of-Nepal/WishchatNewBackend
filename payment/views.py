from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from registration.models import (
    Chatbot,
    ChatbotPaymentTransaction,
    CouponCode,
    CustomUser,
    ChatbotQuota,
)
from registration.serializers import ChatbotQuotaSerializer
import base64
import json
from rest_framework.permissions import IsAuthenticated
from .serializers import MessageCountSerializer

from .serializers import PaymentInitiateSerializer
from uuid import uuid4
import hmac
import hashlib
import requests


class InitiateEsewaPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Validate request data
        serializer = PaymentInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        total_amount = serializer.validated_data["total_amount"]
        coupon = serializer.validated_data.get("coupon", "")
        subscription_plan_id = serializer.validated_data.get("subscription_plan_id")
        # Generate UUID
        transaction_uuid = str(uuid4())

        # Define payload
        payload = {
            "amount": str(total_amount),
            "tax_amount": "0",
            "total_amount": str(total_amount),
            "transaction_uuid": transaction_uuid,
            "product_code": "EPAYTEST",
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "success_url": f"https://pr9rwc8x-5173.inc1.devtunnels.ms/payment-success/x{coupon}/{subscription_plan_id}/",
            "failure_url": "https://pr9rwc8x-5173.inc1.devtunnels.ms/payment-failure/",
            "signed_field_names": "total_amount,transaction_uuid,product_code",
        }

        # Prepare message for signature
        message = f"total_amount={payload['total_amount']},transaction_uuid={payload['transaction_uuid']},product_code={payload['product_code']}"

        # Generate HMAC-SHA256 signature
        secret = "8gBm/:&EnhH.1/q"
        signature = hmac.new(
            secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
        ).digest()
        payload["signature"] = base64.b64encode(signature).decode("utf-8")

        # Send POST request to eSewa without following redirects
        esewa_url = "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
        try:
            # Disable automatic redirect following
            response = requests.post(esewa_url, data=payload, allow_redirects=False)
            response.raise_for_status()  # Raise exception for bad status codes

            # Check for redirect in response headers
            redirect_url = response.headers.get("Location")
            if redirect_url and "bookingId" in redirect_url:
                # Ensure the URL is fully qualified
                if redirect_url.startswith("/"):
                    redirect_url = f"https://rc-epay.esewa.com.np{redirect_url}"
                return Response(
                    {"redirect_url": redirect_url}, status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"error": "Failed to retrieve bookingId URL"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        except requests.RequestException as e:
            return Response(
                {"error": f"Failed to initiate payment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class InitiateKhaltiPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Validate request data
        serializer = PaymentInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        total_amount = serializer.validated_data["total_amount"]
        coupon = serializer.validated_data.get("coupon", "")
        subscription_plan_id = serializer.validated_data.get("subscription_plan_id")

        # Generate UUID for purchase_order_id
        purchase_order_id = str(uuid4())

        # Define Khalti payload
        payload = {
            "return_url": f"https://pr9rwc8x-5173.inc1.devtunnels.ms/payment-success/x{coupon}/{subscription_plan_id}/",
            "website_url": "https://pr9rwc8x-5173.inc1.devtunnels.ms/",
            "amount": total_amount
            * 100,  # Khalti expects amount in paisa (multiply by 100)
            "purchase_order_id": purchase_order_id,
            "purchase_order_name": "Subscription Payment",
            "customer_info": {
                "name": "Customer Name",  # Replace with actual customer name if available
                "email": "customer@example.com",  # Replace with actual customer email if available
                "phone": "9800000000",  # Replace with actual customer phone if available
            },
        }

        # Khalti API endpoint and credentials
        khalti_url = "https://dev.khalti.com/api/v2/epayment/initiate/"
        live_secret_key = (
            "22764718ccef49369337ca1cd89133dc"  # Replace with your Khalti public key
        )
        headers = {
            "Authorization": f"Key {live_secret_key}",
            "Content-Type": "application/json",
        }

        try:
            # Send POST request to Khalti without following redirects
            response = requests.post(
                khalti_url, json=payload, headers=headers, allow_redirects=False
            )
            response.raise_for_status()  # Raise exception for bad status codes

            # Check for redirect URL or pidx in response
            response_data = response.json()
            if response_data.get("pidx") and response_data.get("payment_url"):
                redirect_url = response_data["payment_url"]
                return Response(
                    {"redirect_url": redirect_url, "pidx": response_data["pidx"]},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Failed to retrieve payment URL or pidx"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        except requests.RequestException as e:
            return Response(
                {"error": f"Failed to initiate payment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PaymentSuccessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Extract common parameters
        chatbot_id = request.data.get("chatbot_id")
        coupon_code = request.data.get("coupon_code", "")
        subscription_plan_id = request.data.get("subscription_plan_id")

        if not chatbot_id:
            return Response(
                {"status": "error", "message": "Chatbot ID required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
        except Chatbot.DoesNotExist:
            return Response(
                {"status": "error", "message": "Chatbot not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get the organization associated with the chatbot
        organization = (
            chatbot.organization if hasattr(chatbot, "organization") else None
        )

        # Check for eSewa payment
        encoded_data = request.data.get("data")
        if encoded_data:
            if not encoded_data:
                return Response(
                    {"status": "error", "message": "No data parameter received"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                decoded_data = base64.b64decode(encoded_data).decode("utf-8")
                payment_data = json.loads(decoded_data)
                print(f"Decoded payment data: {payment_data}")

                if payment_data.get("status") != "COMPLETE":
                    return Response(
                        {"status": "error", "message": "Payment not completed"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                transaction_code = payment_data.get("transaction_code")
                if not transaction_code:
                    return Response(
                        {"status": "error", "message": "Transaction ID not found"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                total_amount = int(
                    float(payment_data.get("total_amount", "0").replace(",", ""))
                )
                if not total_amount:
                    return Response(
                        {"status": "error", "message": "Total amount not found"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                transaction = ChatbotPaymentTransaction.create_and_confirm_transaction(
                    chatbot=chatbot,
                    payment_amount=total_amount,
                    payment_transaction_code=transaction_code,
                    subscription_plan_id=subscription_plan_id,
                    coupon_code=coupon_code if coupon_code else None,
                    organization=organization,  # Pass organization for enterprise discount
                )
                print("Transaction created successfully:", transaction)

                return Response(
                    {
                        "status": "success",
                        "message": "Subscription updated successfully",
                        "chatbot_id": transaction.chatbot.id,
                        "message_limit": transaction.chatbot.quota.get_message_limit(),
                        "messages_used": transaction.chatbot.quota.messages_used,
                    },
                    status=status.HTTP_200_OK,
                )

            except ValueError as e:
                print(f"Error: {str(e)}")
                return Response(
                    {"status": "error", "message": str(e)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                print(f"Error processing payment: {str(e)}")
                return Response(
                    {"status": "error", "message": "Error processing payment"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Handle Khalti payment
        pidx = request.data.get("pidx")
        if not pidx:
            return Response(
                {"status": "error", "message": "pidx or data parameter required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Khalti lookup API endpoint and credentials
        khalti_lookup_url = "https://dev.khalti.com/api/v2/epayment/lookup/"
        secret_key = (
            "22764718ccef49369337ca1cd89133dc"  # Replace with your Khalti secret key
        )
        headers = {
            "Authorization": f"Key {secret_key}",
            "Content-Type": "application/json",
        }
        payload = {"pidx": pidx}

        try:
            # Send POST request to Khalti lookup API
            response = requests.post(khalti_lookup_url, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()

            # Check payment status
            payment_status = response_data.get("status")
            if payment_status == "Completed":
                # Extract transaction details
                transaction_code = response_data.get("transaction_id")
                total_amount = response_data.get("total_amount")  # Amount in paisa

                if not transaction_code:
                    return Response(
                        {"status": "error", "message": "Transaction ID not found"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not total_amount:
                    return Response(
                        {"status": "error", "message": "Total amount not found"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Convert amount from paisa to rupees
                total_amount = total_amount / 100
                # Create and confirm transaction
                transaction = ChatbotPaymentTransaction.create_and_confirm_transaction(
                    chatbot=chatbot,
                    payment_amount=total_amount,
                    payment_transaction_code=transaction_code,
                    subscription_plan_id=subscription_plan_id,
                    coupon_code=coupon_code if coupon_code else None,
                    organization=organization,  # Pass organization for enterprise discount
                )
                print("Khalti transaction created successfully:", transaction)

                return Response(
                    {
                        "status": "success",
                        "message": "Subscription updated successfully",
                        "chatbot_id": transaction.chatbot.id,
                        "message_limit": transaction.chatbot.quota.get_message_limit(),
                        "messages_used": transaction.chatbot.quota.messages_used,
                    },
                    status=status.HTTP_200_OK,
                )
            elif payment_status in ["Pending", "Initiated"]:
                return Response(
                    {
                        "status": "pending",
                        "message": "Payment is still processing",
                        "pidx": pidx,
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            else:
                return Response(
                    {
                        "status": "error",
                        "message": f"Payment verification failed: {payment_status}",
                        "pidx": pidx,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except requests.RequestException as e:
            print(f"Error verifying Khalti payment: {str(e)}")
            return Response(
                {"status": "error", "message": f"Failed to verify payment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChatbotPaymentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Check if the user is a superadmin or staff member
        if not (request.user.is_superuser or request.user.is_staff):
            return Response(
                {
                    "error": "This endpoint is restricted to super admins and service team members only"
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get chatbot_id from query parameters
        chatbot_id = request.query_params.get("chatbot_id")
        if not chatbot_id:
            return Response(
                {"error": "Chatbot ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Verify the chatbot exists
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
        except Chatbot.DoesNotExist:
            return Response(
                {"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Fetch all transactions for the chatbot
        transactions = ChatbotPaymentTransaction.objects.filter(
            chatbot=chatbot
        ).order_by("-payment_date")

        # Prepare the response data
        transaction_list = []
        for transaction in transactions:
            coupon_used = transaction.coupon_code is not None
            paid_amount = (
                transaction.discounted_amount if coupon_used else transaction.amount
            )
            transaction_data = {
                "transaction_code": transaction.transaction_id,
                "paid_amount": float(
                    paid_amount
                ),  # Convert Decimal to float for JSON serialization
                "payment_date": transaction.payment_date.isoformat(),
                "coupon_used": coupon_used,
            }
            if coupon_used:
                transaction_data.update(
                    {
                        "coupon_code": transaction.coupon_code.code,
                        "discount_percent": float(
                            transaction.coupon_code.discount_percent
                        ),
                    }
                )
            transaction_list.append(transaction_data)

        response_data = {
            "chatbot_id": chatbot.id,
            "chatbot_name": chatbot.name,
            "organization": chatbot.organization.name if chatbot.organization else None,
            "transactions": transaction_list,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class ChatbotQuotaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chatbot_id):
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            quota = chatbot.quota
            serializer = ChatbotQuotaSerializer(quota)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Chatbot.DoesNotExist:
            return Response(
                {"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND
            )


class MessageQuotaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chatbot_id):
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            quota = chatbot.quota
            serializer = MessageCountSerializer(quota)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Chatbot.DoesNotExist:
            return Response(
                {"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND
            )
