import base64
from random import randint
import re
from api.users.models import *
import uuid
from django.conf import settings
from django.core.cache import cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
CACHE_TTL = getattr(settings, 'CACHE_TTL', DEFAULT_TIMEOUT)
import random
from firebase_admin import auth
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import jwt
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
import requests
import time
from api.users.serializers import *
from api.property.models import *
import os

# Initialize BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)

def b64encode(source):
    source = "xsd0xa" + source + "xsd1xa"
    source = source.encode('utf-8')
    content = base64.b64encode(source).decode('utf-8')
    return content


def b64decode(source):
    content = base64.b64decode(source).decode('utf-8')
    content = content[6::]
    content = content[:-6:]
    return content


def random_with_digits(n):
    range_start = 10**(n-1)
    range_end = (10**n)-1
    return randint(range_start, range_end)


def remove_space(string):
    string = string.lower().strip()
    pattern = re.compile(r'\s+')
    return re.sub(pattern, '', string)


def remove_special(string):
    # return re.sub("[!@#$%^&*-_(){}/|=?':.]", "", string)
    return re.sub("[^A-Za-z]", "", string)


def make_subdomain(string):
    string = remove_space(string)
    string = remove_special(string)
    network_domain = NetworkDomain.objects.filter(domain_name=string).first()
    if network_domain is None:
        return string
    else:
        random_digit = random_with_digits(4)
        domain_name = string + str(random_digit)
        return domain_name


def forgot_token():
    try:
        u_id = uuid.uuid4()
        return u_id.time_low
    except Exception as exp:
        return False


def replace_space(string):
    string = string.lower().strip()
    pattern = re.compile(r'\s+')
    return re.sub(pattern, '_', string)


def get_cache(cache_name):
    try:
        if settings.REDIS_CACHE == "True" and cache_name in cache and cache.get(cache_name) != "" and len(list(cache.get(cache_name))) > 0:
            all_data = list(cache.get(cache_name))
        else:
            all_data = None
        return all_data
    except Exception as exp:
        return None


def set_cache(cache_name, data):
    try:
        if settings.REDIS_CACHE == "True":
            cache.set(cache_name, data, timeout=int(CACHE_TTL))
        return True
    except Exception as exp:
        return False


def unique_registration_id():
    try:
        u_id = uuid.uuid4()
        return u_id.time_low
    except Exception as exp:
        return False


def create_otp(digits=4):
    try:
        if digits > 1:
            lower_bound = 10**(digits - 1)
            upper_bound = (10**digits) - 1
            return random.randint(lower_bound, upper_bound)
        else:
            return 1234
    except Exception as exp:
        return 1234
    

def firebase_token(idToken, signup_source):
    try:
        all_data = {}
        # if int(signup_source) == 2:
        #     decoded_token = auth.verify_id_token(idToken)
        #     uid = decoded_token['uid']
        #     email = decoded_token['email']
        # else:
        #     decoded_token = jwt.decode(idToken, options={"verify_signature": False})
        #     uid = decoded_token['sub']
        #     email = decoded_token['email']
        decoded_token = jwt.decode(idToken, options={"verify_signature": False})
        uid = decoded_token['sub']
        email = decoded_token['email']
        name = decoded_token.get('name')
        name = name.title() if isinstance(name, str) else ""
        try:
            validate_email(email)
            all_data['email'] = email
            all_data['name'] = name
            all_data['uid'] = uid
            all_data['error'] = 0
            all_data['msg'] = "Success"
        except ValidationError:
            return {"error": 1, "msg": "Invalid Email"}
        return all_data
    except auth.InvalidIdTokenError:
        return {"error": 1, "msg": "Invalid Token"}
    except auth.ExpiredIdTokenError:
        return {"error": 1, "msg": "Token has expired"}
    except auth.RevokedIdTokenError:
        return {"error": 1, "msg": "Token has been revoked"}
    except Exception as exp:
        return {"error": 1, "msg": "An unexpected error occurred"}
     

def save_to_bucket(file_resource, file_path, container_name=settings.AZURE_CONTAINER_NAME):
    """Function to save uploaded file resource to azure blob

    para1:
       uploaded file resource
    param2:
       file_path: Path within the container to save the file (e.g., 'folder1/folder2').
    param3:
        container_name: The name of the container to upload the file.
    return:
       A dictionary containing the status, error, file_name, and message.
    """

    if file_resource is not None and file_path is not None:
        try:
            upload_file_name = file_resource.name
            upload_file_name = re.sub(r'\s+', '_', upload_file_name)
            times = time.time()
            cloud_filename = file_path + '/' + str(times) + '_' + upload_file_name
            file_name = str(times) + '_' + upload_file_name

            # Get container client and upload the blob
            container_client = blob_service_client.get_container_client(container_name)
            container_client.upload_blob(name=cloud_filename, data=file_resource, overwrite=True)
        except Exception as err:
            return {'status': 403, 'error': 1, 'file_name': '', 'msg': str(err)}
        else:
            return {'status': 200, 'error': 0, 'file_name': file_name, 'msg': 'uploaded'}


def save_document(site_id, user_id, doc_type, bucket_name, document, seller_upload = None):
    """Function to save uploaded file resource to azure blob and user uploads database

    para1:
       site_id for store table
    param2:
       user_id for store table 
    param3:
        doc_type for store table
    param4:
        bucket_name for store table
    param5:
        uploaded file resource
    return:
       A dictionary containing the status, error, file_name, and message.
    """
    try:
        upload_ids = []

        # Disallowed (dangerous) file extensions
        disallowed_extensions = [
            "py", "pyc", "php", "js", "jsp", "exe", "sh", "bat", "cmd", "rb",
            "cgi", "pl", "asp", "aspx", "dll", "jar", "msi", "vb", "vbs"
        ]

        for file in document:
            file_size = file.size
            file_name = file.name
            file_size_mb = round(file_size / (1024 * 1024), 2)

            # Extract file extension safely (lowercase, without dot)
            _, file_extension = os.path.splitext(file_name)
            file_extension = file_extension.lower().lstrip('.')  # e.g. "pdf", "jpg"
            # Block unsafe file types
            if file_extension in disallowed_extensions:
                return None

            upload_azure = save_to_bucket(file, bucket_name)
            upload_param = {}
            if 'error' in upload_azure and upload_azure['error'] == 0:
                upload_param['site'] = site_id
                upload_param['user'] = user_id
                upload_param['doc_file_name'] = upload_azure['file_name']
                upload_param['document'] = doc_type
                upload_param['bucket_name'] = bucket_name
                upload_param['added_by'] = user_id
                upload_param['updated_by'] = user_id
                upload_param['file_size'] = str(file_size_mb) + 'MB'
                upload_param['is_active'] = 1
                serializer = UserUploadsSerializer(data=upload_param)
                if serializer.is_valid():
                    upload = serializer.save()
                    if upload is not None:
                        upload_id = upload.id
                        upload_ids.append(upload_id)
        
        if upload_ids is not None and upload_ids:
            if(seller_upload) :
                return {"doc_file_name": upload_azure['file_name'], "upload_id": upload_ids[0]}
            else:
                return upload_ids
        else:
            return []
    except Exception as err:
            return []
    

def property_similar_attribute(property_id):
    try:
        all_attribute = {}
        property_details = PropertyListing.objects.filter(id=property_id).last()
        if property_details is not None:
            all_attribute['project'] = property_details.project_id
            all_attribute['state'] = property_details.state_id
            all_attribute['community'] = property_details.community
            all_attribute['property_type'] = property_details.property_type_id   
        return all_attribute
    except Exception as exp:
        return {}

