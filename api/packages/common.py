from api.notifications.models import *
from collections import defaultdict


def add_notification(domain_id, user_id, added_by, notification_for, template_slug="", extra_data={}):
    try:
        users = Users.objects.filter(id=user_id, allow_notifications=True).first()
        if users is not None:
            notification_template = NotificationTemplate.objects.filter(event__slug=template_slug).values('id', 'notification_subject', "notification_text", "notification_subject_ar", "notification_text_ar").last()
            if notification_template is not None:
                # ------------------Dynamic content-----------
                notification_subject = notification_template['notification_subject']
                notification_subject_ar = notification_template['notification_subject_ar']
                notification_text = notification_template['notification_text']
                notification_text_ar = notification_template['notification_text_ar']
                formated_data = defaultdict(lambda: "")
                formated_data.update(extra_data)
                notification_text = notification_text.format_map(formated_data)

                formated_data_ar = defaultdict(lambda: "")
                formated_data_ar.update(extra_data)
                notification_text_ar = notification_text_ar.format_map(formated_data_ar)

                event_notification = EventNotification()
                event_notification.domain_id = domain_id
                event_notification.property_id = extra_data['property_id'] if "property_id" in extra_data else ""
                event_notification.notification_for = notification_for
                event_notification.title = notification_subject
                event_notification.content = notification_text
                event_notification.title_ar = notification_subject_ar
                event_notification.content_ar = notification_text_ar
                event_notification.redirect_url = extra_data['redirect_url'] if "redirect_url" in extra_data else ""
                event_notification.app_content = extra_data['app_content'] if "app_content" in extra_data else ""
                event_notification.app_content_ar = extra_data['app_content_ar'] if "app_content_ar" in extra_data else ""
                event_notification.app_screen_type = extra_data['app_screen_type'] if "app_screen_type" in extra_data else ""
                event_notification.app_notification_image = extra_data['app_notification_image'] if "app_notification_image" in extra_data else ""
                event_notification.app_notification_button_text = extra_data['app_notification_button_text'] if "app_notification_button_text" in extra_data else ""
                event_notification.app_notification_button_text_ar = extra_data['app_notification_button_text_ar'] if "app_notification_button_text_ar" in extra_data else ""
                event_notification.user_id = user_id
                event_notification.added_by_id = added_by
                event_notification.status_id = 1
                event_notification.save()
        return True
    except Exception as exp:
        return False


def number_format(number):
    try:
        number = "{:,}".format(int(number))
        return number
    except Exception as exp:
        return 0


def phone_format_old(phone):
    try:
        number = str(phone)
        first = number[0:3]
        second = number[3:6]
        third = number[6:10]
        phone_no = '(' + first + ')' + ' ' + second + '-' + third
        return phone_no
    except Exception as exp:
        return 0
    
def phone_format(phone):
    try:
        number = str(phone)
        first = number[0:2]
        second = number[2:5]
        third = number[5:]
        # phone_no = '(' + first + ')' + ' ' + second + '-' + third
        phone_no = '(+971) ' + first + ' ' + second + ' ' + third
        return phone_no
    except Exception as exp:
        return 0    
    
def phone_format_new(phone, phone_country_code):
    try:
        if int(phone_country_code) == 971:
            number = str(phone)
            first = number[0:2]
            second = number[2:6]
            third = number[6:]
            phone_no = first + ' ' + second + ' ' + third
        elif int(phone_country_code) == 1:
            number = str(phone)
            first = number[0:3]
            second = number[3:6]
            third = number[6:]
            phone_no = '(' + first + ')' + ' ' + second + '-' + third
        elif int(phone_country_code) == 91:
            number = str(phone)
            first = number[0:3]
            second = number[3:]
            phone_no = first + ' ' + second
        else:
            number = str(phone)
            first = number[0:3]
            second = number[3:6]
            third = number[6:]
            phone_no = first + '' + second + ' ' + third            
        return phone_no
    except Exception as exp:
        return 0   


def int_to_en(num):
    d = {0: 'zero', 1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine',
         10: 'ten', 11: 'eleven', 12: 'twelve', 13: 'thirteen', 14: 'fourteen', 15: 'fifteen', 16: 'sixteen',
         17: 'seventeen', 18: 'eighteen', 19: 'nineteen', 20: 'twenty', 30: 'thirty', 40: 'forty', 50: 'fifty',
         60: 'sixty', 70: 'seventy', 80: 'eighty', 90: 'ninety'}
    k = 1000
    m = k * 1000
    b = m * 1000
    t = b * 1000

    assert(0 <= num)
    if num < 20:
        return d[num]

    if num < 100:
        if num % 10 == 0:
            return d[num]
        else:
            return d[num // 10 * 10] + ' ' + d[num % 10]

    if num < k:
        if num % 100 == 0:
            return d[num // 100] + ' hundred'
        else:
            return d[num // 100] + ' hundred ' + int_to_en(num % 100)

    if num < m:
        if num % k == 0:
            return int_to_en(num // k) + ' thousand'
        else:
            return int_to_en(num // k) + ' thousand, ' + int_to_en(num % k)

    if num < b:
        if num % m == 0:
            return int_to_en(num // m) + ' million'
        else:
            return int_to_en(num // m) + ' million, ' + int_to_en(num % m)

    if num < t:
        if num % b == 0:
            return int_to_en(num // b) + ' billion'
        else:
            return int_to_en(num // b) + ' billion, ' + int_to_en(num % b)

    if num % t == 0:
        return int_to_en(num // t) + ' trillion'
    else:
        return int_to_en(num // t) + ' trillion, ' + int_to_en(num % t)
    raise AssertionError('num is too large: %s' % str(num))