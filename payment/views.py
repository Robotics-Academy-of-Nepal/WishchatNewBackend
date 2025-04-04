from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from registration.models import Chatbot , ChatbotPaymentTransaction
import base64
import json
from rest_framework.permissions import IsAuthenticated


class PaymentSuccessView(APIView):
    authentication_classes = [IsAuthenticated]

    def post(self, request):
        encoded_data = request.data.get('data')
        chatbot_id = request.data.get('chatbot_id')
        discount_applied = request.data.get('discount_applied', False)  # Boolean flag
        coupon_code = request.data.get('coupon_code') if discount_applied else None

        if not encoded_data:
            return Response({'status': 'error', 'message': 'No data parameter received'}, status=status.HTTP_400_BAD_REQUEST)
        if not chatbot_id:
            return Response({'status': 'error', 'message': 'Chatbot ID required'}, status=status.HTTP_400_BAD_REQUEST)
        if discount_applied and not coupon_code:
            return Response({'status': 'error', 'message': 'Coupon code required if discount applied'}, status=status.HTTP_400_BAD_REQUEST)

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

            transaction = ChatbotPaymentTransaction.create_and_congrokaifirm_transaction(
                chatbot=chatbot,
                payment_amount=total_amount,
                payment_transaction_code=transaction_code,
                coupon_code=coupon_code if discount_applied else None
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