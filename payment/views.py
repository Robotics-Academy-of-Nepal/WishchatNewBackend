from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from registration.models import Chatbot , ChatbotPaymentTransaction, CouponCode, CustomUser
import base64
import json
from rest_framework.permissions import IsAuthenticated


class PaymentSuccessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        encoded_data = request.data.get('data')
        chatbot_id = request.data.get('chatbot_id')
        # discount_applied = request.data.get('discount_applied', False)  # Boolean flag
        coupon_code = request.data.get('coupon_code')
        print("coupon:", coupon_code)

        if not encoded_data:
            return Response({'status': 'error', 'message': 'No data parameter received'}, status=status.HTTP_400_BAD_REQUEST)
        if not chatbot_id:
            return Response({'status': 'error', 'message': 'Chatbot ID required'}, status=status.HTTP_400_BAD_REQUEST)
        # if not coupon_code:
        #     return Response({'status': 'error', 'message': 'Coupon code required if discount applied'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
        except Chatbot.DoesNotExist:
            return Response({'status': 'error', 'message': 'Chatbot not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            decoded_data = base64.b64decode(encoded_data).decode('utf-8')
            payment_data = json.loads(decoded_data)
            print(f"Decoded payment data: {payment_data}")

            if payment_data.get('status') != 'COMPLETE':
                return Response({'status': 'error', 'message': 'Payment not completed'}, status=status.HTTP_400_BAD_REQUEST)

            transaction_code = payment_data.get('transaction_code')
            if not transaction_code:
                return Response({'status': 'error', 'message': 'Transaction ID not found'}, status=status.HTTP_400_BAD_REQUEST)

            total_amount = int(float(payment_data.get('total_amount', '0').replace(',', '')))
            if not total_amount:
                return Response({'status': 'error', 'message': 'Total amount not found'}, status=status.HTTP_400_BAD_REQUEST)

            transaction = ChatbotPaymentTransaction.create_and_confirm_transaction(
                chatbot=chatbot,
                payment_amount=total_amount,
                payment_transaction_code=transaction_code,
                coupon_code=coupon_code if coupon_code else None
            )

            return Response({
                'status': 'success',
                'message': 'Subscription updated successfully',
                'chatbot_id': transaction.chatbot.id,
                'message_limit': transaction.chatbot.quota.message_limit,
                'messages_used': transaction.chatbot.quota.messages_used
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            print(f"Error: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error processing payment: {str(e)}")
            return Response({'status': 'error', 'message': 'Error processing payment'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class ChatbotPaymentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Check if the user is a superadmin or staff member
        if not (request.user.is_superuser or request.user.is_staff):
            return Response({
                "error": "This endpoint is restricted to super admins and service team members only"
            }, status=status.HTTP_403_FORBIDDEN)

        # Get chatbot_id from query parameters
        chatbot_id = request.query_params.get('chatbot_id')
        if not chatbot_id:
            return Response({
                "error": "Chatbot ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Verify the chatbot exists
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
        except Chatbot.DoesNotExist:
            return Response({
                "error": "Chatbot not found"
            }, status=status.HTTP_404_NOT_FOUND)

        # Fetch all transactions for the chatbot
        transactions = ChatbotPaymentTransaction.objects.filter(chatbot=chatbot).order_by('-payment_date')

        # Prepare the response data
        transaction_list = []
        for transaction in transactions:
            coupon_used = transaction.coupon_code is not None
            paid_amount = transaction.discounted_amount if coupon_used else transaction.amount
            transaction_data = {
                "transaction_code": transaction.transaction_id,
                "paid_amount": float(paid_amount),  # Convert Decimal to float for JSON serialization
                "payment_date": transaction.payment_date.isoformat(),
                "coupon_used": coupon_used,
            }
            if coupon_used:
                transaction_data.update({
                    "coupon_code": transaction.coupon_code.code,
                    "discount_percent": float(transaction.coupon_code.discount_percent),
                })
            transaction_list.append(transaction_data)

        response_data = {
            "chatbot_id": chatbot.id,
            "chatbot_name": chatbot.name,
            "organization": chatbot.organization.name if chatbot.organization else None,
            "transactions": transaction_list
        }

        return Response(response_data, status=status.HTTP_200_OK)