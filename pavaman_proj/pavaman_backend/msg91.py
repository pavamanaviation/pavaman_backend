import requests
import json
from django.conf import settings

def send_bulk_sms(mobile_number,otp):
    url = settings.MSG91_SMS_URL
    
    payload = {
        "flow_id": settings.MSG91_FLOW_ID_RESETPASSWORD,
        "sender":settings.MSG91_SENDER_ID,
        # "mobiles": mobile_number,
        "mobiles": ",".join(mobile_number),  # results in "919876543210"

        "OTP": otp
    }

    headers = {
        'accept': "application/json",
        'authkey': settings.MSG91_AUTH_KEY,
        'content-type': "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.json()


def send_order_confirmation_sms(mobile_number, order_id, amount):
    payload = {
        "flow_id": settings.MSG91_ORDER_CONFIRM_FLOW_ID,
        "sender": settings.MSG91_SENDER_ID,
        # "mobiles": mobile,
        "mobiles": ",".join(mobile_number), 
        "ORDER_ID": order_id,
        "AMOUNT": amount
    }

    headers = {
        "accept": "application/json",
        "authkey": settings.MSG91_AUTH_KEY,
        "content-type": "application/json"
    }

    response = requests.post(settings.MSG91_SMS_URL, json=payload, headers=headers)
    return response.json()

def send_verify_mobile(mobile_number,otp):
    url = settings.MSG91_SMS_URL
    
    payload = {
        "flow_id": settings.MSG91_FLOW_ID_MOILE_VERIFY,
        "sender":settings.MSG91_SENDER_ID,
        "mobiles": ",".join(mobile_number), 
        # "mobiles": mobile_number,
        "OTP": otp
    }

    headers = {
        'accept': "application/json",
        'authkey': settings.MSG91_AUTH_KEY,
        'content-type': "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.json()

