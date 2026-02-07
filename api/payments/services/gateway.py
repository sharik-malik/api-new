import json
import requests
from django.conf import settings
from api.bid.models import BidTransaction, BidTransactionGatewayLog, BidRegistration

def call_payment_gateway(action, transaction, url, payload, action_type):
    response = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        cert=(settings.PFX_CERT_PATH, settings.PFX_KEY_PATH),
        verify=False
    )
    result = response.json()
    status = result.get("status")

    # Log response
    BidTransactionGatewayLog.objects.create(
        bid_transaction=transaction,
        action=action_type,
        status=status,
        raw_request=json.dumps(payload),
        raw_response=json.dumps(result),
    )
    return result


def void_other_transactions(property_id, exclude_transaction_id=None, capture_for=None):
    if capture_for is None:
        transaction_ids = BidRegistration.objects.filter(
            property_id=property_id
        ).exclude(
            transaction_id=exclude_transaction_id
        ).values_list('transaction_id', flat=True)
    else:
        transaction_ids = BidTransaction.objects.filter(
            property_id=property_id
        ).exclude(
            id=exclude_transaction_id
        ).values_list('id', flat=True)  

    transactions = BidTransaction.objects.filter(
        id__in=transaction_ids,
        gateway_status="APPROVED",
        authorizationStatus=1
    )

    for txn in transactions:
        try:
            void_payment(txn.id)  # safe recursive call
        except Exception as e:
            print(f"Error voiding transaction {txn.id}: {e}")


def capture_payment(transaction_id, capture_for=None):
    transaction = BidTransaction.objects.filter(id=transaction_id).last()
    if not transaction:
        raise Exception("Transaction information not exists")

    if transaction.gateway_status != "APPROVED" or transaction.authorizationStatus != 1:
        raise Exception("Transaction not valid for capture")
    
    # Fetch property_id from BidRegistration
    if capture_for is None:
        property_id = BidRegistration.objects.filter(
            transaction=transaction
        ).values_list("property_id", flat=True).first()
    else:
        property_id = transaction.property_id   

    url = settings.PAYMENT_GATEWAY_CAPTURE_PAYMENT_URL
    payload = {
        "action": "5",
        "id": settings.PAYMENT_GATEWAY_MAGNATI_ID,
        "password": settings.PAYMENT_GATEWAY_MAGNATI_PASSWORD,
        "transid": transaction.paymentid,
        "servicedata": [
            {
                "amount": str(transaction.amount),
                "noOfTransactions": "1",
                "serviceId": settings.PAYMENT_GATEWAY_MAGNATI_SERVICE_ID,
                "merchantId": settings.PAYMENT_GATEWAY_MAGNATI_MERCHANT_ID
            }
        ],
        "langid": "en",
        "udf5": "PaymentID"
    }

    result = call_payment_gateway("5", transaction, url, payload, "capture")
    status = result.get("status")

    if status == "CAPTURED":
        transaction.authorizationStatus = 2
        transaction.save()
        if property_id:
            # void_other_transactions(property_id, exclude_transaction_id=transaction.id, capture_for)
            void_other_transactions(property_id, transaction.id, capture_for="purchase")
        return {"success": True, "message": "Payment captured", "data": result}

    return {"success": False, "message": "Capture failed", "data": result}


def void_payment(transaction_id, property_id=None):
    transaction = BidTransaction.objects.filter(id=transaction_id).last()
    if not transaction:
        raise Exception("Transaction information not exists")

    if transaction.gateway_status != "APPROVED" or transaction.authorizationStatus != 1:
        raise Exception("Transaction not valid for void")

    url = settings.PAYMENT_GATEWAY_VOID_PAYMENT_URL
    payload = {
        "action": "3",
        "id": settings.PAYMENT_GATEWAY_MAGNATI_ID,
        "password": settings.PAYMENT_GATEWAY_MAGNATI_PASSWORD,
        "transid": transaction.paymentid,
        "langid": "en",
        "udf5": "PaymentID"
    }

    result = call_payment_gateway("3", transaction, url, payload, "void")
    status = result.get("status")

    transaction.authorizationStatus = 3
    transaction.status_id = 26
    transaction.save()

    if property_id:
        void_other_transactions(property_id, exclude_transaction_id=transaction.id)

    return {"success": True, "message": "Payment voided"}


def cron_void_payment(transaction_id, property_id=None):
    transaction = BidTransaction.objects.filter(id=transaction_id).last()
    if not transaction:
        return {"success": True, "message": "Payment voided"}

    if transaction.gateway_status != "APPROVED" or transaction.authorizationStatus != 1:
        return {"success": True, "message": "Payment voided"}

    url = settings.PAYMENT_GATEWAY_VOID_PAYMENT_URL
    payload = {
        "action": "3",
        "id": settings.PAYMENT_GATEWAY_MAGNATI_ID,
        "password": settings.PAYMENT_GATEWAY_MAGNATI_PASSWORD,
        "transid": transaction.paymentid,
        "langid": "en",
        "udf5": "PaymentID"
    }

    result = call_payment_gateway("3", transaction, url, payload, "void")
    status = result.get("status")

    transaction.authorizationStatus = 3
    transaction.status_id = 26
    transaction.save()

    if property_id:
        void_other_transactions(property_id, exclude_transaction_id=transaction.id)

    return {"success": True, "message": "Payment voided"}


def refund_payment(transaction_id):
    transaction = BidTransaction.objects.filter(id=transaction_id).first()
    if not transaction:
        raise Exception("Transaction information not exists")

    if transaction.authorizationStatus != 2:
        raise Exception("Transaction is not valid for refund")

    url = settings.PAYMENT_GATEWAY_REFUND_PAYMENT_URL
    payload = {
        "action": "2",
        "id": settings.PAYMENT_GATEWAY_MAGNATI_ID,
        "password": settings.PAYMENT_GATEWAY_MAGNATI_PASSWORD,
        "transid": transaction.paymentid,
        "servicedata": [
            {
                "amount": str(transaction.amount),
                "noOfTransactions": "1",
                "serviceId": settings.PAYMENT_GATEWAY_MAGNATI_SERVICE_ID,
                "merchantId": settings.PAYMENT_GATEWAY_MAGNATI_MERCHANT_ID
            }
        ],
        "langid": "en",
        "udf5": "PaymentID"
    }

    response = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        cert=(settings.PFX_CERT_PATH, settings.PFX_KEY_PATH),
        verify=False
    )

    result = response.json()
    status = result.get("status")
    
    # Create a log entry
    BidTransactionGatewayLog.objects.create(
        bid_transaction=transaction,
        action='refund',
        status=status,
        raw_request=json.dumps(payload),
        raw_response=json.dumps(result),
    )

    if status == "CAPTURED":
        transaction.authorizationStatus = 4
        transaction.save()
        return {"success": True, "message": "Payment successfully refunded and status updated", "data": result}

    transaction.save()
    return {"success": False, "message": "Payment not refunded. Logged full response." , "data": result}
