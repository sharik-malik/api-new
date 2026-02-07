import requests
from django.http import JsonResponse
from django.conf import settings


def send_sms(to, text):
    try:
        url = settings.INFOBIP_BASE_URL
        headers = {
            "Authorization": settings.INFOBIP_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "messages": [
                {
                    "from": settings.INFOBIP_SENDER_ID,
                    "destinations": [{"to": to}],
                    "text": text
                }
            ]
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return True
        else:
            print("Response JSON:", response.json())
            return False

        # return True if response.status_code == 200 else False
        # response.raise_for_status()
        # response_data = response.json()  # Get JSON response
        # print("Response:", response_data)  # Debugging purpose
        # return True
    except Exception as exp:
        print(exp)
        return False