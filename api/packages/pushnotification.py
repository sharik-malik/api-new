from api.users.models import *
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
CACHE_TTL = getattr(settings, 'CACHE_TTL', DEFAULT_TIMEOUT)
from api.property.models import *
from api.notifications.models import *
from pyfcm import FCMNotification
from fcm_django.models import FCMDevice
from firebase_admin import messaging
# push_service = FCMNotification(settings.FCM_SERVER_KEY)
# fcm = FCMNotification(
#     service_account_file=str(settings.BASE_DIR / "firebase.json"),
#     project_id="bidhom-adres"
# )

def save_push_notifications(data: dict):
    if not data:
        return None

    try:
        push_notification = PushNotification.objects.create(
            property_id=data.get("property_id", None),
            title=data.get("title", ""),
            message=data.get("message", ""),
            description=data.get("description", ""),
            notification_to_id=data.get("notification_to", None),
            redirect_to=data.get("redirect_to", None)
        )
        # --------Send Push Notification-------
        send_push_notification(push_notification.id)
        return push_notification.id
    except Exception as e:
        return None


def send_push_notifications(user_id, extra_data={}):
    try:
        device_token = DeviceToken.objects.filter(user_id=user_id, status=1, device_type__in=['ios', 'android'])
        print(device_token)
        if device_token is not None:
            for device_id  in device_token:
                print(device_id.token)
                result = fcm.notify(
                    fcm_token=device_id.token,
                    notification_title=extra_data.get('title', ""),
                    notification_body=extra_data.get('message', ""),
                    notification_image=None,     # optional
                    data_payload=None,           # optional
                )
                print(result)
        return True
    except Exception as exp:
        print(exp)
        return False

def get_mail_template_by_id(template_id):
    """This function return mail template stored in
    database
    Args:
      template_id(int): template id to fetch single template from db
    
    Returns:
      array: template fields in array stored in db    
    """
    try:
        if int(template_id) > 0:
            mail_template = NotificationTemplate.objects.filter(id=template_id,status = 1).first()
            
            if mail_template:
                return mail_template
    except Exception as exp:
        return False
    

def send_push_notification(notification_id, to_all=False):
    try:
        # 1. Fetch the notification data
        notif_data = PushNotification.objects.get(id=notification_id, status=1)
        title = notif_data.title or ""
        message = notif_data.message or ""

        # 2. Load the user (to check if they allow notifications)
        if to_all is True:
            # devices = FCMDevice.objects.all()
            devices = FCMDevice.objects.filter(active=True).values_list("registration_id", flat=True)
            tokens = list(devices)  # convert queryset to list if needed
        else:
            users = Users.objects.filter(id=notif_data.notification_to_id, status=1).last()
            send_push = True if users is not None and users.allow_notifications else False
            if not send_push:
                return False
            devices = FCMDevice.objects.filter(user_id=notif_data.notification_to_id, active=True).values_list("registration_id", flat=True)
            tokens = list(devices)  # convert queryset to list if needed

        if len(tokens) < 1:
            print("No devices found for user")
            return False

        # 3. Badge count (if you use it)
        badge_count = add_badge_count(notif_data.notification_to_id)

        # 4. Prepare notification payload
        my_data = {
            'property_id': str(notif_data.property_id) if notif_data.property_id is not None or notif_data.property_id != "" else "",
            'redirect_to': str(notif_data.redirect_to) if notif_data.redirect_to is not None or notif_data.redirect_to != "" else "",
            'description': str(notif_data.description) if notif_data.description is not None or notif_data.description != "" else "",
        }

        # message = messaging.MulticastMessage(
        #     notification=messaging.Notification(
        #         title=title,
        #         body=message,
        #     ),
        #     data={**my_data, "badge": str(badge_count)},
        #     tokens=tokens,
        # )
        # response = messaging.send_multicast(message)
        # print(response.success_count)
        # print(response.responses)
        # print(response.failure_count)
        
        for token in tokens:
            try:
                message = messaging.Message(
                    token=token,
                    notification=messaging.Notification(
                        title = title,
                        body = message
                    ),
                    data={**my_data, "badge": str(badge_count)},
                )
                response = messaging.send(message)
                print(response)
            except Exception as exp:
                print(exp)

        return True
    except Exception as exp:
        print("Error sending push:", exp)
        return False

 
def push_notification(notification_id=None, user_id=None, extra_data=None):
    try:
        # Get devices
        if not user_id:
            devices = FCMDevice.objects.filter(active=True).values_list("registration_id", flat=True)
            tokens = list(devices)  # convert queryset to list
        else:
            user = Users.objects.filter(id=user_id, status=1).first()
            if not user or not getattr(user, "allow_notifications", True):
                return None  # user disabled notifications

            devices = FCMDevice.objects.filter(user_id=user_id).values_list("registration_id", flat=True)
            tokens = list(devices)  # convert queryset to list

        if len(tokens) < 1:
            return None

        # Fetch notification
        notif_data = PushNotification.objects.get(id=int(notification_id), status=1)
        title = notif_data.title or ""
        message = notif_data.message or ""

        # Badge count
        badge_count = add_badge_count(user_id)

        # Payload
        payload = {
            "notification_id": notification_id,
            "user_id": user_id,
            "title": title,
            "body": message,
        }
        if extra_data:
            payload.update(extra_data)

        # Send push
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=message,
            ),
            data={**payload, "badge": str(badge_count)},
            tokens=tokens,
        )
        return message
    except Exception as exp:
        return None
 
 
def add_badge_count(user_id):
    """Save and return number of badge
 
    :param user_id:
    :return: Number of badge
    """
    try:
        if int(user_id) < 1:
            return 0
 
        devices = FCMDevice.objects.filter(user_id=user_id, active=True).first()
        if devices is None:
            return 0
 
        data = PushNotificationBadge.objects.filter(user_id=int(user_id)).first()
        if data is not None and data.id > 0:
            if data.badge_count is not None and data.badge_count > 0:
                badge_count = data.badge_count + 1
            else:
                badge_count = 1
            data.badge_count = badge_count
            data.save()
        else:
            insert_data = PushNotificationBadge()
            badge_count = 1
            insert_data.user_id = user_id
            insert_data.badge_count = badge_count
            insert_data.save()
        return badge_count
    except Exception as exp:
        return 0
 