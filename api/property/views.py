# -*- coding: utf-8 -*-
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.viewsets import ViewSet
from api.packages.response import Response as response
from api.property.models import *
import datetime
from django.utils import timezone
from api.property.serializers import *
from api.packages.globalfunction import *
from django.db import transaction
from rest_framework.authentication import TokenAuthentication
from oauth2_provider.contrib.rest_framework import *
from django.db.models import F, FilteredRelation
from django.db.models import Q
from django.conf import settings
from django.db.models.functions import Concat
from django.db.models import Value as V
from datetime import timedelta
from django.db.models import CharField
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from django.core.cache import cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
CACHE_TTL = getattr(settings, 'CACHE_TTL', DEFAULT_TIMEOUT)
from api.packages.mail_service import send_email, compose_email, send_custom_email
from api.packages.multiupload import *
from api.packages.common import *
import pandas as pd
import pytz
from api.packages.constants import *
from django.db.models.functions import TruncDate
import re
import ssl
import json
import base64
import requests
from django.db.models import Case, When, Value, IntegerField, Count, Q, F
from api.payments.services.gateway import void_payment, capture_payment, cron_void_payment
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db.models import Sum
from api.packages.pushnotification import *
ssl._create_default_https_context = ssl._create_unverified_context


class AddPropertyApiView(APIView):
    """
    Add/Update Property
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
                data['domain'] = site_id
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            property_id = None
            check_update = None
            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
                check_update = True
                property_id = PropertyListing.objects.filter(id=property_id, domain=site_id).first()
                if property_id is None:
                    return Response(response.parsejson("Property not exist.", "", status=403))
            if "step" in data and data['step'] != "":
                step = int(data['step'])
            else:
                return Response(response.parsejson("step is required.", "", status=403))
            user_domain = None
            creater_user_type = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=site_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5], status=1).first()
                    # if users is None:
                    #     users = Users.objects.filter(id=user_id, network_user__domain=site_id, network_user__is_agent=1, network_user__status=1, status=1, user_type=4).first()
                    #     if users is None:
                    #         return Response(response.parsejson("User not exist.", "", status=403))
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                if property_id is not None:
                    user_id = property_id.agent_id
                data["agent"] = user_id
                user_domain = users.site_id
                creater_user_type = users.user_type_id
                if users.site_id is None and users.user_type_id == 5:
                    network_user = NetworkUser.objects.filter(user=user_id).first()
                    if network_user is not None:
                        data['developer'] = network_user.developer_id  
                elif users.site_id is None:             
                    data['developer'] = user_id
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))
            
            listing_update_email = None
            if step == 1:
                un_priced = 0
                if "un_priced" in data and data['un_priced'] != "":
                    un_priced = int(data['un_priced'])

                required_all = 0
                if "required_all" in data and data['required_all'] != "":
                    required_all = int(data['required_all'])

                if "property_asset" in data and data['property_asset'] != "":
                    property_asset = int(data['property_asset'])
                    asset = LookupPropertyAsset.objects.filter(id=property_asset, is_active=1).first()
                    if asset is None:
                        return Response(response.parsejson("Property asset not available.", "", status=403))
                else:
                    return Response(response.parsejson("property_asset is required.", "", status=403))

                if "address_one" in data and data['address_one'] != "":
                    address_one = data['address_one']
                else:
                    return Response(response.parsejson("address_one is required.", "", status=403))
                
                if "property_name" in data and data['property_name'] != "":
                    property_name = data['property_name']
                else:
                    return Response(response.parsejson("property_name is required.", "", status=403))

                if "case_number" in data and data['case_number'] != "":
                    case_number = data['case_number']
                else:
                    return Response(response.parsejson("case_number is required.", "", status=403))  
                
                if "sale_lot" in data and data['sale_lot'] != "":
                    sale_lot = data['sale_lot']
                else:
                    return Response(response.parsejson("sale_lot is required.", "", status=403))  

                if "city" in data and data['city'] != "":
                    city = data['city']
                else:
                    return Response(response.parsejson("city is required.", "", status=403))

                if "state" in data and data['state'] != "":
                    state = int(data['state'])
                else:
                    return Response(response.parsejson("state is required.", "", status=403))

                if "postal_code" in data and data['postal_code'] != "":
                    postal_code = int(data['postal_code'])
                else:
                    return Response(response.parsejson("postal_code is required.", "", status=403))
                
                if int(property_asset) != 6 or int(property_asset) != 4:
                    if "property_type" in data and data['property_type'] != "":
                        property_type = int(data['property_type'])
                    else:
                        return Response(response.parsejson("property_type is required.", "", status=403))

                if "sale_by_type" in data and data['sale_by_type'] != "":
                    sale_by_type = int(data['sale_by_type'])
                else:
                    return Response(response.parsejson("sale_by_type is required.", "", status=403))

                if sale_by_type in [1, 7]:
                    if "buyers_premium" in data and data['buyers_premium'] != "":
                        buyers_premium = int(data['buyers_premium'])
                    else:
                        return Response(response.parsejson("buyers_premium is required.", "", status=403))
                    if buyers_premium:
                        if "buyers_premium_percentage" in data and data['buyers_premium_percentage'] != "" and float(data['buyers_premium_percentage']) > 0:
                            buyers_premium_percentage = data['buyers_premium_percentage']
                        else:
                            return Response(response.parsejson("buyers_premium_percentage is required.", "", status=403))

                        # if "buyers_premium_min_amount" in data and data['buyers_premium_min_amount'] != "" and float(data['buyers_premium_min_amount']) > 0:
                        #     buyers_premium_min_amount = data['buyers_premium_min_amount']
                        # else:
                        #     return Response(response.parsejson("buyers_premium_min_amount is required.", "", status=403))
                else:
                    data['buyers_premium'] = False
                    data['buyers_premium_percentage'] = None
                    data['buyers_premium_min_amount'] = None

                # -------------For Deposit Listings-------------
                if sale_by_type in [1, 2]:
                    data['deposit_amount'] = data['deposit_amount'] if int(data['is_deposit_required']) == 1 else 0 
                else:
                    data['deposit_amount'] = 0
                    data['is_deposit_required'] = 0

                if sale_by_type == 6:
                    if "auction_location" in data and data['auction_location'] != "":
                        auction_location = data['auction_location']
                    else:
                        return Response(response.parsejson("auction_location is required.", "", status=403))

                if sale_by_type == 7 and required_all == 1:
                    if "due_diligence_period" in data and data['due_diligence_period'] != "":
                        due_diligence_period = int(data['due_diligence_period'])
                    else:
                        return Response(response.parsejson("due_diligence_period is required.", "", status=403))

                    if "escrow_period" in data and data['escrow_period'] != "":
                        escrow_period = int(data['escrow_period'])
                    else:
                        return Response(response.parsejson("escrow_period is required.", "", status=403))

                    if "earnest_deposit" in data and data['earnest_deposit'] != "":
                        earnest_deposit = data['earnest_deposit']
                    else:
                        return Response(response.parsejson("earnest_deposit is required.", "", status=403))

                    if "earnest_deposit_type" in data and data['earnest_deposit_type'] != "":
                        earnest_deposit_type = int(data['earnest_deposit_type'])
                    else:
                        return Response(response.parsejson("earnest_deposit_type is required.", "", status=403))

                    if "highest_best_format" in data and data['highest_best_format'] != "":
                        highest_best_format = int(data['highest_best_format'])
                    else:
                        return Response(response.parsejson("highest_best_format is required.", "", status=403))

                if "status" in data and data['status'] != "":
                    status = int(data['status'])
                else:
                    data['status'] = 2

                if property_asset != 1:
                    if "property_opening_dates" in data and type(data['property_opening_dates']) == list and len(data['property_opening_dates']) > 0:
                        property_opening_dates = data['property_opening_dates']
                    else:
                        return Response(response.parsejson("property_opening_dates is required.", "", status=403))

                if "property_auction_data" in data and type(data["property_auction_data"]) == dict and len(data["property_auction_data"]) > 0:
                    property_auction_data = data["property_auction_data"]
                    if "auction_status" in property_auction_data and property_auction_data["auction_status"] != "":
                        auction_status = int(property_auction_data["auction_status"])
                    else:
                        return Response(response.parsejson("property_auction_data->auction_status is required.", "", status=403))

                    if sale_by_type == 7:
                        start_price = None
                        if required_all == 1:
                            if "start_price" in property_auction_data and property_auction_data['start_price'] != "":
                                start_price = property_auction_data['start_price']
                            else:
                                if not un_priced:
                                    return Response(response.parsejson("property_auction_data->start_price is required.", "", status=403))
                                # else:
                                #     start_price = None
                    else:
                        if "start_price" in property_auction_data and property_auction_data['start_price'] != "":
                            start_price = property_auction_data['start_price']
                        else:
                            return Response(response.parsejson("property_auction_data->start_price is required.", "", status=403))
                    if sale_by_type != 4:   # ----------- Not traditional auction
                        if "start_date" in property_auction_data and property_auction_data['start_date'] != "":
                            start_date = property_auction_data['start_date']
                        else:
                            return Response(response.parsejson("property_auction_data->start_date is required.", "", status=403))

                        if "end_date" in property_auction_data and property_auction_data['end_date'] != "":
                            end_date = property_auction_data['end_date']
                        else:
                            return Response(response.parsejson("property_auction_data->end_date is required.", "", status=403))
                        
                    if sale_by_type == 1:
                        if "bid_increments" in property_auction_data and property_auction_data['bid_increments'] != "":
                            bid_increments = property_auction_data['bid_increments']
                        else:
                            return Response(response.parsejson("property_auction_data->bid_increments is required.", "", status=403))
                        
                    if sale_by_type in [1, 6]:
                        if "reserve_amount" in property_auction_data and property_auction_data['reserve_amount'] != "":
                            reserve_amount = property_auction_data['reserve_amount']
                        else:
                            return Response(response.parsejson("property_auction_data->reserve_amount is required.", "", status=403))    

                    # if sale_by_type != 2:
                    if sale_by_type != 2 and sale_by_type != 7:
                        if "reserve_amount" in property_auction_data and property_auction_data['reserve_amount'] != "" and property_auction_data['reserve_amount'] is not None:
                            reserve_amount = property_auction_data['reserve_amount']
                            if float(start_price) > float(reserve_amount):
                                return Response(response.parsejson("reserve_amount should be greater than start_price.", "", status=403))

                    if sale_by_type == 2:
                        if "bid_increments" in property_auction_data and property_auction_data['bid_increments'] != "":
                            bid_increments = property_auction_data['bid_increments']
                        else:
                            return Response(response.parsejson("property_auction_data->bid_increments is required.", "", status=403))

                        if "insider_price_decrease" in property_auction_data and property_auction_data['insider_price_decrease'] != "":
                            insider_price_decrease = property_auction_data['insider_price_decrease']
                        else:
                            return Response(response.parsejson("property_auction_data->insider_price_decrease is required.", "", status=403))

                        if "dutch_time" in property_auction_data and property_auction_data['dutch_time'] != "":
                            dutch_time = property_auction_data['dutch_time']
                        else:
                            return Response(response.parsejson("property_auction_data->dutch_time is required.", "", status=403))

                        if "start_date" in property_auction_data and property_auction_data['start_date'] != "":
                            start_date = property_auction_data['start_date']
                        else:
                            return Response(response.parsejson("property_auction_data->start_date is required.", "", status=403))

                        if "dutch_end_time" in property_auction_data and property_auction_data['dutch_end_time'] != "":
                            dutch_end_time = property_auction_data['dutch_end_time']
                        else:
                            return Response(response.parsejson("property_auction_data->dutch_end_time is required.", "", status=403))

                        if "dutch_pause_time" in property_auction_data and property_auction_data['dutch_pause_time'] != "":
                            dutch_pause_time = property_auction_data['dutch_pause_time']
                        else:
                            return Response(response.parsejson("property_auction_data->dutch_pause_time is required.", "", status=403))

                        if "sealed_time" in property_auction_data and property_auction_data['sealed_time'] != "":
                            sealed_time = property_auction_data['sealed_time']
                        else:
                            return Response(response.parsejson("property_auction_data->sealed_time is required.", "", status=403))

                        if "sealed_start_time" in property_auction_data and property_auction_data['sealed_start_time'] != "":
                            sealed_start_time = property_auction_data['sealed_start_time']
                        else:
                            return Response(response.parsejson("property_auction_data->sealed_start_time is required.", "", status=403))

                        if "sealed_end_time" in property_auction_data and property_auction_data['sealed_end_time'] != "":
                            sealed_end_time = property_auction_data['sealed_end_time']
                        else:
                            return Response(response.parsejson("property_auction_data->sealed_end_time is required.", "", status=403))

                        if "sealed_pause_time" in property_auction_data and property_auction_data['sealed_pause_time'] != "":
                            sealed_pause_time = property_auction_data['sealed_pause_time']
                        else:
                            return Response(response.parsejson("property_auction_data->sealed_pause_time is required.", "", status=403))

                        if "english_time" in property_auction_data and property_auction_data['english_time'] != "":
                            english_time = property_auction_data['english_time']
                        else:
                            return Response(response.parsejson("property_auction_data->english_time is required.", "", status=403))

                        if "english_start_time" in property_auction_data and property_auction_data['english_start_time'] != "":
                            english_start_time = property_auction_data['english_start_time']
                        else:
                            return Response(response.parsejson("property_auction_data->english_start_time is required.", "", status=403))

                        # if "english_end_time" in property_auction_data and property_auction_data['english_end_time'] != "":
                        #     english_end_time = property_auction_data['english_end_time']
                        # else:
                        #     return Response(response.parsejson("property_auction_data->english_end_time is required.", "", status=403))
                else:
                    return Response(response.parsejson("property_auction_data is required.", "", status=403))

                if property_asset == 3:
                    if "beds" in data and data['beds'] != "":
                        beds = data['beds']
                    else:
                        return Response(response.parsejson("beds is required.", "", status=403))

                    if "baths" in data and data['baths'] != "":
                        baths = data['baths']
                    else:
                        return Response(response.parsejson("baths is required.", "", status=403))

                    if "year_built" in data and data['year_built'] != "":
                        year_built = int(data['year_built'])
                    else:
                        return Response(response.parsejson("year_built is required.", "", status=403))

                    if "square_footage" in data and data['square_footage'] != "":
                        square_footage = int(data['square_footage'])
                    else:
                        return Response(response.parsejson("square_footage is required.", "", status=403))
                elif property_asset == 2:
                    if "year_built" in data and data['year_built'] != "":
                        year_built = int(data['year_built'])
                    else:
                        return Response(response.parsejson("year_built is required.", "", status=403))

                    if "square_footage" in data and data['square_footage'] != "":
                        square_footage = int(data['square_footage'])
                    else:
                        return Response(response.parsejson("square_footage is required.", "", status=403))
                data["create_step"] = 1
                # data["status"] = 1
                data["title"] = "testing"
                if user_domain == site_id or int(creater_user_type) == 2:
                    data['is_approved'] = 1
                serializer = AddPropertySerializer(property_id, data=data)
                if serializer.is_valid():
                    property_id = serializer.save()
                    property_id = property_id.id
                else:
                    copy_errors = serializer.errors.copy()
                    return Response(response.parsejson(copy_errors, "", status=403))
                # ----------------------Property Auction---------------------
                if "property_auction_data" in data and type(data["property_auction_data"]) == dict and len(data["property_auction_data"]) > 0:
                    property_auction_data = data["property_auction_data"]
                    property_auction = PropertyAuction.objects.filter(property=property_id).first()
                    if property_auction is not None:
                        if property_auction.bid_increments != property_auction_data['bid_increments']:
                            listing_update_email = 'bid_increment'
                        if sale_by_type != 4:
                            start_date_obj = datetime.datetime.strptime(property_auction_data['start_date'], "%Y-%m-%d %H:%M:%S")
                            end_date_obj = datetime.datetime.strptime(property_auction_data['end_date'], "%Y-%m-%d %H:%M:%S")
                            mismatch_property_auction = PropertyAuction.objects.filter(property=property_id, start_date=start_date_obj, end_date=end_date_obj).first()
                            if mismatch_property_auction is None:
                                listing_update_email = 'date_mismatch'
                    if property_auction is None:
                        property_auction = PropertyAuction()
                        property_auction.property_id = property_id
                    property_auction.start_date = property_auction_data['start_date']
                    property_auction.end_date = property_auction_data['end_date'] if "end_date" in property_auction_data else None
                    property_auction.bid_increments = property_auction_data['bid_increments']
                    property_auction.reserve_amount = property_auction_data['reserve_amount'] if "reserve_amount" in property_auction_data else None
                    property_auction.time_zone_id = property_auction_data['time_zone']
                    property_auction.start_price = property_auction_data['start_price']
                    property_auction.insider_decreased_price = property_auction_data['start_price']
                    property_auction.status_id = property_auction_data['auction_status']
                    # property_auction.open_house_start_date = property_auction_data['open_house_start_date']
                    # property_auction.open_house_end_date = property_auction_data['open_house_end_date']
                    property_auction.offer_amount = property_auction_data['offer_amount'] if "offer_amount" in property_auction_data else None
                    property_auction.auction_id = sale_by_type
                    property_auction.domain_id = site_id
                    property_auction.un_priced = un_priced
                    property_auction.required_all = required_all
                    property_auction.insider_price_decrease = property_auction_data['insider_price_decrease'] if "insider_price_decrease" in property_auction_data else None
                    property_auction.dutch_time = int(property_auction_data['dutch_time']) if "dutch_time" in property_auction_data else None
                    property_auction.dutch_end_time = property_auction_data['dutch_end_time'] if "dutch_end_time" in property_auction_data else None
                    property_auction.dutch_pause_time = int(property_auction_data['dutch_pause_time']) if "dutch_pause_time" in property_auction_data else None
                    property_auction.sealed_time = int(property_auction_data['sealed_time']) if "sealed_time" in property_auction_data else None
                    property_auction.sealed_start_time = property_auction_data['sealed_start_time'] if "sealed_start_time" in property_auction_data else None
                    property_auction.sealed_end_time = property_auction_data['sealed_end_time'] if "sealed_end_time" in property_auction_data else None
                    property_auction.sealed_pause_time = int(property_auction_data['sealed_pause_time']) if "sealed_pause_time" in property_auction_data else None
                    property_auction.english_time = int(property_auction_data['english_time']) if "english_time" in property_auction_data else None
                    property_auction.english_start_time = property_auction_data['english_start_time'] if "english_start_time" in property_auction_data else None
                    # property_auction.english_end_time = property_auction_data['english_end_time'] if "english_end_time" in property_auction_data else None


                    property_auction.save()
                # ----------------------Property Subtype---------------------
                if "property_subtype" in data and type(data["property_subtype"]) == list:
                    property_subtype = data["property_subtype"]
                    PropertySubtype.objects.filter(property=property_id).delete()
                    for subtype in property_subtype:
                        property_subtype = PropertySubtype()
                        property_subtype.property_id = property_id
                        property_subtype.subtype_id = subtype
                        property_subtype.save()

                # ----------------------Terms Accepted---------------------
                if "terms_accepted" in data and type(data["terms_accepted"]) == list:
                    terms_accepted = data["terms_accepted"]
                    PropertyTermAccepted.objects.filter(property=property_id).delete()
                    for terms in terms_accepted:
                        property_term_accepted = PropertyTermAccepted()
                        property_term_accepted.property_id = property_id
                        property_term_accepted.term_accepted_id = terms
                        property_term_accepted.save()

                # ----------------------Occupied By---------------------
                if "occupied_by" in data and type(data["occupied_by"]) == list:
                    occupied_by = data["occupied_by"]
                    PropertyOccupiedBy.objects.filter(property=property_id).delete()
                    for occupied in occupied_by:
                        property_occupied_by = PropertyOccupiedBy()
                        property_occupied_by.property_id = property_id
                        property_occupied_by.occupied_by_id = occupied
                        property_occupied_by.save()

                # ----------------------Ownership---------------------
                if "ownership" in data and type(data["ownership"]) == list:
                    ownership = data["ownership"]
                    PropertyOwnership.objects.filter(property=property_id).delete()
                    for owner in ownership:
                        property_ownership = PropertyOwnership()
                        property_ownership.property_id = property_id
                        property_ownership.ownership_id = owner
                        property_ownership.save()

                # ----------------------Possession---------------------
                if "possession" in data and type(data["possession"]) == list:
                    possession = data["possession"]
                    PropertyPossession.objects.filter(property=property_id).delete()
                    for pos in possession:
                        property_possession = PropertyPossession()
                        property_possession.property_id = property_id
                        property_possession.possession_id = pos
                        property_possession.save()

                # ----------------------Style---------------------
                if "style" in data and type(data["style"]) == list:
                    style = data["style"]
                    PropertyStyle.objects.filter(property=property_id).delete()
                    for st in style:
                        property_style = PropertyStyle()
                        property_style.property_id = property_id
                        property_style.style_id = st
                        property_style.save()

                # ----------------------Cooling---------------------
                if "cooling" in data and type(data["cooling"]) == list:
                    cooling = data["cooling"]
                    PropertyCooling.objects.filter(property=property_id).delete()
                    for cool in cooling:
                        property_cooling = PropertyCooling()
                        property_cooling.property_id = property_id
                        property_cooling.cooling_id = cool
                        property_cooling.save()

                # ----------------------Stories---------------------
                if "stories" in data and type(data["stories"]) == list:
                    stories = data["stories"]
                    PropertyStories.objects.filter(property=property_id).delete()
                    for story in stories:
                        property_stories = PropertyStories()
                        property_stories.property_id = property_id
                        property_stories.stories_id = story
                        property_stories.save()

                # ----------------------HeatingStories---------------------
                if "heating" in data and type(data["heating"]) == list:
                    heating = data["heating"]
                    PropertyHeating.objects.filter(property=property_id).delete()
                    for heat in heating:
                        property_heating = PropertyHeating()
                        property_heating.property_id = property_id
                        property_heating.heating_id = heat
                        property_heating.save()

                # ----------------------Electric---------------------
                if "electric" in data and type(data["electric"]) == list:
                    electric = data["electric"]
                    PropertyElectric.objects.filter(property=property_id).delete()
                    for ele in electric:
                        property_electric = PropertyElectric()
                        property_electric.property_id = property_id
                        property_electric.electric_id = ele
                        property_electric.save()

                # ----------------------Gas---------------------
                if "gas" in data and type(data["gas"]) == list:
                    gas = data["gas"]
                    PropertyGas.objects.filter(property=property_id).delete()
                    for g in gas:
                        property_gas = PropertyGas()
                        property_gas.property_id = property_id
                        property_gas.gas_id = g
                        property_gas.save()

                # ----------------------Recent Updates---------------------
                if "recent_updates" in data and type(data["recent_updates"]) == list:
                    recent_updates = data["recent_updates"]
                    PropertyRecentUpdates.objects.filter(property=property_id).delete()
                    for updates in recent_updates:
                        property_recent_updates = PropertyRecentUpdates()
                        property_recent_updates.property_id = property_id
                        property_recent_updates.recent_updates_id = updates
                        property_recent_updates.save()

                # ----------------------Water---------------------
                if "water" in data and type(data["water"]) == list:
                    water = data["water"]
                    PropertyWater.objects.filter(property=property_id).delete()
                    for wa in water:
                        property_water = PropertyWater()
                        property_water.property_id = property_id
                        property_water.water_id = wa
                        property_water.save()

                # ----------------------Security Features---------------------
                if "security_features" in data and type(data["security_features"]) == list:
                    security_features = data["security_features"]
                    PropertySecurityFeatures.objects.filter(property=property_id).delete()
                    for security in security_features:
                        property_security_features = PropertySecurityFeatures()
                        property_security_features.property_id = property_id
                        property_security_features.security_features_id = security
                        property_security_features.save()

                # ----------------------Sewer---------------------
                if "sewer" in data and type(data["sewer"]) == list:
                    sewer = data["sewer"]
                    PropertySewer.objects.filter(property=property_id).delete()
                    for se in sewer:
                        property_sewer = PropertySewer()
                        property_sewer.property_id = property_id
                        property_sewer.sewer_id = se
                        property_sewer.save()

                # ----------------------Tax Exemptions---------------------
                if "tax_exemptions" in data and type(data["tax_exemptions"]) == list:
                    tax_exemptions = data["tax_exemptions"]
                    PropertyTaxExemptions.objects.filter(property=property_id).delete()
                    for tax in tax_exemptions:
                        property_tax_exemptions = PropertyTaxExemptions()
                        property_tax_exemptions.property_id = property_id
                        property_tax_exemptions.tax_exemptions_id = tax
                        property_tax_exemptions.save()

                # ----------------------Zoning---------------------
                if "zoning" in data and type(data["zoning"]) == list:
                    zoning = data["zoning"]
                    PropertyZoning.objects.filter(property=property_id).delete()
                    for zo in zoning:
                        property_zoning = PropertyZoning()
                        property_zoning.property_id = property_id
                        property_zoning.zoning_id = zo
                        property_zoning.save()

                # ----------------------Hoa Amenities---------------------
                if "hoa_amenities" in data and type(data["hoa_amenities"]) == list:
                    hoa_amenities = data["hoa_amenities"]
                    PropertyAmenities.objects.filter(property=property_id).delete()
                    for hoa in hoa_amenities:
                        property_amenities = PropertyAmenities()
                        property_amenities.property_id = property_id
                        property_amenities.amenities_id = hoa
                        property_amenities.save()

                # ----------------------Kitchen Features---------------------
                if "kitchen_features" in data and type(data["kitchen_features"]) == list:
                    kitchen_features = data["kitchen_features"]
                    PropertyKitchenFeatures.objects.filter(property=property_id).delete()
                    for kitchen in kitchen_features:
                        property_kitchen_features = PropertyKitchenFeatures()
                        property_kitchen_features.property_id = property_id
                        property_kitchen_features.kitchen_features_id = kitchen
                        property_kitchen_features.save()

                # ----------------------Appliances---------------------
                if "appliances" in data and type(data["appliances"]) == list:
                    appliances = data["appliances"]
                    PropertyAppliances.objects.filter(property=property_id).delete()
                    for apl in appliances:
                        property_appliances = PropertyAppliances()
                        property_appliances.property_id = property_id
                        property_appliances.appliances_id = apl
                        property_appliances.save()

                # ----------------------Flooring---------------------
                if "flooring" in data and type(data["flooring"]) == list:
                    flooring = data["flooring"]
                    PropertyFlooring.objects.filter(property=property_id).delete()
                    for floor in flooring:
                        property_flooring = PropertyFlooring()
                        property_flooring.property_id = property_id
                        property_flooring.flooring_id = floor
                        property_flooring.save()

                # ----------------------Windows---------------------
                if "windows" in data and type(data["windows"]) == list:
                    windows = data["windows"]
                    PropertyWindows.objects.filter(property=property_id).delete()
                    for window in windows:
                        property_windows = PropertyWindows()
                        property_windows.property_id = property_id
                        property_windows.windows_id = window
                        property_windows.save()

                # ----------------------Bedroom Features---------------------
                if "bedroom_features" in data and type(data["bedroom_features"]) == list:
                    bedroom_features = data["bedroom_features"]
                    PropertyBedroomFeatures.objects.filter(property=property_id).delete()
                    for bedroom in bedroom_features:
                        property_bedroom_features = PropertyBedroomFeatures()
                        property_bedroom_features.property_id = property_id
                        property_bedroom_features.bedroom_features_id = bedroom
                        property_bedroom_features.save()

                # ----------------------Other Rooms---------------------
                if "other_rooms" in data and type(data["other_rooms"]) == list:
                    other_rooms = data["other_rooms"]
                    PropertyOtherRooms.objects.filter(property=property_id).delete()
                    for other in other_rooms:
                        property_other_rooms = PropertyOtherRooms()
                        property_other_rooms.property_id = property_id
                        property_other_rooms.other_rooms_id = other
                        property_other_rooms.save()

                # ----------------------Bathroom Features---------------------
                if "bathroom_features" in data and type(data["bathroom_features"]) == list:
                    bathroom_features = data["bathroom_features"]
                    PropertyBathroomFeatures.objects.filter(property=property_id).delete()
                    for bathroom in bathroom_features:
                        property_bathroom_features = PropertyBathroomFeatures()
                        property_bathroom_features.property_id = property_id
                        property_bathroom_features.bathroom_features_id = bathroom
                        property_bathroom_features.save()
                # ----------------------Other Features---------------------
                if "other_features" in data and type(data["other_features"]) == list:
                    other_features = data["other_features"]
                    PropertyOtherFeatures.objects.filter(property=property_id).delete()
                    for other in other_features:
                        property_other_features = PropertyOtherFeatures()
                        property_other_features.property_id = property_id
                        property_other_features.other_features_id = other
                        property_other_features.save()

                # ----------------------Master Bedroom Features---------------------
                if "master_bedroom_features" in data and type(data["master_bedroom_features"]) == list:
                    master_bedroom_features = data["master_bedroom_features"]
                    PropertyMasterBedroomFeatures.objects.filter(property=property_id).delete()
                    for master_bedroom in master_bedroom_features:
                        property_master_bedroom_features = PropertyMasterBedroomFeatures()
                        property_master_bedroom_features.property_id = property_id
                        property_master_bedroom_features.master_bedroom_features_id = master_bedroom
                        property_master_bedroom_features.save()

                # ----------------------Fireplace Type---------------------
                if "fireplace_type" in data and type(data["fireplace_type"]) == list:
                    fireplace_type = data["fireplace_type"]
                    PropertyFireplaceType.objects.filter(property=property_id).delete()
                    for fireplace in fireplace_type:
                        property_fireplace_type = PropertyFireplaceType()
                        property_fireplace_type.property_id = property_id
                        property_fireplace_type.fireplace_type_id = fireplace
                        property_fireplace_type.save()

                # ----------------------Basement Features---------------------
                if "basement_features" in data and type(data["basement_features"]) == list:
                    basement_features = data["basement_features"]
                    PropertyBasementFeatures.objects.filter(property=property_id).delete()
                    for basement in basement_features:
                        property_basement_features = PropertyBasementFeatures()
                        property_basement_features.property_id = property_id
                        property_basement_features.basement_features_id = basement
                        property_basement_features.save()

                # ----------------------Handicap Amenities---------------------
                if "handicap_amenities" in data and type(data["handicap_amenities"]) == list:
                    handicap_amenities = data["handicap_amenities"]
                    PropertyHandicapAmenities.objects.filter(property=property_id).delete()
                    for amenities in handicap_amenities:
                        property_handicap_amenities = PropertyHandicapAmenities()
                        property_handicap_amenities.property_id = property_id
                        property_handicap_amenities.handicap_amenities_id = amenities
                        property_handicap_amenities.save()

                # ----------------------Construction---------------------
                if "construction" in data and type(data["construction"]) == list:
                    construction = data["construction"]
                    PropertyConstruction.objects.filter(property=property_id).delete()
                    for cons in construction:
                        property_construction = PropertyConstruction()
                        property_construction.property_id = property_id
                        property_construction.construction_id = cons
                        property_construction.save()

                # ----------------------Garage Parking---------------------
                if "garage_parking" in data and type(data["garage_parking"]) == list:
                    garage_parking = data["garage_parking"]
                    PropertyGarageParking.objects.filter(property=property_id).delete()
                    for parking in garage_parking:
                        property_garage_parking = PropertyGarageParking()
                        property_garage_parking.property_id = property_id
                        property_garage_parking.garage_parking_id = parking
                        property_garage_parking.save()

                # ----------------------Exterior Features---------------------
                if "exterior_features" in data and type(data["exterior_features"]) == list:
                    exterior_features = data["exterior_features"]
                    PropertyExteriorFeatures.objects.filter(property=property_id).delete()
                    for exterior in exterior_features:
                        property_exterior_features = PropertyExteriorFeatures()
                        property_exterior_features.property_id = property_id
                        property_exterior_features.exterior_features_id = exterior
                        property_exterior_features.save()

                # ----------------------Garage Features---------------------
                if "garage_features" in data and type(data["garage_features"]) == list:
                    garage_features = data["garage_features"]
                    PropertyGarageFeatures.objects.filter(property=property_id).delete()
                    for garage in garage_features:
                        property_garage_features = PropertyGarageFeatures()
                        property_garage_features.property_id = property_id
                        property_garage_features.garage_features_id = garage
                        property_garage_features.save()

                # ----------------------Roof---------------------
                if "roof" in data and type(data["roof"]) == list:
                    roof = data["roof"]
                    PropertyRoof.objects.filter(property=property_id).delete()
                    for rf in roof:
                        property_roof = PropertyRoof()
                        property_roof.property_id = property_id
                        property_roof.roof_id = rf
                        property_roof.save()

                # ----------------------Outbuildings---------------------
                if "outbuildings" in data and type(data["outbuildings"]) == list:
                    outbuildings = data["outbuildings"]
                    PropertyOutbuildings.objects.filter(property=property_id).delete()
                    for buildings in outbuildings:
                        property_outbuildings = PropertyOutbuildings()
                        property_outbuildings.property_id = property_id
                        property_outbuildings.outbuildings_id = buildings
                        property_outbuildings.save()

                # ----------------------Foundation---------------------
                if "foundation" in data and type(data["foundation"]) == list:
                    foundation = data["foundation"]
                    PropertyFoundation.objects.filter(property=property_id).delete()
                    for fd in foundation:
                        property_foundation = PropertyFoundation()
                        property_foundation.property_id = property_id
                        property_foundation.foundation_id = fd
                        property_foundation.save()

                # ----------------------Location Features---------------------
                if "location_features" in data and type(data["location_features"]) == list:
                    location_features = data["location_features"]
                    PropertyLocationFeatures.objects.filter(property=property_id).delete()
                    for location in location_features:
                        property_location_features = PropertyLocationFeatures()
                        property_location_features.property_id = property_id
                        property_location_features.location_features_id = location
                        property_location_features.save()

                # ----------------------Fence---------------------
                if "fence" in data and type(data["fence"]) == list:
                    fence = data["fence"]
                    PropertyFence.objects.filter(property=property_id).delete()
                    for fnc in fence:
                        property_fence = PropertyFence()
                        property_fence.property_id = property_id
                        property_fence.fence_id = fnc
                        property_fence.save()

                # ----------------------Road Frontage---------------------
                if "road_frontage" in data and type(data["road_frontage"]) == list:
                    road_frontage = data["road_frontage"]
                    PropertyRoadFrontage.objects.filter(property=property_id).delete()
                    for frontage in road_frontage:
                        property_road_frontage = PropertyRoadFrontage()
                        property_road_frontage.property_id = property_id
                        property_road_frontage.road_frontage_id = frontage
                        property_road_frontage.save()

                # ----------------------Pool---------------------
                if "pool" in data and type(data["pool"]) == list:
                    pool = data["pool"]
                    PropertyPool.objects.filter(property=property_id).delete()
                    for pl in pool:
                        property_pool = PropertyPool()
                        property_pool.property_id = property_id
                        property_pool.pool_id = pl
                        property_pool.save()

                # ----------------------Property Faces---------------------
                if "property_faces" in data and type(data["property_faces"]) == list:
                    property_faces = data["property_faces"]
                    PropertyPropertyFaces.objects.filter(property=property_id).delete()
                    for faces in property_faces:
                        property_property_faces = PropertyPropertyFaces()
                        property_property_faces.property_id = property_id
                        property_property_faces.property_faces_id = faces
                        property_property_faces.save()

                # ----------------Commercial------------------

                # ----------------------Property Faces---------------------
                if "lease_type" in data and type(data["lease_type"]) == list:
                    lease_type = data["lease_type"]
                    PropertyLeaseType.objects.filter(property=property_id).delete()
                    for lease in lease_type:
                        property_lease_type = PropertyLeaseType()
                        property_lease_type.property_id = property_id
                        property_lease_type.lease_type_id = lease
                        property_lease_type.save()

                # ----------------------Tenant Pays---------------------
                if "tenant_pays" in data and type(data["tenant_pays"]) == list:
                    tenant_pays = data["tenant_pays"]
                    PropertyTenantPays.objects.filter(property=property_id).delete()
                    for tenant in tenant_pays:
                        property_tenant_pays = PropertyTenantPays()
                        property_tenant_pays.property_id = property_id
                        property_tenant_pays.tenant_pays_id = tenant
                        property_tenant_pays.save()

                # ----------------------Tenant Pays---------------------
                if "tenant_pays" in data and type(data["tenant_pays"]) == list:
                    tenant_pays = data["tenant_pays"]
                    PropertyTenantPays.objects.filter(property=property_id).delete()
                    for tenant in tenant_pays:
                        property_tenant_pays = PropertyTenantPays()
                        property_tenant_pays.property_id = property_id
                        property_tenant_pays.tenant_pays_id = tenant
                        property_tenant_pays.save()

                # ----------------------Inclusions---------------------
                if "inclusions" in data and type(data["inclusions"]) == list:
                    inclusions = data["inclusions"]
                    PropertyInclusions.objects.filter(property=property_id).delete()
                    for incl in inclusions:
                        property_inclusions = PropertyInclusions()
                        property_inclusions.property_id = property_id
                        property_inclusions.inclusions_id = incl
                        property_inclusions.save()

                # ----------------------Building Class---------------------
                if "building_class" in data and type(data["building_class"]) == list:
                    building_class = data["building_class"]
                    PropertyBuildingClass.objects.filter(property=property_id).delete()
                    for building in building_class:
                        property_building_class = PropertyBuildingClass()
                        property_building_class.property_id = property_id
                        property_building_class.building_class_id = building
                        property_building_class.save()

                # ----------------------Interior Features---------------------
                if "interior_features" in data and type(data["interior_features"]) == list:
                    interior_features = data["interior_features"]
                    PropertyInteriorFeatures.objects.filter(property=property_id).delete()
                    for interior in interior_features:
                        property_interior_features = PropertyInteriorFeatures()
                        property_interior_features.property_id = property_id
                        property_interior_features.interior_features_id = interior
                        property_interior_features.save()

                # ------------------Land-----------------
                # ----------------------Mineral Rights---------------------
                if "mineral_rights" in data and type(data["mineral_rights"]) == list:
                    mineral_rights = data["mineral_rights"]
                    PropertyMineralRights.objects.filter(property=property_id).delete()
                    for mineral in mineral_rights:
                        property_mineral_rights = PropertyMineralRights()
                        property_mineral_rights.property_id = property_id
                        property_mineral_rights.mineral_rights_id = mineral
                        property_mineral_rights.save()

                # ----------------------Easements---------------------
                if "easements" in data and type(data["easements"]) == list:
                    easements = data["easements"]
                    PropertyEasements.objects.filter(property=property_id).delete()
                    for eas in easements:
                        property_easements = PropertyEasements()
                        property_easements.property_id = property_id
                        property_easements.easements_id = eas
                        property_easements.save()

                # ----------------------Survey---------------------
                if "survey" in data and type(data["survey"]) == list:
                    survey = data["survey"]
                    PropertySurvey.objects.filter(property=property_id).delete()
                    for sur in survey:
                        property_survey = PropertySurvey()
                        property_survey.property_id = property_id
                        property_survey.survey_id = sur
                        property_survey.save()

                # ----------------------Utilities---------------------
                if "utilities" in data and type(data["utilities"]) == list:
                    utilities = data["utilities"]
                    PropertyUtilities.objects.filter(property=property_id).delete()
                    for uti in utilities:
                        property_utilities = PropertyUtilities()
                        property_utilities.property_id = property_id
                        property_utilities.utilities_id = uti
                        property_utilities.save()

                # ----------------------Improvements---------------------
                if "improvements" in data and type(data["improvements"]) == list:
                    improvements = data["improvements"]
                    PropertyImprovements.objects.filter(property=property_id).delete()
                    for imp in improvements:
                        property_improvements = PropertyImprovements()
                        property_improvements.property_id = property_id
                        property_improvements.improvements_id = imp
                        property_improvements.save()

                # ----------------------Topography---------------------
                if "topography" in data and type(data["topography"]) == list:
                    topography = data["topography"]
                    PropertyTopography.objects.filter(property=property_id).delete()
                    for top in topography:
                        property_topography = PropertyTopography()
                        property_topography.property_id = property_id
                        property_topography.topography_id = top
                        property_topography.save()

                # ----------------------Wildlife---------------------
                if "wildlife" in data and type(data["wildlife"]) == list:
                    wildlife = data["wildlife"]
                    PropertyWildlife.objects.filter(property=property_id).delete()
                    for wild in wildlife:
                        property_wildlife = PropertyWildlife()
                        property_wildlife.property_id = property_id
                        property_wildlife.wildlife_id = wild
                        property_wildlife.save()

                # ----------------------Fish---------------------
                if "fish" in data and type(data["fish"]) == list:
                    fish = data["fish"]
                    PropertyFish.objects.filter(property=property_id).delete()
                    for fi in fish:
                        property_fish = PropertyFish()
                        property_fish.property_id = property_id
                        property_fish.fish_id = fi
                        property_fish.save()

                # ----------------------Irrigation System---------------------
                if "irrigation_system" in data and type(data["irrigation_system"]) == list:
                    irrigation_system = data["irrigation_system"]
                    PropertyIrrigationSystem.objects.filter(property=property_id).delete()
                    for irrigation in irrigation_system:
                        property_irrigation_system = PropertyIrrigationSystem()
                        property_irrigation_system.property_id = property_id
                        property_irrigation_system.irrigation_system_id = irrigation
                        property_irrigation_system.save()

                # ----------------------Recreation---------------------
                if "recreation" in data and type(data["recreation"]) == list:
                    recreation = data["recreation"]
                    PropertyRecreation.objects.filter(property=property_id).delete()
                    for rec in recreation:
                        property_recreation = PropertyRecreation()
                        property_recreation.property_id = property_id
                        property_recreation.recreation_id = rec
                        property_recreation.save()

                # ----------------------Property opening date---------------------
                if property_asset != 1:
                    if "property_opening_dates" in data and type(data["property_opening_dates"]) == list:
                        property_opening_dates = data["property_opening_dates"]
                        PropertyOpening.objects.filter(property=property_id).delete()
                        for dates in property_opening_dates:
                            property_opening = PropertyOpening()
                            property_opening.domain_id = site_id
                            property_opening.property_id = property_id
                            property_opening.opening_start_date = dates['start_date'] if dates['start_date'] != "" else None
                            property_opening.opening_end_date = dates['end_date'] if dates['end_date'] != "" else None
                            property_opening.status_id = 1
                            property_opening.save()

                try:
                    property_listing = PropertyListing.objects.get(id=property_id)
                except:
                    pass

            elif step == 2:
                if property_id is None:
                    return Response(response.parsejson("property_id is required.", "", status=403))
                property_id = property_id.id
                if "is_map_view" in data and data["is_map_view"] != "":
                    is_map_view = data["is_map_view"]
                else:
                    return Response(response.parsejson("is_map_view is required.", "", status=403))

                if "is_street_view" in data and data["is_street_view"] != "":
                    is_street_view = data["is_street_view"]
                else:
                    return Response(response.parsejson("is_street_view is required.", "", status=403))

                if "is_arial_view" in data and data["is_arial_view"] != "":
                    is_arial_view = data["is_arial_view"]
                else:
                    return Response(response.parsejson("is_arial_view is required.", "", status=403))

                map_url = None
                if "map_url" in data and data['map_url'] != "":
                    map_url = data['map_url']
                # else:
                #     return Response(response.parsejson("map_url is required.", "", status=403))

                latitude = None
                if "latitude" in data and data['latitude'] != "":
                    latitude = data['latitude']

                longitude = None
                if "longitude" in data and data['longitude'] != "":
                    longitude = data['longitude']

                property_listing = PropertyListing.objects.get(id=property_id)
                property_listing.is_map_view = is_map_view
                property_listing.is_street_view = is_street_view
                property_listing.is_arial_view = is_arial_view
                property_listing.create_step = 2
                property_listing.map_url = map_url
                property_listing.latitude = latitude
                property_listing.longitude = longitude
                property_listing.save()
            elif step == 3:
                if property_id is None:
                    return Response(response.parsejson("property_id is required.", "", status=403))
                property_id = property_id.id
                if "property_pic" in data and type(data["property_pic"]) == list and len(data["property_pic"]) > 0:
                    property_pic = data["property_pic"]
                    PropertyUploads.objects.filter(property=property_id, upload_type=1).delete()
                    cnt = 0
                    for pic in property_pic:
                        property_uploads = PropertyUploads()
                        property_uploads.upload_id = pic
                        property_uploads.property_id = property_id
                        property_uploads.upload_type = 1
                        property_uploads.status_id = 1
                        property_uploads.photo_description = data['photo_description'][cnt] if len(data['photo_description']) and data['photo_description'][cnt] is not None and data['photo_description'][cnt] !='' else ""
                        property_uploads.save()
                        cnt +=1

                if "property_video" in data and type(data["property_video"]) == list and len(data["property_video"]) > 0:
                    property_video = data["property_video"]
                    PropertyUploads.objects.filter(property=property_id, upload_type=2).delete()
                    for video in property_video:
                        property_uploads = PropertyUploads()
                        property_uploads.upload_id = video
                        property_uploads.property_id = property_id
                        property_uploads.upload_type = 2
                        property_uploads.status_id = 1
                        property_uploads.save()

                property_listing = PropertyListing.objects.get(id=property_id)
                property_listing.create_step = 3
                property_listing.save()
            elif step == 4:
                if property_id is None:
                    return Response(response.parsejson("property_id is required.", "", status=403))
                property_id = property_id.id
                if "property_documents" in data and type(data["property_documents"]) == list and len(data["property_documents"]) > 0:
                    property_documents = data["property_documents"]
                    PropertyUploads.objects.filter(property=property_id, upload_type=3).delete()
                    for documents in property_documents:
                        property_uploads = PropertyUploads()
                        property_uploads.upload_id = documents
                        property_uploads.property_id = property_id
                        property_uploads.upload_type = 3
                        property_uploads.status_id = 1
                        property_uploads.save()

                property_listing = PropertyListing.objects.get(id=property_id)
                property_listing.create_step = 4
                property_listing.save()
            property_auction_data = PropertyAuction.objects.filter(property=property_id).last()
            all_data = {"property_id": property_id, "auction_id": property_auction_data.id, "auction_type": property_auction_data.auction_id}
            # ----------------------------Email----------------------------------------
            if check_update is None:
                property_detail = property_listing
                user_detail = property_listing.agent
                property_user_name = user_detail.first_name
                agent_email = user_detail.email
                agent_phone = user_detail.phone_no if user_detail.phone_no is not None else ""
                auction_type = property_detail.sale_by_type.auction_type
                auction_data = PropertyAuction.objects.get(property=property_id)
                start_price = auction_data.start_price
                upload = PropertyUploads.objects.filter(property=property_id, upload_type=1).first()
                web_url = settings.FRONT_BASE_URL
                image_url = web_url+'/static/admin/images/property-default-img.png'
                if upload is not None:
                    image = upload.upload.doc_file_name
                    bucket_name = upload.upload.bucket_name
                    image_url = 'https://realtyonegroup.s3.us-west-1.amazonaws.com/'+str(bucket_name)+'/'+str(image)
                subdomain_url = settings.SUBDOMAIN_URL
                domain_name = network.domain_name
                domain_url = subdomain_url.replace("###", domain_name)+"admin/listing/"
                notif_type = 2
                if property_detail.sale_by_type_id == 7:
                    domain_url = domain_url + "?auction_type=highest%20offer"
                    notif_type =  6
                elif property_detail.sale_by_type_id == 4:
                    domain_url = domain_url + "?auction_type=traditional%20offer"
                    notif_type =  4
                elif property_detail.sale_by_type_id == 6:
                    domain_url = domain_url + "?auction_type=live%20offer"
                    notif_type =  7
                elif property_detail.sale_by_type_id == 2:
                    domain_url = domain_url + "?auction_type=insider%20auction"
                    notif_type =  8
                property_address = property_detail.address_one
                property_city = property_detail.city
                property_state = property_detail.state.state_name
                asset_type = property_detail.property_asset.name
                template_data = {"domain_id": site_id, "slug": "add_listing"}
                extra_data = {
                    'property_user_name': property_user_name,
                    'web_url': web_url,
                    'property_image': image_url,
                    'property_address': property_address,
                    'property_city': property_city,
                    'property_state': property_state,
                    'auction_type': auction_type,
                    'asset_type': asset_type,
                    'starting_price': "$" + str(number_format(start_price)) if not auction_data.un_priced else 'Unpriced',
                    'starting_bid_offer': 'Starting Bid' if property_detail.sale_by_type_id in [1, 6] else "Asking Price",
                    'dashboard_link': domain_url,
                    "domain_id": site_id
                }
                compose_email(to_email=[agent_email], template_data=template_data, extra_data=extra_data)
                # =============send email to broker==============
                broker_detail = Users.objects.get(site_id=site_id)
                broker_name = broker_detail.first_name if broker_detail.first_name is not None else ""
                broker_email = broker_detail.email if broker_detail.email is not None else ""
                if broker_email.lower() != agent_email.lower():
                    try:
                        #send email to broker
                        template_data = {"domain_id": site_id, "slug": "add_listing_broker"}
                        extra_data = {
                            'property_user_name': broker_name,
                            'web_url': web_url,
                            'property_image': image_url,
                            'property_address': property_address,
                            'property_city': property_city,
                            'property_state': property_state,
                            'auction_type': auction_type,
                            'asset_type': asset_type,
                            'starting_price': "$" + str(number_format(start_price)) if not auction_data.un_priced else 'Unpriced',
                            'starting_bid_offer': 'Starting Bid' if property_detail.sale_by_type_id in [1, 6] else "Asking Price",
                            'dashboard_link': domain_url,
                            "domain_id": site_id,
                            'domain_name': domain_name,
                            'agent_name': property_user_name,
                            'agent_email': agent_email,
                            'agent_phone': phone_format(agent_phone)
                        }
                        compose_email(to_email=[broker_email], template_data=template_data, extra_data=extra_data)
                        # --------Approval Pending Email To Broker--------
                        template_data = {"domain_id": site_id, "slug": "approval_pending"}
                        compose_email(to_email=[broker_email], template_data=template_data, extra_data=extra_data)
                    except Exception as e:
                        pass
                    
                try:
                    prop_name = property_detail.address_one if property_detail.address_one else str(property_detail.id)
                    # check if domain owner/broker is adding
                    if broker_detail.id != user_id:
                        # send notif to broker person to review
                        content = "A new listing is created for review! <span>[" + prop_name + "]</span>"
                        add_notification(
                            site_id,
                            "Create Listing",
                            content,
                            user_id=broker_detail.id,
                            added_by=broker_detail.id,
                            notification_for=2,
                            property_id=property_id,
                            notification_type=notif_type
                        )
                        #  add notif to agent
                        content = "Your listing is submitted for review! <span>[" + prop_name + "]</span>"
                        add_notification(
                            site_id,
                            "Create Listing",
                            content,
                            user_id=user_id,
                            added_by=user_id,
                            notification_for=2,
                            property_id=property_id,
                            notification_type=notif_type
                        )
                    else:
                        # send notif to broker person to review
                        content = "You have created a new listing! <span>[" + prop_name + "]</span>"
                        add_notification(
                            site_id,
                            "Create Listing",
                            content,
                            user_id=broker_detail.id,
                            added_by=broker_detail.id,
                            notification_for=2,
                            property_id=property_id,
                            notification_type=notif_type
                        )
                except Exception as e:
                    pass
            else:
                if listing_update_email:
                    property_detail = property_listing
                    web_url = settings.FRONT_BASE_URL
                    image_url = web_url+'/static/admin/images/property-default-img.png'
                    property_address = property_detail.address_one
                    property_city = property_detail.city
                    property_state = property_detail.state.state_name
                    auction_type = property_detail.sale_by_type.auction_type
                    asset_type = property_detail.property_asset.name
                    user_detail = property_listing.agent
                    property_user_name = user_detail.first_name
                    agent_email = user_detail.email
                    agent_phone = user_detail.phone_no if user_detail.phone_no is not None else ""
                    auction_data = PropertyAuction.objects.get(property=property_id)
                    start_price = auction_data.start_price
                    subdomain_url = settings.SUBDOMAIN_URL
                    domain_name = network.domain_name
                    # domain_url = subdomain_url.replace("###", domain_name)+"admin/listing/"
                    domain_url = subdomain_url.replace("###", domain_name)+"asset-details/?property_id="+str(property_id)
                    # print(domain_url)
                    extra_data = {
                            'web_url': web_url,
                            'property_image': image_url,
                            'property_address': property_address,
                            'property_city': property_city,
                            'property_state': property_state,
                            'auction_type': auction_type,
                            'asset_type': asset_type,
                            'starting_price': "$" + str(number_format(start_price)) if not auction_data.un_priced else 'Unpriced',
                            'starting_bid_offer': 'Starting Bid' if property_detail.sale_by_type_id in [1, 6] else "Asking Price",
                            'dashboard_link': domain_url,
                            "domain_id": site_id,
                            'domain_name': domain_name,
                            'agent_name': property_user_name,
                            'agent_email': agent_email,
                            'agent_phone': phone_format(agent_phone)
                        }
                    # ----------Email Registered Bidder---------  
                    registered_bidder = BidRegistration.objects.filter(property=property_id, status=1)
                    if registered_bidder is not None and len(registered_bidder):
                        for bidder in registered_bidder:
                            email = bidder.user.email
                            extra_data['property_user_name'] = bidder.user.first_name
                            template_data = {"domain_id": site_id, "slug": "changes_in_property"}
                            compose_email(to_email=[bidder.user.email], template_data=template_data, extra_data=extra_data)
                            content = "Property attributes have been updated, visit the property to view the updates"
                            try:
                                broker_detail = Users.objects.get(site_id=site_id)
                                add_notification(
                                    site_id,
                                    "Update in property",
                                    content,
                                    user_id=bidder.user_id,
                                    added_by=broker_detail.id,
                                    notification_for=1,
                                    property_id=property_id,
                                    notification_type=1
                                )
                            except Exception as exp:
                                pass 
                    
                    # --------Email to favourite user--------                
                    favourite_property = FavouriteProperty.objects.filter(property=property_id)
                    if favourite_property is not None and len(favourite_property):
                        for bidder in favourite_property:
                            email = bidder.user.email
                            extra_data['property_user_name'] = bidder.user.first_name
                            template_data = {"domain_id": site_id, "slug": "changes_in_property"}
                            compose_email(to_email=[bidder.user.email], template_data=template_data, extra_data=extra_data)
                            content = "Property attributes have been updated, visit the property to view the updates"
                            try:
                                broker_detail = Users.objects.get(site_id=site_id)
                                add_notification(
                                    site_id,
                                    "Update in property",
                                    content,
                                    user_id=bidder.user_id,
                                    added_by=broker_detail.id,
                                    notification_for=1,
                                    property_id=property_id,
                                    notification_type=1
                                )
                            except Exception as exp:
                                pass        

            return Response(response.parsejson("Property added/updated successfully.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AddPropertySellerApiView(APIView):
    """
    Seller Add/Update Property
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            source = None
            if "source" in data and data['source'] != "":
                source = data['source'].lower()

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
                data['domain'] = site_id
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            property_id = None
            check_update = None
            if "property_id" in data and data['property_id'] != "" and data["property_id"] is not None:
                property_id = int(data['property_id'])
                check_update = True
                property_id = PropertyListing.objects.filter(id=property_id, domain=site_id).first()
                if property_id is None:
                    return Response(response.parsejson("Property not exist.", "", status=403))
            if "step" in data and data['step'] != "":
                step = int(data['step'])
            else:
                return Response(response.parsejson("step is required.", "", status=403))
            user_domain = None
            creater_user_type = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, status=1).first()
                if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))

                network_user = NetworkUser.objects.filter(user=user_id, status=1, user__status=1).first()
                if network_user is None:
                    data["developer"] = user_id
                else:
                    data["developer"] = network_user.developer_id if network_user.developer_id is not None else user_id

                if property_id is not None:
                    user_id = property_id.agent_id
                    data["developer"] = property_id.developer_id

                data["agent"] = user_id
                user_domain = users.site_id
                creater_user_type = users.user_type_id
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            # --- Verify that user_id matches the token user ---
            auth_user = request.user  # user from Bearer token
            if int(user_id) != auth_user.id:
                return Response(response.parsejson("Permission denied.", "", status=403))     

            if step == 1:
                if "property_name" in data and data['property_name'] != "":
                    property_name = data['property_name']
                else:
                    return Response(response.parsejson("property_name is required.", "", status=403))
                
                if "property_name_ar" in data and data['property_name_ar'] != "":
                    property_name_ar = data['property_name_ar']
                else:
                    return Response(response.parsejson("property_name is required.", "", status=403))
                
                if "country" in data and data['country'] != "":
                    data['country'] = data['country']
                else:
                    return Response(response.parsejson("country is required.", "", status=403))

                if "city" in data and data['city'] != "":
                    data['state'] = int(data['city'])
                else:
                    return Response(response.parsejson("city is required.", "", status=403))

                if "municipality" in data and data['municipality'] != "":
                    data['municipality'] = int(data['municipality'])
                else:
                    return Response(response.parsejson("municipality is required.", "", status=403))

                if "district" in data and data['district'] != "":
                    data['district'] = int(data['district'])
                else:
                    return Response(response.parsejson("district is required.", "", status=403))

                if "project" in data and data['project'] is not None:
                    data['project'] = int(data['project'])

                if "community" in data and data['community'] != "":
                    data['community'] = data['community']
                else:
                    return Response(response.parsejson("community is required.", "", status=403))

                if "building" in data and data['building'] != "":
                    data['building'] = data['building']
                else:
                    return Response(response.parsejson("building is required.", "", status=403))

                if "map_url" in data and data['map_url'] != "":
                    data['map_url'] = data['map_url']
                else:
                    return Response(response.parsejson("map_url is required.", "", status=403))

                if "propertyType" in data and data['propertyType'] != "":
                    data['property_type'] = int(data['propertyType'])
                else:
                    return Response(response.parsejson("property_type is required.", "", status=403))
                if source is None:
                    if "owners" in data and type(data['owners']) == list and len(data['owners']) > 0:
                        owners = data['owners']
                    else:
                        return Response(response.parsejson("owners is required.", "", status=403))
                else:
                    if "owners" in data and isinstance(data['owners'], dict) and len(data['owners']) > 0:
                        owners = list(data["owners"].values())  # Convert dictionary values to a list
                    else:
                        return Response(response.parsejson("owners is required.", "", status=403))    

                if "areaSize" in data and data["areaSize"] != "":
                    data["square_footage"] = data["areaSize"]
                else:
                    return Response(response.parsejson("areaSize is required.", "", status=403))

                if "numOfBedrooms" in data and data["numOfBedrooms"] != "":
                    data["beds"] = data["numOfBedrooms"]
                else:
                    return Response(response.parsejson("numOfBedrooms is required.", "", status=403))

                if "numOfBathrooms" in data and data["numOfBathrooms"] != "":
                    data["baths"] = data["numOfBathrooms"]
                else:
                    return Response(response.parsejson("numOfBathrooms is required.", "", status=403))

                if "numOfParkings" in data and data["numOfParkings"] != "":
                    data["number_of_outdoor_parking_spaces"] = data["numOfParkings"]
                else:
                    return Response(response.parsejson("numOfParkings is required.", "", status=403))

                data["rental_till"] = None
                if "vacancy" in data and int(data["vacancy"]) in [1, 2]:
                    vacancy = int(data['vacancy'])
                    if vacancy == 1:
                        if "rentalTill" in data and data['rentalTill'] != "":
                            data["rental_till"] = data['rentalTill']
                        else:
                            return Response(response.parsejson("rentalTill is required.", "", status=403))
                else:
                    return Response(response.parsejson("vacancy is required.", "", status=403))

                if "constructionStatus" in data and data["constructionStatus"] != "":
                    data["construction_status"] = data['constructionStatus']
                else:
                    return Response(response.parsejson("constructionStatus is required.", "", status=403))

                if "description" in data and data["description"] != "":
                    description = data['description']
                else:
                    return Response(response.parsejson("description is required.", "", status=403))

                if "description_ar" in data and data["description_ar"] != "":
                    description_ar = data['description_ar']
                else:
                    return Response(response.parsejson("description_ar is required.", "", status=403))    

                if "status" in data and data['status'] != "":
                    data['status'] = int(data['status'])
                else:
                    data['status'] = 1

                if "seller_status" in data and data['seller_status'] != "":
                    data['seller_status'] = int(data['seller_status'])
                else:
                    data['seller_status'] = 24

                data["create_step"] = 1
                data["title"] = "testing"
                if user_domain == site_id or int(creater_user_type) == 2:
                    data['is_approved'] = 1
                serializer = AddPropertySerializer(property_id, data=data)
                if serializer.is_valid():
                    property_id = serializer.save()
                    property_id = property_id.id
                else:
                    copy_errors = serializer.errors.copy()
                    return Response(response.parsejson(copy_errors, "", status=403))
                # ----------------------Owners---------------------
                if source is None:
                    if "owners" in data and type(data["owners"]) == list:
                        owners = data["owners"]
                        PropertyOwners.objects.filter(property=property_id).delete()
                        for owner in owners:
                            property_owners = PropertyOwners()
                            property_owners.property_id = property_id
                            property_owners.name = owner["ownerName"]
                            property_owners.eid = owner["eid"]
                            property_owners.passport = owner.get("passport") or None
                            property_owners.share_percentage = owner["sharePercentage"]
                            # property_owners.nationality = owner["nationality"]
                            property_owners.owner_nationality_id = owner["nationality"]
                            property_owners.dob = owner["dob"]
                            property_owners.phone = owner["phone"]
                            property_owners.email = owner["email"]
                            property_owners.useEID = owner["useEID"]
                            property_owners.save()
                else:
                    if "owners" in data and isinstance(data['owners'], dict) and len(data['owners']) > 0:
                        owners = list(data["owners"].values())
                        PropertyOwners.objects.filter(property=property_id).delete()
                        for owner in owners:
                            property_owners = PropertyOwners()
                            property_owners.property_id = property_id
                            property_owners.name = owner["ownerName"]
                            property_owners.eid = owner["eid"]
                            property_owners.passport = owner.get("passport") or None
                            property_owners.share_percentage = owner["sharePercentage"]
                            property_owners.owner_nationality_id = owner["nationality"]
                            property_owners.dob = owner["dob"]
                            property_owners.phone = owner["phone"]
                            property_owners.email = owner["email"]
                            property_owners.useEID = owner["useEID"]
                            property_owners.save()
                
                if source is None:
                    if "amenities" in data and type(data["amenities"]) == list:
                        amenities = data["amenities"]
                        PropertyAmenity.objects.filter(property=property_id).delete()
                        for amenity in amenities:
                            property_amenities = PropertyAmenity()
                            property_amenities.property_id = property_id
                            property_amenities.amenities_id = amenity["value"]
                            property_amenities.save()
                else:
                    if "amenities" in data and isinstance(data['amenities'], dict) and len(data['amenities']) > 0:
                        # amenities = data["amenities"]
                        amenities = list(data["amenities"].values())
                        PropertyAmenity.objects.filter(property=property_id).delete()
                        for amenity in amenities:
                            property_amenities = PropertyAmenity()
                            property_amenities.property_id = property_id
                            property_amenities.amenities_id = amenity["value"]
                            property_amenities.save()           
                if source is None:
                    if "tags" in data and type(data["tags"]) == list and len(data["tags"]) > 0:
                        tags = data["tags"]
                        PropertyTags.objects.filter(property=property_id).delete()
                        for tag in tags:
                            property_tag = PropertyTags()
                            property_tag.property_id = property_id
                            property_tag.tags_id = tag["value"]
                            property_tag.save()
                    else:
                        PropertyTags.objects.filter(property=property_id).delete()       
                else:            
                    if "tags" in data and isinstance(data['tags'], dict) and len(data['tags']) > 0:
                        # tags = data["tags"]
                        tags = list(data["tags"].values())
                        PropertyTags.objects.filter(property=property_id).delete()
                        for tag in tags:
                            property_tag = PropertyTags()
                            property_tag.property_id = property_id
                            property_tag.tags_id = tag["value"]
                            property_tag.save()
                    else:
                        PropertyTags.objects.filter(property=property_id).delete()       
                if source is None:
                    if "property_pic" in data and type(data["property_pic"]) == list:
                        property_pic = data["property_pic"]
                        PropertyUploads.objects.filter(property=property_id, upload_type=1).delete()
                        cnt = 0
                        for pic in property_pic:
                            property_uploads = PropertyUploads()
                            property_uploads.upload_id = pic["upload_id"]
                            property_uploads.property_id = property_id
                            property_uploads.upload_type = 1
                            property_uploads.status_id = 1
                            property_uploads.upload_identifier = pic["upload_identifier"]
                            property_uploads.save()
                            cnt +=1
                else:
                     if "property_pic" in data and isinstance(data['property_pic'], dict) and len(data['property_pic']) > 0:
                        # property_pic = data["property_pic"]
                        property_pic = list(data["property_pic"].values())
                        PropertyUploads.objects.filter(property=property_id, upload_type=1).delete()
                        cnt = 0
                        for pic in property_pic:
                            property_uploads = PropertyUploads()
                            property_uploads.upload_id = pic["upload_id"]
                            property_uploads.property_id = property_id
                            property_uploads.upload_type = 1
                            property_uploads.status_id = 1
                            property_uploads.upload_identifier = pic["upload_identifier"]
                            property_uploads.save()
                            cnt +=1           
                if source is None:
                    if "property_video" in data and type(data["property_video"]) == list:
                        property_video = data["property_video"]
                        PropertyUploads.objects.filter(property=property_id, upload_type=2).delete()
                        for video in property_video:
                            property_uploads = PropertyUploads()
                            property_uploads.upload_id = video["upload_id"]
                            property_uploads.property_id = property_id
                            property_uploads.upload_type = 2
                            property_uploads.upload_identifier = video["upload_identifier"]
                            property_uploads.status_id = 1
                            property_uploads.save()
                else:
                    if "property_video" in data and isinstance(data['property_video'], dict) and len(data['property_video']) > 0:
                        # property_video = data["property_video"]
                        property_video = list(data["property_video"].values())
                        PropertyUploads.objects.filter(property=property_id, upload_type=2).delete()
                        for video in property_video:
                            property_uploads = PropertyUploads()
                            property_uploads.upload_id = video["upload_id"]
                            property_uploads.property_id = property_id
                            property_uploads.upload_type = 2
                            property_uploads.upload_identifier = video["upload_identifier"]
                            property_uploads.status_id = 1
                            property_uploads.save()          

                if source is None:
                    if "property_documents" in data and type(data["property_documents"]) == list and len(data["property_documents"]) > 0:
                        property_documents = data["property_documents"]
                        PropertyUploads.objects.filter(property=property_id, upload_type=3).delete()
                        for documents in property_documents:
                            if not isinstance(documents, dict):
                                continue
                            property_uploads = PropertyUploads()
                            property_uploads.upload_id = documents.get("upload_id")
                            property_uploads.property_id = property_id
                            property_uploads.upload_type = 3
                            property_uploads.upload_identifier = documents.get("upload_identifier")
                            property_uploads.status_id = 1
                            property_uploads.save()
                else:
                    if "property_documents" in data and isinstance(data['property_documents'], dict) and len(data['property_documents']) > 0:
                        # property_documents = data["property_documents"]
                        property_documents = list(data["property_documents"].values())
                        PropertyUploads.objects.filter(property=property_id, upload_type=3).delete()
                        for documents in property_documents:
                            if not isinstance(documents, dict):
                                continue
                            property_uploads = PropertyUploads()
                            property_uploads.upload_id = documents.get("upload_id")
                            property_uploads.property_id = property_id
                            property_uploads.upload_type = 3
                            property_uploads.upload_identifier = documents.get("upload_identifier")
                            property_uploads.status_id = 1
                            property_uploads.save()            
            elif step == 2:
                if property_id is None:
                    return Response(response.parsejson("property_id is required.", "", status=403))
                property_id = property_id.id

                is_reopen = False
                if "is_reopen" in data and data['is_reopen']:
                    is_reopen = True

                if "reservation_agreement_accepted" in data and data['reservation_agreement_accepted'] == 1:
                    reservation_agreement_accepted = data['reservation_agreement_accepted']
                else:
                    return Response(response.parsejson("reservation_agreement_accepted is required.", "", status=403))

                if "reservation_agreement_sign" in data and data['reservation_agreement_sign'] != "":
                    reservation_agreement_sign = data['reservation_agreement_sign']
                else:
                    return Response(response.parsejson("reservation_agreement_sign is required.", "", status=403))

                # if "sale_by_type" in data and data['sale_by_type'] != "":
                #     sale_by_type = data['sale_by_type']
                # else:
                #     return Response(response.parsejson("sale_by_type is required.", "", status=403))

                if "start_time" in data and data['start_time'] != "":
                    start_time = data['start_time']
                else:
                    return Response(response.parsejson("start_time is required.", "", status=403))

                if "end_time" in data and data['end_time'] != "":
                    end_time = data['end_time']
                else:
                    return Response(response.parsejson("end_time is required.", "", status=403))

                if "start_date" in data and data["start_date"] != "":
                    data["start_date"] = f'{data["start_date"]}'
                else:
                    return Response(response.parsejson("start_date is required.", "", status=403))

                if "end_date" in data and data["end_date"] != "":
                    data["end_date"] = f'{data["end_date"]}'
                else:
                    return Response(response.parsejson("end_date is required.", "", status=403))

                bid_increments = None
                if "bid_increment_status" in data and data["bid_increment_status"] in [0, 1]:
                    bid_increment_status = data['bid_increment_status']
                    if bid_increment_status == 1 :
                        if "bid_increments" in data and data['bid_increments'] != "":
                            bid_increments = data['bid_increments']
                        else:
                            return Response(response.parsejson("bid_increments is required.", "", status=403))
                else:
                    return Response(response.parsejson("bid_increment_status is not valid.", "", status=403))

                full_amount = None
                if "sell_at_full_amount_status" in data and data["sell_at_full_amount_status"] in [0, 1]:
                    sell_at_full_amount_status = data['sell_at_full_amount_status']
                    if sell_at_full_amount_status == 1:
                        if "full_amount" in data and data['full_amount'] != "":
                            full_amount = data['full_amount']
                        else:
                            return Response(response.parsejson("full_amount is required.", "", status=403))
                else:
                    return Response(response.parsejson("bid_increment_status is required.", "", status=403))

                if "start_price" in data and data['start_price'] != "":
                    start_price = data['start_price']
                else:
                    return Response(response.parsejson("start_price is required.", "", status=403))

                if "deposit_amount" in data and data['deposit_amount'] != "":
                    deposit_amount = data['deposit_amount']
                else:
                    return Response(response.parsejson("deposit_amount is required.", "", status=403))

                if "is_featured" in data and data['is_featured'] != "" and data["is_featured"] in [0, 1]:
                    is_featured = data['is_featured']
                else:
                    return Response(response.parsejson("is_featured is required.", "", status=403))

                if "buyer_preference" in data and data['buyer_preference'] != "" and data["buyer_preference"] in [1, 2, 3]:
                    buyer_preference = data['buyer_preference']
                else:
                    return Response(response.parsejson("buyer_preference is required.", "", status=403))

                if "reserve_amount" in data and data['reserve_amount'] != "":
                    reserve_amount = data['reserve_amount']
                    if float(start_price) > float(reserve_amount):
                        return Response(response.parsejson("reserve_amount should be greater than start_price.", "", status=403))
                else:
                    return Response(response.parsejson("reserve_amount is required.", "", status=403))

                property_auction = PropertyAuction.objects.filter(property=property_id).first()
                if property_auction is None:
                    property_auction = PropertyAuction()
                    property_auction.property_id = property_id
                    property_auction.auction_unique_id = unique_registration_id()
                    property_auction_status = 1
                else: 
                    property_auction_status = property_auction.status_id

                property_auction.start_date = data["start_date"]
                property_auction.end_date = data["end_date"]
                property_auction.bid_increment_status = bid_increment_status
                property_auction.bid_increments = bid_increments
                property_auction.reserve_amount = reserve_amount
                property_auction.time_zone_id = 575
                property_auction.start_price = start_price
                property_auction.status_id = 1 #data['auction_status'] if data['auction_status'] is not None else 1
                property_auction.auction_id = 1 #sale_by_type
                property_auction.domain_id = site_id
                property_auction.buyer_preference = buyer_preference
                property_auction.sell_at_full_amount_status = sell_at_full_amount_status
                property_auction.full_amount = full_amount
                property_auction.save()

                property_listing = PropertyListing.objects.get(id=property_id)
                property_listing.deposit_amount = deposit_amount
                property_listing.is_featured = is_featured
                property_listing.seller_status_id = 27
                if is_reopen:
                    property_listing.status_id = 1
                property_listing.create_step = 4
                
                if property_auction_status != 1:
                    pass
                    # property_listing.status_id = 1
                    # property_listing.winner = None
                    # property_listing.sold_price = 0
                    # property_listing.date_sold = None
                property_listing.save()


                reservation_agreement = PropertyReservationAgreement.objects.filter(property=property_id).first()
                if reservation_agreement is None:
                    reservation_agreement = PropertyReservationAgreement()
                reservation_agreement.property_id = property_id
                reservation_agreement.seller_id = user_id
                reservation_agreement.signature = reservation_agreement_sign
                reservation_agreement.reservation_agreement_accepted = reservation_agreement_accepted
                reservation_agreement.save()
            # --------------Email & Notification-----------  
            try:
                # --------------Email-----------
                property_detail = PropertyListing.objects.filter(id=property_id).first()
                user_detail = property_detail.agent
                property_user_name = user_detail.first_name
                agent_email = user_detail.email
                agent_phone = user_detail.phone_no if user_detail.phone_no is not None else ""
                phone_country_code = user_detail.phone_country_code if user_detail.phone_country_code is not None else ""
                upload = PropertyUploads.objects.filter(property=property_id, upload_type=1).first()
                web_url = network.domain_url
                image_url = network.domain_url+'static/images/property-default-img.png'
                if upload is not None:
                    image = upload.upload.doc_file_name
                    bucket_name = upload.upload.bucket_name
                    image_url = settings.AZURE_BLOB_URL + str(bucket_name)+ '/' +str(image)

                property_state = property_detail.state.state_name
                property_type = property_detail.property_type.property_type
                property_name = property_detail.property_name
                property_name_ar = property_detail.property_name_ar
                community = property_detail.community    
                if int(step) == 1:
                    decorator_url = property_detail.property_name.lower() + " " + property_detail.country.country_name.lower()
                    decorator_url = re.sub(r"\s+", '-', decorator_url)
                    domain_url = network.domain_react_url+"seller/property/detail/"+str(property_id)+"/"+decorator_url
                    # -------------Email send to Agent-----------
                    template_data = {"domain_id": site_id, "slug": "add_listing"}
                    extra_data = {
                        'property_user_name': property_user_name,
                        'web_url': web_url,
                        'property_image': image_url,
                        'property_state': property_state,
                        'property_type': property_type,
                        'property_name': property_name,
                        'community': community,
                        'dashboard_link': domain_url,
                        "domain_id": site_id
                    }
                    compose_email(to_email=[agent_email], template_data=template_data, extra_data=extra_data)
                    # -------------Send email to super admin--------------
                    domain_url = network.domain_url+"admin/listing/"
                    broker_detail = Users.objects.get(site_id=site_id)
                    broker_name = broker_detail.first_name if broker_detail.first_name is not None else ""
                    broker_email = broker_detail.email if broker_detail.email is not None else ""
                    if broker_email.lower() != agent_email.lower() or True:
                        template_data = {"domain_id": site_id, "slug": "add_listing_broker"}
                        extra_data = {
                            'property_user_name': broker_name,
                            'web_url': web_url,
                            'property_image': image_url,
                            'property_state': property_state,
                            'property_type': property_type,
                            'property_name': property_name,
                            'community': community,
                            'dashboard_link': domain_url,
                            "domain_id": site_id,
                            'agent_name': property_user_name,
                            'agent_email': agent_email,
                            'agent_phone': phone_format_new(agent_phone, phone_country_code)
                        }
                        compose_email(to_email=[broker_email], template_data=template_data, extra_data=extra_data)
                        # --------Approval Pending Email To Super Admin--------
                        template_data = {"domain_id": site_id, "slug": "approval_pending"}
                        compose_email(to_email=[broker_email], template_data=template_data, extra_data=extra_data)
                
                    # ------------------Notifications-------------
                    prop_name = property_detail.property_name
                    prop_name_ar = property_detail.property_name_ar
                    #  -----------Add notification for seller-----------
                    decorator_url = property_detail.property_name.lower() + " " + property_detail.country.country_name.lower()
                    decorator_url = re.sub(r"\s+", '-', decorator_url)
                    redirect_url = network.domain_react_url+"seller/property/detail/"+str(property_id)+"/"+decorator_url
                    notification_extra_data = {'image_name': 'review.svg', 'property_name': prop_name, 'property_name_ar': prop_name_ar, 'redirect_url': redirect_url}
                    notification_extra_data['app_content'] = 'Your property <b>'+prop_name+'</b> is submitted for <b>review</b>.'
                    notification_extra_data['app_content_ar'] = 'ممتلكاتك '+prop_name_ar+' تم تقديمه للمراجعة'
                    notification_extra_data['app_screen_type'] = 6
                    notification_extra_data['app_notification_image'] = 'review.png'
                    notification_extra_data['property_id'] = property_id
                    notification_extra_data['app_notification_button_text'] = 'View Details'
                    notification_extra_data['app_notification_button_text_ar'] = 'عرض التفاصيل'
                    template_slug = "add_listing"
                    # content = '<div class="icon orange-bg"><img src="img/review.svg" alt="Reload Icon"></div><div class="text"><h6>Your property "'+prop_name+'" is submitted for review!</h6><a class="btn btn-sky btn-xs" href="'+redirect_url+'">View</a></div>'
                    add_notification(
                        site_id,
                        user_id=user_id,
                        added_by=user_id,
                        notification_for=1,
                        template_slug=template_slug,
                        extra_data=notification_extra_data
                    )

                    # ------------Add notification for superadmin--------
                    redirect_url = network.domain_url+"admin/listing/"
                    notification_extra_data = {'image_name': 'review.svg', 'property_name': prop_name, 'property_name_ar': prop_name_ar, 'redirect_url': redirect_url}
                    notification_extra_data['app_content'] = 'A new property <b>'+prop_name+'</b> is created for <b>review</b>!'
                    notification_extra_data['app_content_ar'] = 'عقار جديد '+prop_name_ar+' تم إنشاؤه للمراجعة!'
                    notification_extra_data['app_screen_type'] = 7
                    notification_extra_data['app_notification_image'] = 'review.png'
                    notification_extra_data['property_id'] = property_id
                    notification_extra_data['app_notification_button_text'] = 'View Details'
                    notification_extra_data['app_notification_button_text_ar'] = 'عرض التفاصيل'
                    template_slug = "approval_pending"
                    # content ='<div class="icon orange-bg"><img src="img/review.svg" alt="Reload Icon"></div><div class="text"><h6>A new property "'+prop_name+'" is created for review!</h6><a class="btn btn-sky btn-xs" href="'+redirect_url+'">View</a></div>'
                    add_notification(
                        site_id,
                        user_id=broker_detail.id,
                        added_by=broker_detail.id,
                        notification_for=1,
                        template_slug=template_slug,
                        extra_data=notification_extra_data
                    ) 
                elif int(step) == 2:
                    decorator_url = property_detail.property_name.lower() + " " + property_detail.country.country_name.lower()
                    decorator_url = re.sub(r"\s+", '-', decorator_url)
                    domain_url = network.domain_react_url+"property/detail/"+str(property_id)+"/"+decorator_url
                    # -------------Email send to Agent-----------
                    template_data = {"domain_id": site_id, "slug": "on_auction"}
                    extra_data = {
                        'property_user_name': property_user_name,
                        'web_url': web_url,
                        'property_image': image_url,
                        'property_state': property_state,
                        'property_type': property_type,
                        'property_name': property_name,
                        'community': community,
                        'dashboard_link': domain_url,
                        "domain_id": site_id
                    }
                    compose_email(to_email=[agent_email], template_data=template_data, extra_data=extra_data)

                    #  -----------Add notification for seller-----------
                    notification_extra_data = {'image_name': 'success.svg', 'property_name': property_name, 'property_name_ar': property_name_ar, 'redirect_url': domain_url}
                    notification_extra_data['app_content'] = 'Your property <b>'+property_name+'</b> is <b>on auction</b>.'
                    notification_extra_data['app_content_ar'] = 'ممتلكاتك '+property_name_ar+' معروض في المزاد'
                    notification_extra_data['app_screen_type'] = 1
                    notification_extra_data['app_notification_image'] = 'success.png'
                    notification_extra_data['property_id'] = property_id
                    notification_extra_data['app_notification_button_text'] = 'View Details'
                    notification_extra_data['app_notification_button_text_ar'] = 'عرض التفاصيل'
                    template_slug = "on_auction"
                    add_notification(
                        site_id,
                        user_id=user_id,
                        added_by=user_id,
                        notification_for=1,
                        template_slug=template_slug,
                        extra_data=notification_extra_data
                    )
            except Exception as exp:
                pass
            all_data = {"property_id": property_id}
            return Response(response.parsejson("Property added/updated successfully.", all_data, status=201))
        except Exception as exp:
            print(exp);
            return Response(response.parsejson(str(exp), exp, status=403))


class AssetListingApiView(APIView):
    """
    Asset Listing
    """
    authentication_classes = [TokenAuthentication, OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            all_data = get_cache("property_asset")
            if all_data is None:
                data = request.data
                ids = [3, 2, 1, 6, 5, 4]
                # all_data = LookupPropertyAsset.objects.filter(is_active=1).order_by("-id").values("id", "name")
                all_data = LookupPropertyAsset.objects.filter(is_active=1, id__in=ids).values("id", "name")
                all_data = sorted(all_data, key=lambda x: ids.index(x["id"]))
                set_cache("property_asset", all_data)

            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyTypeListingApiView(APIView):
    """
    Property type Listing
    """
    authentication_classes = [TokenAuthentication,OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_type"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupPropertyType.objects.filter(is_active=1)
                if asset_id is not None:
                    all_data = all_data.filter(asset=asset_id)
                all_data = all_data.order_by("-id").values("id", name=F("property_type"))
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertySubTypeListingApiView(APIView):
    """
    Property subtype Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_subtype"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupPropertySubType.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyTermsAcceptedListingApiView(APIView):
    """
    Property terms accepted Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_terms_accepted"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupTermsAccepted.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyOccupiedByListingApiView(APIView):
    """
    Property occupied by Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_occupied_by"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupOccupiedBy.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyOwnershipListingApiView(APIView):
    """
    Property ownership Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_ownership"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupOwnership.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyPossessionListingApiView(APIView):
    """
    Property possession Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_possession"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupPossession.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)

            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyLotSizeListingApiView(APIView):
    """
    Property lot size Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_lot_size"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupLotSize.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyStyleListingApiView(APIView):
    """
    Property style Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_style"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupStyle.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyCoolingListingApiView(APIView):
    """
    Property cooling Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_cooling"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupCooling.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyStoriesListingApiView(APIView):
    """
    Property stories Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_stories"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupStories.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyHeatingListingApiView(APIView):
    """
    Property heating Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_heating"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupHeating.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyElectricListingApiView(APIView):
    """
    Property electric Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_electric"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupElectric.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyGasListingApiView(APIView):
    """
    Property gas Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_gas"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupGas.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyRecentUpdateListingApiView(APIView):
    """
    Property recent update Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_recent_update"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupRecentUpdates.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyWaterListingApiView(APIView):
    """
    Property recent update Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_water"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupWater.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertySecurityFeaturesListingApiView(APIView):
    """
    Property security features Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_security_features"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupSecurityFeatures.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)

            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertySewerListingApiView(APIView):
    """
    Property sewer Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_sewer"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupSewer.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyTaxExemptionsListingApiView(APIView):
    """
    Property tax exemptions Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_tax_exemptions"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupTaxExemptions.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyZoningListingApiView(APIView):
    """
    Property zoning Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_zoning"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupZoning.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyAmenitiesListingApiView(APIView):
    """
    Property amenities Listing
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_amenities"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupAmenities.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyKitchenFeaturesListingApiView(APIView):
    """
    Property kitchen features Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_kitchen_features"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupKitchenFeatures.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyAppliancesListingApiView(APIView):
    """
    Property appliances Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_appliances"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupAppliances.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyFlooringListingApiView(APIView):
    """
    Property flooring Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_flooring"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupFlooring.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyWindowsListingApiView(APIView):
    """
    Property windows Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_windows"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupWindows.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyBedroomFeaturesListingApiViews(APIView):
    """
    Property Bedroom Features Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_bedroom_features"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupBedroomFeatures.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyOtherRoomsListingApiView(APIView):
    """
    Property other rooms Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_other_rooms"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupOtherRooms.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyBathroomFeaturesListingApiView(APIView):
    """
    Property bathroom features rooms Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_bathroom_features"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupBathroomFeatures.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyOtherFeaturesListingApiView(APIView):
    """
    Property other features rooms Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_other_features"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupOtherFeatures.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyMasterBedroomListingApiView(APIView):
    """
    Property master bedroom features rooms Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_master_bedroom_features"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupMasterBedroomFeatures.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyFireplaceTypeListingApiView(APIView):
    """
    Property fireplace type Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_fireplace_type"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupFireplaceType.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyBasementFeaturesListingApiView(APIView):
    """
    Property basement features Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_basement_features"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupBasementFeatures.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyHandicapAmenitiesListingApiView(APIView):
    """
    Property handicap amenities Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_handicap_amenities"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupHandicapAmenities.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyConstructionListingApiView(APIView):
    """
    Property construction Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_construction"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupConstruction.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyGarageParkingListingApiView(APIView):
    """
    Property garage parking Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_garage_parking"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupGarageParking.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyExteriorFeaturesListingApiView(APIView):
    """
    Property exterior features Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_exterior_features"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupExteriorFeatures.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyGarageFeaturesListingApiView(APIView):
    """
    Property garage features Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_garage_features"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupGarageFeatures.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyRoofListingApiView(APIView):
    """
    Property roof Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_roof"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupRoof.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyOutbuildingsListingApiView(APIView):
    """
    Property outbuildings Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_outbuildings"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupOutbuildings.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyFoundationListingApiView(APIView):
    """
    Property foundation Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_foundation"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupFoundation.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyLocationFeaturesListingApiView(APIView):
    """
    Property location features Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_location_features"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupLocationFeatures.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyFencesListingApiView(APIView):
    """
    Property fences Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_fences"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupFence.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyRoadFrontageListingApiView(APIView):
    """
    Property road frontage Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_road_frontage"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupRoadFrontage.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyPoolListingApiView(APIView):
    """
    Property pool Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_pool"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupPool.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyPropertyFacesListingApiView(APIView):
    """
    Property property faces Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_property_faces"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupPropertyFaces.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyLeaseTypeListingApiView(APIView):
    """
    Property lease type Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_lease_type"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupLeaseType.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyTenantPaysListingApiView(APIView):
    """
    Property tenant pays Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_tenant_pays"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupTenantPays.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyInclusionsListingApiView(APIView):
    """
    Property inclusions Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_inclusions"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupInclusions.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyBuildingClassListingApiView(APIView):
    """
    Property building class Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_building_class"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupBuildingClass.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyInteriorFeaturesListingApiView(APIView):
    """
    Property interior features Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_interior_features"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupInteriorFeatures.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyMineralRightsListingApiView(APIView):
    """
    Property mineral rights Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_mineral_rights"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupMineralRights.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyEasementsListingApiView(APIView):
    """
    Property easements Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_easements"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupEasements.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertySurveyListingApiView(APIView):
    """
    Property survey Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_survey"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupSurvey.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyUtilitiesListingApiView(APIView):
    """
    Property utilities Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_utilities"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupUtilities.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyImprovementsListingApiView(APIView):
    """
    Property improvements Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_improvements"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupImprovements.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyTopographyListingApiView(APIView):
    """
    Property topography Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_topography"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupTopography.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyWildlifeListingApiView(APIView):
    """
    Property wildlife Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_wildlife"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupWildlife.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyFishListingApiView(APIView):
    """
    Property fish Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_fish"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupFish.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyIrrigationSystemListingApiView(APIView):
    """
    Property irrigation system Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_irrigation_system"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupIrrigationSystem.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyRecreationListingApiView(APIView):
    """
    Property recreation Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            asset_id = None
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            cache_name = "property_recreation"
            if asset_id is not None:
                cache_name = cache_name + "_" + str(asset_id)
            all_data = get_cache(cache_name)
            if all_data is None:
                all_data = LookupRecreation.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                set_cache(cache_name, all_data)
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyListingApiView(APIView):
    """
    Property listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            project_id = None
            if 'project_id' in data and data['project_id'] != "":
                project_id = int(data['project_id'])

            developer_id = None
            if 'developer_id' in data and data['developer_id'] != "":
                developer_id = int(data['developer_id'])

            employee_id = None
            if 'employee_id' in data and data['employee_id'] != "":
                employee_id = int(data['employee_id'])

            seller_id = None
            if 'seller_id' in data and data['seller_id'] != "":
                seller_id = int(data['seller_id'])    

            sub_admin_id = None
            if 'sub_admin_id' in data and data['sub_admin_id'] != "":
                sub_admin_id = int(data['sub_admin_id'])          

            user_type = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5, 6], status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
                user_type = users.user_type_id
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            # --- Verify that user_id matches the token user ---
            auth_user = request.user  # user from Bearer token
            if int(user_id) != auth_user.id:
                return Response(response.parsejson("Permission denied.", "", status=403))    

            property_listing = PropertyListing.objects.filter(domain=site_id).exclude(status=5)
            if user_type is not None and user_type == 6: # ------------For Developer-----------
                property_listing = property_listing.filter(Q(developer=user_id) | Q(agent_id=user_id))
            elif user_type is not None and user_type == 5: # ---------For Employee--------
                property_listing = property_listing.filter(agent=user_id)

            if project_id is not None:
                property_listing = property_listing.filter(project_id=project_id)
            agent_ids = []

            if developer_id is not None:
                agent_ids.append(developer_id)
                # property_listing = property_listing.filter(Q(developer_id=developer_id) | Q(agent_id=developer_id)) 
            if employee_id is not None:
                agent_ids.append(employee_id)
                # property_listing = property_listing.filter(Q(agent_id=employee_id))
            if seller_id is not None:
                agent_ids.append(seller_id)
                # property_listing = property_listing.filter(Q(agent_id=seller_id))     
            if sub_admin_id is not None:
                agent_ids.append(sub_admin_id)
                # property_listing = property_listing.filter(Q(agent_id=sub_admin_id))

            if len(agent_ids):
                property_listing = property_listing.filter(agent_id__in=agent_ids)
                
            # -----------------Filter-------------------
            if "agent_id" in data and data["agent_id"] != "":
                agent_id = int(data["agent_id"])
                property_listing = property_listing.filter(Q(agent=agent_id))
            if "auction_id" in data and data["auction_id"] != "":
                auction_id = int(data["auction_id"])
                property_listing = property_listing.filter(Q(sale_by_type=auction_id))

            if "asset_id" in data and data["asset_id"] != "":
                asset_id = int(data["asset_id"])
                property_listing = property_listing.filter(Q(property_asset=asset_id))

            if "status" in data and data["status"] != "":
                status = int(data["status"])
                if status in [1, 2, 8]:
                    property_listing = property_listing.filter(Q(status=status))
                else:
                    property_listing = property_listing.filter(Q(closing_status=status))    

            # if "closing_status" in data and data["closing_status"] != "":
            #     closing_status = int(data["closing_status"])
            #     property_listing = property_listing.filter(Q(closing_status=closing_status))    

            if "property_type" in data and data["property_type"] != "":
                property_type = int(data["property_type"])
                property_listing = property_listing.filter(Q(property_type=property_type))

            # if "developer_id" in data and data["developer_id"] != "":
            #     developer_id = int(data["developer_id"])
            #     property_listing = property_listing.filter(Q(developer=developer_id) | Q(agent=developer_id))
            
            if "property_approval" in data and data["property_approval"] != "":
                property_approval = int(data["property_approval"])
                property_listing = property_listing.filter(Q(seller_status=property_approval))

            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                # if search.isdigit():
                #     property_listing = property_listing.filter(Q(id=search) | Q(postal_code__icontains=search))
                # else:
                property_listing = property_listing.filter(Q(property_name__icontains=search) | Q(state__state_name__icontains=search) | Q(property_type__property_type__icontains=search) | Q(postal_code__icontains=search))

            total = property_listing.count()
            property_listing = property_listing.order_by(F("ordering").asc(nulls_last=True)).only("id")[offset:limit]
            serializer = PropertyListingSerializer(property_listing, many=True)
            all_data = {"data": serializer.data, "total": total, "user_domain": ""}
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AdminPropertyListingApiView(APIView):
    """
    Admin property listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            property_listing = PropertyListing.objects.exclude(status=5)
            # -----------------Filter-------------------
            if "agent_id" in data and data["agent_id"] != "":
                agent_id = int(data["agent_id"])
                property_listing = property_listing.filter(agent=agent_id)
            if "user_id" in data and type(data['user_id']) == list and len(data['user_id']) > 0:
                user_id = data["user_id"]
                property_listing = property_listing.filter(agent__in=user_id)

            if "site_id" in data and type(data['site_id']) == list and len(data['site_id']) > 0:
                site_id = data["site_id"]
                property_listing = property_listing.filter(domain__in=site_id)

            if "auction_id" in data and type(data['auction_id']) == list and len(data['auction_id']) > 0:
                auction_id = data["auction_id"]
                property_listing = property_listing.filter(Q(sale_by_type__in=auction_id))

            if "asset_id" in data and type(data['asset_id']) == list and len(data['asset_id']) > 0:
                asset_id = data["asset_id"]
                property_listing = property_listing.filter(Q(property_asset__in=asset_id))

            if "asset_sub_type" in data and type(data['asset_sub_type']) == list and len(data['asset_sub_type']) > 0:
                asset_sub_type = data["asset_sub_type"]
                property_listing = property_listing.filter(Q(property_type__in=asset_sub_type))

            if "status" in data and type(data['status']) == list and len(data['status']) > 0:
                status = data["status"]
                property_listing = property_listing.filter(Q(status__in=status))

            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                if search.isdigit():
                    property_listing = property_listing\
                        .annotate(property_name=Concat('address_one', V(', '), 'city', V(', '), 'state__state_name', V(' '), 'postal_code', output_field=CharField()))\
                        .filter(
                            Q(id=search) |
                            Q(agent__user_business_profile__company_name__icontains=search) | 
                            Q(property_name__icontains=search)
                        )
                else:
                    property_listing = property_listing\
                        .annotate(property_name=Concat('address_one', V(', '), 'city', V(', '), 'state__state_name', V(' '), 'postal_code', output_field=CharField()))\
                        .annotate(full_name=Concat('agent__user_business_profile__first_name', V(' '), 'agent__user_business_profile__last_name'))\
                        .filter(
                                Q(sale_by_type__auction_type__icontains=search) |
                                Q(agent__user_business_profile__company_name__icontains=search) |
                                Q(agent__user_business_profile__first_name__icontains=search) |
                                Q(agent__user_business_profile__last_name__icontains=search) |
                                Q(full_name__icontains=search) |
                                Q(property_name__icontains=search)
                        )

            total = property_listing.count()
            property_listing = property_listing.order_by("-id").only("id")[offset:limit]
            serializer = AdminPropertyListingSerializer(property_listing, many=True)
            all_data = {"data": serializer.data, "total": total}

            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SubdomainPropertyDetailApiView(APIView):
    """
    Subdomain property detail
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required", "", status=403))

            if "step_id" in data and data['step_id'] != "":
                step_id = int(data['step_id'])
            else:
                return Response(response.parsejson("step_id is required", "", status=403))
            property_listing = PropertyListing.objects.get(id=property_id, domain=site_id)
            if step_id == 1:
                serializer = PropertyDetailStepOneSerializer(property_listing)
            elif step_id == 2:
                serializer = PropertyDetailStepTwoSerializer(property_listing)
            elif step_id == 3:
                serializer = PropertyDetailStepThreeSerializer(property_listing)
            elif step_id == 4:
                serializer = PropertyDetailStepFourSerializer(property_listing)
            return Response(response.parsejson("Fetch Data.", serializer.data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SubdomainAddPropertyVideoApiView(APIView):
    """
    Subdomain add property video
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=site_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=site_id, network_user__is_agent=1,
                                                 network_user__status=1, status=1, user_type=2).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "video_url" in data and data['video_url'] != "":
                video_url = data['video_url']
            else:
                return Response(response.parsejson("video_url is required.", "", status=403))

            user_uploads = UserUploads()
            user_uploads.user_id = user_id
            user_uploads.site_id = site_id
            user_uploads.doc_file_name = video_url
            user_uploads.added_by_id = user_id
            user_uploads.updated_by_id = user_id
            user_uploads.save()
            upload_id = user_uploads.id
            all_data = {"upload_id": upload_id, "video_url": video_url}
            return Response(response.parsejson("Video added successfully.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AdminAddPropertyVideoApiView(APIView):
    """
    Admin add property video
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                users = Users.objects.filter(id=admin_id, user_type=3, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "video_url" in data and data['video_url'] != "":
                video_url = data['video_url']
            else:
                return Response(response.parsejson("video_url is required.", "", status=403))

            user_uploads = UserUploads()
            user_uploads.user_id = admin_id
            user_uploads.site_id = site_id
            user_uploads.doc_file_name = video_url
            user_uploads.added_by_id = admin_id
            user_uploads.updated_by_id = admin_id
            user_uploads.save()
            upload_id = user_uploads.id
            all_data = {"upload_id": upload_id, "video_url": video_url}
            return Response(response.parsejson("Video added successfully.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SubdomainPropertyDocumentDeleteApiView(APIView):
    """
    Subdomain property document delete
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5], status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            property_id = None
            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
                property_id = PropertyListing.objects.filter(id=property_id, domain=site_id).first()
                if property_id is None:
                    return Response(response.parsejson("Property not exist.", "", status=403))
            # else:
            #     return Response(response.parsejson("property_id is required.", "", status=403))

            if "upload_id" in data and data['upload_id'] != "":
                upload_id = int(data['upload_id'])
            else:
                return Response(response.parsejson("upload_id is required.", "", status=403))
            if property_id is not None:
                PropertyUploads.objects.filter(upload=upload_id, property=property_id, property__domain=site_id).delete()
            UserUploads.objects.filter(id=upload_id, site=site_id).delete()
            return Response(response.parsejson("Delete successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AdminPropertyDocumentDeleteApiView(APIView):
    """
    Admin property document delete
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
                property_id = PropertyListing.objects.filter(id=property_id).first()
                if property_id is None:
                    return Response(response.parsejson("Property not exist.", "", status=403))
            else:
                return Response(response.parsejson("property_id is required.", "", status=403))

            if "upload_id" in data and data['upload_id'] != "":
                upload_id = int(data['upload_id'])
            else:
                return Response(response.parsejson("upload_id is required.", "", status=403))

            PropertyUploads.objects.filter(upload=upload_id, property=property_id).delete()
            UserUploads.objects.filter(id=upload_id).delete()
            return Response(response.parsejson("Delete successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AddPropertyFeaturesApiView(APIView):
    """
    Add property features
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            features_table = {
                "property_type": LookupPropertyType,
                "property_subtype": LookupPropertySubType,
                "terms_accepted": LookupTermsAccepted,
                "occupied_by": LookupOccupiedBy,
                "ownership": LookupOwnership,
                "possession": LookupPossession,
                "lot_size": LookupLotSize,
                "style": LookupStyle,
                "cooling": LookupCooling,
                "stories": LookupStories,
                "heating": LookupHeating,
                "electric": LookupElectric,
                "gas": LookupGas,
                "recent_updates": LookupRecentUpdates,
                "water": LookupWater,
                "security_features": LookupSecurityFeatures,
                "sewer": LookupSewer,
                "tax_exemptions": LookupTaxExemptions,
                "zoning": LookupZoning,
                "amenities": LookupAmenities,
                "kitchen_features": LookupKitchenFeatures,
                "appliances": LookupAppliances,
                "flooring": LookupFlooring,
                "windows": LookupWindows,
                "bedroom_features": LookupBedroomFeatures,
                "bathroom_features": LookupBathroomFeatures,
                "other_rooms": LookupOtherRooms,
                "other_features": LookupOtherFeatures,
                "master_bedroom_features": LookupMasterBedroomFeatures,
                "fireplace_type": LookupFireplaceType,
                "basement_features": LookupBasementFeatures,
                "handicap_amenities": LookupHandicapAmenities,
                "construction": LookupConstruction,
                "exterior_features": LookupExteriorFeatures,
                "garage_parking": LookupGarageParking,
                "garage_features": LookupGarageFeatures,
                "roof": LookupRoof,
                "outbuildings": LookupOutbuildings,
                "foundation": LookupFoundation,
                "location_features": LookupLocationFeatures,
                "fence": LookupFence,
                "road_frontage": LookupRoadFrontage,
                "pool": LookupPool,
                "property_faces": LookupPropertyFaces,
                "lease_type": LookupLeaseType,
                "tenant_pays": LookupTenantPays,
                "inclusions": LookupInclusions,
                "building_class": LookupBuildingClass,
                "interior_features": LookupInteriorFeatures,
                "mineral_rights": LookupMineralRights,
                "easements": LookupEasements,
                "survey": LookupSurvey,
                "utilities": LookupUtilities,
                "improvements": LookupImprovements,
                "topography": LookupTopography,
                "wildlife": LookupWildlife,
                "fish": LookupFish,
                "irrigation_system": LookupIrrigationSystem,
                "recreation": LookupRecreation,
            }
            data = request.data
            if "feature_type" in data and data['feature_type'] != "":
                feature_type = data['feature_type'].strip()
                feature_table = features_table[feature_type]
            else:
                return Response(response.parsejson("feature_type is required.", "", status=403))

            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            else:
                return Response(response.parsejson("asset_id is required.", "", status=403))

            if "name" in data and data['name'] != "":
                name = data['name'].strip()
                if feature_type == "property_type":
                    check_name = feature_table.objects.filter(property_type=name, asset=asset_id).first()
                else:
                    check_name = feature_table.objects.filter(name=name, asset=asset_id).first()
                if check_name is not None:
                    all_data = {"feature_id": check_name.id}
                    return Response(response.parsejson("Feature added successfully.", all_data, status=201))
            else:
                return Response(response.parsejson("name is required.", "", status=403))

            feature = feature_table()
            if feature_type == "property_type":
                feature.property_type = name
            else:
                feature.name = name
            feature.asset_id = asset_id
            feature.is_active = 1
            feature.save()
            feature_id = feature.id
            all_data = {"feature_id": feature_id}
            return Response(response.parsejson("Feature added successfully.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyFeaturesListingsApiView(APIView):
    """
    Add property features
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            features_table = {
                "property_type": LookupPropertyType,
                "property_subtype": LookupPropertySubType,
                "terms_accepted": LookupTermsAccepted,
                "occupied_by": LookupOccupiedBy,
                "ownership": LookupOwnership,
                "possession": LookupPossession,
                "lot_size": LookupLotSize,
                "style": LookupStyle,
                "cooling": LookupCooling,
                "stories": LookupStories,
                "heating": LookupHeating,
                "electric": LookupElectric,
                "gas": LookupGas,
                "recent_updates": LookupRecentUpdates,
                "water": LookupWater,
                "security_features": LookupSecurityFeatures,
                "sewer": LookupSewer,
                "tax_exemptions": LookupTaxExemptions,
                "zoning": LookupZoning,
                "amenities": LookupAmenities,
                "kitchen_features": LookupKitchenFeatures,
                "appliances": LookupAppliances,
                "flooring": LookupFlooring,
                "windows": LookupWindows,
                "bedroom_features": LookupBedroomFeatures,
                "bathroom_features": LookupBathroomFeatures,
                "other_rooms": LookupOtherRooms,
                "other_features": LookupOtherFeatures,
                "master_bedroom_features": LookupMasterBedroomFeatures,
                "fireplace_type": LookupFireplaceType,
                "basement_features": LookupBasementFeatures,
                "handicap_amenities": LookupHandicapAmenities,
                "construction": LookupConstruction,
                "exterior_features": LookupExteriorFeatures,
                "garage_parking": LookupGarageParking,
                "garage_features": LookupGarageFeatures,
                "roof": LookupRoof,
                "outbuildings": LookupOutbuildings,
                "foundation": LookupFoundation,
                "location_features": LookupLocationFeatures,
                "fence": LookupFence,
                "road_frontage": LookupRoadFrontage,
                "pool": LookupPool,
                "property_faces": LookupPropertyFaces,
                "lease_type": LookupLeaseType,
                "tenant_pays": LookupTenantPays,
                "inclusions": LookupInclusions,
                "building_class": LookupBuildingClass,
                "interior_features": LookupInteriorFeatures,
                "mineral_rights": LookupMineralRights,
                "easements": LookupEasements,
                "survey": LookupSurvey,
                "utilities": LookupUtilities,
                "improvements": LookupImprovements,
                "topography": LookupTopography,
                "wildlife": LookupWildlife,
                "fish": LookupFish,
                "irrigation_system": LookupIrrigationSystem,
                "recreation": LookupRecreation,
            }
            data = request.data
            if "asset_id" in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            else:
                return Response(response.parsejson("asset_id is required.", "", status=403))

            all_data = {}
            for key, values in features_table.items():
                if key == "property_type":
                    features = values.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", name=F("property_type"))
                else:
                    features = values.objects.filter(asset=asset_id, is_active=1).order_by("-id").values("id", "name")
                all_data[key] = features

            auction_type = LookupAuctionType.objects.filter(is_active=1).order_by("id").values("id", "auction_type")
            all_data["auction_type"] = auction_type
            
            return Response(response.parsejson("Fetch data", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AdminAddPropertyApiView(APIView):
    """
    Admin add/update Property
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            property_id = None
            check_update = None
            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
                check_update = True
                property_id = PropertyListing.objects.filter(id=property_id).first()
                if property_id is None:
                    return Response(response.parsejson("Property not exist.", "", status=403))

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
                data['domain'] = site_id
            else:
                if property_id is None:
                    return Response(response.parsejson("site_id is required", "", status=403))

            if "step" in data and data['step'] != "":
                step = int(data['step'])
            else:
                return Response(response.parsejson("step is required.", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=site_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=site_id, network_user__is_agent=1, network_user__status=1, status=1, user_type=2).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                data["agent"] = user_id
            else:
                if step == 1:
                    return Response(response.parsejson("user_id is required.", "", status=403))

            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                admin_users = Users.objects.filter(id=admin_id, user_type=3, status=1).first()
                if admin_users is None:
                    return Response(response.parsejson("Super admin not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            if step == 1:
                un_priced = 0
                if "un_priced" in data and data['un_priced'] != "":
                    un_priced = int(data['un_priced'])

                required_all = 0
                if "required_all" in data and data['required_all'] != "":
                    required_all = int(data['required_all'])

                if "property_asset" in data and data['property_asset'] != "":
                    property_asset = int(data['property_asset'])
                    asset = LookupPropertyAsset.objects.filter(id=property_asset, is_active=1).first()
                    if asset is None:
                        return Response(response.parsejson("Property asset not available.", "", status=403))
                else:
                    return Response(response.parsejson("property_asset is required.", "", status=403))

                if "address_one" in data and data['address_one'] != "":
                    address_one = data['address_one']
                else:
                    return Response(response.parsejson("address_one is required.", "", status=403))

                if "city" in data and data['city'] != "":
                    city = data['city']
                else:
                    return Response(response.parsejson("city is required.", "", status=403))

                if "state" in data and data['state'] != "":
                    state = int(data['state'])
                else:
                    return Response(response.parsejson("state is required.", "", status=403))

                if "postal_code" in data and data['postal_code'] != "":
                    postal_code = int(data['postal_code'])
                else:
                    return Response(response.parsejson("postal_code is required.", "", status=403))

                if "property_type" in data and data['property_type'] != "":
                    property_type = int(data['property_type'])
                else:
                    return Response(response.parsejson("property_type is required.", "", status=403))

                if "sale_by_type" in data and data['sale_by_type'] != "":
                    sale_by_type = int(data['sale_by_type'])
                else:
                    return Response(response.parsejson("sale_by_type is required.", "", status=403))

                if sale_by_type == 6:
                    if "auction_location" in data and data['auction_location'] != "":
                        auction_location = data['auction_location']
                    else:
                        return Response(response.parsejson("auction_location is required.", "", status=403))

                if sale_by_type == 7 and required_all == 1:
                    if "due_diligence_period" in data and data['due_diligence_period'] != "":
                        due_diligence_period = int(data['due_diligence_period'])
                    else:
                        return Response(response.parsejson("due_diligence_period is required.", "", status=403))

                    if "escrow_period" in data and data['escrow_period'] != "":
                        escrow_period = int(data['escrow_period'])
                    else:
                        return Response(response.parsejson("escrow_period is required.", "", status=403))

                    if "earnest_deposit" in data and data['earnest_deposit'] != "":
                        earnest_deposit = data['earnest_deposit']
                    else:
                        return Response(response.parsejson("earnest_deposit is required.", "", status=403))

                    if "earnest_deposit_type" in data and data['earnest_deposit_type'] != "":
                        earnest_deposit_type = int(data['earnest_deposit_type'])
                    else:
                        return Response(response.parsejson("earnest_deposit_type is required.", "", status=403))
                    
                    if "highest_best_format" in data and data['highest_best_format'] != "":
                        highest_best_format = int(data['highest_best_format'])
                    else:
                        return Response(response.parsejson("highest_best_format is required.", "", status=403))

                if "status" in data and data['status'] != "":
                    status = int(data['status'])
                else:
                    data['status'] = 2
                if property_asset != 1:
                    if "property_opening_dates" in data and type(data['property_opening_dates']) == list and len(data['property_opening_dates']) > 0:
                        property_opening_dates = data['property_opening_dates']
                    else:
                        return Response(response.parsejson("property_opening_dates is required.", "", status=403))

                if "property_auction_data" in data and type(data["property_auction_data"]) == dict and len(data["property_auction_data"]) > 0:
                    property_auction_data = data["property_auction_data"]
                    if "auction_status" in property_auction_data and property_auction_data["auction_status"] != "":
                        auction_status = int(property_auction_data["auction_status"])
                    else:
                        return Response(response.parsejson("property_auction_data->auction_status is required.", "", status=403))

                    if sale_by_type == 7:
                        start_price = None
                        if required_all == 1:
                            if "start_price" in property_auction_data and property_auction_data['start_price'] != "":
                                start_price = property_auction_data['start_price']
                            else:
                                if not un_priced:
                                    return Response(response.parsejson("property_auction_data->start_price is required.", "", status=403))
                    else:
                        if "start_price" in property_auction_data and property_auction_data['start_price'] != "":
                            start_price = property_auction_data['start_price']
                        else:
                            return Response(response.parsejson("property_auction_data->start_price is required.", "", status=403))
                    if sale_by_type != 4:
                        if "start_date" in property_auction_data and property_auction_data['start_date'] != "":
                            start_date = property_auction_data['start_date']
                        else:
                            return Response(response.parsejson("property_auction_data->start_date is required.", "", status=403))

                        if "end_date" in property_auction_data and property_auction_data['end_date'] != "":
                            end_date = property_auction_data['end_date']
                        else:
                            return Response(response.parsejson("property_auction_data->end_date is required.", "", status=403))
                    if sale_by_type == 1:
                        if "bid_increments" in property_auction_data and property_auction_data['bid_increments'] != "":
                            bid_increments = property_auction_data['bid_increments']
                        else:
                            return Response(response.parsejson("property_auction_data->bid_increments is required.", "", status=403))
                    if sale_by_type == 7:
                        if "offer_amount" in property_auction_data and property_auction_data['offer_amount'] != "":
                            offer_amount = property_auction_data['offer_amount']
                        else:
                            return Response(response.parsejson("property_auction_data->offer_amount is required.", "", status=403))

                    if sale_by_type != 2:
                        if "reserve_amount" in property_auction_data and property_auction_data['reserve_amount'] != "" and property_auction_data['reserve_amount'] is not None:
                            reserve_amount = property_auction_data['reserve_amount']
                            if float(start_price) > float(reserve_amount):
                                return Response(response.parsejson("reserve_amount should be greater than start_price.", "", status=403))

                    if sale_by_type == 2:
                        if "bid_increments" in property_auction_data and property_auction_data['bid_increments'] != "":
                            bid_increments = property_auction_data['bid_increments']
                        else:
                            return Response(response.parsejson("property_auction_data->bid_increments is required.", "", status=403))

                        if "insider_price_decrease" in property_auction_data and property_auction_data['insider_price_decrease'] != "":
                            insider_price_decrease = property_auction_data['insider_price_decrease']
                        else:
                            return Response(response.parsejson("property_auction_data->insider_price_decrease is required.", "", status=403))

                        if "dutch_time" in property_auction_data and property_auction_data['dutch_time'] != "":
                            dutch_time = property_auction_data['dutch_time']
                        else:
                            return Response(response.parsejson("property_auction_data->dutch_time is required.", "", status=403))

                        if "start_date" in property_auction_data and property_auction_data['start_date'] != "":
                            start_date = property_auction_data['start_date']
                        else:
                            return Response(response.parsejson("property_auction_data->start_date is required.", "", status=403))

                        if "dutch_end_time" in property_auction_data and property_auction_data['dutch_end_time'] != "":
                            dutch_end_time = property_auction_data['dutch_end_time']
                        else:
                            return Response(response.parsejson("property_auction_data->dutch_end_time is required.", "", status=403))

                        if "dutch_pause_time" in property_auction_data and property_auction_data['dutch_pause_time'] != "":
                            dutch_pause_time = property_auction_data['dutch_pause_time']
                        else:
                            return Response(response.parsejson("property_auction_data->dutch_pause_time is required.", "", status=403))

                        if "sealed_time" in property_auction_data and property_auction_data['sealed_time'] != "":
                            sealed_time = property_auction_data['sealed_time']
                        else:
                            return Response(response.parsejson("property_auction_data->sealed_time is required.", "", status=403))

                        if "sealed_start_time" in property_auction_data and property_auction_data['sealed_start_time'] != "":
                            sealed_start_time = property_auction_data['sealed_start_time']
                        else:
                            return Response(response.parsejson("property_auction_data->sealed_start_time is required.", "", status=403))

                        if "sealed_end_time" in property_auction_data and property_auction_data['sealed_end_time'] != "":
                            sealed_end_time = property_auction_data['sealed_end_time']
                        else:
                            return Response(response.parsejson("property_auction_data->sealed_end_time is required.", "", status=403))

                        if "sealed_pause_time" in property_auction_data and property_auction_data['sealed_pause_time'] != "":
                            sealed_pause_time = property_auction_data['sealed_pause_time']
                        else:
                            return Response(response.parsejson("property_auction_data->sealed_pause_time is required.", "", status=403))

                        if "english_time" in property_auction_data and property_auction_data['english_time'] != "":
                            english_time = property_auction_data['english_time']
                        else:
                            return Response(response.parsejson("property_auction_data->english_time is required.", "", status=403))

                        if "english_start_time" in property_auction_data and property_auction_data['english_start_time'] != "":
                            english_start_time = property_auction_data['english_start_time']
                        else:
                            return Response(response.parsejson("property_auction_data->english_start_time is required.", "", status=403))

                        # if "english_end_time" in property_auction_data and property_auction_data['english_end_time'] != "":
                        #     english_end_time = property_auction_data['english_end_time']
                        # else:
                        #     return Response(response.parsejson("property_auction_data->english_end_time is required.", "", status=403))
                else:
                    return Response(response.parsejson("property_auction_data is required.", "", status=403))

                if property_asset == 3:
                    if "beds" in data and data['beds'] != "":
                        beds = int(data['beds'])
                    else:
                        return Response(response.parsejson("beds is required.", "", status=403))

                    if "baths" in data and data['baths'] != "":
                        baths = int(data['baths'])
                    else:
                        return Response(response.parsejson("baths is required.", "", status=403))

                    if "year_built" in data and data['year_built'] != "":
                        year_built = int(data['year_built'])
                    else:
                        return Response(response.parsejson("year_built is required.", "", status=403))

                    if "square_footage" in data and data['square_footage'] != "":
                        square_footage = int(data['square_footage'])
                    else:
                        return Response(response.parsejson("square_footage is required.", "", status=403))
                elif property_asset == 2:
                    if "year_built" in data and data['year_built'] != "":
                        year_built = int(data['year_built'])
                    else:
                        return Response(response.parsejson("year_built is required.", "", status=403))

                    if "square_footage" in data and data['square_footage'] != "":
                        square_footage = int(data['square_footage'])
                    else:
                        return Response(response.parsejson("square_footage is required.", "", status=403))
                data["create_step"] = 1
                # data["status_id"] = 1
                data["title"] = "testing"
                serializer = AddPropertySerializer(property_id, data=data)
                if serializer.is_valid():
                    property_data = serializer.save()
                    property_id = property_data.id
                else:
                    copy_errors = serializer.errors.copy()
                    return Response(response.parsejson(copy_errors, "", status=403))
                # ----------------------Property Auction---------------------
                if "property_auction_data" in data and type(data["property_auction_data"]) == dict and len(data["property_auction_data"]) > 0:
                    property_auction_data = data["property_auction_data"]
                    property_auction = PropertyAuction.objects.filter(property=property_id).first()
                    if property_auction is None:
                        property_auction = PropertyAuction()
                        property_auction.property_id = property_id
                    property_auction.start_date = property_auction_data['start_date']
                    property_auction.end_date = property_auction_data['end_date'] if "end_date" in property_auction_data else None
                    # property_auction.bid_increments = property_auction_data['bid_increments']
                    property_auction.bid_increments = property_auction_data['bid_increments'] if "bid_increments" in property_auction_data and property_auction_data['bid_increments'] is not None and property_auction_data['bid_increments'] != "" else None
                    property_auction.reserve_amount = property_auction_data['reserve_amount'] if "reserve_amount" in property_auction_data and property_auction_data['reserve_amount'] is not None and property_auction_data['reserve_amount'] != "" else None
                    property_auction.time_zone_id = property_auction_data['time_zone']
                    # property_auction.start_price = property_auction_data['start_price']
                    property_auction.bid_increments = property_auction_data['start_price'] if "start_price" in property_auction_data and property_auction_data['start_price'] is not None and property_auction_data['start_price'] != "" else None
                    # property_auction.insider_decreased_price = property_auction_data['start_price']
                    property_auction.insider_decreased_price = property_auction_data['start_price'] if "start_price" in property_auction_data and property_auction_data['start_price'] is not None and property_auction_data['start_price'] != "" else None
                    property_auction.status_id = property_auction_data['auction_status']
                    property_auction.offer_amount = property_auction_data['offer_amount'] if "offer_amount" in property_auction_data else None
                    property_auction.auction_id = sale_by_type
                    property_auction.domain_id = site_id
                    property_auction.un_priced = un_priced
                    property_auction.required_all = required_all
                    property_auction.insider_price_decrease = property_auction_data['insider_price_decrease'] if "insider_price_decrease" in property_auction_data else None
                    property_auction.dutch_time = int(property_auction_data['dutch_time']) if "dutch_time" in property_auction_data else None
                    property_auction.dutch_end_time = property_auction_data['dutch_end_time'] if "dutch_end_time" in property_auction_data else None
                    property_auction.dutch_pause_time = int(property_auction_data['dutch_pause_time']) if "dutch_pause_time" in property_auction_data else None
                    property_auction.sealed_time = int(property_auction_data['sealed_time']) if "sealed_time" in property_auction_data else None
                    property_auction.sealed_start_time = property_auction_data['sealed_start_time'] if "sealed_start_time" in property_auction_data else None
                    property_auction.sealed_end_time = property_auction_data['sealed_end_time'] if "sealed_end_time" in property_auction_data else None
                    property_auction.sealed_pause_time = int(property_auction_data['sealed_pause_time']) if "sealed_pause_time" in property_auction_data else None
                    property_auction.english_time = int(property_auction_data['english_time']) if "english_time" in property_auction_data else None
                    property_auction.english_start_time = property_auction_data['english_start_time'] if "english_start_time" in property_auction_data else None
                    # property_auction.english_end_time = property_auction_data['english_end_time'] if "english_end_time" in property_auction_data else None
                    property_auction.save()
                # ----------------------Property Subtype---------------------
                if "property_subtype" in data and type(data["property_subtype"]) == list:
                    property_subtype = data["property_subtype"]
                    PropertySubtype.objects.filter(property=property_id).delete()
                    for subtype in property_subtype:
                        property_subtype = PropertySubtype()
                        property_subtype.property_id = property_id
                        property_subtype.subtype_id = subtype
                        property_subtype.save()

                # ----------------------Terms Accepted---------------------
                if "terms_accepted" in data and type(data["terms_accepted"]) == list:
                    terms_accepted = data["terms_accepted"]
                    PropertyTermAccepted.objects.filter(property=property_id).delete()
                    for terms in terms_accepted:
                        property_term_accepted = PropertyTermAccepted()
                        property_term_accepted.property_id = property_id
                        property_term_accepted.term_accepted_id = terms
                        property_term_accepted.save()

                # ----------------------Occupied By---------------------
                if "occupied_by" in data and type(data["occupied_by"]) == list:
                    occupied_by = data["occupied_by"]
                    PropertyOccupiedBy.objects.filter(property=property_id).delete()
                    for occupied in occupied_by:
                        property_occupied_by = PropertyOccupiedBy()
                        property_occupied_by.property_id = property_id
                        property_occupied_by.occupied_by_id = occupied
                        property_occupied_by.save()

                # ----------------------Ownership---------------------
                if "ownership" in data and type(data["ownership"]) == list:
                    ownership = data["ownership"]
                    PropertyOwnership.objects.filter(property=property_id).delete()
                    for owner in ownership:
                        property_ownership = PropertyOwnership()
                        property_ownership.property_id = property_id
                        property_ownership.ownership_id = owner
                        property_ownership.save()

                # ----------------------Possession---------------------
                if "possession" in data and type(data["possession"]) == list:
                    possession = data["possession"]
                    PropertyPossession.objects.filter(property=property_id).delete()
                    for pos in possession:
                        property_possession = PropertyPossession()
                        property_possession.property_id = property_id
                        property_possession.possession_id = pos
                        property_possession.save()

                # ----------------------Style---------------------
                if "style" in data and type(data["style"]) == list:
                    style = data["style"]
                    PropertyStyle.objects.filter(property=property_id).delete()
                    for st in style:
                        property_style = PropertyStyle()
                        property_style.property_id = property_id
                        property_style.style_id = st
                        property_style.save()

                # ----------------------Cooling---------------------
                if "cooling" in data and type(data["cooling"]) == list:
                    cooling = data["cooling"]
                    PropertyCooling.objects.filter(property=property_id).delete()
                    for cool in cooling:
                        property_cooling = PropertyCooling()
                        property_cooling.property_id = property_id
                        property_cooling.cooling_id = cool
                        property_cooling.save()

                # ----------------------Stories---------------------
                if "stories" in data and type(data["stories"]) == list:
                    stories = data["stories"]
                    PropertyStories.objects.filter(property=property_id).delete()
                    for story in stories:
                        property_stories = PropertyStories()
                        property_stories.property_id = property_id
                        property_stories.stories_id = story
                        property_stories.save()

                # ----------------------HeatingStories---------------------
                if "heating" in data and type(data["heating"]) == list:
                    heating = data["heating"]
                    PropertyHeating.objects.filter(property=property_id).delete()
                    for heat in heating:
                        property_heating = PropertyHeating()
                        property_heating.property_id = property_id
                        property_heating.heating_id = heat
                        property_heating.save()

                # ----------------------Electric---------------------
                if "electric" in data and type(data["electric"]) == list:
                    electric = data["electric"]
                    PropertyElectric.objects.filter(property=property_id).delete()
                    for ele in electric:
                        property_electric = PropertyElectric()
                        property_electric.property_id = property_id
                        property_electric.electric_id = ele
                        property_electric.save()

                # ----------------------Gas---------------------
                if "gas" in data and type(data["gas"]) == list:
                    gas = data["gas"]
                    PropertyGas.objects.filter(property=property_id).delete()
                    for g in gas:
                        property_gas = PropertyGas()
                        property_gas.property_id = property_id
                        property_gas.gas_id = g
                        property_gas.save()

                # ----------------------Recent Updates---------------------
                if "recent_updates" in data and type(data["recent_updates"]) == list:
                    recent_updates = data["recent_updates"]
                    PropertyRecentUpdates.objects.filter(property=property_id).delete()
                    for updates in recent_updates:
                        property_recent_updates = PropertyRecentUpdates()
                        property_recent_updates.property_id = property_id
                        property_recent_updates.recent_updates_id = updates
                        property_recent_updates.save()

                # ----------------------Water---------------------
                if "water" in data and type(data["water"]) == list:
                    water = data["water"]
                    PropertyWater.objects.filter(property=property_id).delete()
                    for wa in water:
                        property_water = PropertyWater()
                        property_water.property_id = property_id
                        property_water.water_id = wa
                        property_water.save()

                # ----------------------Security Features---------------------
                if "security_features" in data and type(data["security_features"]) == list:
                    security_features = data["security_features"]
                    PropertySecurityFeatures.objects.filter(property=property_id).delete()
                    for security in security_features:
                        property_security_features = PropertySecurityFeatures()
                        property_security_features.property_id = property_id
                        property_security_features.security_features_id = security
                        property_security_features.save()

                # ----------------------Sewer---------------------
                if "sewer" in data and type(data["sewer"]) == list:
                    sewer = data["sewer"]
                    PropertySewer.objects.filter(property=property_id).delete()
                    for se in sewer:
                        property_sewer = PropertySewer()
                        property_sewer.property_id = property_id
                        property_sewer.sewer_id = se
                        property_sewer.save()

                # ----------------------Tax Exemptions---------------------
                if "tax_exemptions" in data and type(data["tax_exemptions"]) == list:
                    tax_exemptions = data["tax_exemptions"]
                    PropertyTaxExemptions.objects.filter(property=property_id).delete()
                    for tax in tax_exemptions:
                        property_tax_exemptions = PropertyTaxExemptions()
                        property_tax_exemptions.property_id = property_id
                        property_tax_exemptions.tax_exemptions_id = tax
                        property_tax_exemptions.save()

                # ----------------------Zoning---------------------
                if "zoning" in data and type(data["zoning"]) == list:
                    zoning = data["zoning"]
                    PropertyZoning.objects.filter(property=property_id).delete()
                    for zo in zoning:
                        property_zoning = PropertyZoning()
                        property_zoning.property_id = property_id
                        property_zoning.zoning_id = zo
                        property_zoning.save()

                # ----------------------Hoa Amenities---------------------
                if "hoa_amenities" in data and type(data["hoa_amenities"]) == list:
                    hoa_amenities = data["hoa_amenities"]
                    PropertyAmenities.objects.filter(property=property_id).delete()
                    for hoa in hoa_amenities:
                        property_amenities = PropertyAmenities()
                        property_amenities.property_id = property_id
                        property_amenities.amenities_id = hoa
                        property_amenities.save()

                # ----------------------Kitchen Features---------------------
                if "kitchen_features" in data and type(data["kitchen_features"]) == list:
                    kitchen_features = data["kitchen_features"]
                    PropertyKitchenFeatures.objects.filter(property=property_id).delete()
                    for kitchen in kitchen_features:
                        property_kitchen_features = PropertyKitchenFeatures()
                        property_kitchen_features.property_id = property_id
                        property_kitchen_features.kitchen_features_id = kitchen
                        property_kitchen_features.save()

                # ----------------------Appliances---------------------
                if "appliances" in data and type(data["appliances"]) == list:
                    appliances = data["appliances"]
                    PropertyAppliances.objects.filter(property=property_id).delete()
                    for apl in appliances:
                        property_appliances = PropertyAppliances()
                        property_appliances.property_id = property_id
                        property_appliances.appliances_id = apl
                        property_appliances.save()

                # ----------------------Flooring---------------------
                if "flooring" in data and type(data["flooring"]) == list:
                    flooring = data["flooring"]
                    PropertyFlooring.objects.filter(property=property_id).delete()
                    for floor in flooring:
                        property_flooring = PropertyFlooring()
                        property_flooring.property_id = property_id
                        property_flooring.flooring_id = floor
                        property_flooring.save()

                # ----------------------Windows---------------------
                if "windows" in data and type(data["windows"]) == list:
                    windows = data["windows"]
                    PropertyWindows.objects.filter(property=property_id).delete()
                    for window in windows:
                        property_windows = PropertyWindows()
                        property_windows.property_id = property_id
                        property_windows.windows_id = window
                        property_windows.save()

                # ----------------------Bedroom Features---------------------
                if "bedroom_features" in data and type(data["bedroom_features"]) == list:
                    bedroom_features = data["bedroom_features"]
                    PropertyBedroomFeatures.objects.filter(property=property_id).delete()
                    for bedroom in bedroom_features:
                        property_bedroom_features = PropertyBedroomFeatures()
                        property_bedroom_features.property_id = property_id
                        property_bedroom_features.bedroom_features_id = bedroom
                        property_bedroom_features.save()

                # ----------------------Other Rooms---------------------
                if "other_rooms" in data and type(data["other_rooms"]) == list:
                    other_rooms = data["other_rooms"]
                    PropertyOtherRooms.objects.filter(property=property_id).delete()
                    for other in other_rooms:
                        property_other_rooms = PropertyOtherRooms()
                        property_other_rooms.property_id = property_id
                        property_other_rooms.other_rooms_id = other
                        property_other_rooms.save()

                # ----------------------Bathroom Features---------------------
                if "bathroom_features" in data and type(data["bathroom_features"]) == list:
                    bathroom_features = data["bathroom_features"]
                    PropertyBathroomFeatures.objects.filter(property=property_id).delete()
                    for bathroom in bathroom_features:
                        property_bathroom_features = PropertyBathroomFeatures()
                        property_bathroom_features.property_id = property_id
                        property_bathroom_features.bathroom_features_id = bathroom
                        property_bathroom_features.save()
                # ----------------------Other Features---------------------
                if "other_features" in data and type(data["other_features"]) == list:
                    other_features = data["other_features"]
                    PropertyOtherFeatures.objects.filter(property=property_id).delete()
                    for other in other_features:
                        property_other_features = PropertyOtherFeatures()
                        property_other_features.property_id = property_id
                        property_other_features.other_features_id = other
                        property_other_features.save()

                # ----------------------Master Bedroom Features---------------------
                if "master_bedroom_features" in data and type(data["master_bedroom_features"]) == list:
                    master_bedroom_features = data["master_bedroom_features"]
                    PropertyMasterBedroomFeatures.objects.filter(property=property_id).delete()
                    for master_bedroom in master_bedroom_features:
                        property_master_bedroom_features = PropertyMasterBedroomFeatures()
                        property_master_bedroom_features.property_id = property_id
                        property_master_bedroom_features.master_bedroom_features_id = master_bedroom
                        property_master_bedroom_features.save()

                # ----------------------Fireplace Type---------------------
                if "fireplace_type" in data and type(data["fireplace_type"]) == list:
                    fireplace_type = data["fireplace_type"]
                    PropertyFireplaceType.objects.filter(property=property_id).delete()
                    for fireplace in fireplace_type:
                        property_fireplace_type = PropertyFireplaceType()
                        property_fireplace_type.property_id = property_id
                        property_fireplace_type.fireplace_type_id = fireplace
                        property_fireplace_type.save()

                # ----------------------Basement Features---------------------
                if "basement_features" in data and type(data["basement_features"]) == list:
                    basement_features = data["basement_features"]
                    PropertyBasementFeatures.objects.filter(property=property_id).delete()
                    for basement in basement_features:
                        property_basement_features = PropertyBasementFeatures()
                        property_basement_features.property_id = property_id
                        property_basement_features.basement_features_id = basement
                        property_basement_features.save()

                # ----------------------Handicap Amenities---------------------
                if "handicap_amenities" in data and type(data["handicap_amenities"]) == list:
                    handicap_amenities = data["handicap_amenities"]
                    PropertyHandicapAmenities.objects.filter(property=property_id).delete()
                    for amenities in handicap_amenities:
                        property_handicap_amenities = PropertyHandicapAmenities()
                        property_handicap_amenities.property_id = property_id
                        property_handicap_amenities.handicap_amenities_id = amenities
                        property_handicap_amenities.save()

                # ----------------------Construction---------------------
                if "construction" in data and type(data["construction"]) == list:
                    construction = data["construction"]
                    PropertyConstruction.objects.filter(property=property_id).delete()
                    for cons in construction:
                        property_construction = PropertyConstruction()
                        property_construction.property_id = property_id
                        property_construction.construction_id = cons
                        property_construction.save()

                # ----------------------Garage Parking---------------------
                if "garage_parking" in data and type(data["garage_parking"]) == list:
                    garage_parking = data["garage_parking"]
                    PropertyGarageParking.objects.filter(property=property_id).delete()
                    for parking in garage_parking:
                        property_garage_parking = PropertyGarageParking()
                        property_garage_parking.property_id = property_id
                        property_garage_parking.garage_parking_id = parking
                        property_garage_parking.save()

                # ----------------------Exterior Features---------------------
                if "exterior_features" in data and type(data["exterior_features"]) == list:
                    exterior_features = data["exterior_features"]
                    PropertyExteriorFeatures.objects.filter(property=property_id).delete()
                    for exterior in exterior_features:
                        property_exterior_features = PropertyExteriorFeatures()
                        property_exterior_features.property_id = property_id
                        property_exterior_features.exterior_features_id = exterior
                        property_exterior_features.save()

                # ----------------------Garage Features---------------------
                if "garage_features" in data and type(data["garage_features"]) == list:
                    garage_features = data["garage_features"]
                    PropertyGarageFeatures.objects.filter(property=property_id).delete()
                    for garage in garage_features:
                        property_garage_features = PropertyGarageFeatures()
                        property_garage_features.property_id = property_id
                        property_garage_features.garage_features_id = garage
                        property_garage_features.save()

                # ----------------------Roof---------------------
                if "roof" in data and type(data["roof"]) == list:
                    roof = data["roof"]
                    PropertyRoof.objects.filter(property=property_id).delete()
                    for rf in roof:
                        property_roof = PropertyRoof()
                        property_roof.property_id = property_id
                        property_roof.roof_id = rf
                        property_roof.save()

                # ----------------------Outbuildings---------------------
                if "outbuildings" in data and type(data["outbuildings"]) == list:
                    outbuildings = data["outbuildings"]
                    PropertyOutbuildings.objects.filter(property=property_id).delete()
                    for buildings in outbuildings:
                        property_outbuildings = PropertyOutbuildings()
                        property_outbuildings.property_id = property_id
                        property_outbuildings.outbuildings_id = buildings
                        property_outbuildings.save()

                # ----------------------Foundation---------------------
                if "foundation" in data and type(data["foundation"]) == list:
                    foundation = data["foundation"]
                    PropertyFoundation.objects.filter(property=property_id).delete()
                    for fd in foundation:
                        property_foundation = PropertyFoundation()
                        property_foundation.property_id = property_id
                        property_foundation.foundation_id = fd
                        property_foundation.save()

                # ----------------------Location Features---------------------
                if "location_features" in data and type(data["location_features"]) == list:
                    location_features = data["location_features"]
                    PropertyLocationFeatures.objects.filter(property=property_id).delete()
                    for location in location_features:
                        property_location_features = PropertyLocationFeatures()
                        property_location_features.property_id = property_id
                        property_location_features.location_features_id = location
                        property_location_features.save()

                # ----------------------Fence---------------------
                if "fence" in data and type(data["fence"]) == list:
                    fence = data["fence"]
                    PropertyFence.objects.filter(property=property_id).delete()
                    for fnc in fence:
                        property_fence = PropertyFence()
                        property_fence.property_id = property_id
                        property_fence.fence_id = fnc
                        property_fence.save()

                # ----------------------Road Frontage---------------------
                if "road_frontage" in data and type(data["road_frontage"]) == list:
                    road_frontage = data["road_frontage"]
                    PropertyRoadFrontage.objects.filter(property=property_id).delete()
                    for frontage in road_frontage:
                        property_road_frontage = PropertyRoadFrontage()
                        property_road_frontage.property_id = property_id
                        property_road_frontage.road_frontage_id = frontage
                        property_road_frontage.save()

                # ----------------------Pool---------------------
                if "pool" in data and type(data["pool"]) == list:
                    pool = data["pool"]
                    PropertyPool.objects.filter(property=property_id).delete()
                    for pl in pool:
                        property_pool = PropertyPool()
                        property_pool.property_id = property_id
                        property_pool.pool_id = pl
                        property_pool.save()

                # ----------------------Property Faces---------------------
                if "property_faces" in data and type(data["property_faces"]) == list:
                    property_faces = data["property_faces"]
                    PropertyPropertyFaces.objects.filter(property=property_id).delete()
                    for faces in property_faces:
                        property_property_faces = PropertyPropertyFaces()
                        property_property_faces.property_id = property_id
                        property_property_faces.property_faces_id = faces
                        property_property_faces.save()

                # ----------------Commercial------------------

                # ----------------------Property Faces---------------------
                if "lease_type" in data and type(data["lease_type"]) == list:
                    lease_type = data["lease_type"]
                    PropertyLeaseType.objects.filter(property=property_id).delete()
                    for lease in lease_type:
                        property_lease_type = PropertyLeaseType()
                        property_lease_type.property_id = property_id
                        property_lease_type.lease_type_id = lease
                        property_lease_type.save()

                # ----------------------Tenant Pays---------------------
                if "tenant_pays" in data and type(data["tenant_pays"]) == list:
                    tenant_pays = data["tenant_pays"]
                    PropertyTenantPays.objects.filter(property=property_id).delete()
                    for tenant in tenant_pays:
                        property_tenant_pays = PropertyTenantPays()
                        property_tenant_pays.property_id = property_id
                        property_tenant_pays.tenant_pays_id = tenant
                        property_tenant_pays.save()

                # ----------------------Tenant Pays---------------------
                if "tenant_pays" in data and type(data["tenant_pays"]) == list:
                    tenant_pays = data["tenant_pays"]
                    PropertyTenantPays.objects.filter(property=property_id).delete()
                    for tenant in tenant_pays:
                        property_tenant_pays = PropertyTenantPays()
                        property_tenant_pays.property_id = property_id
                        property_tenant_pays.tenant_pays_id = tenant
                        property_tenant_pays.save()

                # ----------------------Inclusions---------------------
                if "inclusions" in data and type(data["inclusions"]) == list:
                    inclusions = data["inclusions"]
                    PropertyInclusions.objects.filter(property=property_id).delete()
                    for incl in inclusions:
                        property_inclusions = PropertyInclusions()
                        property_inclusions.property_id = property_id
                        property_inclusions.inclusions_id = incl
                        property_inclusions.save()

                # ----------------------Building Class---------------------
                if "building_class" in data and type(data["building_class"]) == list:
                    building_class = data["building_class"]
                    PropertyBuildingClass.objects.filter(property=property_id).delete()
                    for building in building_class:
                        property_building_class = PropertyBuildingClass()
                        property_building_class.property_id = property_id
                        property_building_class.building_class_id = building
                        property_building_class.save()

                # ----------------------Interior Features---------------------
                if "interior_features" in data and type(data["interior_features"]) == list:
                    interior_features = data["interior_features"]
                    PropertyInteriorFeatures.objects.filter(property=property_id).delete()
                    for interior in interior_features:
                        property_interior_features = PropertyInteriorFeatures()
                        property_interior_features.property_id = property_id
                        property_interior_features.interior_features_id = interior
                        property_interior_features.save()

                # ------------------Land-----------------
                # ----------------------Mineral Rights---------------------
                if "mineral_rights" in data and type(data["mineral_rights"]) == list:
                    mineral_rights = data["mineral_rights"]
                    PropertyMineralRights.objects.filter(property=property_id).delete()
                    for mineral in mineral_rights:
                        property_mineral_rights = PropertyMineralRights()
                        property_mineral_rights.property_id = property_id
                        property_mineral_rights.mineral_rights_id = mineral
                        property_mineral_rights.save()

                # ----------------------Easements---------------------
                if "easements" in data and type(data["easements"]) == list:
                    easements = data["easements"]
                    PropertyEasements.objects.filter(property=property_id).delete()
                    for eas in easements:
                        property_easements = PropertyEasements()
                        property_easements.property_id = property_id
                        property_easements.easements_id = eas
                        property_easements.save()

                # ----------------------Survey---------------------
                if "survey" in data and type(data["survey"]) == list:
                    survey = data["survey"]
                    PropertySurvey.objects.filter(property=property_id).delete()
                    for sur in survey:
                        property_survey = PropertySurvey()
                        property_survey.property_id = property_id
                        property_survey.survey_id = sur
                        property_survey.save()

                # ----------------------Utilities---------------------
                if "utilities" in data and type(data["utilities"]) == list:
                    utilities = data["utilities"]
                    PropertyUtilities.objects.filter(property=property_id).delete()
                    for uti in utilities:
                        property_utilities = PropertyUtilities()
                        property_utilities.property_id = property_id
                        property_utilities.utilities_id = uti
                        property_utilities.save()

                # ----------------------Improvements---------------------
                if "improvements" in data and type(data["improvements"]) == list:
                    improvements = data["improvements"]
                    PropertyImprovements.objects.filter(property=property_id).delete()
                    for imp in improvements:
                        property_improvements = PropertyImprovements()
                        property_improvements.property_id = property_id
                        property_improvements.improvements_id = imp
                        property_improvements.save()

                # ----------------------Topography---------------------
                if "topography" in data and type(data["topography"]) == list:
                    topography = data["topography"]
                    PropertyTopography.objects.filter(property=property_id).delete()
                    for top in topography:
                        property_topography = PropertyTopography()
                        property_topography.property_id = property_id
                        property_topography.topography_id = top
                        property_topography.save()

                # ----------------------Wildlife---------------------
                if "wildlife" in data and type(data["wildlife"]) == list:
                    wildlife = data["wildlife"]
                    PropertyWildlife.objects.filter(property=property_id).delete()
                    for wild in wildlife:
                        property_wildlife = PropertyWildlife()
                        property_wildlife.property_id = property_id
                        property_wildlife.wildlife_id = wild
                        property_wildlife.save()

                # ----------------------Fish---------------------
                if "fish" in data and type(data["fish"]) == list:
                    fish = data["fish"]
                    PropertyFish.objects.filter(property=property_id).delete()
                    for fi in fish:
                        property_fish = PropertyFish()
                        property_fish.property_id = property_id
                        property_fish.fish_id = fi
                        property_fish.save()

                # ----------------------Irrigation System---------------------
                if "irrigation_system" in data and type(data["irrigation_system"]) == list:
                    irrigation_system = data["irrigation_system"]
                    PropertyIrrigationSystem.objects.filter(property=property_id).delete()
                    for irrigation in irrigation_system:
                        property_irrigation_system = PropertyIrrigationSystem()
                        property_irrigation_system.property_id = property_id
                        property_irrigation_system.irrigation_system_id = irrigation
                        property_irrigation_system.save()

                # ----------------------Recreation---------------------
                if "recreation" in data and type(data["recreation"]) == list:
                    recreation = data["recreation"]
                    PropertyRecreation.objects.filter(property=property_id).delete()
                    for rec in recreation:
                        property_recreation = PropertyRecreation()
                        property_recreation.property_id = property_id
                        property_recreation.recreation_id = rec
                        property_recreation.save()

                # ----------------------Property opening date---------------------
                if property_asset != 1:
                    if "property_opening_dates" in data and type(data["property_opening_dates"]) == list:
                        property_opening_dates = data["property_opening_dates"]
                        PropertyOpening.objects.filter(property=property_id).delete()
                        for dates in property_opening_dates:
                            property_opening = PropertyOpening()
                            property_opening.domain_id = site_id
                            property_opening.property_id = property_id
                            property_opening.opening_start_date = dates['start_date']
                            property_opening.opening_end_date = dates['end_date']
                            property_opening.status_id = 1
                            property_opening.save()

            elif step == 2:
                if property_id is None:
                    return Response(response.parsejson("property_id is required.", "", status=403))
                property_id = property_id.id
                if "is_map_view" in data and data["is_map_view"] != "":
                    is_map_view = data["is_map_view"]
                else:
                    return Response(response.parsejson("is_map_view is required.", "", status=403))

                if "is_street_view" in data and data["is_street_view"] != "":
                    is_street_view = data["is_street_view"]
                else:
                    return Response(response.parsejson("is_street_view is required.", "", status=403))

                if "is_arial_view" in data and data["is_arial_view"] != "":
                    is_arial_view = data["is_arial_view"]
                else:
                    return Response(response.parsejson("is_arial_view is required.", "", status=403))
                map_url = None
                if "map_url" in data and data["map_url"] != "":
                    map_url = data["map_url"]
                # else:
                #     return Response(response.parsejson("map_url is required.", "", status=403))

                latitude = None
                if "latitude" in data and data["latitude"] != "":
                    latitude = data["latitude"]

                longitude = None
                if "longitude" in data and data["longitude"] != "":
                    longitude = data["longitude"]

                property_listing = PropertyListing.objects.get(id=property_id)
                property_listing.is_map_view = is_map_view
                property_listing.is_street_view = is_street_view
                property_listing.is_arial_view = is_arial_view
                property_listing.create_step = 2
                property_listing.map_url = map_url
                if latitude is not None:
                    property_listing.latitude = latitude
                if longitude is not None:
                    property_listing.longitude = longitude
                property_listing.save()
            elif step == 3:
                if property_id is None:
                    return Response(response.parsejson("property_id is required.", "", status=403))
                property_id = property_id.id
                if "property_pic" in data and type(data["property_pic"]) == list and len(data["property_pic"]) > 0:
                    property_pic = data["property_pic"]
                    PropertyUploads.objects.filter(property=property_id, upload_type=1).delete()
                    for pic in property_pic:
                        property_uploads = PropertyUploads()
                        property_uploads.upload_id = pic
                        property_uploads.property_id = property_id
                        property_uploads.upload_type = 1
                        property_uploads.status_id = 1
                        property_uploads.save()

                if "property_video" in data and type(data["property_video"]) == list and len(data["property_video"]) > 0:
                    property_video = data["property_video"]
                    PropertyUploads.objects.filter(property=property_id, upload_type=2).delete()
                    for video in property_video:
                        property_uploads = PropertyUploads()
                        property_uploads.upload_id = video
                        property_uploads.property_id = property_id
                        property_uploads.upload_type = 2
                        property_uploads.status_id = 1
                        property_uploads.save()

                property_listing = PropertyListing.objects.get(id=property_id)
                property_listing.create_step = 3
                property_listing.save()
            elif step == 4:
                if property_id is None:
                    return Response(response.parsejson("property_id is required.", "", status=403))
                property_id = property_id.id
                if "property_documents" in data and type(data["property_documents"]) == list and len(data["property_documents"]) > 0:
                    property_documents = data["property_documents"]
                    PropertyUploads.objects.filter(property=property_id, upload_type=3).delete()
                    for documents in property_documents:
                        property_uploads = PropertyUploads()
                        property_uploads.upload_id = documents
                        property_uploads.property_id = property_id
                        property_uploads.upload_type = 3
                        property_uploads.status_id = 1
                        property_uploads.save()

                property_listing = PropertyListing.objects.get(id=property_id)
                property_listing.create_step = 4
                property_listing.save()
            all_data = {"property_id": property_id}
            try:
                if not check_update:
                    # Send email to agent and broker
                    broker_data = Users.objects.get(site_id=property_data.domain_id)
                    agent_data = property_data.agent
                    super_admin_data = Users.objects.get(id=admin_id)
                    property_user_name = agent_data.first_name
                    agent_email = agent_data.email
                    auction_type = property_data.sale_by_type.auction_type
                    auction_data = PropertyAuction.objects.get(property=property_id)
                    start_price = auction_data.start_price
                    upload = PropertyUploads.objects.filter(property=property_id, upload_type=1).first()
                    web_url = settings.FRONT_BASE_URL
                    image_url = web_url+'/static/admin/images/property-default-img.png'
                    if upload is not None:
                        image = upload.upload.doc_file_name
                        bucket_name = upload.upload.bucket_name
                        image_url = 'https://realtyonegroup.s3.us-west-1.amazonaws.com/'+bucket_name+'/'+image
                    subdomain_url = settings.SUBDOMAIN_URL
                    domain_name = network.domain_name
                    domain_url = subdomain_url.replace("###", domain_name)+"admin/listing/"
                    notif_type = 2
                    if property_data.sale_by_type_id == 7:
                        notif_type = 6
                        domain_url = domain_url + "?auction_type=highest%20offer"
                    elif property_data.sale_by_type_id == 4:
                        notif_type = 4
                        domain_url = domain_url + "?auction_type=traditional%20offer"
                    elif property_data.sale_by_type_id == 6:
                        notif_type = 7
                        domain_url = domain_url + "?auction_type=live%20offer"
                    domain_name_url = subdomain_url.replace("###", domain_name)
                    template_data = {"domain_id": property_data.domain_id, "slug": "add_listing_super_admin"}
                    prop_name = property_data.address_one if property_data.address_one else property_data.id
                    extra_data = {
                        'property_user_name': broker_data.first_name,
                        'domain_name': domain_name_url,
                        'name': super_admin_data.first_name,
                        'email': super_admin_data.email,
                        'phone':  phone_format(super_admin_data.phone_no),
                        'property_image': image_url,
                        'property_address': property_data.address_one,
                        'property_city': property_data.city,
                        'property_state': property_data.state.state_name,
                        'auction_type': auction_type,
                        'asset_type': property_data.property_asset.name,
                        'starting_price': "$" + number_format(start_price) if not auction_data.un_priced else 'Unpriced',
                        'starting_bid_offer': 'Starting Bid' if property_data.sale_by_type_id in [1, 6] else "Asking Price",
                        'dashboard_link': domain_url,
                        'domain_id': property_data.domain_id
                    }

                    # Email for broker
                    compose_email(to_email=[broker_data.email], template_data=template_data, extra_data=extra_data)

                    #  add notif to broker
                    content = "A new listing is created on your domain! <span>[" + prop_name + "]</span>"
                    add_notification(
                        property_data.domain_id,
                        "Create Listing",
                        content,
                        user_id=broker_data.id,
                        added_by=admin_id,
                        notification_for=2,
                        property_id=property_data.id,
                        notification_type=notif_type
                        )

                    # identify agent
                    if broker_data.id != property_data.agent_id:
                        extra_data['property_user_name'] = property_user_name
                        # email for agent
                        compose_email(to_email=[agent_email], template_data=template_data, extra_data=extra_data)
                        #  add notif to agent
                        content = "A new listing is created for you! <span>[" + prop_name + "]</span>"
                        add_notification(
                            property_data.domain_id,
                            "Create Listing",
                            content,
                            user_id=property_data.agent_id,
                            added_by=admin_id,
                            notification_for=2,
                            property_id=property_data.id,
                            notification_type=notif_type
                            )
            except Exception as e:
                pass

            return Response(response.parsejson("Property added/updated successfully.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AdminPropertyDetailApiView(APIView):
    """
    Admin property detail
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required", "", status=403))

            # if "step_id" in data and data['step_id'] != "":
            #     step_id = int(data['step_id'])
            # else:
            #     return Response(response.parsejson("step_id is required", "", status=403))
            property_listing = PropertyListing.objects.get(id=property_id)
            # if step_id == 1:
            #     serializer = AdminPropertyDetailStepOneSerializer(property_listing)
            # elif step_id == 2:
            #     serializer = AdminPropertyDetailStepTwoSerializer(property_listing)
            # elif step_id == 3:
            #     serializer = AdminPropertyDetailStepThreeSerializer(property_listing)
            # elif step_id == 4:
            #     serializer = AdminPropertyDetailStepFourSerializer(property_listing)
            response_data = {
                'step_1': AdminPropertyDetailStepOneSerializer(property_listing).data,
                'step_2': AdminPropertyDetailStepTwoSerializer(property_listing).data,
                'step_3': AdminPropertyDetailStepThreeSerializer(property_listing).data,
                'step_4': AdminPropertyDetailStepFourSerializer(property_listing).data
            }

            return Response(response.parsejson("Fetch Data.", response_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class ProjectPropertyListingApiView(APIView):
    """
    Project property listing
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'project_id' in data and data['project_id'] != "":
                project_id = int(data['project_id'])
            else:
                return Response(response.parsejson("project_id is required", "", status=403))

            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            user_id = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])

            property_listing = PropertyListing.objects.filter(project=project_id)
            
            if "filter" in data and data["filter"] == "active_listing":
                property_listing = property_listing.filter(Q(status=1))
            elif "filter" in data and data["filter"] == "upcoming_listing":
                max_dt = timezone.now()
                # cst_timezone = pytz.timezone(settings.TIME_ZONE)
                # max_dt = max_dt.astimezone(cst_timezone)
                property_listing = property_listing.filter(property_auction__start_date__gte=max_dt)
            elif "filter" in data and data["filter"] == "closing_soon_listing":
                min_dt = timezone.now()
                max_dt = timezone.now() + timedelta(hours=48)
                # cst_timezone = pytz.timezone(settings.TIME_ZONE)
                # min_dt = max_dt.astimezone(cst_timezone)
                # max_dt = max_dt.astimezone(cst_timezone)
                property_listing = property_listing.filter(property_auction__end_date__range=(min_dt, max_dt))

            if "seller_status" in data and data["seller_status"] != "":
                seller_status = int(data["seller_status"])
                property_listing = property_listing.filter(Q(seller_status=seller_status))

            if "agent_id" in data and data["agent_id"] != "":
                agent_id = int(data["agent_id"])
                property_listing = property_listing.filter(Q(agent=agent_id))

            if "status" in data and data["status"] != "":
                status = int(data["status"])
                property_listing = property_listing.filter(Q(status=status))

            if "property_type" in data and data["property_type"] != "":
                property_type = int(data["property_type"])
                property_listing = property_listing.filter(Q(property_type=property_type))

            if "beds" in data and data["beds"] != "":
                beds = int(data["beds"])
                property_listing = property_listing.filter(Q(beds=beds))

            if "baths" in data and data["baths"] != "":
                baths = int(data["baths"])
                property_listing = property_listing.filter(Q(baths=baths))           


            property_listing = property_listing.order_by(F("ordering").asc(nulls_last=True))
            total = property_listing.count()
            property_listing = property_listing.only("id")[offset:limit]
            serializer = SellerDashboardPropertyListingSerializer(property_listing, many=True, context={"user_id": user_id})
            all_data = {"data": serializer.data, "total": total}
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SellerDashboardPropertyListingApiView(APIView):
    """
    Seller Dashboard property listing
    """
    # authentication_classes = [OAuth2Authentication, TokenAuthentication]
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "agent_id" in data and data['agent_id'] != "":
                agent_id = int(data["agent_id"])
            else:
                return Response(response.parsejson("agent_id is required", "", status=403))

            # --- Verify that user_id matches the token user ---
            auth_user = request.user  # user from Bearer token
            if int(agent_id) != auth_user.id:
                return Response(response.parsejson("Permission denied.", "", status=403))    

            user_id = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])

            source_page = None
            if "source_page" in data and data['source_page'] != "":
                source_page = data['source_page'].lower()   

            property_listing = PropertyListing.objects.filter(agent=agent_id).exclude(status=5)
            if source_page == "my_property":
                property_listing = property_listing.filter(children__isnull=True)

            if "status" in data and data["status"] != "":
                max_dt = timezone.now()
                # property_listing = property_listing.filter(property_auction__start_date__gte=max_dt)
                status = int(data["status"])
                if status == 1:
                    property_listing = property_listing.filter(Q(status=status) & Q(property_auction__start_date__lte=max_dt))
                elif status == 9:
                    property_listing = property_listing.filter(status__in=[8, 9])
                else:
                    property_listing = property_listing.filter(Q(status=status))
            
            if "filter_all" in data and data["filter_all"] != None and data["filter_all"] == "all":
                property_listing = property_listing.exclude(status=8)             

            if "my_auction" in data and data["my_auction"] != "" and int(data["my_auction"]) == 1:
                property_listing = property_listing.filter(seller_status=27)   

            if "seller_status" in data and data["seller_status"] != "":
                seller_status = int(data["seller_status"])
                if seller_status == 27:
                    property_listing = property_listing.filter(Q(seller_status=seller_status) & Q(status=1))
                else:
                    property_listing = property_listing.filter(Q(seller_status=seller_status)).exclude(status=8)
                
            if "filter" in data and data["filter"] == "coming_soon":
                # min_dt = timezone.now() - timedelta(hours=720)
                max_dt = timezone.now()
                property_listing = property_listing.filter(property_auction__start_date__gte=max_dt, status=1)

            if "filter" in data and data["filter"] == "closed_listing":
                property_listing = property_listing.filter(status__in=[8, 9])      


            # property_listing = property_listing.order_by(F("ordering").asc(nulls_last=True))
            property_listing = property_listing.order_by(F("id").desc(nulls_last=True))
            total = property_listing.count()
            property_listing = property_listing.only("id")[offset:limit]
            serializer = SellerDashboardPropertyListingSerializer(property_listing, many=True, context={"user_id": user_id})
            all_data = {"data": serializer.data, "total": total}
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class FrontPropertyListingApiView(APIView):
    """
    Front property listing
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            bidder_id = None
            if "bidder_id" in data and data['bidder_id'] != "":
                bidder_id = int(data['bidder_id'])

            user_id = None
            is_closing = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
            if "filter" in data and data["filter"] == "active_listing":
                status = [1]
            elif "filter" in data and data["filter"] == "recently_closed_listing":
                status = [9, 8]
            elif "filter" in data and data["filter"] == "won":
                status = [9]
            elif "filter" in data and data["filter"] == "closed_listing":
                status = [9]
                is_closing = True  
            elif "filter" in data and data["filter"] == "closed":
                status = [9]    
            else:
                if "filter_status" in data and data['filter_status'] != "":
                    status = [int(data['filter_status'])]
                else:          
                    status = [1]

            # property_listing = PropertyListing.objects.annotate(cnt=Count('id')).filter(domain=site_id, seller_status=27, status=status).exclude(status=5)
            property_listing = PropertyListing.objects.annotate(cnt=Count('id')).filter(domain=site_id, seller_status=27).exclude(status=5)
            if "filter" in data:
                if data["filter"] != "all":
                    if is_closing is not None and is_closing:
                        property_listing = property_listing.filter(Q(status__in=status) | Q(closing_status=16))
                    else:
                        property_listing = property_listing.filter(status__in=status)
            else:
                property_listing = property_listing.filter(status__in=status)

            if 'is_active_bid' in data and data['is_active_bid'] != "" and data['is_active_bid'] == 1:
                property_listing = property_listing.filter(bid_registration_property__user=user_id, bid_registration_property__is_approved=2)

            if bidder_id is not None:
                    property_listing = property_listing.filter(bid_property__user=bidder_id)
                
            # ---- Residential, Commercial and Land/Lots counts ----
            residential = property_listing.filter(property_asset=3, status=1).count()
            commercial = property_listing.filter(property_asset=2, status=1).count()
            land_lots = property_listing.filter(property_asset=1, status=1).count()

            if "city" in data and data["city"] != "":
                city = int(data["city"])
                property_listing = property_listing.filter(state=int(data['city']))

            if "municipality" in data and data["municipality"] != "":
                municipality = int(data["municipality"])
                property_listing = property_listing.filter(municipality=int(data['municipality']))

            if "district" in data and data["district"] != "":
                district = int(data["district"])
                property_listing = property_listing.filter(district=int(data['district']))

            if "construction_status" in data and data["construction_status"] != "":
                construction_status = int(data["construction_status"])
                property_listing = property_listing.filter(construction_status=int(data['construction_status'])) 

            if "property_type" in data and data["property_type"] != "":
                property_type = int(data["property_type"])
                property_listing = property_listing.filter(property_type=int(data['property_type']))        

            if 'property_for' in data and data['property_for'] != "":
                property_listing = property_listing.filter(property_for=int(data['property_for']))

            # -----------------Filter-------------------
            if "auction_id" in data and data["auction_id"] != "":
                auction_id = int(data["auction_id"])
                property_listing = property_listing.filter(Q(sale_by_type=auction_id))

            if "agent_id" in data and data["agent_id"] != "":
                agent_id = int(data["agent_id"])
                property_listing = property_listing.filter(Q(agent=agent_id))

            if "asset_id" in data and data["asset_id"] != "":
                asset_id = int(data["asset_id"])
                property_listing = property_listing.filter(Q(property_asset=asset_id))

            if "status" in data and data["status"] != "":
                status = int(data["status"])
                property_listing = property_listing.filter(Q(status=status))

            if "filter" in data and data["filter"] == "auctions_listing":
                property_listing = property_listing.filter(Q(property_auction__start_date__isnull=False) & Q(property_auction__end_date__isnull=False)).exclude(sale_by_type__in=[4, 7])
            elif "filter" in data and data["filter"] == "new_listing":
                min_dt = timezone.now() - timedelta(hours=720)
                # max_dt = timezone.now()
                property_listing = property_listing.filter(added_on__gte=min_dt)
            elif "filter" in data and data["filter"] == "traditional_listing":
                property_listing = property_listing.filter(sale_by_type=4)
            elif "filter" in data and data["filter"] == "recent_sold_listing":
                # min_dt = timezone.now() - timedelta(hours=720)
                # max_dt = timezone.now()
                # property_listing = property_listing.filter(date_sold__gte=min_dt)
                pass
            elif "filter" in data and data["filter"] == "recently_closed_listing":
                min_dt = timezone.now() - timedelta(hours=720)
                # max_dt = timezone.now()
                # property_listing = property_listing.filter(Q(status=8) | Q(date_sold__gte=min_dt))
                property_listing = property_listing.filter(property_auction__end_date__gte=min_dt)
            elif "filter" in data and data["filter"] == "featured":
                property_listing = property_listing.filter(is_featured=1)
            elif "filter" in data and data["filter"] == "coming_soon":
                # min_dt = timezone.now() - timedelta(hours=720)
                max_dt = timezone.now()
                cst_timezone = pytz.timezone(settings.TIME_ZONE)
                max_dt = max_dt.astimezone(cst_timezone)
                property_listing = property_listing.filter(property_auction__start_date__gte=max_dt)
            # elif "filter" in data and data["filter"] == "closed_listing":
            #     property_listing = property_listing.filter(status=9)
            elif "filter" in data and data["filter"] == "upcoming_listing":
                max_dt = timezone.now()
                # cst_timezone = pytz.timezone(settings.TIME_ZONE)
                # max_dt = max_dt.astimezone(cst_timezone)
                property_listing = property_listing.filter(property_auction__start_date__gt=max_dt)
            elif "filter" in data and data["filter"] == "closing_soon_listing":
                min_dt = timezone.now()
                max_dt = timezone.now() + timedelta(hours=48)
                # cst_timezone = pytz.timezone(settings.TIME_ZONE)
                # min_dt = max_dt.astimezone(cst_timezone)
                # max_dt = max_dt.astimezone(cst_timezone)
                property_listing = property_listing.filter(property_auction__end_date__range=(min_dt, max_dt), property_auction__start_date__lt=min_dt)
            elif "filter" in data and data["filter"] == "live":
                # bid_registration_property__user=user_id, bid_registration_property__is_approved=2
                min_dt = timezone.now()
                property_listing = property_listing.filter(Q(property_for=2) & (Q(property_auction__start_date__lte=min_dt) | Q(property_auction__end_date__gte=min_dt))) 
                #property_listing = property_listing.filter(Q(property_for=2) & (Q(property_auction__start_date__lte=min_dt) | Q(property_auction__end_date__gte=min_dt)) & Q(bid_registration_property__user=user_id) & Q(bid_registration_property__is_approved=2))

            elif "filter" in data and data["filter"] == "closed":
                property_listing = property_listing.filter(~Q(winner=user_id))

            elif "filter" in data and data["filter"] == "won":
                # property_listing = property_listing.filter(Q(winner=user_id) & Q(sold_price__gte=F('property_auction__reserve_amount')))
                property_listing = property_listing.filter(winner=user_id)

            elif "filter" in data and data["filter"] == "on_auction":
                property_listing = property_listing.filter(seller_status=27)             

            if "filter_asset_type" in data and data["filter_asset_type"] != "":
                property_listing = property_listing.filter(property_asset=int(data["filter_asset_type"]))
            
            if "filter_property_type" in data and data["filter_property_type"] != "":
                    property_listing = property_listing.filter(property_type=int(data["filter_property_type"])) 
            
            if "filter_auction_type" in data and data["filter_auction_type"] != "":
                property_listing = property_listing.filter(sale_by_type=int(data["filter_auction_type"]))
            
            if "filter_beds" in data and data["filter_beds"] != "":
                if isinstance(data["filter_beds"], list):
                    property_listing = property_listing.filter(beds__in=data["filter_beds"])
                else:
                    property_listing = property_listing.filter(beds=int(data["filter_beds"]))
            
            if "filter_baths" in data and data["filter_baths"] != "":
                if isinstance(data["filter_baths"], list):
                    property_listing = property_listing.filter(baths__in=data["filter_baths"])
                else:
                    property_listing = property_listing.filter(baths=int(data["filter_baths"]))  
            
            if "filter_mls_property" in data and data["filter_mls_property"] != "":
                property_listing = property_listing.filter(idx_property_id__icontains=data["filter_mls_property"])
            
            if "filter_min_price" in data and data["filter_min_price"] != "" and "filter_max_price" in data and data["filter_max_price"] != "":
                property_listing = property_listing.filter(Q(property_auction__start_price__gte=data["filter_min_price"]) & Q(property_auction__start_price__lte=data["filter_max_price"]))
            elif "filter_min_price" in data and data["filter_min_price"] != "" and "filter_max_price" in data and data["filter_max_price"] == "":
                property_listing = property_listing.filter(Q(property_auction__start_price__gte=data["filter_min_price"]))
            elif "filter_min_price" in data and data["filter_min_price"] == "" and "filter_max_price" in data and data["filter_max_price"] != "":
                property_listing = property_listing.filter(Q(property_auction__start_price__lte=data["filter_max_price"]))
            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                if search.isdigit():
                    property_listing = property_listing.filter(Q(id=search) | Q(postal_code__icontains=search) | Q(idx_property_id__icontains=search))
                else:
                    property_listing = property_listing.filter(Q(property_name__icontains=search) |
                                                               Q(property_name_ar__icontains=search) |
                                                               Q(community__icontains=search) |
                                                               Q(city__icontains=search) |
                                                               Q(state__state_name__icontains=search) |
                                                               Q(address_one__icontains=search) |
                                                               Q(postal_code__icontains=search) |
                                                               Q(property_asset__name__icontains=search) |
                                                               Q(sale_by_type__auction_type__icontains=search) |
                                                               Q(district__district_name__icontains=search) |
                                                               Q(idx_property_id__icontains=search))

            # -----------------Search text-------------------
            if 'search_text' in data and data['search_text'] != '':
                search_text = data['search_text'].strip()
                if search_text.isdigit():
                    property_listing = property_listing.filter(Q(id=search_text) | Q(postal_code__icontains=search_text) | Q(idx_property_id__icontains=search_text))
                else:
                    property_listing = property_listing.filter(Q(city__icontains=search_text) | Q(state__state_name__icontains=search_text) | Q(address_one__icontains=search_text) | Q(postal_code__icontains=search_text) | Q(property_asset__name__icontains=search_text) | Q(sale_by_type__auction_type__icontains=search_text) | Q(idx_property_id__icontains=search_text))

            # -----------------Sort------------------
            # if "short_by" in data and data["short_by"] != "" and "sort_order" in data and data["sort_order"] != "":
            if "short_by" in data and data["short_by"] != "":
                if data["short_by"].lower() == "auction_start" and data["sort_order"].lower() == "asc":
                    property_listing = property_listing.order_by(F("property_auction__start_date").asc(nulls_last=True))
                elif data["short_by"].lower() == "auction_start" and data["sort_order"].lower() == "desc":
                    property_listing = property_listing.order_by(F("property_auction__start_date").desc(nulls_last=True))
                elif data["short_by"].lower() == "auction_end" and data["sort_order"].lower() == "asc":
                    property_listing = property_listing.order_by(F("property_auction__end_date").asc(nulls_last=True))
                elif data["short_by"].lower() == "auction_end" and data["sort_order"].lower() == "desc":
                    property_listing = property_listing.order_by(F("property_auction__end_date").desc(nulls_last=True))
                elif data["short_by"].lower() == "highest_price":
                    property_listing = property_listing.order_by(F("property_auction__start_price").desc(nulls_last=True))
                elif data["short_by"].lower() == "lowest_price":
                    property_listing = property_listing.order_by(F("property_auction__start_price").asc(nulls_last=True))
                elif data["short_by"].lower() == "page_default":
                    property_listing = property_listing.order_by(F("ordering").asc(nulls_last=True))
                elif data["short_by"].lower() == "ending_soonest":
                    property_listing = property_listing.order_by(F("property_auction__end_date").asc(nulls_last=True))
                elif data["short_by"].lower() == "ending_latest":
                    property_listing = property_listing.order_by(F("property_auction__end_date").desc(nulls_last=True))
            else:
                property_listing = property_listing.order_by(F("ordering").asc(nulls_last=True))

            # ---- Radius Filter using ZIP code and radius ----
            if "radius" in data and data["radius"] != "" and "zip_code" in data and data["zip_code"] != "":
                radius = float(data["radius"])
                zipcode = int(data["zip_code"])
                lat = data["latitude"]
                lon = data["longitude"]
                property_listing = property_listing.filter(postal_code=data["zip_code"])
                #property_listing = property_listing.only("id")[offset:limit]
                property_listing = PropertyListing.filter_by_radius(property_listing, lat, lon, radius)
                total = len(property_listing)
                property_listing = property_listing[offset:limit]
            else:
                total = property_listing.count()
                property_listing = property_listing.only("id")[offset:limit]

            # total = property_listing.count()
            # property_listing = property_listing.only("id")[offset:limit]
            serializer = FrontPropertyListingSerializer(property_listing, many=True, context={"user_id": user_id})
            all_data = {"data": serializer.data, "residential": residential, "commercial": commercial, "land_lots": land_lots, "total": total}
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyDetailApiView(APIView):
    """
    Property detail
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required", "", status=403))

            user_id = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])

            property_listing = PropertyListing.objects.get(id=property_id, domain=site_id)
            serializer = PropertyDetailSerializer(property_listing, context=user_id)
            return Response(response.parsejson("Fetch Data.", serializer.data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SellerUploadPropertyMediaApiView(APIView):
    """
    Seller Upload Property Media ApiView
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user" in data and data['user'] != "":
                user = int(data['user'])
                users = Users.objects.filter(id=user, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user is required", "", status=403))

            if "doc_type" in data and data['doc_type'] != "":
                doc_type = int(data['doc_type'])
            else:
                return Response(response.parsejson("doc_type is required", "", status=403))

            if "bucket_name" in data and data['bucket_name'] != "":
                bucket_name = data['bucket_name']
            else:
                return Response(response.parsejson("bucket_name is required", "", status=403))

            media_document = request.FILES.getlist('media')
            res_document = save_document(site_id, user, doc_type, bucket_name, media_document, True)
            if res_document is not None and res_document:
                return Response(response.parsejson("Media uploaded.", res_document, status=201))
            else:
                return Response(response.parsejson("Something went wrong!", "", status=403))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class FrontPropertyDetailApiView(APIView):
    """
    Front Property detail
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required", "", status=403))

            user_id = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                
            property_listing = PropertyListing.objects.filter(id=property_id).exclude(status=5)
            if not property_listing.exists():
                return Response(response.parsejson("No property listing found with the given ID.", "", status=403))
            
            if "source_page" in data and data['source_page'] != "" and data['source_page'].lower() == 'auction':
                property_listing = property_listing.filter(seller_status__in=[28, 27])
            
            agent_id = None    
            if "agent_id" in data and data["agent_id"] != "":
                agent_id = int(data["agent_id"])
                property_listing = property_listing.filter(Q(agent=agent_id))

            if agent_id is not None:
                # --- Verify that user_id matches the token user ---
                auth_user = request.user  # user from Bearer token
                if int(agent_id) != auth_user.id:
                    return Response(response.parsejson("Permission denied.", "", status=403))

            property_listing = property_listing.first()
            serializer = FrontPropertyDetailSerializer(property_listing, context=user_id)
            return Response(response.parsejson("Fetch Data.", serializer.data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyStatusChangeApiView(APIView):
    """
    Property status change
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                # Translators: This message appears when site_id is empty
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4], status=1).first()
                if users is None:
                    return Response(response.parsejson("You are not authentic user to update property.", "", status=403))
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required", "", status=403))

            if "status" in data and data['status'] != "":
                status = data['status']
            else:
                # Translators: This message appears when status is empty
                return Response(response.parsejson("status is required", "", status=403))

            PropertyListing.objects.filter(id=property_id, domain=site_id).update(status_id=status)
            return Response(response.parsejson("Status changed successfully..", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyApprovalChangeApiView(APIView):
    """
    Property approval change
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                # Translators: This message appears when site_id is empty
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=site_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, user_type=2, status=1).first()
                    if users is None:
                        return Response(response.parsejson("You are not authentic user to update property.", "", status=403))
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required", "", status=403))

            if "is_approved" in data and data['is_approved'] != "":
                is_approved = data['is_approved']
            else:
                # Translators: This message appears when is_approved is empty
                return Response(response.parsejson("is_approved is required", "", status=403))

            PropertyListing.objects.filter(id=property_id, domain=site_id).update(is_approved=is_approved)
            try:
                #-------------Email--------------------
                if "is_approved" in data and int(data['is_approved']) == 1:
                    property_approved_status = 'approved'
                else:
                    property_approved_status = 'unapproved'
                property_detail = PropertyListing.objects.get(id=property_id)
                user_detail = Users.objects.get(id=property_detail.agent_id)
                property_user_name = user_detail.first_name
                agent_email = user_detail.email
                auction_type = property_detail.sale_by_type.auction_type
                auction_data = PropertyAuction.objects.get(property=property_id)
                start_price = auction_data.start_price
                upload = None
                upload = PropertyUploads.objects.filter(property=property_id, upload_type=1).first()
                web_url = settings.FRONT_BASE_URL
                image_url = web_url+'/static/admin/images/property-default-img.png'
                if upload is not None:
                    image = upload.upload.doc_file_name
                    bucket_name = upload.upload.bucket_name
                    image_url = 'https://realtyonegroup.s3.us-west-1.amazonaws.com/'+bucket_name+'/'+image
                subdomain_url = settings.SUBDOMAIN_URL
                domain_name = network.domain_name


                domain_url = subdomain_url.replace("###", domain_name)+"admin/listing/"
                notif_type = 2
                if property_detail.sale_by_type_id == 7:
                    domain_url = domain_url + "?auction_type=highest%20offer"
                    notif_type = 6
                elif property_detail.sale_by_type_id == 4:
                    notif_type = 4
                    domain_url = domain_url + "?auction_type=traditional%20offer"
                elif property_detail.sale_by_type_id == 6:
                    notif_type = 7
                    domain_url = domain_url + "?auction_type=live%20offer"
                elif property_detail.sale_by_type_id == 2:
                    notif_type = 8
                    domain_url = domain_url + "?auction_type=insider%20auction"

                property_address = property_detail.address_one
                property_city = property_detail.city
                property_state = property_detail.state.state_name
                asset_type = property_detail.property_asset.name
                template_data = {"domain_id": site_id, "slug": "listing_approval"}
                extra_data = {
                    'property_user_name': property_user_name,
                    'property_approved_status': property_approved_status,
                    'web_url': web_url,
                    'property_image': image_url,
                    'property_address': property_address,
                    'property_city': property_city,
                    'property_state': property_state,
                    'auction_type': auction_type,
                    'asset_type': asset_type,
                    'starting_price': "$" + number_format(start_price) if not auction_data.un_priced else 'Unpriced',
                    'starting_bid_offer': 'Starting Bid' if property_detail.sale_by_type_id in [1, 6] else "Asking Price",
                    'dashboard_link': domain_url,
                    "domain_id": site_id
                }
                compose_email(to_email=[agent_email], template_data=template_data, extra_data=extra_data)
            except Exception as exp:
                pass
            # send notif to agent for approved or not approved
            try:
                prop_name = property_detail.address_one if property_detail.address_one else property_detail.id
                # check who approved/not approved
                if is_approved and int(is_approved) == 1:
                    content = "Your listing has been approved! <span>[" + prop_name + "]</span>"
                    owner_content = "You approved a listing! <span>[" + prop_name + "]</span>"
                else:
                    content = "Your listing has been made Unapproved! <span>[" + prop_name + "]</span>"
                    owner_content = "You Unapproved a listing! <span>[" + prop_name + "]</span>"
                if property_detail.agent_id != user_id:
                    # send notif to agent person for approved/not approved
                    add_notification(
                        site_id,
                        "Listing Approval",
                        content,
                        user_id=property_detail.agent_id,
                        added_by=property_detail.agent_id,
                        notification_for=2,
                        property_id=property_id,
                        notification_type=notif_type
                    )
                #  add notif to owner for for approval/not approval
                add_notification(
                    site_id,
                    "Listing Approval",
                    owner_content,
                    user_id=user_id,
                    added_by=user_id,
                    notification_for=2,
                    property_id=property_id,
                    notification_type=notif_type
                )

            except Exception as e:
                pass
            return Response(response.parsejson("Approval changed successfully..", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AllPropertyDeleteApiView(APIView):
    """
    Property approval change
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            # data = request.data
            # delete_table = [
            #     PropertySubtype, PropertyTermAccepted, PropertyOccupiedBy, PropertyOwnership, PropertyPossession, PropertyStyle, PropertyCooling, PropertyStories, PropertyHeating,
            #     PropertyElectric, PropertyGas, PropertyRecentUpdates, PropertyWater, PropertySecurityFeatures, PropertySewer, PropertyTaxExemptions, PropertyZoning, PropertyAmenities,
            #     PropertyKitchenFeatures, PropertyAppliances, PropertyFlooring, PropertyWindows, PropertyBedroomFeatures, PropertyOtherRooms, PropertyBathroomFeatures, PropertyOtherFeatures,
            #     PropertyMasterBedroomFeatures, PropertyFireplaceType, PropertyBasementFeatures, PropertyHandicapAmenities, PropertyConstruction, PropertyGarageParking, PropertyExteriorFeatures,
            #     PropertyGarageFeatures, PropertyRoof, PropertyOutbuildings, PropertyFoundation, PropertyLocationFeatures, PropertyFence, PropertyRoadFrontage, PropertyPool,
            #     PropertyPropertyFaces, PropertyLeaseType, PropertyTenantPays, PropertyInclusions, PropertyBuildingClass, PropertyInteriorFeatures, PropertyMineralRights, PropertyEasements,
            #     PropertySurvey, PropertyUtilities, PropertyImprovements, PropertyTopography, PropertyWildlife, PropertyFish, PropertyIrrigationSystem, PropertyRecreation, PropertyAuction, PropertyUploads,
            #     PropertyListing
            # ]
            # for table in delete_table:
            #     table.objects.all().delete()
            return Response(response.parsejson("Delete table successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AdminPropertyStatusChangeApiView(APIView):
    """
    Admin property status change
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type=3, status=1).first()
                if users is None:
                    return Response(response.parsejson("You are not authentic user to update property.", "", status=403))
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required", "", status=403))

            if "status" in data and data['status'] != "":
                status = data['status']
            else:
                # Translators: This message appears when status is empty
                return Response(response.parsejson("status is required", "", status=403))

            PropertyListing.objects.filter(id=property_id).update(status_id=status)
            return Response(response.parsejson("Status changed successfully..", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AdminPropertyApprovalChangeApiView(APIView):
    """
    Admin property approval change
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type=3, status=1).first()
                if users is None:
                    return Response(response.parsejson("You are not authentic user to update property.", "", status=403))
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required", "", status=403))

            if "is_approved" in data and data['is_approved'] != "":
                is_approved = data['is_approved']
            else:
                # Translators: This message appears when is_approved is empty
                return Response(response.parsejson("is_approved is required", "", status=403))
            
            try:
                property_detail = PropertyListing.objects.get(id=property_id)
                broker_data = Users.objects.get(site_id=property_detail.domain_id)
                prop_name = property_detail.address_one if property_detail.address_one else property_detail.id
                if is_approved and int(is_approved) == 1:
                    property_approved_status = "approved"
                    content = "Your listing has been approved! <span>[" + prop_name + "]</span>"
                    owner_content = "Admin approved a listing! <span>[" + prop_name + "]</span>"
                else:
                    property_approved_status = 'unapproved'
                    content = "Your listing has been made Unapproved! <span>[" + prop_name + "]</span>"
                    owner_content = "Admin Unapproved a listing! <span>[" + prop_name + "]</span>"
                # send email to agent for approval/not approval
                agent_data = property_detail.agent
                property_user_name = agent_data.first_name
                agent_email = agent_data.email
                auction_type = property_detail.sale_by_type.auction_type
                auction_data = PropertyAuction.objects.get(property=property_id)
                start_price = auction_data.start_price
                upload = None
                upload = PropertyUploads.objects.filter(property=property_id, upload_type=1).first()
                web_url = settings.FRONT_BASE_URL
                image_url = web_url+'/static/admin/images/property-default-img.png'
                if upload is not None:
                    image = upload.upload.doc_file_name
                    bucket_name = upload.upload.bucket_name
                    image_url = 'https://realtyonegroup.s3.us-west-1.amazonaws.com/'+bucket_name+'/'+image
                subdomain_url = settings.SUBDOMAIN_URL
                network = NetworkDomain.objects.filter(id=property_detail.domain_id, is_active=1).first()
                domain_name = network.domain_name

                domain_url = subdomain_url.replace("###", domain_name)+"admin/listing/"
                notif_type =  2
                if property_detail.sale_by_type_id == 7:
                    notif_type = 6
                    domain_url = domain_url + "?auction_type=highest%20offer"
                elif property_detail.sale_by_type_id == 4:
                    notif_type = 4
                    domain_url = domain_url + "?auction_type=traditional%20offer"
                elif property_detail.sale_by_type_id == 6:
                    notif_type = 7
                    domain_url = domain_url + "?auction_type=live%20offer"

                property_address = property_detail.address_one
                property_city = property_detail.city
                property_state = property_detail.state.state_name
                asset_type = property_detail.property_asset.name
                template_data = {"domain_id": property_detail.domain_id, "slug": "listing_approval"}
                extra_data = {
                    'property_user_name': property_user_name,
                    'property_approved_status': property_approved_status,
                    'web_url': web_url,
                    'property_image': image_url,
                    'property_address': property_address,
                    'property_city': property_city,
                    'property_state': property_state,
                    'auction_type': auction_type,
                    'asset_type': asset_type,
                    'starting_price': "$" + number_format(start_price) if not auction_data.un_priced else 'Unpriced',
                    'starting_bid_offer': 'Starting Bid' if property_detail.sale_by_type_id in [1, 6] else "Asking Price",
                    'dashboard_link': domain_url,
                    "domain_id": property_detail.domain_id
                }
                compose_email(to_email=[agent_email], template_data=template_data, extra_data=extra_data)
                # check if owner and aget not same then send email to broker
                if property_detail.agent_id != broker_data.id:
                    property_user_name = broker_data.first_name 
                    broker_email = broker_data.email
                    extra_data = {'property_user_name': property_user_name, 'property_approved_status': property_approved_status, 'web_url': web_url, 'property_image': image_url, 'property_address': property_address, 'property_city': property_city, 'property_state': property_state, 'auction_type': auction_type, 'asset_type': asset_type, 'starting_price': start_price, 'dashboard_link': domain_url, "domain_id": property_detail.domain_id}
                    compose_email(to_email=[broker_email], template_data=template_data, extra_data=extra_data)
                
                #  add notif to owner for for approval/not approval
                add_notification(
                    property_detail.domain_id,
                    "Listing Approval",
                    owner_content,
                    user_id=broker_data.id,
                    added_by=user_id,
                    notification_for=2,
                    property_id=property_id,
                    notification_type=notif_type
                )
                # check if owner and agent not same
                if property_detail.agent_id != broker_data.id:
                    # send notif to agent person for approved/not approved
                    add_notification(
                        property_detail.domain_id,
                        "Listing Approval",
                        content,
                        user_id=property_detail.agent_id,
                        added_by=user_id,
                        notification_for=2,
                        property_id=property_id,
                        notification_type=notif_type
                    )
            except Exception as e:
                pass

            PropertyListing.objects.filter(id=property_id).update(is_approved=is_approved)
            return Response(response.parsejson("Approval changed successfully..", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AddPropertyViewApiView(APIView):
    """
    Add property view
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                # Translators: This message appears when site_id is empty
                return Response(response.parsejson("site_id is required.", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                # Translators: This message appears when user_id is empty
                # return Response(response.parsejson("user_id is required.", "", status=403))
                user_id = None

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
                property_data = PropertyListing.objects.get(id=property_id)
                if property_data is None:
                    return Response(response.parsejson("Property not exist.", "", status=403))
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required", "", status=403))
            
            view_data = None
            if user_id is not None:
                view_data = PropertyView.objects.filter(domain=site_id, property=property_id, user=user_id).first()
                
            if view_data is None:
                view_data = PropertyView()
                view_data.domain_id = site_id
                view_data.property_id = property_id
                view_data.user_id = user_id
                view_data.save()
            return Response(response.parsejson("Save successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SubdomainPropertySuggestionApiView(APIView):
    """
    Subdomain property suggestion
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "search" in data and data['search'] != "":
                search = data['search']
            else:
                return Response(response.parsejson("search is required", "", status=403))
            searched_data = []

            property_listing = PropertyListing.objects.annotate(data=F('address_one')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('city')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('state__state_name')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('property_asset__name')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('sale_by_type__auction_type')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=Concat('agent__user_business_profile__first_name', V(' '), 'agent__user_business_profile__last_name')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('postal_code')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=Concat('address_one', V(', '), 'city', V(', '), 'state__state_name', V(' '), 'postal_code', output_field=CharField())).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            searched_data = [i['data'] for i in searched_data]
            searched_data = list(set(searched_data))
            return Response(response.parsejson("Fetch data.", searched_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class FrontPropertySuggestionApiView(APIView):
    """
    Front property suggestion
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "search" in data and data['search'] != "":
                search = data['search']
            else:
                return Response(response.parsejson("search is required", "", status=403))
            searched_data = []

            property_listing = PropertyListing.objects.annotate(data=F('address_one')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('city')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('state__state_name')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('property_asset__name')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('sale_by_type__auction_type')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('postal_code')).filter(domain=site_id, data__icontains=search).exclude(status=5).values("data")
            searched_data = searched_data + list(property_listing)

            searched_data = [i['data'] for i in searched_data]
            searched_data = list(set(searched_data))
            return Response(response.parsejson("Fetch data.", searched_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class DeletePropertyApiView(APIView):
    """
    Delete property
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=site_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=site_id, network_user__is_agent=1, network_user__status=1, status=1, user_type=2).first()
                    if users is None:
                        return Response(response.parsejson("You are not authorised to delete property.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required", "", status=403))

            PropertyListing.objects.filter(id=property_id, domain=site_id).update(status=5)
            return Response(response.parsejson("Property deleted successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SavePropertySettingApiView(APIView):
    """
    Save property setting
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
                data['domain'] = site_id
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5, 6], status=1).first()
                if users is None:
                    return Response(response.parsejson("You are not authorised to update setting.", "", status=403))
                data['user'] = user_id
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            # --- Verify that user_id matches the token user ---
            auth_user = request.user  # user from Bearer token
            if int(user_id) != auth_user.id:
                return Response(response.parsejson("Permission denied.", "", status=403))    

            if "property_id" in data and data['property_id'] != "":
                data['property'] = int(data['property_id'])
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required", "", status=403))

            # if "time_flash" in data and data['time_flash'] != "":
            #     time_flash = int(data['time_flash'])
            # else:
            #     return Response(response.parsejson("time_flash is required", "", status=403))

            # if "auto_approval" in data and int(data['auto_approval']) == 1:
            #     if "bid_limit" in data and data['bid_limit'] != "":
            #         bid_limit = int(data['bid_limit'])
            #         data['bid_limit'] = bid_limit
            #     else:
            #         return Response(response.parsejson("bid_limit is required", "", status=403))
            # else:
            #     data['bid_limit'] = None

            # if "is_deposit_required" in data and data['is_deposit_required'] != "":
            #     is_deposit_required = int(data['is_deposit_required'])
            # else:
            #     return Response(response.parsejson("is_deposit_required is required", "", status=403))

            # if "deposit_amount" in data and data['deposit_amount'] != "":
            #     deposit_amount = data['deposit_amount']
            # elif is_deposit_required == 1:
            #     return Response(response.parsejson("deposit_amount is required", "", status=403))    

            property_settings = PropertySettings.objects.filter(domain=site_id, property=int(data['property_id']), status=1, is_agent=0, is_broker=0).first()
            data['status'] = 1
            serializer = SavePropertySettingSerializer(property_settings, data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                copy_errors = serializer.errors.copy()
                return Response(response.parsejson(copy_errors, "", status=403))
            property_auction_data = PropertyAuction.objects.filter(property=property_id).last()
            auction_id = property_auction_data.id if property_auction_data is not None else ""
            auction_type = property_auction_data.auction_id if property_auction_data is not None else ""
            all_data = {"property_id": property_id, "auction_id": auction_id, "auction_type": auction_type}
            return Response(response.parsejson("Setting save successfully.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SaveGlobalPropertySettingApiView(APIView):
    """
    Save global property setting
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
                data['domain'] = site_id
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4], status=1).first()
                if users is None:
                    return Response(response.parsejson("You are not authorised to update setting.", "", status=403))
                setting_type = "broker"
                # if users is None:
                #     users = Users.objects.filter(id=user_id, network_user__domain=site_id, network_user__is_agent=1, network_user__status=1, status=1, user_type=2).first()
                #     setting_type = "agent"
                #     if users is None:
                #         return Response(response.parsejson("You are not authorised to update setting.", "", status=403))
                data['user'] = user_id
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            # --- Verify that user_id matches the token user ---
            auth_user = request.user  # user from Bearer token
            if int(user_id) != auth_user.id:
                return Response(response.parsejson("Permission denied.", "", status=403))    

            # if "time_flash" in data and data['time_flash'] != "":
            #     time_flash = int(data['time_flash'])
            # else:
            #     return Response(response.parsejson("time_flash is required", "", status=403))

            # if "auto_approval" in data and int(data['auto_approval']) == 1:
            #     if "bid_limit" in data and data['bid_limit'] != "":
            #         bid_limit = int(data['bid_limit'])
            #         data['bid_limit'] = bid_limit
            #     else:
            #         return Response(response.parsejson("bid_limit is required", "", status=403))
            # else:
            #     data['bid_limit'] = None

            # if "is_deposit_required" in data and data['is_deposit_required'] != "":
            #     is_deposit_required = int(data['is_deposit_required'])
            # else:
            #     return Response(response.parsejson("is_deposit_required is required", "", status=403))

            # if "deposit_amount" in data and data['deposit_amount'] != "":
            #     deposit_amount = data['deposit_amount']
            # elif is_deposit_required == 1:
            #     return Response(response.parsejson("deposit_amount is required", "", status=403))    

            autobid = 0
            if "autobid" in data and data['autobid'] != "":
                autobid = data['autobid']

            if "autobid_setup" in data and data['autobid_setup'] != "":
                autobid_setup = data['autobid_setup']
            elif autobid == 1:
                return Response(response.parsejson("autobid_setup is required", "", status=403))

            if "service_fee" in data and data['service_fee'] != "":
                service_fee = float(data['service_fee'])
            else:
                return Response(response.parsejson("service_fee is required", "", status=403))

            if "auction_fee" in data and data['auction_fee'] != "":
                auction_fee = int(data['auction_fee'])
            else:
                return Response(response.parsejson("auction_fee is required", "", status=403))        

            data['status'] = 1
            data['property'] = None
            if setting_type == "broker":
                data['is_broker'] = 1
                data['is_agent'] = 0
                property_settings = PropertySettings.objects.filter(domain=site_id, is_agent=0, is_broker=1, status=1).first()
            else:
                data['is_broker'] = 0
                data['is_agent'] = 1
                property_settings = PropertySettings.objects.filter(domain=site_id, is_agent=1, is_broker=0, status=1).first()
            serializer = SavePropertySettingSerializer(property_settings, data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                copy_errors = serializer.errors.copy()
                return Response(response.parsejson(copy_errors, "", status=403))
            return Response(response.parsejson("Setting save successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class GetPropertySettingApiView(APIView):
    """
    Get property setting
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            property_id = None
            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])

            is_broker = 0
            if "is_broker" in data and data['is_broker'] != "":
                is_broker = int(data['is_broker'])

            is_agent = 0
            if "is_agent" in data and data['is_agent'] != "":
                is_agent = int(data['is_agent'])

            property_settings = PropertySettings.objects.get(domain=site_id, property=property_id, is_broker=is_broker, is_agent=is_agent, status=1)
            serializer = PropertySettingSerializer(property_settings)
            return Response(response.parsejson("Fetch data.", serializer.data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class RegisterPropertyInterestApiView(APIView):
    """
    Register property Interest
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            data['site_id'] = 3

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
                data['domain'] = site_id
            else:
                return Response(response.parsejson("site_id is required", "", status=403))
        
            if "user" in data and data['user'] != "":
                user = int(data['user'])
                users = Users.objects.filter(id=user, status=1).first()
                if users is None:
                    return Response(response.parsejson("User Not Exist.", "", status=201))
            else:
                return Response(response.parsejson("user is required", "", status=403))

            if "property" in data and data['property'] != "":
                property = int(data['property'])
            else:
                return Response(response.parsejson("property is required", "", status=403))
            
            register_interest_property = PropertyRegisterInterest.objects.filter(property=property, user=user).first()
            if register_interest_property is None:
                serializer = RegisterPropertyInterestSerializer(data=data)
                if serializer.is_valid():
                    data = serializer.save()
                    property_detail = PropertyListing.objects.filter(id=property).first()
                    user_detail = Users.objects.filter(id=user).first()
                    template_data = {"domain_id": site_id, "slug": "register_property_interest"}

                    upload = PropertyUploads.objects.filter(property=property, upload_type=1).first()
                    web_url = network.domain_url
                    image_url = network.domain_url+'static/images/property-default-img.png'
                    if upload is not None:
                        image = upload.upload.doc_file_name
                        bucket_name = upload.upload.bucket_name
                        image_url = settings.AZURE_BLOB_URL + str(bucket_name)+ '/' +str(image)

                    property_state = property_detail.state.state_name
                    property_type = property_detail.property_type.property_type
                    property_name = property_detail.property_name
                    community = property_detail.community    
                    decorator_url = property_detail.property_name.lower() + " " + property_detail.country.country_name.lower()
                    decorator_url = re.sub(r"\s+", '-', decorator_url)
                    redirect_url = network.domain_react_url+"property/detail/"+str(property)+"/"+decorator_url

                    extra_data = {
                            'property_name': property_name,
                            'user_name': f"{user_detail.first_name} {user_detail.last_name}" if user_detail.last_name else user_detail.first_name,
                            'property_state': property_state,
                            'community': community,
                            'property_type': property_type,
                            'property_image': image_url,
                            'web_url': web_url,
                            'dashboard_link': redirect_url,
                            "domain_id": site_id,
                        }
                    compose_email(to_email=[user_detail.email], template_data=template_data, extra_data=extra_data)

                    prop_name = property_detail.property_name 
                    prop_name_ar = property_detail.property_name_ar                    
                    notification_extra_data = {'image_name': 'heart-icon.svg', 'property_name': prop_name, 'property_name_ar': prop_name_ar, 'redirect_url': redirect_url}
                    notification_extra_data['app_content'] = 'Listing '+property_name+' added to interest!'
                    notification_extra_data['app_content_ar'] = 'قائمة '+prop_name_ar+' تمت إضافته إلى الاهتمام!'
                    notification_extra_data['app_screen_type'] = 1
                    notification_extra_data['app_notification_image'] = 'heart-icon.png'
                    notification_extra_data['property_id'] = property
                    notification_extra_data['app_notification_button_text'] = 'View'
                    notification_extra_data['app_notification_button_text_ar'] = 'منظر'
                    template_slug = "register_property_interest"
                    add_notification(
                        site_id,
                        user_id=user,
                        added_by=user,
                        notification_for=1,
                        template_slug=template_slug,
                        extra_data=notification_extra_data
                    )
                else:
                    copy_errors = serializer.errors.copy()
                    return Response(response.parsejson(copy_errors, "", status=403))
            else:
                register_interest_property.delete()
            
            return Response(response.parsejson("Interest saved successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))
        

class MakeFavouritePropertyApiView(APIView):
    """
    Make favourite property
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain" in data and data['domain'] != "":
                site_id = int(data['domain'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "user" in data and data['user'] != "":
                user_id = int(data['user'])
                users = Users.objects.filter(id=user_id, status=1).first()
                if users is None:
                    return Response(response.parsejson("User Not Exist.", "", status=201))
            else:
                return Response(response.parsejson("user is required", "", status=403))

            if "property" in data and data['property'] != "":
                property_id = int(data['property'])
            else:
                return Response(response.parsejson("property is required", "", status=403))

            favourite_property = FavouriteProperty.objects.filter(domain=site_id, property=property_id, user=user_id).first()
            if favourite_property is None:
                serializer = FavouritePropertySerializer(data=data)
                if serializer.is_valid():
                    data = serializer.save()
                    content = '<div class="icon orange-bg"><img src="img/heart-icon-r.svg" alt="Reload Icon"></div><div class="text"><h6>Listing added to favorites['+data.property.property_name+']!</h6></div>'
                    notification_extra_data = {'image_name': 'heart-icon-r.svg', 'property_name': data.property.property_name, 'property_name_ar': data.property.property_name_ar}
                    notification_extra_data['app_content'] = 'Listing added to favorites <b>'+ data.property.property_name + '</b>'
                    notification_extra_data['app_content_ar'] = 'تمت إضافة القائمة إلى المفضلة '+ ' <b>' +data.property.property_name_ar + '</b>'
                    notification_extra_data['app_screen_type'] = None
                    notification_extra_data['app_notification_image'] = 'heart-icon-r.png'
                    notification_extra_data['app_notification_button_text'] = None
                    notification_extra_data['app_notification_button_text_ar'] = None
                    notification_extra_data['property_id'] = data.property_id
                    template_slug = "make_favourite"
                else:
                    copy_errors = serializer.errors.copy()
                    return Response(response.parsejson(copy_errors, "", status=403))
            else:
                # content = '<div class="icon orange-bg"><img src="img/heart-icon.svg" alt="Reload Icon"></div><div class="text"><h6>Listing removed from favorites['+favourite_property.property.property_name+']!</h6></div>'
                notification_extra_data = {'image_name': 'heart-icon.svg', 'property_name': favourite_property.property.property_name, 'property_name_ar': favourite_property.property.property_name_ar}
                notification_extra_data['app_content'] = 'Listing removed from favorites <b>'+ favourite_property.property.property_name + '</b>'
                notification_extra_data['app_content_ar'] = 'تمت إزالة القائمة من المفضلة '+ ' <b>' +favourite_property.property.property_name_ar + '</b>'
                notification_extra_data['app_screen_type'] = None
                notification_extra_data['app_notification_image'] = 'heart-icon.png'
                notification_extra_data['app_notification_button_text'] = None
                notification_extra_data['app_notification_button_text_ar'] = None
                notification_extra_data['property_id'] = favourite_property.property_id
                template_slug = "remove_favourite"
                favourite_property.delete()

            add_notification(
                site_id,
                user_id=user_id,
                added_by=user_id,
                notification_for=1,
                template_slug=template_slug,
                extra_data=notification_extra_data
            )
            return Response(response.parsejson("Save data successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class FavouritePropertyListingApiView(APIView):
    """
    Favourite property listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "domain" in data and data['domain'] != "":
                domain = int(data['domain'])
                network = NetworkDomain.objects.filter(id=domain, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "user" in data and data['user'] != "":
                user = int(data['user'])
                users = Users.objects.filter(id=user, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=201))
            else:
                return Response(response.parsejson("user is required", "", status=403))

            favourite_property = FavouriteProperty.objects.filter(domain=domain, user=user).exclude(property__status=5)
            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                if search.isdigit():
                    favourite_property = favourite_property.filter(Q(id=search))
                else:
                    favourite_property = favourite_property.annotate(property_name=Concat('property__city', V(', '), 'property__state__state_name', V(' '), 'property__postal_code', output_field=CharField())).filter(Q(property__address_one__icontains=search) | Q(property__city__icontains=search) | Q(property__state__state_name__icontains=search) | Q(property__sale_by_type__auction_type__icontains=search) | Q(property__property_asset__name__icontains=search) | Q(property_name__icontains=search))

            # if "filter" in data and data['filter'] != "" and data['filter'] == "under_review":
            #     favourite_property = favourite_property.filter(Q(property__seller_status=24))
            # elif "filter" in data and data['filter'] != "" and data['filter'] == "ready_for_publish":
            #     favourite_property = favourite_property.filter(Q(property__seller_status=28))
            # elif "filter" in data and data['filter'] != "" and data['filter'] == "on_auction":
            #     favourite_property = favourite_property.filter(Q(property__seller_status=27)) 
            if "filter" in data and data["filter"] == "under_review":
                favourite_property = favourite_property.filter(Q(property__seller_status=24) & Q(property__status=1))
            elif "filter" in data and data["filter"] == "ready_for_publish":
                favourite_property = favourite_property.filter(Q(property__seller_status=28) & Q(property__status=1))
            elif "filter" in data and data["filter"] == "on_auction":
                favourite_property = favourite_property.filter(Q(property__seller_status=27) & Q(property__status=1))
            elif "filter" in data and data["filter"] == "active":
                favourite_property = favourite_property.filter(Q(property__status=1))
            elif "filter" in data and data["filter"] == "upcoming_listing":
                max_dt = timezone.now()
                favourite_property = favourite_property.filter(Q(property__property_auction__start_date__gt=max_dt) & Q(property__status=1))
            elif "filter" in data and data["filter"] == "closing_soon_listing":
                min_dt = timezone.now()
                max_dt = timezone.now() + timedelta(hours=48)
                favourite_property = favourite_property.filter(Q(property__property_auction__end_date__range=(min_dt, max_dt)) & Q(property__property_auction__start_date__lt=min_dt) & Q(property__status=1))
            elif "filter" in data and data["filter"] == "recently_closed_listing":
                min_dt = timezone.now() - timedelta(hours=720)
                # max_dt = timezone.now()
                # favourite_property = favourite_property.filter(Q(property__date_sold__gte=min_dt) & Q(property__status=9))  
                favourite_property = favourite_property.filter(property__property_auction__end_date__gte=min_dt, property__status__in=[8, 9])      
            total = favourite_property.count()
            favourite_property = favourite_property.order_by("-id").only("id")[offset: limit]
            serializer = FavouritePropertyListingSerializer(favourite_property, many=True)
            all_data = {
                "data": serializer.data,
                "total": total
            }
            return Response(response.parsejson("Fetch data", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class DeleteFavouritePropertyApiView(APIView):
    """
    Delete favourite property
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain" in data and data['domain'] != "":
                domain = int(data['domain'])
                network = NetworkDomain.objects.filter(id=domain, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "user" in data and data['user'] != "":
                user = int(data['user'])
                users = Users.objects.filter(id=user, site=domain, status=1, user_type__in=[1, 2]).first()
                if users is None:
                    users = Users.objects.filter(id=user, status=1, network_user__domain=domain, user_type__in=[1, 2, 4]).first()
                    if users is None:
                        return Response(response.parsejson("Not site user.", "", status=201))
            else:
                return Response(response.parsejson("user is required", "", status=403))

            if "property" in data and data['property'] != "":
                property_id = int(data['property'])
            else:
                return Response(response.parsejson("property is required", "", status=403))
            
            try:
                property_details = PropertyListing.objects.get(id=property_id)
                prop_name = property_details.address_one if property_details.address_one else property_details.id
                content = "Listing removed from favorites! <span>[" + prop_name + "]</span>"
                add_notification(
                    domain,
                    "Listing Favorite",
                    content,
                    user_id=user,
                    added_by=user,
                    notification_for=1,
                    property_id=property_id
                )
            except:
                pass

            FavouriteProperty.objects.filter(domain=domain, user=user, property=property_id).delete()
            return Response(response.parsejson("Data deleted successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class FavouriteSuggestionApiView(APIView):
    """
    Front property suggestion
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
            else:
                return Response(response.parsejson("user_id is required", "", status=403))

            if "search" in data and data['search'] != "":
                search = data['search']
            else:
                return Response(response.parsejson("search is required", "", status=403))
            searched_data = []

            property_listing = FavouriteProperty.objects.annotate(data=F('property__address_one')).filter(domain=site_id, user=user_id, data__icontains=search).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = FavouriteProperty.objects.annotate(data=F('property__city')).filter(domain=site_id, user=user_id, data__icontains=search).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = FavouriteProperty.objects.annotate(data=F('property__state__state_name')).filter(domain=site_id, user=user_id, data__icontains=search).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = FavouriteProperty.objects.annotate(data=F('property__sale_by_type__auction_type')).filter(domain=site_id, user=user_id, data__icontains=search).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = FavouriteProperty.objects.annotate(data=F('property__postal_code')).filter(domain=site_id, user=user_id, data__icontains=search).values("data")
            searched_data = searched_data + list(property_listing)

            property_listing = FavouriteProperty.objects.annotate(data=F('property__property_asset__name')).filter(domain=site_id, user=user_id, data__icontains=search).values("data")
            searched_data = searched_data + list(property_listing)

            searched_data = [i['data'] for i in searched_data]
            searched_data = list(set(searched_data))
            return Response(response.parsejson("Fetch data.", searched_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class MakeWatchPropertyApiView(APIView):
    """
    Make watch property
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain" in data and data['domain'] != "":
                site_id = int(data['domain'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "user" in data and data['user'] != "":
                user_id = int(data['user'])
                users = Users.objects.filter(id=user_id, site=site_id, status=1, user_type__in=[1, 2]).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, status=1, network_user__domain=site_id,
                                                 user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("Not site user.", "", status=201))
            else:
                return Response(response.parsejson("user is required", "", status=403))

            if "property" in data and data['property'] != "":
                property_id = int(data['property'])
            else:
                return Response(response.parsejson("property is required", "", status=403))

            watch_property = WatchProperty.objects.filter(domain=site_id, property=property_id, user=user_id).first()
            if watch_property is None:
                serializer = WatchPropertySerializer(data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    copy_errors = serializer.errors.copy()
                    return Response(response.parsejson(copy_errors, "", status=403))
            else:
                watch_property.delete()
            return Response(response.parsejson("Save data successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class ScheduleTourApiView(APIView):
    """
    Schedule tour
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain" in data and data['domain'] != "":
                site_id = int(data['domain'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "user" in data and data['user'] != "":
                user_id = int(data['user'])
                users = Users.objects.filter(id=user_id, site=site_id, status=1, user_type=2).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, status=1, network_user__status=1, network_user__domain=site_id).first()
                    if users is None:
                        return Response(response.parsejson("Not site user.", "", status=201))
            else:
                return Response(response.parsejson("user is required", "", status=403))

            if "property" in data and data['property'] != "":
                property_id = int(data['property'])
            else:
                return Response(response.parsejson("property is required", "", status=403))

            if "schedule_date" in data and data['schedule_date'] != "":
                schedule_date = data['schedule_date']
            else:
                return Response(response.parsejson("schedule_date is required", "", status=403))

            if "tour_type" not in data or data['tour_type'] == "":
                return Response(response.parsejson("tour_type is required", "", status=403))
            elif int(data['tour_type']) == 1:
                tour_type = 'In-Person'
            else:
                tour_type = 'Video Chat'
                    
            if "first_name" not in data or data['first_name'] == "":
                return Response(response.parsejson("first_name is required", "", status=403))

            if "last_name" not in data or data['last_name'] == "":
                return Response(response.parsejson("last_name is required", "", status=403))

            if "email" in data and data['email'] != "":
                email = data['email']
                try:
                    validate_email(email)
                except ValidationError:
                    # Translators: This message appears when email is invalid
                    return Response(response.parsejson("Invalid email address", "", status=404))
            else:
                return Response(response.parsejson("email is required", "", status=403))

            if "phone_no" not in data or data['phone_no'] == "":
                return Response(response.parsejson("phone_no is required", "", status=403))

            if "availability" not in data or data['availability'] == "":
                return Response(response.parsejson("availability is required", "", status=403))
            elif int(data['availability']) == 1:
                availability = 'Morning'
            elif int(data['availability']) == 2:
                availability = 'Afternoon'
            elif int(data['availability']) == 3:
                availability = 'Evening'
            else:
                availability = 'Flexible'        

            data['status'] = 1
            serializer = ScheduleTourSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                copy_errors = serializer.errors.copy()
                return Response(response.parsejson(copy_errors, "", status=403))
            
            try:
                #----Send Email---------------------
                subdomain_url = settings.SUBDOMAIN_URL
                domain_name = network.domain_name
                domain_admin_url = subdomain_url.replace("###", domain_name)+"admin/schedule-tour-list/"
                property_url = subdomain_url.replace("###", domain_name)+"asset-details/?property_id="+str(property_id)
                property_button = 'property-btn.jpg' 
                dashboard_button = 'dashboard-btn.jpg'
                # if int(users.user_type.id) == 2 and users.site_id is None:
                #     dashboard_text = 'dashboard-btn.jpg'
                #     domain_url = subdomain_url.replace("###", domain_name)+"admin/schedule-tour-list/"
                # else:
                #     dashboard_text = 'property-btn.jpg' 
                #     domain_url = subdomain_url.replace("###", domain_name)+"asset-details/?property_id="+str(property_id)
                number = data['phone_no']
                buyer_email = users.email
                property_detail = PropertyListing.objects.get(id=property_id)
                agent_datail = property_detail.agent
                agent_name = agent_datail.first_name
                agent_email = agent_datail.email
                broker_detail = Users.objects.get(site_id=site_id)
                broker_name = broker_detail.first_name
                broker_email = broker_detail.email
                chat_message = data['message'] if data['message'] !="" else None
                template_data = {"domain_id": site_id, "slug": "virtual_tour"}
                upload = PropertyUploads.objects.filter(property=property_id, upload_type=1).first()
                web_url = settings.FRONT_BASE_URL
                image_url = web_url+'/static/admin/images/property-default-img.png'
                date = data['schedule_date'].split( )
                if upload is not None:
                    image = upload.upload.doc_file_name
                    bucket_name = upload.upload.bucket_name
                    image_url = settings.AZURE_BLOB_URL+bucket_name+'/'+image
                
                content_text = "Thank you for Requesting for property tour.<br/>Admin has received your request and is currently under review"
                if buyer_email.lower() == agent_email.lower():
                    extra_data = {"user_name": data['first_name'], 'web_url': settings.FRONT_BASE_URL, 'property_image': image_url, 'property_name': data['property_name'], 'property_address': data['property_address'], 'property_city':data['property_city'], 'property_state': data['property_state'], 'property_zipcode': data['property_zipcode'], 'chat_message': chat_message, 'tour_person_name': data['first_name'], 'tour_type': tour_type, 'tour_date': date[0], 'tour_availability': availability, 'tour_person_phone': phone_format(number), 'tour_person_email': data['email'], 'tour_comment': chat_message, 'dashboard_link': property_url, "domain_id": site_id, "content_text": content_text, 'dashboard_text': property_button}
                    compose_email(to_email=[email], template_data=template_data, extra_data=extra_data)
                else:
                    extra_data = {"user_name": data['first_name'], 'web_url': settings.FRONT_BASE_URL, 'property_image': image_url, 'property_name': data['property_name'], 'property_address': data['property_address'], 'property_city':data['property_city'], 'property_state': data['property_state'], 'property_zipcode': data['property_zipcode'], 'chat_message': chat_message, 'tour_person_name': data['first_name'], 'tour_type': tour_type, 'tour_date': date[0], 'tour_availability': availability, 'tour_person_phone': phone_format(number), 'tour_person_email': data['email'], 'tour_comment': chat_message, 'dashboard_link': property_url, "domain_id": site_id, "content_text": content_text, 'dashboard_text': property_button}
                    compose_email(to_email=[email], template_data=template_data, extra_data=extra_data)

                    content_text = 'You have Received One Request for Schedule Tour By Buyer'
                    extra_data = {"user_name": agent_name, 'web_url': settings.FRONT_BASE_URL, 'property_image': image_url, 'property_name': data['property_name'], 'property_address': data['property_address'], 'property_city':data['property_city'], 'property_state': data['property_state'], 'property_zipcode': data['property_zipcode'], 'chat_message': chat_message, 'tour_person_name': data['first_name'], 'tour_type': tour_type, 'tour_date': date[0], 'tour_availability': availability, 'tour_person_phone': phone_format(number), 'tour_person_email': data['email'], 'tour_comment': chat_message, 'dashboard_link': domain_admin_url, "domain_id": site_id, "content_text": content_text, 'dashboard_text': dashboard_button}
                    compose_email(to_email=[agent_email], template_data=template_data, extra_data=extra_data)

                if buyer_email.lower() != broker_email.lower() and agent_email.lower() != broker_email.lower():
                    content_text = 'You have Received One Request for Schedule Tour By Buyer'
                    extra_data = {"user_name": broker_name, 'web_url': settings.FRONT_BASE_URL, 'property_image': image_url, 'property_name': data['property_name'], 'property_address': data['property_address'], 'property_city':data['property_city'], 'property_state': data['property_state'], 'property_zipcode': data['property_zipcode'], 'chat_message': chat_message, 'tour_person_name': data['first_name'], 'tour_type': tour_type, 'tour_date': date[0], 'tour_availability': availability, 'tour_person_phone': phone_format(number), 'tour_person_email': data['email'], 'tour_comment': chat_message, 'dashboard_link': domain_admin_url, "domain_id": site_id, "content_text": content_text, 'dashboard_text': dashboard_button}
                    compose_email(to_email=[broker_email], template_data=template_data, extra_data=extra_data)
            except:
                pass

            return Response(response.parsejson("Save data successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class ScheduleTourDetailApiView(APIView):
    """
    Schedule tour detail
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain" in data and data['domain'] != "":
                site_id = int(data['domain'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "user" in data and data['user'] != "":
                user_id = int(data['user'])
                users = Users.objects.filter(id=user_id, site=site_id, status=1, user_type=2).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, status=1, network_user__status=1, network_user__domain=site_id).first()
                    if users is None:
                        return Response(response.parsejson("Not site user.", "", status=201))
            else:
                return Response(response.parsejson("user is required", "", status=403))
            serializer = ScheduleTourDetailSerializer(users)
            return Response(response.parsejson("Fetch data.", serializer.data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SuperAdminScheduleTourListingApiView(APIView):
    """
    Super admin schedule tour listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            domain = None
            if "domain" in data and type(data['domain']) == list and len(data['domain']) > 0:
                domain = data['domain']

            schedule_tour = ScheduleTour.objects
            if domain is not None and len(domain) > 0:
                schedule_tour = schedule_tour.filter(domain__in=domain)
            
            if "status" in data and type(data["status"]) == list and len(data["status"]) > 0:
                schedule_tour = schedule_tour.filter(status__in=data["status"])
            
            if "tour_type" in data and type(data["tour_type"]) == list and len(data["tour_type"]) > 0:
                schedule_tour = schedule_tour.filter(tour_type__in=data["tour_type"])
            
            if "availability" in data and type(data["availability"]) == list and len(data["availability"]) > 0:
                schedule_tour = schedule_tour.filter(availability__in=data["availability"])

            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                if search.isdigit():
                    schedule_tour = schedule_tour.annotate(property_name=Concat('property__address_one', V(', '), 'property__city', V(', '), 'property__state__state_name', V(' '), 'property__postal_code', output_field=CharField())).filter(Q(phone_no__icontains=search) | Q(property_name__icontains=search))
                else:
                    tour_type = {"in person": 1, "virtual tour": 2}
                    availability = {"morning": 1, "afternoon": 2, "evening": 3, "flexible": 4}
                    tour_search = availability_search = 111
                    if search.lower() in tour_type:
                        tour_search = tour_type[search.lower()]
                    if search.lower() in availability:
                        availability_search = availability[search.lower()]
                        
                    schedule_tour = schedule_tour\
                        .annotate(property_name=Concat(
                            'property__address_one', V(', '),
                            'property__city', V(', '),
                            'property__state__state_name', V(' '),
                            'property__postal_code', output_field=CharField()))\
                        .annotate(full_name=Concat('first_name', V(' '), 'last_name'))\
                        .filter(
                            Q(domain__domain_name__icontains=search) |
                            Q(first_name__icontains=search) |
                            Q(last_name__icontains=search) |
                            Q(message__icontains=search) |
                            Q(status__status_name__icontains=search) |
                            Q(property_name__icontains=search) |
                            Q(full_name__icontains=search) |
                            Q(email__icontains=search) |
                            Q(user__status__status_name__icontains=search) |
                            Q(tour_type=tour_search) |
                            Q(availability=availability_search)
                        )

            total = schedule_tour.count()
            schedule_tour = schedule_tour.order_by("-id").only("id")[offset: limit]
            serializer = SuperAdminScheduleTourSerializer(schedule_tour, many=True)
            all_data = {
                "data": serializer.data,
                "total": total
            }
            return Response(response.parsejson("Fetch data", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SubdomainScheduleTourListingApiView(APIView):
    """
    Subdomain schedule tour listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "domain" in data and data['domain'] != "":
                domain = int(data['domain'])
                network = NetworkDomain.objects.filter(id=domain, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = data['user_id']
                user = Users.objects.filter(id=user_id, status=1, site=domain).first()
                if user is None:
                    network_user = NetworkUser.objects.filter(domain=domain, user=user_id, status=1, user__status=1, is_agent=1).first()
                    if network_user is None:
                        return Response(response.parsejson("You are not authorised to update.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required", "", status=403))

            schedule_tour = ScheduleTour.objects.filter(Q(domain=domain) & (Q(property__agent=user_id) | Q(property__domain__users_site_id__id=user_id)))

            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                if search.isdigit():
                    schedule_tour = schedule_tour.annotate(property_name=Concat('property__address_one', V(', '), 'property__city', V(', '), 'property__state__state_name', V(' '), 'property__postal_code', output_field=CharField())).filter(Q(user__phone_no__icontains=search) | Q(property_name__icontains=search))
                else:
                    tour_type = {"in person": 1, "virtual tour": 2}
                    tour_search = 111
                    if search.lower() in tour_type:
                        tour_search = tour_type[search.lower()]

                    availability = {"morning": 1, "afternoon": 2, "evening": 3, "flexible": 4}
                    availability_search = 111
                    if search.lower() in availability:
                        availability_search = availability[search.lower()]

                    schedule_tour = schedule_tour.annotate(property_name=Concat('property__address_one', V(', '), 'property__city', V(', '), 'property__state__state_name', V(' '), 'property__postal_code', output_field=CharField())).annotate(full_name=Concat('first_name', V(' '), 'last_name')).filter(Q(domain__domain_name__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(message__icontains=search) | Q(status__status_name__icontains=search) | Q(property_name__icontains=search) | Q(full_name__icontains=search) | Q(email__icontains=search) | Q(user__status__status_name__icontains=search) | Q(tour_type=tour_search) | Q(availability=availability_search))

            total = schedule_tour.count()
            schedule_tour = schedule_tour.order_by("-id").only("id")[offset: limit]
            serializer = SubdomainScheduleTourSerializer(schedule_tour, many=True)
            all_data = {
                "data": serializer.data,
                "total": total
            }
            return Response(response.parsejson("Fetch data", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class DocumentVaultVisitApiView(APIView):
    """
    Document vault visit
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain" in data and data['domain'] != "":
                site_id = int(data['domain'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "user" in data and data['user'] != "":
                user_id = int(data['user'])
                users = Users.objects.filter(id=user_id, site=site_id, status=1, user_type=2).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, status=1, network_user__status=1, network_user__domain=site_id).first()
                    if users is None:
                        return Response(response.parsejson("Not site user.", "", status=201))
            else:
                return Response(response.parsejson("user is required", "", status=403))

            if "property" in data and data['property'] != "":
                property_id = int(data['property'])
            else:
                return Response(response.parsejson("property is required", "", status=403))

            if "documents" in data and data['documents'] != "":
                documents = int(data['documents'])
                property_uploads = PropertyUploads.objects.filter(id=documents, property=property_id, upload_type=3, property__domain=site_id, status=1).first()
                if property_uploads is None:
                    return Response(response.parsejson("Please enter valid documents.", "", status=403))
            else:
                return Response(response.parsejson("documents is required", "", status=403))

            data['status'] = 1
            document_vault_visit = DocumentVaultVisit.objects.filter(domain=site_id, property=property_id, user=user_id, documents=documents, status=1).first()
            serializer = DocumentVaultVisitSerializer(document_vault_visit, data=data)
            if serializer.is_valid():
                serializer.save()
            else:
                copy_errors = serializer.errors.copy()
                return Response(response.parsejson(copy_errors, "", status=403))
            return Response(response.parsejson("Added successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyUploadDetailApiView(APIView):
    """
    Property upload detail
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain" in data and data['domain'] != "":
                site_id = int(data['domain'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "user" in data and data['user'] != "":
                user_id = int(data['user'])
                users = Users.objects.filter(id=user_id, site=site_id, status=1, user_type=2).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, status=1, network_user__status=1, network_user__domain=site_id).first()
                    if users is None:
                        return Response(response.parsejson("Not site user.", "", status=201))
            else:
                return Response(response.parsejson("user is required", "", status=403))

            if "property" in data and data['property'] != "":
                property_id = int(data['property'])
            else:
                return Response(response.parsejson("property is required", "", status=403))

            if "upload_id" in data and data['upload_id'] != "":
                upload_id = int(data['upload_id'])
                property_uploads = PropertyUploads.objects.filter(upload=upload_id, property=property_id, upload_type=3, property__domain=site_id, status=1).first()
                if property_uploads is None:
                    return Response(response.parsejson("Please enter valid upload id.", "", status=403))
            else:
                return Response(response.parsejson("upload_id is required", "", status=403))
            all_data = {
                "upload_id": upload_id,
                "doc_file_name": property_uploads.upload.doc_file_name,
                "bucket_name": property_uploads.upload.bucket_name,
            }
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyListingOrderingApiView(APIView):
    """
    Property listing ordering
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain" in data and data['domain'] != "":
                site_id = int(data['domain'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "user" in data and data['user'] != "":
                user_id = int(data['user'])
                users = Users.objects.filter(id=user_id, site=site_id, status=1, user_type=2).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, status=1, network_user__status=1, user_type=2, network_user__domain=site_id).first()
                    if users is None:
                        return Response(response.parsejson("Not site user.", "", status=201))
            else:
                return Response(response.parsejson("user is required", "", status=403))

            if "ordering" in data and type(data['ordering']) == dict and len(data['ordering']) > 0:
                ordering = data['ordering']
            else:
                return Response(response.parsejson("ordering is required", "", status=403))
            for key, value in ordering.items():
                try:
                    PropertyListing.objects.filter(Q(id=int(key)) & Q(domain=site_id) & (Q(agent=user_id) | Q(domain__users_site_id__id=user_id))).update(ordering=value)
                except Exception as exp:
                    pass
            return Response(response.parsejson("Successfully updated.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SubdomainScheduleTourSuggestionApiView(APIView):
    """
    Subdomain schedule tour suggestion
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user" in data and data['user'] != "":
                user_id = int(data['user'])
                users = Users.objects.filter(id=user_id, site=site_id, status=1, user_type=2).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, status=1, network_user__status=1, user_type=2, network_user__domain=site_id, network_user__is_agent=1).first()
                    if users is None:
                        return Response(response.parsejson("Not site user.", "", status=201))
            else:
                return Response(response.parsejson("user is required", "", status=403))

            if "search" in data and data['search'] != "":
                search = data['search']
            else:
                return Response(response.parsejson("search is required", "", status=403))
            searched_data = []

            schedule_tour = ScheduleTour.objects.annotate(data=F('domain__domain_name')).filter(domain=site_id, data__icontains=search).values("data")
            searched_data = searched_data + list(schedule_tour)

            schedule_tour = ScheduleTour.objects.annotate(data=Concat('property__address_one', V(', '), 'property__city', V(', '), 'property__state__state_name', V(' '), 'property__postal_code', output_field=CharField())).filter(domain=site_id, data__icontains=search).values("data")
            searched_data = searched_data + list(schedule_tour)

            schedule_tour = ScheduleTour.objects.annotate(data=Concat('first_name', V(' '), 'last_name')).filter(domain=site_id, data__icontains=search).values("data")
            searched_data = searched_data + list(schedule_tour)

            schedule_tour = ScheduleTour.objects.annotate(data=F('phone_no')).filter(domain=site_id, data__icontains=search).values("data")
            searched_data = searched_data + list(schedule_tour)

            schedule_tour = ScheduleTour.objects.annotate(data=F('email')).filter(domain=site_id, data__icontains=search).values("data")
            searched_data = searched_data + list(schedule_tour)

            searched_data = [i['data'] for i in searched_data]
            searched_data = list(set(searched_data))
            return Response(response.parsejson("Fetch data.", searched_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SuperAdminFavouritePropertyListingApiView(APIView):
    """
    Super admin favourite property listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            favourite_property = FavouriteProperty.objects
            if "listing_id" in data and data['listing_id']:
                favourite_property = favourite_property.filter(property__id=data['listing_id'])

            if "domain" in data and type(data['domain']) == list and len(data['domain']) > 0:
                favourite_property = favourite_property.filter(domain__in=data['domain'])
            
            if "asset_type" in data and type(data['asset_type']) == list and len(data['asset_type']) > 0:
                favourite_property= favourite_property.filter(property__property_asset__in=data['asset_type'])
            
            if "auction_type" in data and type(data['auction_type']) == list and len(data['auction_type']) > 0:
                favourite_property = favourite_property.filter(property__sale_by_type__in=data['auction_type'])
            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                if search.isdigit():
                    favourite_property = favourite_property\
                        .annotate(property_name=Concat('property__address_one', V(', '), 'property__city', V(', '), 'property__state__state_name', V(' '), 'property__postal_code', output_field=CharField()))\
                        .filter(
                            Q(id=search) |
                            Q(property_name__icontains=search)
                        )
                else:
                    favourite_property = favourite_property\
                        .annotate(property_name=Concat('property__address_one', V(', '), 'property__city', V(', '), 'property__state__state_name', V(' '), 'property__postal_code', output_field=CharField()))\
                        .annotate(name=Concat('user__first_name', V(' '), 'user__last_name', output_field=CharField()))\
                        .filter(
                            Q(property__address_one__icontains=search) |
                            Q(property__city__icontains=search) |
                            Q(property__state__state_name__icontains=search) |
                            Q(property__sale_by_type__auction_type__icontains=search) |
                            Q(property__property_asset__name__icontains=search) |
                            Q(property_name__icontains=search) |
                            Q(name__icontains=search) | 
                            Q(user__first_name__icontains=search) |
                            Q(user__last_name__icontains=search) |
                            Q(user__email__icontains=search) |
                            Q(domain__domain_name__icontains=search)
                        )

            total = favourite_property.count()
            favourite_property = favourite_property.order_by("id").only("id")[offset: limit]
            serializer = SuperAdminFavouritePropertyListingSerializer(favourite_property, many=True)
            all_data = {
                "data": serializer.data,
                "total": total
            }
            return Response(response.parsejson("Fetch data", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SuperAdminDeleteFavouritePropertyApiView(APIView):
    """
    Super admin delete favourite property
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                users = Users.objects.filter(id=admin_id, status=1, user_type__in=[3]).first()
                if users is None:
                    return Response(response.parsejson("Not authorised for this action.", "", status=201))
            else:
                return Response(response.parsejson("admin_id is required", "", status=403))

            if "favourite_id" in data and data['favourite_id'] != "":
                favourite_id = int(data['favourite_id'])
            else:
                return Response(response.parsejson("favourite_id is required", "", status=403))

            fav_prop = FavouriteProperty.objects.filter(id=favourite_id).first()
            try:
                prop_name = fav_prop.property.address_one if fav_prop.property.address_one else fav_prop.property.id
                content = "Listing removed from favorites! <span>[" + prop_name + "]</span>"
                add_notification(
                    fav_prop.domain_id,
                    "Listing Favorite",
                    content,
                    user_id=fav_prop.user_id,
                    added_by=admin_id,
                    notification_for=1,
                    property_id=fav_prop.property_id
                )
            except:
                pass
            
            fav_prop.delete()

            return Response(response.parsejson("Data deleted successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertySettingApiView(APIView):
    """
    Property setting
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required", "", status=403))
            all_data = {}
            property_settings = PropertySettings.objects.filter(domain=domain_id, property=property_id, is_broker=0, is_agent=0, status=1).first()
            if property_settings is not None:
                all_data['is_log_time_extension'] = property_settings.is_log_time_extension
                all_data['time_flash'] = property_settings.time_flash
                all_data['remain_time_to_add_extension'] = property_settings.remain_time_to_add_extension
                all_data['log_time_extension'] = property_settings.log_time_extension
            else:
                property_settings = PropertySettings.objects.filter(domain=domain_id, is_broker=0, is_agent=1, status=1).first()
                if property_settings is not None:
                    all_data['is_log_time_extension'] = property_settings.is_log_time_extension
                    all_data['time_flash'] = property_settings.time_flash
                    all_data['remain_time_to_add_extension'] = property_settings.remain_time_to_add_extension
                    all_data['log_time_extension'] = property_settings.log_time_extension
                else:
                    property_settings = PropertySettings.objects.filter(domain=domain_id, is_broker=1, is_agent=0, status=1).first()
                    if property_settings is not None:
                        all_data['is_log_time_extension'] = property_settings.is_log_time_extension
                        all_data['time_flash'] = property_settings.time_flash
                        all_data['remain_time_to_add_extension'] = property_settings.remain_time_to_add_extension
                        all_data['log_time_extension'] = property_settings.log_time_extension
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyAuctionDashboardApiView(APIView):
    """
    Property auction dashboard
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))
            
            user_type = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5, 6], status=1).last()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
                user_type = users.user_type_id    
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            property_data = PropertyListing.objects.annotate(dcount=Count("id")).filter(domain=domain_id, seller_status=27).exclude(status=5)
            if user_type is not None and user_type == 5:
                property_data = property_data.filter(agent=user_id)
            elif user_type is not None and user_type == 6:
                property_data = property_data.filter(Q(agent=user_id) | Q(developer=user_id))         

            if "status" in data and data['status'] != "":
                status = int(data['status'])
                if status <= 8:
                    property_data = property_data.filter(Q(status=status))
                else:
                    property_data = property_data.filter(Q(closing_status=status))
                # if status == 1:
                #     property_data = property_data.filter(Q(status=1) & Q(property_auction__start_date__lte=timezone.now()))
                # elif status == 17:
                #     property_data = property_data.filter(Q(status=1) & Q(property_auction__start_date__gt=timezone.now()))
                # else:
                #     property_data = property_data.filter(Q(status=status))

            # -----------------Filter-------------------
            if "agent_id" in data and data["agent_id"] != "":
                agent_id = int(data["agent_id"])
                property_data = property_data.filter(Q(agent=agent_id))

            if "developer_id" in data and data["developer_id"] != "":
                developer_id = int(data["developer_id"])
                property_data = property_data.filter(Q(developer=developer_id))

            if "employee_id" in data and data["employee_id"] != "":
                employee_id = int(data["employee_id"])
                property_data = property_data.filter(Q(agent=developer_id))        

            if "auction_id" in data and data["auction_id"] != "":
                auction_id = int(data["auction_id"])
                property_data = property_data.filter(Q(sale_by_type=auction_id))

            if "asset_id" in data and data["asset_id"] != "":
                asset_id = int(data["asset_id"])
                property_data = property_data.filter(Q(property_asset=asset_id))

            if "property_type" in data and data["property_type"] != "":
                property_type = int(data["property_type"])
                property_data = property_data.filter(Q(property_type=property_type))

            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                property_data = property_data.filter(Q(property_name__icontains=search) | Q(state__state_name__icontains=search) | Q(community__icontains=search))

            total = property_data.count()
            property_data = property_data.order_by(F("ordering").asc(nulls_last=True)).only("id")[offset:limit]
            serializer = PropertyAuctionDashboardSerializer(property_data, many=True)
            all_data = {
                "data": serializer.data,
                "total": total
            }
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyAuctionSuggestionApiView(APIView):
    """
    Property auction suggestion
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5], status=1).first()
                is_agent = None
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
                data["agent"] = user_id
                if users.site_id is None:
                    is_agent = True
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "search" in data and data['search'] != "":
                search = data['search']
            else:
                return Response(response.parsejson("search is required", "", status=403))
            searched_data = []

            property_listing = PropertyListing.objects.annotate(data=F('state__state_name')).filter(domain=site_id, status=1, data__icontains=search).values("data")
            if is_agent:
                property_listing = property_listing.filter(Q(agent=user_id) | Q(developer=user_id))
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('property_name')).filter(domain=site_id, data__icontains=search).values("data")
            if is_agent:
                property_listing = property_listing.filter(Q(agent=user_id) | Q(developer=user_id))
            searched_data = searched_data + list(property_listing)

            property_listing = PropertyListing.objects.annotate(data=F('community')).filter(domain=site_id, data__icontains=search).values("data")
            if is_agent:
                property_listing = property_listing.filter(Q(agent=user_id) | Q(developer=user_id))
            searched_data = searched_data + list(property_listing)

            searched_data = [i['data'] for i in searched_data]
            searched_data = list(set(searched_data))
            return Response(response.parsejson("Fetch data.", searched_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class StartStopAuctionApiView(APIView):
    """
    Start stop auction
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            is_super_admin = None
            if "is_super_admin" in data and data['is_super_admin'] != "":
                is_super_admin = int(data['is_super_admin'])

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
            else:
                if is_super_admin is None:
                    return Response(response.parsejson("domain_id is required", "", status=403))
                else:
                    domain_id = None

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                is_agent = None
                if is_super_admin is None:
                    users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5, 6], status=1).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                else:
                    users = Users.objects.filter(id=user_id, status=1, user_type=3).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required.", "", status=403))

            property_auction = PropertyAuction.objects.filter(property=property_id)
            if domain_id is not None:
                property_auction = property_auction.filter(domain=domain_id)
            if users.user_type_id == 5:
                property_auction = property_auction.filter(property__agent=user_id)
            elif users.user_type_id == 6:
                property_auction = property_auction.filter(Q(property__agent=user_id) | Q(property__developer=user_id))    

            property_auction = property_auction.first()
            if property_auction is not None and property_auction.status_id == 1:
                property_auction.status_id = 2
            elif property_auction is not None and property_auction.status_id == 2:
                property_auction.status_id = 1
            else:
                property_auction.status_id = property_auction.status_id

            property_auction.save()
            return Response(response.parsejson("Data successfully updated.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class UpdateBidIncrementApiView(APIView):
    """
    Update bid increment
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            is_super_admin = None
            if "is_super_admin" in data and data['is_super_admin'] != "":
                is_super_admin = int(data['is_super_admin'])

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
            else:
                if is_super_admin is None:
                    return Response(response.parsejson("domain_id is required", "", status=403))
                else:
                    domain_id = None

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                is_agent = None
                if is_super_admin is None:
                    users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5, 6], status=1).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                else:
                    users = Users.objects.filter(id=user_id, status=1, user_type=3).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required.", "", status=403))

            if "bid_increments" in data and data['bid_increments'] != "":
                bid_increments = int(data['bid_increments'])
            else:
                return Response(response.parsejson("bid_increments is required.", "", status=403))

            property_auction = PropertyAuction.objects.filter(property=property_id)
            if domain_id is not None:
                property_auction = property_auction.filter(domain=domain_id)
            if users.user_type_id == 5:
                property_auction = property_auction.filter(property__agent=user_id)
            elif users.user_type_id == 6:
                property_auction = property_auction.filter(Q(property__agent=user_id) | Q(property__developer=user_id))    

            property_auction = property_auction.first()
            if property_auction is not None:
                property_auction.bid_increments = bid_increments

            property_auction.save()
            return Response(response.parsejson("Data successfully updated.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class UpdateReserveAmountApiView(APIView):
    """
    Update reserve amount
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            is_super_admin = None
            if "is_super_admin" in data and data['is_super_admin'] != "":
                is_super_admin = int(data['is_super_admin'])

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
            else:
                if is_super_admin is None:
                    return Response(response.parsejson("domain_id is required", "", status=403))
                else:
                    domain_id = None

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                is_agent = None
                if is_super_admin is None:
                    users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5, 6], status=1).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                else:
                    users = Users.objects.filter(id=user_id, status=1, user_type=3).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required.", "", status=403))

            if "reserve_amount" in data and data['reserve_amount'] != "":
                reserve_amount = int(data['reserve_amount'])
            else:
                return Response(response.parsejson("reserve_amount is required.", "", status=403))

            property_auction = PropertyAuction.objects.filter(property=property_id)
            if domain_id is not None:
                property_auction = property_auction.filter(domain=domain_id)
            if users.user_type_id == 5:
                property_auction = property_auction.filter(property__agent=user_id)
            elif users.user_type_id == 6:
                property_auction = property_auction.filter(Q(property__agent=user_id) | Q(property__developer=user_id))    

            property_auction = property_auction.first()
            if property_auction is not None:
                property_auction.reserve_amount = reserve_amount

            property_auction.save()
            return Response(response.parsejson("Data successfully updated.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class UpdateAuctionDateApiView(APIView):
    """
    Update auction date
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            is_super_admin = None
            if "is_super_admin" in data and data['is_super_admin'] != "":
                is_super_admin = int(data['is_super_admin'])

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
            else:
                if is_super_admin is None:
                    return Response(response.parsejson("domain_id is required", "", status=403))
                else:
                    domain_id = None

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                is_agent = None
                if is_super_admin is None:
                    users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                    if users is None:
                        is_agent = True
                        users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__is_agent=1,
                                                     network_user__status=1, status=1, user_type=2).first()
                        if users is None:
                            return Response(response.parsejson("User not exist.", "", status=403))
                else:
                    users = Users.objects.filter(id=user_id, status=1, user_type=3).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required.", "", status=403))

            if "start_date" in data and data['start_date'] != "":
                start_date = data['start_date']
            else:
                return Response(response.parsejson("start_date is required.", "", status=403))

            if "end_date" in data and data['end_date'] != "":
                end_date = data['end_date']
            else:
                return Response(response.parsejson("end_date is required.", "", status=403))

            property_auction = PropertyAuction.objects.filter(property=property_id)
            if domain_id is not None:
                property_auction = property_auction.filter(domain=domain_id)

            if is_agent:
                property_auction = property_auction.filter(property__agent=user_id)

            property_auction = property_auction.first()
            if property_auction is not None:
                property_auction.start_date = start_date
                property_auction.end_date = end_date

            property_auction.save()
            return Response(response.parsejson("Data successfully updated.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AuctionListingReadApiView(APIView):
    """
    Auction listing read
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            is_super_admin = None
            if "is_super_admin" in data and data['is_super_admin'] != "":
                is_super_admin = int(data['is_super_admin'])

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
            else:
                if is_super_admin is None:
                    return Response(response.parsejson("domain_id is required", "", status=403))
                else:
                    domain_id = None

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                if is_super_admin is None:
                    users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                    if users is None:
                        users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__is_agent=1, network_user__status=1, status=1, user_type=2).first()
                        if users is None:
                            return Response(response.parsejson("User not exist.", "", status=403))
                else:
                    users = Users.objects.filter(id=user_id, status=1, user_type=3).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required.", "", status=403))

            property_listing = PropertyListing.objects.filter(id=property_id)
            if domain_id is not None:
                property_listing = property_listing.filter(domain=domain_id)
            property_listing = property_listing.first()
            property_listing.read_by_auction_dashboard = 1
            property_listing.save()
            return Response(response.parsejson("Data successfully updated.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AddPropertyEvaluatorCategoryApiView(APIView):
    """
    Add Property Evaluator Category
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            category_id = None
            if "category_id" in data and data['category_id'] != "":
                category_id = int(data['category_id'])

            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                users = Users.objects.filter(id=admin_id, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            if "name" in data and data['name'] != "":
                name = data['name']
            else:
                return Response(response.parsejson("name is required", "", status=403))

            if "status" in data and data['status'] != "":
                status = int(data['status'])
            else:
                return Response(response.parsejson("status is required", "", status=403))

            property_evaluator_category = PropertyEvaluatorCategory()
            if category_id is not None:
                property_evaluator_category = PropertyEvaluatorCategory.objects.get(id=category_id)

            property_evaluator_category.name = name
            property_evaluator_category.status_id = status
            property_evaluator_category.save()
            return Response(response.parsejson("Category save successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyEvaluatorCategoryListApiView(APIView):
    """
    Property Evaluator Category List
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                users = Users.objects.filter(id=admin_id, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            property_evaluator_category = PropertyEvaluatorCategory.objects
            if 'search' in data and data['search'] != "":
                property_evaluator_category = property_evaluator_category.filter(name__icontains=data['search'])

            if 'status' in data and type(data['status'] == list) and len(data['status']) > 0:
                property_evaluator_category = property_evaluator_category.filter(status__in=data['status'])

            total = property_evaluator_category.count()
            property_evaluator_category = property_evaluator_category.order_by("-id").values("id", "name", status_name=F("status__status_name"))[offset: limit]
            all_data = {'total': total, 'data': property_evaluator_category}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyEvaluatorCategoryDetailApiView(APIView):
    """
    Property Evaluator Category Detail
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                users = Users.objects.filter(id=admin_id, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            if "category_id" in data and data['category_id'] != "":
                category_id = int(data['category_id'])
            else:
                return Response(response.parsejson("category_id is required.", "", status=403))

            property_evaluator_category = PropertyEvaluatorCategory.objects.filter(id=category_id).values("id", "name", "status")
            return Response(response.parsejson("Fetch data.", property_evaluator_category, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AddPropertyEvaluatorQuestionApiView(APIView):
    """
    Add Property Evaluator Question
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            question_id = None
            if "question_id" in data and data['question_id'] != "":
                question_id = int(data['question_id'])

            placeholder = None
            if "placeholder" in data and data['placeholder'] != "":
                placeholder = data['placeholder']

            if "category" in data and data['category'] != "":
                category = int(data['category'])
            else:
                return Response(response.parsejson("category_id is required.", "", status=403))

            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                users = Users.objects.filter(id=admin_id, user_type=3, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            if "question" in data and data['question'] != "":
                question = data['question']
            else:
                return Response(response.parsejson("question is required.", "", status=403))

            if "option_type" in data and data['option_type'] != "":
                option_type = int(data['option_type'])
            else:
                return Response(response.parsejson("option_type is required.", "", status=403))

            if "property_type" in data and data['property_type'] != "":
                property_type = int(data['property_type'])
            else:
                return Response(response.parsejson("property_type is required.", "", status=403))

            if "status" in data and data['status'] != "":
                status = int(data['status'])
            else:
                return Response(response.parsejson("status is required.", "", status=403))

            question_option = None
            if "question_option" in data and type(data['question_option']) == list and len(data['question_option']) > 0:
                question_option = data['question_option']

            with transaction.atomic():
                try:
                    property_evaluator_question = PropertyEvaluatorQuestion.objects.filter(id=question_id).first()
                    serializer = AddPropertyEvaluatorQuestionSerializer(property_evaluator_question, data=data)
                    if serializer.is_valid():
                        question_id = serializer.save()
                        question_id = question_id.id
                    else:
                        transaction.set_rollback(True)  # -----Rollback Transaction----
                        copy_errors = serializer.errors.copy()
                        return Response(response.parsejson(copy_errors, "", status=403))

                    if question_option is not None:
                        PropertyEvaluatorQuestionOption.objects.filter(question=question_id).delete()
                        for option in question_option:
                            property_evaluator_question_option=PropertyEvaluatorQuestionOption()
                            property_evaluator_question_option.question_id = question_id
                            property_evaluator_question_option.option = option
                            property_evaluator_question_option.status_id = 1
                            property_evaluator_question_option.save()

                except Exception as exp:
                    transaction.set_rollback(True)  # -----Rollback Transaction----
                    return Response(response.parsejson(str(exp), exp, status=403))
            return Response(response.parsejson("Question save successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyEvaluatorQuestionListApiView(APIView):
    """
    Property Evaluator Question List
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                users = Users.objects.filter(id=admin_id, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            property_evaluator_question = PropertyEvaluatorQuestion.objects
            if 'search' in data and data['search'] != "":
                property_evaluator_question = property_evaluator_question.filter(Q(question__icontains=data['search']) | Q(category__name__icontains=data['search']))

            if 'status' in data and type(data['status'] == list) and len(data['status']) > 0:
                property_evaluator_question = property_evaluator_question.filter(status__in=data['status'])

            total = property_evaluator_question.count()
            property_evaluator_question = property_evaluator_question.order_by("-id").values("id", "question", "option_type", status_name=F("status__status_name"), category_name=F("category__name"))
            all_data = {'total': total, 'data': property_evaluator_question}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyEvaluatorQuestionDetailApiView(APIView):
    """
    Property Evaluator Question Detail
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                users = Users.objects.filter(id=admin_id, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            if "question_id" in data and data['question_id'] != "":
                question_id = int(data['question_id'])
            else:
                return Response(response.parsejson("question_id is required.", "", status=403))

            property_evaluator_question = PropertyEvaluatorQuestion.objects.get(id=question_id)
            serializer = PropertyEvaluatorQuestionDetailSerializer(property_evaluator_question)
            return Response(response.parsejson("Fetch data.", serializer.data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SavePropertyEvaluatorAnswerApiView(APIView):
    """
    Save Property Evaluator Answer
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
            else:
                return Response(response.parsejson("domain_id is required.", "", status=403))

            option_type = None
            if "question_id" in data and data['question_id'] != "":
                question_id = int(data['question_id'])
                option_type = PropertyEvaluatorQuestion.objects.filter(id=question_id).first()
                option_type = option_type.option_type
            else:
                return Response(response.parsejson("question_id is required.", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            answer = None
            answer_data = None
            if option_type != 4:
                if "answer" in data and data['answer'] != "":
                    answer = data['answer']
            elif option_type == 4 and "answer" in data and type(data['answer']) == list and len(data['answer']) > 0:
                answer_data = data['answer']

            with transaction.atomic():
                try:
                    property_evaluator_domain = PropertyEvaluatorDomain.objects.filter(domain=domain_id, user=user_id).first()
                    property_evaluator_domain
                    if property_evaluator_domain is None:
                        property_evaluator_domain = PropertyEvaluatorDomain()
                        property_evaluator_domain.domain_id = domain_id
                        property_evaluator_domain.user_id = user_id
                        property_evaluator_domain.status_id = 1
                        property_evaluator_domain.save()
                        property_evaluator_id = property_evaluator_domain.id
                    else:
                        property_evaluator_id = property_evaluator_domain.id

                    property_evaluator_user_answer = PropertyEvaluatorUserAnswer.objects.filter(property_evaluator=property_evaluator_id, question=question_id).first()
                    if property_evaluator_user_answer is None:
                        property_evaluator_user_answer = PropertyEvaluatorUserAnswer()
                    property_evaluator_user_answer.property_evaluator_id = property_evaluator_id
                    property_evaluator_user_answer.question_id = question_id
                    property_evaluator_user_answer.answer = answer
                    property_evaluator_user_answer.save()
                    answer_id = property_evaluator_user_answer.id
                    if answer_data is not None and len(answer_data) > 0:
                        PropertyEvaluatorDocAnswer.objects.filter(answer=answer_id).delete()
                        for doc_id in answer_data:
                            property_evaluator_doc_answer = PropertyEvaluatorDocAnswer()
                            property_evaluator_doc_answer.answer_id = answer_id
                            property_evaluator_doc_answer.document_id = doc_id
                            property_evaluator_doc_answer.user_id = user_id
                            property_evaluator_doc_answer.save()
                    else:
                        PropertyEvaluatorDocAnswer.objects.filter(answer=answer_id).delete()

                except Exception as exp:
                    transaction.set_rollback(True)  # -----Rollback Transaction----
                    return Response(response.parsejson(str(exp), exp, status=403))

            if "is_last_question" in data and data['is_last_question'] != "" and data['is_last_question']:
                user_business_profile = UserBusinessProfile.objects.filter(user__site=domain_id).first()
                super_admin = Users.objects.filter(id=1, user_type=3, status=1).first()
                extra_data = {
                    "user_name": users.first_name + ' ' + users.last_name,
                    "domain_name": user_business_profile.company_name
                }
                # ------Email to Super Admin------
                # template_data = {"domain_id": domain_id, "slug": "received_property_bot_request"}
                # compose_email(to_email=[super_admin.email], template_data=template_data, extra_data=extra_data)

                # ------Email to Broker------
                template_data = {"domain_id": domain_id, "slug": "received_property_bot_request"}
                compose_email(to_email=[user_business_profile.user.email], template_data=template_data, extra_data=extra_data)

                # ------Email to Customer------
                template_data = {"domain_id": domain_id, "slug": "send_property_bot_request"}
                compose_email(to_email=[users.email], template_data=template_data, extra_data=extra_data)

            return Response(response.parsejson("Answer save successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyEvaluatorQuestionApiView(APIView):
    """
    Property Evaluator Question
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
            else:
                return Response(response.parsejson("domain_id is required.", "", status=403))

            business_profile = UserBusinessProfile.objects.filter(user__site=domain_id).first()

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))
            setting = PropertyEvaluatorSetting.objects.filter(domain=domain_id, status=1).order_by("property_type").values("id", "property_type_id")
            property_address = PropertyEvaluatorQuestion.objects.filter(category=1, status=1).order_by("id")
            property_address = PropertyEvaluatorQuestionSerializer(property_address, many=True, context={"user_id": user_id, "domain_id": domain_id})
            property_details = PropertyEvaluatorQuestion.objects.filter(category=2, status=1).order_by("id")
            property_details = PropertyEvaluatorQuestionSerializer(property_details, many=True, context={"user_id": user_id, "domain_id": domain_id})
            photos_document = PropertyEvaluatorQuestion.objects.filter(category=3, status=1).order_by("id")
            photos_document = PropertyEvaluatorQuestionSerializer(photos_document, many=True, context={"user_id": user_id, "domain_id": domain_id})
            additionals_questions = PropertyEvaluatorQuestion.objects.filter(category=4, status=1).order_by("id")
            additionals_questions = PropertyEvaluatorQuestionSerializer(additionals_questions, many=True, context={"user_id": user_id, "domain_id": domain_id})
            property_user_answer = PropertyEvaluatorUserAnswer.objects.filter(question=3, property_evaluator__domain=domain_id).first()
            property_type = None
            if property_user_answer is not None:
                property_type = property_user_answer.answer
            all_data = {"property_address": property_address.data, "property_details": property_details.data, "photos_document": photos_document.data, "additionals_questions": additionals_questions.data, "property_type": property_type, "domain_name": business_profile.company_name, "setting": setting}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyEvaluatorCategoryApiView(APIView):
    """
    Property Evaluator Category
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            property_evaluator_category = PropertyEvaluatorCategory.objects.filter(status=1).order_by("id").values("id", "name")
            return Response(response.parsejson("Fetch data.", property_evaluator_category, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SubdomainPropertyEvaluatorApiView(APIView):
    """
    Subdomain Property Evaluator
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            is_agent = None

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                    is_agent = True
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))
            agent_list = Users.objects.filter(network_user__domain=domain_id, network_user__status=1, network_user__is_agent=1, status=1).order_by("-id").values("id", "first_name", "last_name", "email")
            property_evaluator_domain = PropertyEvaluatorDomain.objects.filter(domain=domain_id, status=1)
            if is_agent is not None:
                property_evaluator_domain = property_evaluator_domain.filter(assign_to=user_id)
            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                # if search.isdigit():
                #     property_listing = property_listing.filter(Q(id=search) | Q(postal_code__icontains=search))
                # else:
                property_evaluator_domain = property_evaluator_domain.annotate(full_name=Concat('user__first_name', V(' '),'user__last_name')).filter(Q(full_name__icontains=search) | Q(user__email__icontains=search) | Q(user__phone_no__icontains=search))
            total = property_evaluator_domain.count()
            property_evaluator_domain = property_evaluator_domain.order_by("-id").only('id')[offset: limit]
            serializer = SubdomainPropertyEvaluatorSerializer(property_evaluator_domain, many=True)
            all_data = {'total': total, 'data': serializer.data, "agent_list": agent_list}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AssignPropertyEvaluatorApiView(APIView):
    """
    Assign Property Evaluator
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
                    # users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    # if users is None:
                    #     return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "bot_id" in data and data['bot_id'] != "":
                bot_id = int(data['bot_id'])
            else:
                return Response(response.parsejson("bot_id is required.", "", status=403))

            if "assign_to" in data and data['assign_to'] != "":
                assign_to = int(data['assign_to'])
            else:
                return Response(response.parsejson("assign_to is required.", "", status=403))

            property_evaluator_domain = PropertyEvaluatorDomain.objects.filter(id=bot_id, domain=domain_id, status=1).first()
            property_evaluator_domain.assign_to_id = assign_to
            property_evaluator_domain.save()
            return Response(response.parsejson("Assign successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AgentPropertyEvaluatorApiView(APIView):
    """
    Agent Property Evaluator
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            property_evaluator_domain = PropertyEvaluatorDomain.objects.filter(domain=domain_id, assign_to=user_id, status=1)
            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                # if search.isdigit():
                #     property_listing = property_listing.filter(Q(id=search) | Q(postal_code__icontains=search))
                # else:
                property_evaluator_domain = property_evaluator_domain.annotate(full_name=Concat('user__first_name', V(' '),'user__last_name')).filter(Q(full_name__icontains=search) | Q(user__email__icontains=search) | Q(user__phone_no__icontains=search))
            total = property_evaluator_domain.count()
            property_evaluator_domain = property_evaluator_domain.order_by("-id").only('id')[offset: limit]
            serializer = AgentPropertyEvaluatorSerializer(property_evaluator_domain, many=True)
            all_data = {'total': total, 'data': serializer.data }
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyEvaluatorDetailApiView(APIView):
    """
    Property Evaluator Detail
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            agent_id = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                    agent_id = user_id
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "bot_id" in data and data['bot_id'] != "":
                bot_id = int(data['bot_id'])
            else:
                return Response(response.parsejson("bot_id is required", "", status=403))

            if "category_id" in data and data['category_id'] != "":
                category_id = int(data['category_id'])
            else:
                return Response(response.parsejson("category_id is required", "", status=403))

            property_evaluator = PropertyEvaluatorUserAnswer.objects.filter(property_evaluator=bot_id, question__category=category_id, property_evaluator__domain=domain_id, property_evaluator__status=1).order_by("question__id")
            if agent_id is not None:
                property_evaluator = property_evaluator.filter(property_evaluator__assign_to=agent_id)
            serializer = PropertyEvaluatorDetailSerializer(property_evaluator, many=True)
            return Response(response.parsejson("Fetch data.", serializer.data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyEvaluatorStatusChangeApiView(APIView):
    """
    Property Evaluator Status Change
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            agent = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                    agent = True
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "bot_id" in data and data['bot_id'] != "":
                bot_id = int(data['bot_id'])
            else:
                return Response(response.parsejson("bot_id is required.", "", status=403))

            if "status" in data and data['status'] != "":
                status = int(data['status'])
            else:
                return Response(response.parsejson("status is required.", "", status=403))

            property_evaluator_domain = PropertyEvaluatorDomain.objects.filter(id=bot_id, domain=domain_id, status=1)
            if agent is not None:
                property_evaluator_domain = property_evaluator_domain.filter(assign_to=user_id)
            property_evaluator_domain = property_evaluator_domain.first()
            property_evaluator_domain.complete_status_id = status
            property_evaluator_domain.save()
            return Response(response.parsejson("Status change successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class ChangeEvaluatorSettingApiView(APIView):
    """
    Change Evaluator Setting
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_type" in data and type(data['property_type']) == list and len(data['property_type']) > 0:
                property_type = data['property_type']
            else:
                return Response(response.parsejson("property_type is required.", "", status=403))

            PropertyEvaluatorSetting.objects.filter(domain=domain_id).delete()
            for property_type_id in property_type:
                property_evaluator_setting = PropertyEvaluatorSetting()
                property_evaluator_setting.domain_id = domain_id
                property_evaluator_setting.property_type_id = property_type_id
                property_evaluator_setting.status_id = 1
                property_evaluator_setting.save()
            return Response(response.parsejson("Setting change successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyEvaluatorSaveMsgApiView(APIView):
    """
    Property Evaluator Save Msg
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            agent = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                    agent = True
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "bot_id" in data and data['bot_id'] != "":
                bot_id = int(data['bot_id'])
            else:
                return Response(response.parsejson("bot_id is required.", "", status=403))

            if "msg" in data and data['msg'] != "":
                msg = data['msg']
            else:
                return Response(response.parsejson("msg is required.", "", status=403))

            property_evaluator_domain = PropertyEvaluatorDomain.objects.filter(id=bot_id, domain=domain_id, status=1)
            if agent is not None:
                property_evaluator_domain = property_evaluator_domain.filter(assign_to=user_id)
            property_evaluator_domain = property_evaluator_domain.first()
            property_evaluator_domain.review_msg = msg
            property_evaluator_domain.save()
            return Response(response.parsejson("Message saved successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class DeleteBotDocApiView(APIView):
    """
    Delete Bot Doc
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "bot_doc_id" in data and data['bot_doc_id'] != "":
                bot_doc_id = int(data['bot_doc_id'])
            else:
                return Response(response.parsejson("bot_doc_id is required.", "", status=403))

            property_evaluator_domain = PropertyEvaluatorDomain.objects.filter(domain=domain_id, user=user_id, status=1).first()
            if property_evaluator_domain is None:
                return Response(response.parsejson("Not authority to delete.", "", status=201))

            PropertyEvaluatorDocAnswer.objects.filter(document=bot_doc_id).delete()
            UserUploads.objects.filter(id=bot_doc_id).delete()
            return Response(response.parsejson("Document delete successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class RebaPropertyListingApiView(APIView):
    """
    Reba property listing
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            user_id = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])

            property_listing = PropertyListing.objects.filter(is_approved=1, status=1)

            # -----------------Filter-------------------
            if "auction_id" in data and data["auction_id"] != "":
                auction_id = int(data["auction_id"])
                property_listing = property_listing.filter(Q(sale_by_type=auction_id))

            if "property_type" in data and type(data["property_type"]) == list and len(data["property_type"]) > 0:
                property_type = data["property_type"]
                property_listing = property_listing.filter(Q(property_type__in=property_type))

            if "minimum_price" in data and data["minimum_price"] != "":
                minimum_price = int(data["minimum_price"])
                property_listing = property_listing.filter(Q(property_auction__start_price__gte=minimum_price))

            if "maximum_price" in data and data["maximum_price"] != "":
                maximum_price = int(data["maximum_price"])
                property_listing = property_listing.filter(Q(property_auction__start_price__lte=maximum_price))

            if "others" in data and type(data["others"]) == list and len(data["others"]) > 0:
                others = data["others"]
                if len(others) == 2:
                    property_listing = property_listing.filter(Q(broker_co_op=1) | Q(financing_available=1))
                else:
                    if "broker-co-op" in others:
                        property_listing = property_listing.filter(Q(broker_co_op=1))

                    if "financing" in others:
                        property_listing = property_listing.filter(Q(financing_available=1))

            if "agent_id" in data and data["agent_id"] != "":
                agent_id = int(data["agent_id"])
                property_listing = property_listing.filter(Q(agent=agent_id))

            if "asset_id" in data and type(data["asset_id"]) == list and len(data["asset_id"]) > 0:
                asset_id = data["asset_id"]
                property_listing = property_listing.filter(Q(property_asset__in=asset_id))

            if "status" in data and data["status"] != "":
                status = int(data["status"])
                property_listing = property_listing.filter(Q(status=status))

            if "filter" in data and data["filter"] == "auctions_listing":
                property_listing = property_listing.filter(Q(property_auction__start_date__isnull=False) & Q(property_auction__end_date__isnull=False)).exclude(sale_by_type__in=[4, 7])
            elif "filter" in data and data["filter"] == "new_listing":
                min_dt = timezone.now() - timedelta(hours=720)
                # max_dt = timezone.now()
                property_listing = property_listing.filter(added_on__gte=min_dt)
            elif "filter" in data and data["filter"] == "traditional_listing":
                property_listing = property_listing.filter(sale_by_type=4)
            elif "filter" in data and data["filter"] == "recent_sold_listing":
                min_dt = timezone.now() - timedelta(hours=720)
                # max_dt = timezone.now()
                property_listing = property_listing.filter(date_sold__gte=min_dt)
            elif "filter" in data and data["filter"] == "featured":
                property_listing = property_listing.filter(is_featured=1)

            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                if search.isdigit():
                    property_listing = property_listing.filter(Q(id=search) | Q(postal_code__icontains=search))
                else:
                    property_listing = property_listing.filter(Q(city__icontains=search) |
                                                               Q(state__state_name__icontains=search) |
                                                               Q(address_one__icontains=search) |
                                                               Q(postal_code__icontains=search) |
                                                               Q(property_asset__name__icontains=search) |
                                                               Q(sale_by_type__auction_type__icontains=search))

            # -----------------Sort------------------
            # if "short_by" in data and data["short_by"] != "" and "sort_order" in data and data["sort_order"] != "":
            if "short_by" in data and data["short_by"] != "":
                if data["short_by"].lower() == "auction_start" and data["sort_order"].lower() == "asc":
                    property_listing = property_listing.order_by(F("property_auction__start_date").asc(nulls_last=True))
                elif data["short_by"].lower() == "auction_start" and data["sort_order"].lower() == "desc":
                    property_listing = property_listing.order_by(F("property_auction__start_date").desc(nulls_last=True))
                elif data["short_by"].lower() == "auction_end" and data["sort_order"].lower() == "asc":
                    property_listing = property_listing.order_by(F("property_auction__end_date").asc(nulls_last=True))
                elif data["short_by"].lower() == "auction_end" and data["sort_order"].lower() == "desc":
                    property_listing = property_listing.order_by(F("property_auction__end_date").desc(nulls_last=True))
                elif data["short_by"].lower() == "highest_price":
                    property_listing = property_listing.order_by(F("property_auction__start_price").desc(nulls_last=True))
                elif data["short_by"].lower() == "lowest_price":
                    property_listing = property_listing.order_by(F("property_auction__start_price").asc(nulls_last=True))
                elif data["short_by"].lower() == "page_default":
                    property_listing = property_listing.order_by(F("ordering").asc(nulls_last=True))
                elif data["short_by"].lower() == "ending_soonest":
                    property_listing = property_listing.order_by(F("property_auction__end_date").asc(nulls_last=True))
                elif data["short_by"].lower() == "ending_latest":
                    property_listing = property_listing.order_by(F("property_auction__end_date").desc(nulls_last=True))
            else:
                property_listing = property_listing.order_by("-id")

            total = property_listing.count()
            property_listing = property_listing.only("id")[offset:limit]
            serializer = RebaPropertyListingSerializer(property_listing, many=True, context={"user_id": user_id})
            all_data = {"data": serializer.data, "total": total}
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SaveSearchApiView(APIView):
    """
    Save Search
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            domain_id = None
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))

            agent = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "name" in data and data["name"] != "":
                name = data["name"]
            else:
                return Response(response.parsejson("name is required.", "", status=403))

            if "parameters" in data and data['parameters'] != "":
                parameters = data['parameters']
            else:
                return Response(response.parsejson("parameters is required.", "", status=403))

            save_search = SaveSearch()
            save_search.domain_id = domain_id
            save_search.name = name
            save_search.parameters = parameters
            save_search.status_id = 1
            save_search.save()
            return Response(response.parsejson("Save search successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class SuperAdminPropertyEvaluatorListApiView(APIView):
    """
    Super Admin Property Evaluator List
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "admin_id" in data and data['admin_id'] != "":
                users = Users.objects.filter(id=int(data['admin_id']), status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            property_evaluator_domain = PropertyEvaluatorDomain.objects.filter(status=1)
            if "domain_id" in data and type(data['domain_id']) == list and len(data['domain_id']) > 0:
                property_evaluator_domain = property_evaluator_domain.filter(domain__in=data['domain_id'])
            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                property_evaluator_domain = property_evaluator_domain.annotate(full_name=Concat('user__first_name', V(' '), 'user__last_name')).filter(Q(full_name__icontains=search) | Q(user__email__icontains=search) | Q(user__phone_no__icontains=search) | Q(domain__users_site_id__user_business_profile__company_name__icontains=search))
            total = property_evaluator_domain.count()
            property_evaluator_domain = property_evaluator_domain.order_by("-id").only('id')[offset: limit]
            serializer = SuperAdminPropertyEvaluatorListSerializer(property_evaluator_domain, many=True)
            all_data = {'total': total, 'data': serializer.data}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))
        
        
class SuperAdminPropertyEvaluatorDetailApiView(APIView):
    """
    Super Admin Property Evaluator Detail
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "admin_id" in data and data['admin_id'] != "":
                users = Users.objects.filter(id=int(data['admin_id']), status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            if "bot_id" in data and data['bot_id'] != "":
                bot_id = int(data['bot_id'])
            else:
                return Response(response.parsejson("bot_id is required", "", status=403))

            if "category_id" in data and data['category_id'] != "":
                category_id = int(data['category_id'])
            else:
                return Response(response.parsejson("category_id is required", "", status=403))

            property_evaluator = PropertyEvaluatorUserAnswer.objects.filter(property_evaluator=bot_id, question__category=category_id, property_evaluator__status=1).order_by("question__id")
            serializer = SuperAdminPropertyEvaluatorDetailSerializer(property_evaluator, many=True)
            return Response(response.parsejson("Fetch data.", serializer.data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AddPortfolioApiView(APIView):
    """
    Add Portfolio
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain" in data and data['domain'] != "":
                domain = int(data['domain'])
                network = NetworkDomain.objects.filter(id=domain, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "user" in data and data['user'] != "":
                user = int(data['user'])
                users = Users.objects.filter(id=user, site=domain, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user, network_user__domain=domain, network_user__status=1, network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            portfolio_id = None
            if "portfolio_id" in data and data['portfolio_id'] != "":
                portfolio_id = int(data['portfolio_id'])
                portfolio_id = Portfolio.objects.get(id=portfolio_id)

            if "name" in data and data['name'] != "":
                name = data['name']
            else:
                return Response(response.parsejson("name is required.", "", status=403))

            details = None
            if "details" in data and data['details'] != "":
                details = data['details']

            terms = None
            if "terms" in data and data['terms'] != "":
                terms = data['terms']

            contact = None
            if "contact" in data and data['contact'] != "":
                contact = data['contact']

            if "status" in data and data['status'] != "":
                status = int(data['status'])
            else:
                return Response(response.parsejson("status is required.", "", status=403))

            property_id = None
            if "property_id" in data and type(data['property_id']) == list and  len(data['property_id'])> 0:
                property_id = data['property_id']

            portfolio_image = None
            if "portfolio_image" in data and type(data['portfolio_image']) == list and len(data['portfolio_image']) > 0:
                portfolio_image = data['portfolio_image']
            
            with transaction.atomic():
                serializer = AddPortfolioSerializer(portfolio_id, data=data)
                if serializer.is_valid():
                    portfolio_id = serializer.save()
                    portfolio_id = portfolio_id.id
                else:
                    transaction.set_rollback(True)  # -----Rollback Transaction----
                    copy_errors = serializer.errors.copy()
                    return Response(response.parsejson(copy_errors, "", status=403))
                try:
                    PropertyPortfolio.objects.filter(portfolio=portfolio_id).delete()
                    if property_id is not None:
                        # PropertyPortfolio.objects.filter(portfolio=portfolio_id).delete()
                        for prop_id in property_id:
                            check_portfolio = PropertyPortfolio.objects.filter(property=prop_id).first()
                            if check_portfolio is None:
                                property_portfolio = PropertyPortfolio()
                                property_portfolio.portfolio_id = portfolio_id
                                property_portfolio.property_id = prop_id
                                property_portfolio.status_id = 1
                                property_portfolio.save()
                            else:
                                transaction.set_rollback(True)  # -----Rollback Transaction----
                                return Response(response.parsejson("Property already in portfolio.", "", status=403))
                    if portfolio_image is not None:
                        PropertyPortfolioImages.objects.filter(portfolio=portfolio_id).delete()
                        for image in portfolio_image:
                            property_portfolio_images = PropertyPortfolioImages()
                            property_portfolio_images.portfolio_id = portfolio_id
                            property_portfolio_images.upload_id = image
                            property_portfolio_images.status_id = 1
                            property_portfolio_images.save()
                except Exception as exp:
                    transaction.set_rollback(True)  # -----Rollback Transaction----
                    return Response(response.parsejson(str(exp), exp, status=403))
            return Response(response.parsejson("Portfolio added successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PortfolioListingApiView(APIView):
    """
    Portfolio Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))
            
            is_agent = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                    is_agent = True
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            portfolio = Portfolio.objects.filter(domain=domain_id)
            if is_agent is not None:
                portfolio = portfolio.filter(user=user_id)
            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                portfolio = portfolio.annotate(full_name=Concat('user__first_name', V(' '), 'user__last_name')).filter(Q(full_name__icontains=search) | Q(user__email__icontains=search) | Q(name__icontains=search))
            total = portfolio.count()
            portfolio = portfolio.order_by("-id").only('id')[offset: limit]
            serializer = PortfolioListingSerializer(portfolio, many=True)
            all_data = {'total': total, 'data': serializer.data}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PortfolioDetailApiView(APIView):
    """
    Portfolio Detail
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            is_agent = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                    is_agent = True
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "portfolio_id" in data and data['portfolio_id'] != "":
                portfolio_id = int(data['portfolio_id'])
            else:
                return Response(response.parsejson("portfolio_id is required", "", status=403))

            portfolio = Portfolio.objects.filter(id=portfolio_id, domain=domain_id)
            if is_agent is not None:
                portfolio = portfolio.filter(user=user_id)
                
            portfolio = portfolio.first()
            serializer = PortfolioDetailSerializer(portfolio)
            return Response(response.parsejson("Fetch data.", serializer.data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PortfolioDeleteImageApiView(APIView):
    """
    Portfolio Delete Image
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            is_agent = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1,
                                                 network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                    is_agent = True
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "upload_id" in data and data['upload_id'] != "":
                upload_id = int(data['upload_id'])
            else:
                return Response(response.parsejson("upload_id is required", "", status=403))

            PropertyPortfolioImages.objects.filter(upload=upload_id, portfolio__domain=domain_id).delete()
            UserUploads.objects.filter(id=upload_id).delete()
            return Response(response.parsejson("Image deleted successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PortfolioPropertyListApiView(APIView):
    """
    Portfolio Property List
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            is_agent = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1,
                                                 network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                    is_agent = True
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            portfolio_id = None
            if "portfolio_id" in data and data['portfolio_id'] != "":
                portfolio_id = int(data['portfolio_id'])
            if portfolio_id is None:
                data = PropertyListing.objects.annotate(p_count=Count("property_portfolio_property__portfolio")).filter(domain=domain_id, sale_by_type=1, property_asset=1, p_count__lt=1, status=1)
            else:
                data = PropertyListing.objects.annotate(p_count=Count("property_portfolio_property__portfolio", filter=~Q(property_portfolio_property__portfolio__id=portfolio_id))).filter(domain=domain_id, sale_by_type=1, property_asset=1, p_count__lt=1, status=1)
            if is_agent is not None:
                data = data.filter(agent=user_id)
            data = data.values('id', 'address_one', 'address_two', 'city', 'postal_code', state_name=F('state__state_name'))
            return Response(response.parsejson("Fetch data.", data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyTotalViewApiView(APIView):
    """
    Property total view
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                # Translators: This message appears when site_id is empty
                return Response(response.parsejson("site_id is required.", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=site_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=site_id, network_user__is_agent=1, network_user__status=1, status=1, user_type=2).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required", "", status=403))

            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            property_detail = PropertyListing.objects.get(Q(id=property_id) & Q(domain=site_id))
            property_detail = ViewCountPropertyDetailSerializer(property_detail)

            view_data = PropertyView.objects.filter(domain=site_id, property=property_id)
            if "search" in data and data['search'] != "":
                view_data = view_data.annotate(full_name=Concat('user__first_name', V(' '),'user__last_name')).filter(Q(full_name__icontains=data['search']) | Q(user__email__icontains=data['search']) | Q(user__phone_no__icontains=data['search']))
            total = view_data.count()
            view_data = view_data.order_by("-id").only("id")[offset:limit]
            serializer = PropertyVewCountDetailSerializer(view_data, many=True)
            all_data = {"property_detail": property_detail.data, "data": serializer.data, "total": total}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyTotalWatcherApiView(APIView):
    """
    Property total watcher
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                # Translators: This message appears when site_id is empty
                return Response(response.parsejson("site_id is required.", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=site_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=site_id, network_user__is_agent=1, network_user__status=1, status=1, user_type=2).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required", "", status=403))

            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            property_detail = PropertyListing.objects.get(Q(id=property_id) & Q(domain=site_id))
            property_detail = ViewCountPropertyDetailSerializer(property_detail)

            watcher_data = PropertyWatcher.objects.filter(property__domain=site_id, property=property_id)
            if "search" in data and data['search'] != "":
                watcher_data = watcher_data.annotate(full_name=Concat('user__first_name', V(' '),'user__last_name')).filter(Q(full_name__icontains=data['search']) | Q(user__email__icontains=data['search']) | Q(user__phone_no__icontains=data['search']))
            total = watcher_data.count()
            watcher_data = watcher_data.order_by("-id").only("id")[offset:limit]
            serializer = PropertyWatcherCountDetailSerializer(watcher_data, many=True)
            all_data = {"property_detail": property_detail.data, "data": serializer.data, "total": total}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class ParcelDetailApiView(APIView):
    """
    Parcel Detail
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            user_id = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])

            if "parcel_id" in data and data['parcel_id'] != "":
                parcel_id = int(data['parcel_id'])
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("parcel_id is required", "", status=403))

            total_portfolio = PropertyPortfolio.objects.filter(portfolio__domain=domain_id, portfolio=parcel_id, status=1)
            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                if search.isdigit():
                    total_portfolio = total_portfolio.filter(Q(id=search) | Q(property__postal_code__icontains=search))
                else:
                    total_portfolio = total_portfolio.annotate(property_name=Concat('property__address_one', V(', '), 'property__city', V(', '), 'property__state__state_name', V(' '), 'property__postal_code', output_field=CharField())).filter(Q(property__city__icontains=search) | Q(property__state__state_name__icontains=search) | Q(property__address_one__icontains=search) | Q(property__postal_code__icontains=search) | Q(property__property_asset__name__icontains=search) | Q(property__sale_by_type__auction_type__icontains=search) | Q(property_name__icontains=search))
            total = total_portfolio.count()
            total_portfolio = total_portfolio.order_by("-id").only("id")[offset:limit]
            serializer = ParcelDetailSerializer(total_portfolio, many=True, context=user_id)
            portfolio = Portfolio.objects.filter(domain=domain_id, id=parcel_id, status=1).first()
            portfolio_detail = {"name": portfolio.name, "details": portfolio.details, "terms": portfolio.terms, "contact": portfolio.contact}
            all_data = {"data": serializer.data, "total": total, "portfolio_detail": portfolio_detail}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AdminPortfolioListingApiView(APIView):
    """
    Admin Portfolio Listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                users = Users.objects.filter(id=admin_id, user_type=3, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            domain = None
            if "domain" in data and len(data['domain']) > 0 and type(data['domain']) == list:
                domain = data['domain']

            portfolio = Portfolio.objects.filter(status=1)
            if domain is not None:
                portfolio = portfolio.filter(domain__in=domain)
            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                portfolio = portfolio.annotate(full_name=Concat('user__first_name', V(' '), 'user__last_name')).filter(
                    Q(full_name__icontains=search) | Q(user__email__icontains=search) | Q(name__icontains=search))
            total = portfolio.count()
            portfolio = portfolio.order_by("-id").only('id')[offset: limit]
            serializer = AdminPortfolioListingSerializer(portfolio, many=True)
            all_data = {'total': total, 'data': serializer.data}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AdminAddPortfolioApiView(APIView):
    """
    Admin Add Portfolio
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain" in data and data['domain'] != "":
                domain = int(data['domain'])
                network = NetworkDomain.objects.filter(id=domain, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
                users = Users.objects.filter(site=domain, user_type=2, status=1).first()
                if users is None:
                    return Response(response.parsejson("No broker account exist.", "", status=403))
                data['user'] = users.id
            else:
                return Response(response.parsejson("domain is required", "", status=403))

            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                users = Users.objects.filter(id=admin_id, user_type=3, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            portfolio_id = None
            if "portfolio_id" in data and data['portfolio_id'] != "":
                portfolio_id = int(data['portfolio_id'])
                portfolio_id = Portfolio.objects.get(id=portfolio_id)

            if "name" in data and data['name'] != "":
                name = data['name']
            else:
                return Response(response.parsejson("name is required.", "", status=403))

            details = None
            if "details" in data and data['details'] != "":
                details = data['details']

            terms = None
            if "terms" in data and data['terms'] != "":
                terms = data['terms']

            contact = None
            if "contact" in data and data['contact'] != "":
                contact = data['contact']

            if "status" in data and data['status'] != "":
                status = int(data['status'])
            else:
                return Response(response.parsejson("status is required.", "", status=403))

            property_id = None
            if "property_id" in data and type(data['property_id']) == list and len(data['property_id']) > 0:
                property_id = data['property_id']

            portfolio_image = None
            if "portfolio_image" in data and type(data['portfolio_image']) == list and len(data['portfolio_image']) > 0:
                portfolio_image = data['portfolio_image']

            with transaction.atomic():
                serializer = AddPortfolioSerializer(portfolio_id, data=data)
                if serializer.is_valid():
                    portfolio_id = serializer.save()
                    portfolio_id = portfolio_id.id
                else:
                    transaction.set_rollback(True)  # -----Rollback Transaction----
                    copy_errors = serializer.errors.copy()
                    return Response(response.parsejson(copy_errors, "", status=403))
                try:
                    PropertyPortfolio.objects.filter(portfolio=portfolio_id).delete()
                    if property_id is not None:
                        # PropertyPortfolio.objects.filter(portfolio=portfolio_id).delete()
                        for prop_id in property_id:
                            check_portfolio = PropertyPortfolio.objects.filter(property=prop_id).first()
                            if check_portfolio is None:
                                property_portfolio = PropertyPortfolio()
                                property_portfolio.portfolio_id = portfolio_id
                                property_portfolio.property_id = prop_id
                                property_portfolio.status_id = 1
                                property_portfolio.save()
                            else:
                                transaction.set_rollback(True)  # -----Rollback Transaction----
                                return Response(response.parsejson("Property already in portfolio.", "", status=403))
                    if portfolio_image is not None:
                        PropertyPortfolioImages.objects.filter(portfolio=portfolio_id).delete()
                        for image in portfolio_image:
                            property_portfolio_images = PropertyPortfolioImages()
                            property_portfolio_images.portfolio_id = portfolio_id
                            property_portfolio_images.upload_id = image
                            property_portfolio_images.status_id = 1
                            property_portfolio_images.save()
                except Exception as exp:
                    transaction.set_rollback(True)  # -----Rollback Transaction----
                    return Response(response.parsejson(str(exp), exp, status=403))
            return Response(response.parsejson("Portfolio added successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AdminPortfolioDetailApiView(APIView):
    """
    Admin Portfolio Detail
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "admin_id" in data and data['admin_id'] != "":
                admin_id = int(data['admin_id'])
                users = Users.objects.filter(id=admin_id, user_type=3, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                return Response(response.parsejson("admin_id is required.", "", status=403))

            if "portfolio_id" in data and data['portfolio_id'] != "":
                portfolio_id = int(data['portfolio_id'])
            else:
                return Response(response.parsejson("portfolio_id is required", "", status=403))

            portfolio = Portfolio.objects.filter(id=portfolio_id)

            portfolio = portfolio.first()
            serializer = AdminPortfolioDetailSerializer(portfolio)
            return Response(response.parsejson("Fetch data.", serializer.data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class BulkPropertyUploadApiView(APIView):
    """ This is BulkPropertyUploadApiView class

    """
    authentication_classes = [TokenAuthentication, OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            if 'domain_id' in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
            else:
                return Response(response.parsejson("domain_id is required", '', status=403))

            if 'user_id' in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                try:
                    Users.objects.get(id=user_id, user_type=2, status=1)
                except Exception as exp:
                    return Response(response.parsejson("Not valid user", '', status=403))
            else:
                return Response(response.parsejson("user_id is required", '', status=403))

            if 'csv_url' in data and data['csv_url'] != "":
                csv_url = data['csv_url']
            else:
                return Response(response.parsejson("csv_url is required", '', status=403))
            # csv_url = 'https://new-realtyonegroup.s3.us-west-1.amazonaws.com/property_image/1699522753.052704_sample.csv'
            csv_data = pd.read_csv(csv_url)
            csv_data = csv_data.fillna('')
            column_names = list(csv_data.columns.values)
            # ------------Check Heading-------------
            chk_heading = check_csv_heading(column_names)  # CSV Checking Method Call
            if chk_heading == 'notMatch':  # Checking csv heading
                return Response(response.parsejson("Invalid heading", "", status=404))

            # ------------Check Data Type-------------
            data_validation = csv_data_validation(csv_data)
            if type(data_validation) is not list:
                return Response(response.parsejson(str(data_validation), "", status=404))

            # ------------Property Data Entry-------------
            for items in data_validation:
                with transaction.atomic():
                    try:
                        # ---------------------Add Property--------------
                        listing_data = {
                            'domain': domain_id,
                            'agent': user_id,
                            'is_approved': 1,
                            'status': 1,
                            'title': 'Testing',
                            'property_asset': items['property_asset_id'] if 'property_asset_id' in items else None,
                            'property_type': items['property_type_id'] if 'property_type_id' in items else None,
                            # 'property_type': items['subtype'] if 'subtype_id' in items else None
                            'beds': items['beds'] if 'beds' in items else None,
                            'baths': items['baths'] if 'baths' in items else None,
                            'square_footage': items['square_footage'] if 'square_footage' in items else None,
                            'year_built': items['year_built'] if 'year_built' in items else None,
                            'country': items['country_id'] if 'country_id' in items else None,
                            'address_one': items['address_one'] if 'address_one' in items else None,
                            'postal_code': items['postal_code'] if 'postal_code' in items else None,
                            'city': items['city'] if 'city' in items else None,
                            'state': items['state_id'] if 'state_id' in items else None,
                            'sale_by_type': items['sale_by_type_id'] if 'sale_by_type_id' in items else None,
                            'is_featured': items['is_featured'] if 'is_featured' in items else None,
                            'buyers_premium': items['buyers_premium'] if 'buyers_premium' in items else 0,
                            'buyers_premium_percentage': items['buyers_premium_percentage'] if 'buyers_premium_percentage' in items else None,
                            'buyers_premium_min_amount': items['buyers_premium_min_amount'] if 'buyers_premium_min_amount' in items else None,
                            'description': items['description'] if 'description' in items else None,
                            'sale_terms': items['sale_terms'] if 'sale_terms' in items else None,
                            'due_diligence_period': items['due_diligence_period'] if 'due_diligence_period' in items else None,
                            'escrow_period': items['escrow_period'] if 'escrow_period' in items else None,
                            'highest_best_format': items['highest_best_format'] if 'highest_best_format' in items else 3,
                            'auction_location': items['auction_location'] if 'auction_location' in items else None,
                            'total_acres': items['total_acres'] if 'total_acres' in items else None,
                        }

                        serializer = AddBulkPropertySerializer(data=listing_data)
                        if serializer.is_valid():
                            property_id = serializer.save()
                            property_id = property_id.id

                        else:
                            copy_errors = serializer.errors.copy()
                            return Response(response.parsejson(copy_errors, "", status=403))

                        auction_data = {
                            'domain': domain_id,
                            'property': property_id,
                            'start_date': items['bidding_starting_time'] if 'bidding_starting_time' in items else None,
                            'end_date': items['bidding_ending_time'] if 'bidding_ending_time' in items else None,
                            'reserve_amount': items['reserve_amount'] if 'reserve_amount' in items else None,
                            'bid_increments': items['bid_increments'] if 'bid_increments' in items else None,
                            'status': 1,
                            'start_price': items['bidding_min_price'] if 'bidding_min_price' in items else None,
                            'open_house_start_date': items['open_house_start_date'] if 'open_house_start_date' in items else None,
                            'open_house_end_date': items['open_house_end_date'] if 'open_house_end_date' in items else None,
                            'offer_amount': items['bidding_min_price'] if 'bidding_min_price' in items else None,
                            'auction': items['sale_by_type_id'] if 'sale_by_type_id' in items else None,
                        }
                        # print(property_id)
                        # print(auction_data)
                        serializer = AddBulkAuctionSerializer(data=auction_data)
                        if serializer.is_valid():
                            auction_id = serializer.save()
                            auction_id = auction_id.id
                        else:
                            copy_errors = serializer.errors.copy()
                            return Response(response.parsejson(copy_errors, "", status=403))

                        # ------------------PropertySubtype---------------
                        if 'subtype_id' in items and type(items['subtype_id']) == int and items['subtype_id'] > 0:
                            property_subtype = PropertySubtype()
                            property_subtype.property_id = property_id
                            property_subtype.subtype_id = items['subtype_id']
                            property_subtype.save()
                    except Exception as exp:
                        transaction.set_rollback(True)  # -----Rollback Transaction----
                        return Response(response.parsejson(str(exp), exp, status=403))

            return Response(response.parsejson("success", "", status=201))
        except Exception as exp:
            return Response(response.parsejson("Unable to process", "", status=403))


class PropertyTypeApiView(APIView):
    """ This is PropertyTypeApiView class

    """
    authentication_classes = [TokenAuthentication, OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            if 'asset_id' in data and data['asset_id'] != "":
                asset_id = int(data['asset_id'])
            else:
                asset_id = None

            property_type = LookupPropertyType.objects
            if asset_id is not None:
                property_type = property_type.filter(asset=asset_id, is_active=1)
            else:
                property_type = property_type.filter(is_active=1) 

            property_type = property_type.order_by("-id").values("id", "property_type")      
            return Response(response.parsejson("Fetch data", property_type, status=201))
        except Exception as exp:
            return Response(response.parsejson("Unable to process", "", status=403))        


class PropertyListingExportApiView(APIView):
    """
    Property listing
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))
            user_domain = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=site_id, user_type=2, status=1).first()
                is_agent = None
                if users is None:
                    is_agent = True
                    users = Users.objects.filter(id=user_id, network_user__domain=site_id, network_user__is_agent=1, network_user__status=1, status=1, user_type=2).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                data["agent"] = user_id
                user_domain = users.site_id
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            property_listing = PropertyListing.objects.filter(domain=site_id, portfolio__isnull=True).exclude(status=5)
            if is_agent is not None:
                property_listing = property_listing.filter(agent=user_id)

            # -----------------Filter-------------------
            
            if "agent_id" in data and data["agent_id"] != "":
                agent_id = int(data["agent_id"])
                property_listing = property_listing.filter(Q(agent=agent_id))
            if "auction_id" in data and data["auction_id"] != "":
                auction_id = int(data["auction_id"])
                property_listing = property_listing.filter(Q(sale_by_type=auction_id))

            if "asset_id" in data and data["asset_id"] != "":
                asset_id = int(data["asset_id"])
                property_listing = property_listing.filter(Q(property_asset=asset_id))

            if "status" in data and data["status"] != "":
                status = int(data["status"])
                property_listing = property_listing.filter(Q(status=status))

            if "property_type" in data and data["property_type"] != "":
                property_type = int(data["property_type"])
                property_listing = property_listing.filter(Q(property_type=property_type))

            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                property_listing = property_listing.annotate(property_name=Concat('address_one', V(', '), 'city', V(', '), 'state__state_name', V(' '), 'postal_code', output_field=CharField())).annotate(full_name=Concat('agent__user_business_profile__first_name', V(' '), 'agent__user_business_profile__last_name')).filter(Q(property_asset__name__icontains=search) | Q(sale_by_type__auction_type__icontains=search) | Q(agent__user_business_profile__company_name__icontains=search) | Q(full_name__icontains=search) | Q(city__icontains=search) | Q(address_one__icontains=search) | Q(state__state_name__icontains=search) | Q(property_type__property_type__icontains=search) | Q(property_name__icontains=search) | Q(postal_code__icontains=search))

            total = property_listing.count()
            property_listing = property_listing.order_by(F("ordering").asc(nulls_last=True)).only("id")
            serializer = PropertyListingSerializer(property_listing, many=True)
            all_data = {"data": serializer.data, "total": total, "user_domain": user_domain}
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            print('exp', exp)
            return Response(response.parsejson(str(exp), exp, status=403))


class SubdomainPropertyEvaluatorExportApiView(APIView):
    """
    Subdomain Property Evaluator
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network = NetworkDomain.objects.filter(id=domain_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            is_agent = None

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, site=domain_id, user_type=2, status=1).first()
                if users is None:
                    users = Users.objects.filter(id=user_id, network_user__domain=domain_id, network_user__status=1, network_user__is_agent=1, status=1, user_type__in=[1, 2]).first()
                    if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                    is_agent = True
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))
            agent_list = Users.objects.filter(network_user__domain=domain_id, network_user__status=1, network_user__is_agent=1, status=1).order_by("-id").values("id", "first_name", "last_name", "email")
            property_evaluator_domain = PropertyEvaluatorDomain.objects.filter(domain=domain_id, status=1)
            if is_agent is not None:
                property_evaluator_domain = property_evaluator_domain.filter(assign_to=user_id)
            # -----------------Search-------------------
            if 'search' in data and data['search'] != "":
                search = data['search'].strip()
                # if search.isdigit():
                #     property_listing = property_listing.filter(Q(id=search) | Q(postal_code__icontains=search))
                # else:
                property_evaluator_domain = property_evaluator_domain.annotate(full_name=Concat('user__first_name', V(' '),'user__last_name')).filter(Q(full_name__icontains=search) | Q(user__email__icontains=search) | Q(user__phone_no__icontains=search))
            total = property_evaluator_domain.count()
            property_evaluator_domain = property_evaluator_domain.order_by("-id").only('id')
            serializer = SubdomainPropertyEvaluatorSerializer(property_evaluator_domain, many=True)
            all_data = {'total': total, 'data': serializer.data, "agent_list": agent_list}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyApprovalApiView(APIView):
    """
    Property approval
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                # Translators: This message appears when site_id is empty
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4], status=1).first()
                if users is None:
                    return Response(response.parsejson("You are not authentic user to update property.", "", status=403))
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            # --- Verify that user_id matches the token user ---
            auth_user = request.user  # user from Bearer token
            if int(user_id) != auth_user.id:
                return Response(response.parsejson("Permission denied.", "", status=403))    

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required", "", status=403))

            if "is_approved" in data and data['is_approved'] != "":
                is_approved = data['is_approved']
            else:
                # Translators: This message appears when is_approved is empty
                return Response(response.parsejson("is_approved is required", "", status=403))

            return_reason = ""
            if "return_reason" in data and data['return_reason'] != "":
                return_reason = data['return_reason']    

            PropertyListing.objects.filter(id=property_id, domain=site_id).update(seller_status_id=is_approved, seller_property_return_reason=return_reason)
            try:
                #-------------Email--------------------
                property_detail = PropertyListing.objects.get(id=property_id)
                property_name = property_detail.property_name
                property_approved_status = property_detail.seller_status.status_name
                user_detail = Users.objects.get(id=property_detail.agent_id)
                project_detail = DeveloperProject.objects.get(id=property_detail.project_id)
                property_user_name = user_detail.first_name
                project_name  = project_detail.project_name
                agent_email = user_detail.email
                property_state = property_detail.state.state_name
                community = property_detail.community
                property_type = property_detail.property_type.property_type
                asset_type = "Residential"
                upload = PropertyUploads.objects.filter(property=property_id, upload_type=1).first()
                # web_url = settings.BASE_URL
                web_url = network.domain_url
                image_url = network.domain_url+'static/images/property-default-img.png'
                if upload is not None:
                    image = upload.upload.doc_file_name
                    bucket_name = upload.upload.bucket_name
                    image_url = settings.AZURE_BLOB_URL+bucket_name+'/'+image
                
                if is_approved and int(is_approved) == 24:
                    decorator_url = property_detail.property_name.lower() + " " + property_detail.country.country_name.lower()
                    decorator_url = re.sub(r"\s+", '-', decorator_url)
                    domain_url = network.domain_react_url+"seller/property/"+str(property_id)+"/"+decorator_url
                    template_data = {"domain_id": site_id, "slug": "listing_approval_under_review"}
                    extra_data = {
                        'property_user_name': property_user_name,
                        'property_approved_status': property_approved_status,
                        'web_url': web_url,
                        'property_image': image_url,
                        'property_state': property_state,
                        'dashboard_link': domain_url,
                        "domain_id": site_id,
                        "property_name": property_name,
                        "project_name": project_name,
                        "community": community,
                        "property_type": property_type,
                    }
                elif is_approved and int(is_approved) == 28:
                    decorator_url = property_detail.property_name.lower() + " " + property_detail.country.country_name.lower()
                    decorator_url = re.sub(r"\s+", '-', decorator_url)
                    domain_url = network.domain_react_url+"seller/auction/detail/"+str(property_id)+"/"+decorator_url
                    template_data = {"domain_id": site_id, "slug": "listing_approval_ready_for_publish"}
                    extra_data = {
                        'property_user_name': property_user_name,
                        'property_approved_status': property_approved_status,
                        'web_url': web_url,
                        'property_image': image_url,
                        'property_state': property_state,
                        'dashboard_link': domain_url,
                        "domain_id": site_id,
                        "property_name": property_name,
                        "project_name": project_name,
                        "community": community,
                        "property_type": property_type,
                    }
                elif is_approved and int(is_approved) == 29:
                    domain_url = network.domain_react_url+"notification/"+str(property_id)
                    template_data = {"domain_id": site_id, "slug": "listing_approval"}
                    extra_data = {
                        'property_user_name': property_user_name,
                        'property_approved_status': property_approved_status,
                        'web_url': web_url,
                        'property_image': image_url,
                        'property_state': property_state,
                        'dashboard_link': domain_url,
                        "domain_id": site_id,
                        "property_name": property_name,
                        "project_name": project_name,
                        "return_reason": return_reason,
                        "community": community,
                        "property_type": property_type,
                    }  
                compose_email(to_email=[agent_email], template_data=template_data, extra_data=extra_data)
            except Exception as exp:
                pass
            # send notif to agent for approved or not approved
            try:
                prop_name = property_detail.property_name
                prop_name_ar = property_detail.property_name_ar
                if is_approved and int(is_approved) == 28:
                    decorator_url = property_detail.property_name.lower() + " " + property_detail.country.country_name.lower()
                    decorator_url = re.sub(r"\s+", '-', decorator_url)
                    redirect_url = network.domain_react_url+"seller/auction/detail/"+str(property_id)+"/"+decorator_url
                    # content = '<div class="icon orange-bg"><img src="img/success.svg" alt="Reload Icon"></div><div class="text"><h6>Your property "'+prop_name+'" is ready for publish!</h6><a class="btn btn-sky btn-xs" href="'+redirect_url+'">Put it on Auction</a></div>'
                    notification_extra_data = {'image_name': 'check-icon.svg', 'property_name': prop_name, 'property_name_ar': prop_name_ar, 'redirect_url': redirect_url}
                    notification_extra_data['app_content'] = 'Your property <b>'+prop_name+'</b> has been <b>approved</b> for auction.'
                    notification_extra_data['app_content_ar'] = 'تمت الموافقة على طرحه في المزاد. '+ '<b>' + prop_name_ar + '</b> ' +' ممتلكاتك'
                    notification_extra_data['app_screen_type'] = 4
                    notification_extra_data['app_notification_image'] = 'check-icon.png'
                    notification_extra_data['app_notification_button_text'] = 'Put it on Auction'
                    notification_extra_data['app_notification_button_text_ar'] = 'منظر'
                    notification_extra_data['property_id'] = property_id
                    template_slug = "listing_approval_ready_for_publish"
                    message = 'Your property '+prop_name+' is ready for publish.'
                    redirect_to = 3
                elif is_approved and int(is_approved) == 29:
                    redirect_url = network.domain_react_url+"notification/"+str(property_id)
                    # content = '<div class="icon orange-bg"><img src="img/reject.svg" alt="Reload Icon"></div><div class="text"><h6>Your property "'+prop_name+'" is returned for update[Reason: '+return_reason+']!</h6><a class="btn btn-sky btn-xs" href="'+redirect_url+'">View</a></div> '
                    notification_extra_data = {'image_name': 'reload-icon.svg', 'property_name': prop_name, 'property_name_ar': prop_name_ar, 'reason': return_reason, 'redirect_url': redirect_url}
                    # notification_extra_data['app_content'] = 'Your property '+prop_name+' is returned for update[Reason: '+return_reason+']'
                    notification_extra_data['app_content'] = 'Your property <b>'+prop_name+'</b> has been <b>Returned</b>.'
                    notification_extra_data['app_content_ar'] = 'لقد تم إرجاعه '+ '<b>' + prop_name_ar + '</b> ' +' ممتلكاتك'
                    notification_extra_data['app_screen_type'] = 5
                    notification_extra_data['app_notification_image'] = 'reload-icon.png'
                    notification_extra_data['app_notification_button_text'] = 'Resubmit Property'
                    notification_extra_data['app_notification_button_text_ar'] = 'إعادة إرسال الملكية'
                    notification_extra_data['property_id'] = property_id
                    template_slug = "listing_approval"
                    message = 'Your property '+prop_name+' is returned for update[Reason: '+return_reason+']'
                    redirect_to = 4
                elif is_approved and int(is_approved) == 24:
                    decorator_url = property_detail.property_name.lower() + " " + property_detail.country.country_name.lower()
                    decorator_url = re.sub(r"\s+", '-', decorator_url)
                    redirect_url = network.domain_react_url+"seller/property/"+str(property_id)+"/"+decorator_url
                    # content = '<div class="icon orange-bg"><img src="img/review.svg" alt="Reload Icon"></div><div class="text"><h6>Your property "'+prop_name+'" is under review!</h6><a class="btn btn-sky btn-xs" href="'+redirect_url+'">View</a></div>'
                    notification_extra_data = {'image_name': 'review.svg', 'property_name': prop_name, 'property_name_ar': prop_name_ar, 'redirect_url': redirect_url}
                    notification_extra_data['app_content'] = 'Your property <b>'+prop_name+'</b> is <b>under review</b>.'
                    notification_extra_data['app_content_ar'] = 'ممتلكاتك '+ '<b>' + prop_name_ar + '</b> ' + ' قيد المراجعة'
                    notification_extra_data['app_screen_type'] = 6
                    notification_extra_data['app_notification_image'] = 'review.png'
                    notification_extra_data['app_notification_button_text'] = 'View Details'
                    notification_extra_data['app_notification_button_text_ar'] = 'عرض التفاصيل'
                    notification_extra_data['property_id'] = property_id
                    template_slug = "listing_approval_under_review"
                    message = 'Your property '+prop_name+' is move to under review.'
                    redirect_to = 5

                add_notification(
                    site_id,
                    user_id=property_detail.agent_id,
                    added_by=property_detail.agent_id,
                    notification_for=1,
                    template_slug=template_slug,
                    extra_data=notification_extra_data
                )

                # -------Push Notifications-----
                data = {
                    "title": "Property Approval", 
                    "message": message,
                    "description": message,
                    "notification_to": property_detail.agent_id,
                    "property_id": property_id,
                    "redirect_to": redirect_to
                }
                save_push_notifications(data)
            except Exception as e:
                pass
            property_listing = PropertyListing.objects.filter(id=property_id, domain=site_id).last()
            all_data = {"agent_id": property_listing.agent_id, "domain_id": property_listing.domain_id}
            return Response(response.parsejson("Approval changed successfully.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AddListingApiView(APIView):
    """
    Super Admin Add/Update Property
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))
            
            
            if "user_id" in data and data['user_id'] != "":
                developer_id = user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5, 6], status=1).first()
                if users is None:
                        return Response(response.parsejson("User not exist.", "", status=403))
                creater_user_type = users.user_type_id
                if users.user_type_id == 5:
                    network_user = NetworkUser.objects.filter(domain=site_id, user=user_id, status=1).last()
                    if network_user is not None and network_user.developer_id is not None:
                        developer_id = network_user.developer_id
                    else:
                        developer_id = ""    
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))
                
            # --- Verify that user_id matches the token user ---
            auth_user = request.user  # user from Bearer token
            if int(user_id) != auth_user.id:
                return Response(response.parsejson("Permission denied.", "", status=403))    

            if "create_step" in data and data['create_step'] != "":
                step = int(data['create_step'])
            else:
                return Response(response.parsejson("create_step is required.", "", status=403))  
            auction_id = None
            seller_status_id = None
            relist = None
            if step == 1:
                property_id = None
                if "property_id" in data and data['property_id'] != "" and data["property_id"] is not None:
                    property_id = int(data['property_id'])
                    property_id = PropertyListing.objects.filter(id=property_id).first()
                    if property_id is None:
                        return Response(response.parsejson("Property not exist.", "", status=403))
                    seller_status_id = property_id.seller_status_id
                    if users.site_id is None:
                        data['seller_status'] = 24
                else:
                    data["agent"] = user_id
                    data['developer'] = developer_id
                    data["domain"] = site_id
                    data['is_approved'] = 1 if users.site_id is not None else 0
                    data['seller_status'] = 28 if users.site_id is not None else 24
                    data['status'] = 1
                    data['property_for'] = 2

                if "map_url" in data and data['map_url'] != "":
                    map_url = data['map_url']
                else:
                    return Response(response.parsejson("map_url is required.", "", status=403))

                if "country" in data and data['country'] != "":
                    country = data['country']
                else:
                    return Response(response.parsejson("country is required.", "", status=403))    

                if "state" in data and data['state'] != "":
                    state = int(data['state'])
                    data['city'] = state
                else:
                    return Response(response.parsejson("state is required.", "", status=403))

                if "owners" in data and type(data['owners']) == list and len(data['owners']) > 0:
                    owners = data['owners']
                else:
                    return Response(response.parsejson("owners is required.", "", status=403))    

                if "municipality" in data and data['municipality'] != "":
                    municipality = int(data['municipality'])
                else:
                    return Response(response.parsejson("municipality is required.", "", status=403))

                if "district" in data and data['district'] != "":
                    district = int(data['district'])
                else:
                    return Response(response.parsejson("district is required.", "", status=403))

                # if "project" in data and data['project'] != "":
                #     project = int(data['project'])
                # else:
                #     return Response(response.parsejson("project is required.", "", status=403))

                if "property_name" in data and data['property_name'] != "":
                    property_name = data['property_name']
                else:
                    return Response(response.parsejson("property_name is required.", "", status=403))
                
                if "community" in data and data['community'] != "":
                    community = data['community']
                else:
                    return Response(response.parsejson("community is required.", "", status=403))

                if "property_type" in data and data['property_type'] != "":
                    property_type = int(data['property_type'])
                else:
                    return Response(response.parsejson("property_type is required.", "", status=403))    

                if "building" in data and data['building'] != "":
                    building = data['building']
                else:
                    return Response(response.parsejson("building is required.", "", status=403))

                if "square_footage" in data and data["square_footage"] != "":
                    data["square_footage"] = data["square_footage"]
                else:
                    return Response(response.parsejson("square_footage is required.", "", status=403))

                if "beds" in data and data["beds"] != "":
                    data["beds"] = data["beds"]
                else:
                    return Response(response.parsejson("beds is required.", "", status=403))

                if "baths" in data and data["baths"] != "":
                    data["baths"] = data["baths"]
                else:
                    return Response(response.parsejson("baths is required.", "", status=403))

                if "number_of_outdoor_parking_spaces" in data and data["number_of_outdoor_parking_spaces"] != "":
                    data["number_of_outdoor_parking_spaces"] = data["number_of_outdoor_parking_spaces"]
                else:
                    return Response(response.parsejson("number_of_outdoor_parking_spaces is required.", "", status=403))

                if "vacancy" in data and int(data["vacancy"]) in [1, 2]:
                    vacancy = data['vacancy']
                else:
                    return Response(response.parsejson("vacancy is required.", "", status=403))

                if "rental_till" in data and data['rental_till'] != "":
                    rental_till = data['rental_till']
                    if int(vacancy) == 2:
                        data['rental_till'] = None
                elif vacancy == 1:
                    return Response(response.parsejson("rental_till is required.", "", status=403))    

                if "construction_status" in data and data["construction_status"] != "":
                    construction_status = data['construction_status']
                else:
                    return Response(response.parsejson("construction_status is required.", "", status=403))
                
                if "amenities" in data and type(data['amenities']) == list and len(data['amenities']) > 0:
                    amenities = data['amenities']
                else:
                    return Response(response.parsejson("amenities is required.", "", status=403))

                if "tags" in data and type(data['tags']) == list and len(data['tags']) > 0:
                    tags = data['tags']
                else:
                    tags = []    

                if "description" in data and data["description"] != "":
                    description = data['description']
                else:
                    return Response(response.parsejson("description is required.", "", status=403))

                if "description_ar" in data and data["description_ar"] != "":
                    description_ar = data['description_ar']
                else:
                    return Response(response.parsejson("description_ar is required.", "", status=403))    
                 
                if "property_deed" in data and type(data['property_deed']) == list and len(data['property_deed']) > 0:
                    property_deed = data['property_deed']
                else:
                    return Response(response.parsejson("property_deed is required.", "", status=403))

                if "property_floor_plan" in data and type(data['property_floor_plan']) == list and len(data['property_floor_plan']) > 0:
                    property_floor_plan = data['property_floor_plan']
                else:
                    property_floor_plan = []
                    # return Response(response.parsejson("property_floor_plan is required.", "", status=403))

                if "property_cover_image" in data and type(data['property_cover_image']) == list and len(data['property_cover_image']) > 0:
                    property_cover_image = data['property_cover_image']
                else:
                    return Response(response.parsejson("property_cover_image is required.", "", status=403))

                if "property_image" in data and type(data['property_image']) == list and len(data['property_image']) > 0:
                    property_image = data['property_image']
                else:
                    return Response(response.parsejson("property_image is required.", "", status=403))

                property_video = []
                if "property_video" in data and type(data['property_video']) == list and len(data['property_video']) > 0:
                    property_video = data['property_video']
                # else:
                #     return Response(response.parsejson("property_video is required.", "", status=403))                   
                # data['property_for'] = 2
                with transaction.atomic():
                    try: 
                        serializer = AddPropertySerializer(property_id, data=data, partial=True)
                        if serializer.is_valid():
                            property_id = serializer.save()
                            property_id = property_id.id
                        else:
                            transaction.set_rollback(True)  # -----Rollback Transaction----
                            copy_errors = serializer.errors.copy()
                            return Response(response.parsejson(copy_errors, "", status=403))
                        # ----------------------Owners---------------------
                        if "owners" in data and type(data["owners"]) == list:
                            owners = data["owners"]
                            PropertyOwners.objects.filter(property=property_id).delete()
                            for owner in owners:
                                property_owners = PropertyOwners()
                                property_owners.property_id = property_id
                                property_owners.domain_id = site_id
                                
                                property_owners.name = owner["owner_name"]
                                # if data["account_verification_type"] != 2: 
                                #     property_owners.eid = owner["owner_eid"]
                                # else:
                                #     property_owners.passport = owner["owner_passport"]
                                if owner["owner_identity_type"] == 1: 
                                    property_owners.eid = owner["owner_eid"]
                                    property_owners.useEID = 'true'
                                else:
                                    property_owners.passport = owner["owner_passport"]
                                    property_owners.useEID = 'false'

                                property_owners.share_percentage = owner["owner_percentage"]
                                # property_owners.nationality = owner["owner_nationality"]
                                property_owners.owner_nationality_id = owner["owner_nationality"]
                                property_owners.dob = owner["owner_dob"]
                                property_owners.phone = owner["owner_phone"]
                                property_owners.email = owner["owner_email"]
                                property_owners.save()

                        if amenities is not None and len(amenities) > 0:
                            PropertyAmenity.objects.filter(property=property_id).delete()
                            for amenity in amenities:
                                property_amenities = PropertyAmenity()
                                property_amenities.property_id = property_id
                                property_amenities.amenities_id = amenity
                                property_amenities.save()

                        if tags is not None and len(tags) > 0:
                            PropertyTags.objects.filter(property=property_id).delete()
                            for tag in tags:
                                property_tags = PropertyTags()
                                property_tags.property_id = property_id
                                property_tags.tags_id = tag
                                property_tags.save()
                        else:
                            PropertyTags.objects.filter(property=property_id).delete()             
                        
                        if property_deed is not None and len(data["property_deed"]) > 0:
                            PropertyUploads.objects.filter(property=property_id, upload_type__in=[1, 3], upload_identifier=4).delete()
                            for deed in property_deed:
                                property_uploads = PropertyUploads()
                                property_uploads.upload_id = deed
                                property_uploads.property_id = property_id
                                property_uploads.upload_type = 3
                                property_uploads.status_id = 1
                                property_uploads.upload_identifier = 4
                                property_uploads.save()

                        if property_floor_plan is not None and len(property_floor_plan) > 0:
                            PropertyUploads.objects.filter(property=property_id, upload_type__in=[1, 3], upload_identifier=3).delete()
                            for floor_plan in property_floor_plan:
                                property_uploads = PropertyUploads()
                                property_uploads.upload_id = floor_plan
                                property_uploads.property_id = property_id
                                property_uploads.upload_type = 3
                                property_uploads.status_id = 1
                                property_uploads.upload_identifier = 3
                                property_uploads.save()

                        if property_cover_image is not None and len(property_cover_image) > 0:
                            PropertyUploads.objects.filter(property=property_id, upload_type=1, upload_identifier=1).delete()
                            for cover_image in property_cover_image:
                                property_uploads = PropertyUploads()
                                property_uploads.upload_id = cover_image
                                property_uploads.property_id = property_id
                                property_uploads.upload_type = 1
                                property_uploads.status_id = 1
                                property_uploads.upload_identifier = 1
                                property_uploads.save()

                        if property_image is not None and len(property_image) > 0:
                            PropertyUploads.objects.filter(property=property_id, upload_type=1, upload_identifier=2).delete()
                            for image in property_image:
                                property_uploads = PropertyUploads()
                                property_uploads.upload_id = image
                                property_uploads.property_id = property_id
                                property_uploads.upload_type = 1
                                property_uploads.status_id = 1
                                property_uploads.upload_identifier = 2
                                property_uploads.save()                        

                        if property_video is not None and len(property_video) > 0:
                            PropertyUploads.objects.filter(property=property_id, upload_type=2).delete()
                            for video in property_video:
                                property_uploads = PropertyUploads()
                                property_uploads.upload_id = video
                                property_uploads.property_id = property_id
                                property_uploads.upload_type = 2
                                property_uploads.upload_identifier = 5
                                property_uploads.status_id = 1
                                property_uploads.save()
                    except Exception as exp:
                        transaction.set_rollback(True)  # -----Rollback Transaction----
                        return Response(response.parsejson(str(exp), exp, status=403))
            elif step == 2:
                if "property" in data and data['property'] != "":
                    property_id = data['property']
                    property_data = PropertyListing.objects.filter(id=property_id).first()
                    if property_data is None:
                        return Response(response.parsejson("Property not exist.", "", status=403))
                else:
                    return Response(response.parsejson("property_id is required.", "", status=403))
                if "property_for" in data and data['property_for'] != "":
                    property_for = data['property_for']
                else:
                    return Response(response.parsejson("property_for is required.", "", status=403))
                
                if "start_price" in data and data['start_price'] != "":
                    start_price = data['start_price']
                else:
                    return Response(response.parsejson("start_price is required.", "", status=403))

                if "deposit_amount" in data and data['deposit_amount'] != "":
                    deposit_amount = data['deposit_amount']
                else:
                    return Response(response.parsejson("deposit_amount is required.", "", status=403))

                if "reserve_amount" in data and data['reserve_amount'] != "":
                    reserve_amount = data['reserve_amount']
                else:
                    return Response(response.parsejson("reserve_amount is required.", "", status=403)) 

                if "buyer_preference" in data and data['buyer_preference'] != "":
                    buyer_preference = data['buyer_preference']
                else:
                    return Response(response.parsejson("buyer_preference is required.", "", status=403)) 

                if "sell_at_full_amount_status" in data and data['sell_at_full_amount_status'] != "":
                    sell_at_full_amount_status = data['sell_at_full_amount_status']
                else:
                    return Response(response.parsejson("sell_at_full_amount_status is required.", "", status=403))

                if "full_amount" in data and data['full_amount'] != "":
                    full_amount = data['full_amount']
                else:
                    return Response(response.parsejson("full_amount is required.", "", status=403))

                if "bid_increment_status" in data and data['bid_increment_status'] != "":
                    bid_increment_status = data['bid_increment_status']
                else:
                    return Response(response.parsejson("bid_increment_status is required.", "", status=403))

                if "bid_increments" in data and data['bid_increments'] != "":
                    bid_increments = data['bid_increments']
                else:
                    return Response(response.parsejson("bid_increments is required.", "", status=403)) 

                if "start_date" in data and data['start_date'] != "":
                    start_date = data['start_date']
                else:
                    return Response(response.parsejson("start_date is required.", "", status=403)) 

                if "end_date" in data and data['end_date'] != "":
                    end_date = data['end_date']
                else:
                    return Response(response.parsejson("end_date is required.", "", status=403))

                is_featured = 0
                if "is_featured" in data and data['is_featured'] != "":
                    is_featured = data['is_featured']

                if "signature" in data and data['signature'] != "":
                    signature = data['signature']
                else:
                    return Response(response.parsejson("signature is required.", "", status=403))

                if "term_agreement" in data and data['term_agreement'] != "":
                    term_agreement = data['term_agreement']
                    if not term_agreement:
                        return Response(response.parsejson("Need to accept term agreement.", "", status=403)) 
                else:
                    return Response(response.parsejson("term_agreement is required.", "", status=403))    
                
                # if "relist" in data and data['relist'] != "" and int(data['relist']) == 1:
                #     relist = int(data['relist'])

                with transaction.atomic():
                    try:
                        property_auction = PropertyAuction.objects.filter(property=property_id).first()
                        data['domain'] = property_data.domain_id
                        data['time_zone'] = 575
                        data['status'] = 1
                        data['auction'] = 1
                        data['auction_unique_id'] = unique_registration_id()
                        serializer = AddPropertyAuctionSerializer(property_auction, data=data, partial=True)
                        if serializer.is_valid():
                            auction_id = serializer.save()
                            auction_id = auction_id.id
                        else:
                            transaction.set_rollback(True)  # -----Rollback Transaction----
                            copy_errors = serializer.errors.copy()
                            return Response(response.parsejson(copy_errors, "", status=403))

                        property_listing = PropertyListing.objects.get(id=property_id)
                        property_listing.deposit_amount = deposit_amount
                        property_listing.is_featured = is_featured
                        property_listing.seller_status_id = 27
                        property_listing.create_step = 4
                        property_listing.property_for = property_for
                        # if relist is not None:
                        #     property_listing.status_id = 1
                        #     property_listing.date_sold = None
                        #     property_listing.sold_price = 0.00
                        #     property_listing.winner_id = None
                            # -----Remove Highest Bidder Bid----
                            # Bid.objects.filter(property_id=property_id).update(selected_highest_bid=0)
                        property_listing.save() 

                        reservation_agreement = PropertyReservationAgreement.objects.filter(property=property_id).first()
                        if reservation_agreement is None:
                            reservation_agreement = PropertyReservationAgreement()
                        reservation_agreement.property_id = property_id
                        reservation_agreement.seller_id = property_data.agent_id
                        reservation_agreement.signature = signature
                        reservation_agreement.reservation_agreement_accepted = term_agreement
                        reservation_agreement.save()

                    except Exception as exp:
                        transaction.set_rollback(True)  # -----Rollback Transaction----
                        return Response(response.parsejson(str(exp), exp, status=403))
            elif step == 3:
                property_id = None
                owner_user_type = None 
                seller_status_id = None
                if "property_id" in data and data['property_id'] != "" and data["property_id"] is not None:
                    property_id = int(data['property_id'])
                    property_id = PropertyListing.objects.filter(id=property_id).first()
                    if property_id is None:
                        return Response(response.parsejson("Property not exist.", "", status=403))
                    seller_status_id = property_id.seller_status_id
                    if users.site_id is None:
                        data['seller_status'] = 24
                    user_id = property_id.agent_id 
                    owner_user_type = property_id.agent.user_type_id
                    # if owner_user_type == 1:
                    #     data['property_for'] = 1
                    # else:  
                    #     data['property_for'] = 2  
                else:
                    data["agent"] = user_id
                    data['developer'] = developer_id
                    data["domain"] = site_id
                    data['is_approved'] = 1 if users.site_id is not None else 0
                    data['seller_status'] = 27 if users.site_id is not None else 24
                    data['status'] = 1
                    # data['property_for'] = 2
                    owner_user_type = 2
                    seller_status_id = 27

                if "map_url" in data and data['map_url'] != "":
                    map_url = data['map_url']
                else:
                    return Response(response.parsejson("map_url is required.", "", status=403))    

                if "country" in data and data['country'] != "":
                    country = data['country']
                else:
                    return Response(response.parsejson("country is required.", "", status=403))

                if "state" in data and data['state'] != "":
                    state = int(data['state'])
                    data['city'] = state
                else:
                    return Response(response.parsejson("state is required.", "", status=403))

                if "owners" in data and type(data['owners']) == list and len(data['owners']) > 0:
                    owners = data['owners']
                else:
                    return Response(response.parsejson("owners is required.", "", status=403))    

                if "municipality" in data and data['municipality'] != "":
                    municipality = int(data['municipality'])
                else:
                    return Response(response.parsejson("municipality is required.", "", status=403))

                if "district" in data and data['district'] != "":
                    district = int(data['district'])
                else:
                    return Response(response.parsejson("district is required.", "", status=403))

                # if "project" in data and data['project'] != "":
                #     project = int(data['project'])
                # else:
                #     return Response(response.parsejson("project is required.", "", status=403))

                if "property_name" in data and data['property_name'] != "":
                    property_name = data['property_name']
                else:
                    return Response(response.parsejson("property_name is required.", "", status=403))
                
                if "community" in data and data['community'] != "":
                    community = data['community']
                else:
                    return Response(response.parsejson("community is required.", "", status=403))

                if "property_type" in data and data['property_type'] != "":
                    property_type = int(data['property_type'])
                else:
                    return Response(response.parsejson("property_type is required.", "", status=403))    

                if "building" in data and data['building'] != "":
                    building = data['building']
                else:
                    return Response(response.parsejson("building is required.", "", status=403))

                if "square_footage" in data and data["square_footage"] != "":
                    data["square_footage"] = data["square_footage"]
                else:
                    return Response(response.parsejson("square_footage is required.", "", status=403))

                if "beds" in data and data["beds"] != "":
                    data["beds"] = data["beds"]
                else:
                    return Response(response.parsejson("beds is required.", "", status=403))

                if "baths" in data and data["baths"] != "":
                    data["baths"] = data["baths"]
                else:
                    return Response(response.parsejson("baths is required.", "", status=403))

                if "number_of_outdoor_parking_spaces" in data and data["number_of_outdoor_parking_spaces"] != "":
                    data["number_of_outdoor_parking_spaces"] = data["number_of_outdoor_parking_spaces"]
                else:
                    return Response(response.parsejson("number_of_outdoor_parking_spaces is required.", "", status=403))

                if "vacancy" in data and int(data["vacancy"]) in [1, 2]:
                    vacancy = data['vacancy']
                else:
                    return Response(response.parsejson("vacancy is required.", "", status=403))

                if "rental_till" in data and data['rental_till'] != "":
                    rental_till = data['rental_till']
                    if int(vacancy) == 2:
                        data['rental_till'] = None
                elif vacancy == 1:
                    return Response(response.parsejson("rental_till is required.", "", status=403))    

                if "construction_status" in data and data["construction_status"] != "":
                    construction_status = data['construction_status']
                else:
                    return Response(response.parsejson("construction_status is required.", "", status=403))
                
                if "amenities" in data and type(data['amenities']) == list and len(data['amenities']) > 0:
                    amenities = data['amenities']
                else:
                    return Response(response.parsejson("amenities is required.", "", status=403))

                if "tags" in data and type(data['tags']) == list and len(data['tags']) > 0:
                    tags = data['tags']
                else:
                    tags = []    

                if "description" in data and data["description"] != "":
                    description = data['description']
                else:
                    return Response(response.parsejson("description is required.", "", status=403))

                if "description_ar" in data and data["description_ar"] != "":
                    description_ar = data['description_ar']
                else:
                    return Response(response.parsejson("description_ar is required.", "", status=403))    
                 
                if "property_deed" in data and type(data['property_deed']) == list and len(data['property_deed']) > 0:
                    property_deed = data['property_deed']
                else:
                    return Response(response.parsejson("property_deed is required.", "", status=403))

                if "property_floor_plan" in data and type(data['property_floor_plan']) == list and len(data['property_floor_plan']) > 0:
                    property_floor_plan = data['property_floor_plan']
                else:
                    property_floor_plan = []
                    # return Response(response.parsejson("property_floor_plan is required.", "", status=403))

                if "property_cover_image" in data and type(data['property_cover_image']) == list and len(data['property_cover_image']) > 0:
                    property_cover_image = data['property_cover_image']
                else:
                    return Response(response.parsejson("property_cover_image is required.", "", status=403))

                if "property_image" in data and type(data['property_image']) == list and len(data['property_image']) > 0:
                    property_image = data['property_image']
                else:
                    return Response(response.parsejson("property_image is required.", "", status=403))

                property_video = []
                if "property_video" in data and type(data['property_video']) == list and len(data['property_video']) > 0:
                    property_video = data['property_video']
                # else:
                #     return Response(response.parsejson("property_video is required.", "", status=403))                   

                if "property_for" in data and data['property_for'] != "" and data['property_for'] is not None:
                    property_for = data['property_for']
                    c_property_for = True
                else:
                    c_property_for = False
                    data['property_for'] = None
                #     if owner_user_type in [1, 5, 6]:
                #         data['property_for'] = 1
                #     else:    
                #         return Response(response.parsejson("property_for is required.", "", status=403))

                auction_data = {}
                # if property_id is None or int(owner_user_type) == 2 or int(seller_status_id) == 27:
                if True:
                    c_start_price = False
                    if "start_price" in data and data['start_price'] != "" and data['start_price'] is not None:
                        auction_data['start_price'] = data['start_price']
                        c_start_price = True
                    # else:
                    #     return Response(response.parsejson("start_price is required.", "", status=403))

                    c_deposit_amount = False
                    if "deposit_amount" in data and data['deposit_amount'] != "" and data['deposit_amount'] is not None:
                        deposit_amount = data['deposit_amount']
                        c_deposit_amount = True
                    # else:
                    #     return Response(response.parsejson("deposit_amount is required.", "", status=403))

                    c_reserve_amount = False
                    if "reserve_amount" in data and data['reserve_amount'] != "" and data['reserve_amount'] is not None:
                        auction_data['reserve_amount'] = data['reserve_amount']
                        c_reserve_amount = True
                    # else:
                    #     return Response(response.parsejson("reserve_amount is required.", "", status=403)) 

                    c_buyer_preference = False
                    if "buyer_preference" in data and data['buyer_preference'] != "" and data['buyer_preference'] is not None:
                        auction_data['buyer_preference'] = data['buyer_preference']
                        c_buyer_preference = True
                    # else:
                    #     return Response(response.parsejson("buyer_preference is required.", "", status=403)) 

                    if "sell_at_full_amount_status" in data and data['sell_at_full_amount_status'] != "":
                        auction_data['sell_at_full_amount_status'] = data['sell_at_full_amount_status']
                    # else:
                    #     return Response(response.parsejson("sell_at_full_amount_status is required.", "", status=403))

                    if "full_amount" in data and data['full_amount'] != "":
                        auction_data['full_amount'] = data['full_amount']
                    # else:
                    #     return Response(response.parsejson("full_amount is required.", "", status=403))

                    if "bid_increment_status" in data and data['bid_increment_status'] != "":
                        auction_data['bid_increment_status'] = data['bid_increment_status']
                    # else:
                    #     return Response(response.parsejson("bid_increment_status is required.", "", status=403))

                    c_bid_increments = False
                    if "bid_increments" in data and data['bid_increments'] != "" and data['bid_increments'] is not None:
                        auction_data['bid_increments'] = data['bid_increments']
                        c_bid_increments = True
                    # else:
                    #     return Response(response.parsejson("bid_increments is required.", "", status=403)) 
                    
                    c_start_date = False
                    if "start_date" in data and data['start_date'] != "" and data['start_date'] is not None:
                        auction_data['start_date'] = data['start_date']
                        c_start_date = True
                    # else:
                    #     return Response(response.parsejson("start_date is required.", "", status=403)) 

                    c_end_date = False
                    if "end_date" in data and data['end_date'] != "" and data['end_date'] is not None:
                        auction_data['end_date'] = data['end_date']
                        c_end_date = True
                    # else:
                    #     return Response(response.parsejson("end_date is required.", "", status=403))

                    if "is_featured" in data and data['is_featured'] != "":
                        is_featured = data['is_featured']
                    else:
                        data['is_featured'] = 0    

                    c_signature = False
                    if "signature" in data and data['signature'] != "" and data['signature'] is not None:
                        signature = data['signature']
                        c_signature = True
                    else:
                        return Response(response.parsejson("signature is required.", "", status=403))

                    c_term_agreement = False
                    if "term_agreement" in data and data['term_agreement'] != "" and data['term_agreement'] is not None:
                        term_agreement = data['term_agreement']
                        if not term_agreement:
                            return Response(response.parsejson("Need to accept term agreement.", "", status=403)) 
                        c_term_agreement = True 
                    else:
                        return Response(response.parsejson("term_agreement is required.", "", status=403)) 
                else:
                    signature = None
                    term_agreement = None

                # if "relist" in data and data['relist'] != "" and int(data['relist']) == 1:
                #     relist = int(data['relist'])

                data['create_step'] = 4
                # data['property_for'] = 2

                if c_start_price and c_deposit_amount and c_reserve_amount and c_buyer_preference and c_bid_increments and c_start_date and c_end_date and c_signature and c_term_agreement and c_property_for:
                    data['seller_status'] = 27
                elif property_id is None:
                    data['seller_status'] = 24

                with transaction.atomic():
                    try:
                        serializer = AddPropertySerializer(property_id, data=data, partial=True)
                        if serializer.is_valid():
                            property_id = serializer.save()
                            property_id = property_id.id
                        else:
                            transaction.set_rollback(True)  # -----Rollback Transaction----
                            copy_errors = serializer.errors.copy()
                            return Response(response.parsejson(copy_errors, "", status=403))

                        # if relist is not None:
                        #     prop_data = PropertyListing.objects.filter(id=property_id).last()
                        #     prop_data.status_id = 1
                        #     prop_data.date_sold = None
                        #     prop_data.sold_price = 0.00
                        #     prop_data.winner_id = None
                        #     prop_data.save()  
 
                        # ----------------------Owners---------------------
                        if "owners" in data and type(data["owners"]) == list:
                            owners = data["owners"]
                            PropertyOwners.objects.filter(property=property_id).delete()
                            for owner in owners:
                                property_owners = PropertyOwners()
                                property_owners.property_id = property_id
                                property_owners.domain_id = site_id
                                
                                property_owners.name = owner["owner_name"]
                                # if data["account_verification_type"] != 2: 
                                #     property_owners.eid = owner["owner_eid"]
                                # else:
                                #     property_owners.passport = owner["owner_passport"]

                                if owner["owner_identity_type"] == 1: 
                                    property_owners.eid = owner["owner_eid"]
                                    property_owners.useEID = 'true'
                                else:
                                    property_owners.passport = owner["owner_passport"]
                                    property_owners.useEID = 'false'

                                property_owners.share_percentage = owner["owner_percentage"]
                                # property_owners.nationality = owner["owner_nationality"]
                                property_owners.owner_nationality_id = owner["owner_nationality"]
                                property_owners.dob = owner["owner_dob"]
                                property_owners.phone = owner["owner_phone"]
                                property_owners.email = owner["owner_email"]
                                property_owners.save()

                        if amenities is not None and len(amenities) > 0:
                            PropertyAmenity.objects.filter(property=property_id).delete()
                            for amenity in amenities:
                                property_amenities = PropertyAmenity()
                                property_amenities.property_id = property_id
                                property_amenities.amenities_id = amenity
                                property_amenities.save()       

                        if tags is not None and len(tags) > 0:
                            PropertyTags.objects.filter(property=property_id).delete()
                            for tag in tags:
                                property_tags = PropertyTags()
                                property_tags.property_id = property_id
                                property_tags.tags_id = tag
                                property_tags.save()
                        else:
                            PropertyTags.objects.filter(property=property_id).delete()              

                        if property_deed is not None and len(data["property_deed"]) > 0:
                            # PropertyUploads.objects.filter(property=property_id, upload_type=1, upload_identifier=4).delete()
                            PropertyUploads.objects.filter(property=property_id, upload_type__in=[1, 3], upload_identifier=4).delete()
                            for deed in property_deed:
                                ext = deed.split(".")
                                ext = ext[-1]
                                upload_type = 3 if ext in ['pdf', 'docs', 'xls', 'doc'] else 1
                                property_uploads = PropertyUploads()
                                property_uploads.upload_id = deed
                                property_uploads.property_id = property_id
                                # property_uploads.upload_type = 1
                                # property_uploads.upload_type = upload_type
                                property_uploads.upload_type = 3
                                property_uploads.status_id = 1
                                property_uploads.upload_identifier = 4
                                property_uploads.save()

                        if property_floor_plan is not None and len(property_floor_plan) > 0:
                            # PropertyUploads.objects.filter(property=property_id, upload_type=1, upload_identifier=3).delete()
                            PropertyUploads.objects.filter(property=property_id, upload_type__in=[1, 3], upload_identifier=3).delete()
                            for floor_plan in property_floor_plan:
                                ext = floor_plan.split(".")
                                ext = ext[-1]
                                upload_type = 3 if ext in ['pdf', 'docs', 'xls', 'doc'] else 1
                                property_uploads = PropertyUploads()
                                property_uploads.upload_id = floor_plan
                                property_uploads.property_id = property_id
                                # property_uploads.upload_type = 1
                                # property_uploads.upload_type = upload_type
                                property_uploads.upload_type = 3
                                property_uploads.status_id = 1
                                property_uploads.upload_identifier = 3
                                property_uploads.save()

                        if property_cover_image is not None and len(property_cover_image) > 0:
                            PropertyUploads.objects.filter(property=property_id, upload_type=1, upload_identifier=1).delete()
                            for cover_image in property_cover_image:
                                property_uploads = PropertyUploads()
                                property_uploads.upload_id = cover_image
                                property_uploads.property_id = property_id
                                property_uploads.upload_type = 1
                                property_uploads.status_id = 1
                                property_uploads.upload_identifier = 1
                                property_uploads.save()

                        if property_image is not None and len(property_image) > 0:
                            PropertyUploads.objects.filter(property=property_id, upload_type=1, upload_identifier=2).delete()
                            for image in property_image:
                                property_uploads = PropertyUploads()
                                property_uploads.upload_id = image
                                property_uploads.property_id = property_id
                                property_uploads.upload_type = 1
                                property_uploads.status_id = 1
                                property_uploads.upload_identifier = 2
                                property_uploads.save()                        

                        if property_video is not None and len(property_video) > 0:
                            PropertyUploads.objects.filter(property=property_id, upload_type=2).delete()
                            for video in property_video:
                                property_uploads = PropertyUploads()
                                property_uploads.upload_id = video
                                property_uploads.property_id = property_id
                                property_uploads.upload_type = 2
                                property_uploads.upload_identifier = 5
                                property_uploads.status_id = 1
                                property_uploads.save()
      
                        if len(auction_data):
                            property_auction = PropertyAuction.objects.filter(property=property_id).first()
                            if property_auction is None:
                                auction_data['domain'] = site_id
                                auction_data['time_zone'] = 575
                                auction_data['status'] = 1
                                auction_data['auction'] = 1
                                auction_data['property'] = property_id
                                auction_data['auction_unique_id'] = unique_registration_id()

                            serializer = AddPropertyAuctionSerializer(property_auction, data=auction_data, partial=True)
                            if serializer.is_valid():
                                auction_id = serializer.save()
                                auction_id = auction_id.id
                            else:
                                transaction.set_rollback(True)  # -----Rollback Transaction----
                                copy_errors = serializer.errors.copy()
                                return Response(response.parsejson(copy_errors, "", status=403))
                            
                            if signature is not None and term_agreement is not None:
                                reservation_agreement = PropertyReservationAgreement.objects.filter(property=property_id).first()
                                if reservation_agreement is None:
                                    reservation_agreement = PropertyReservationAgreement()
                                reservation_agreement.property_id = property_id
                                reservation_agreement.seller_id = user_id
                                reservation_agreement.signature = signature
                                reservation_agreement.reservation_agreement_accepted = term_agreement
                                reservation_agreement.save()            
                    except Exception as exp:
                        transaction.set_rollback(True)  # -----Rollback Transaction----
                        return Response(response.parsejson(str(exp), exp, status=403))
            
            # --------------Email & Notification-----------  
            try:
                # --------------Email-----------
                if (step in [1, 3] and (data["property_id"] is None or data["property_id"] == "")) or (step in [1, 3] and data["property_id"] is not None and seller_status_id is not None and seller_status_id == 29):
                    property_detail = PropertyListing.objects.filter(id=property_id).first()
                    user_detail = property_detail.agent
                    property_user_name = user_detail.first_name
                    agent_email = user_detail.email
                    agent_phone = user_detail.phone_no if user_detail.phone_no is not None else ""
                    phone_country_code = user_detail.phone_country_code if user_detail.phone_country_code is not None else ""
                    upload = PropertyUploads.objects.filter(property=property_id, upload_type=1).first()
                    web_url = network.domain_url
                    image_url = network.domain_url+'static/images/property-default-img.png'
                    if upload is not None:
                        image = upload.upload.doc_file_name
                        bucket_name = upload.upload.bucket_name
                        image_url = settings.AZURE_BLOB_URL + str(bucket_name)+ '/' +str(image)
                    domain_url = network.domain_url+"admin/listing/"
                    property_state = property_detail.state.state_name
                    property_type = property_detail.property_type.property_type
                    property_name = property_detail.property_name
                    community = property_detail.community
                    # -------------Email send to Agent-----------
                    template_data = {"domain_id": site_id, "slug": "add_listing"}
                    extra_data = {
                        'property_user_name': property_user_name,
                        'web_url': web_url,
                        'property_image': image_url,
                        'property_state': property_state,
                        'property_type': property_type,
                        'property_name': property_name,
                        'community': community,
                        'dashboard_link': domain_url,
                        "domain_id": site_id
                    }
                    compose_email(to_email=[agent_email], template_data=template_data, extra_data=extra_data)
                    # -------------Send email to super admin--------------
                    if step == 1: # --------When user is not super admin-------
                        broker_detail = Users.objects.get(site_id=site_id)
                        broker_name = broker_detail.first_name if broker_detail.first_name is not None else ""
                        broker_email = broker_detail.email if broker_detail.email is not None else ""
                        if broker_email.lower() != agent_email.lower() or True:
                            template_data = {"domain_id": site_id, "slug": "add_listing_broker"}
                            extra_data = {
                                'property_user_name': broker_name,
                                'web_url': web_url,
                                'property_image': image_url,
                                'property_state': property_state,
                                'property_type': property_type,
                                'property_name': property_name,
                                'community': community,
                                'dashboard_link': domain_url,
                                "domain_id": site_id,
                                'agent_name': property_user_name,
                                'agent_email': agent_email,
                                'agent_phone': phone_format_new(agent_phone, phone_country_code)
                            }
                            compose_email(to_email=[broker_email], template_data=template_data, extra_data=extra_data)
                            # --------Approval Pending Email To Super Admin--------
                            template_data = {"domain_id": site_id, "slug": "approval_pending"}
                            compose_email(to_email=[broker_email], template_data=template_data, extra_data=extra_data)
                
                    # ------------------Notifications-------------
                    prop_name = property_detail.property_name
                    prop_name_ar = property_detail.property_name_ar
                    #  -----------Add notification for seller-----------
                    decorator_url = property_detail.property_name.lower() + " " + property_detail.country.country_name.lower()
                    decorator_url = re.sub(r"\s+", '-', decorator_url)
                    redirect_url = network.domain_react_url+"seller/property/detail/"+str(property_id)+"/"+decorator_url
                    notification_extra_data = {'image_name': 'review.svg', 'property_name': prop_name, 'property_name_ar': prop_name_ar, 'redirect_url': redirect_url}
                    notification_extra_data['app_content'] = 'Your property '+prop_name+' is submitted for review'
                    notification_extra_data['app_content_ar'] = 'ممتلكاتك '+prop_name_ar+' تم تقديمه للمراجعة'
                    notification_extra_data['app_screen_type'] = 6
                    notification_extra_data['app_notification_image'] = 'review.png'
                    notification_extra_data['app_notification_button_text'] = 'View'
                    notification_extra_data['app_notification_button_text_ar'] = 'منظر'
                    notification_extra_data['property_id'] = property_id
                    template_slug = "add_listing"
                    # content = '<div class="icon orange-bg"><img src="img/review.svg" alt="Reload Icon"></div><div class="text"><h6>Your property "'+prop_name+'" is submitted for review!</h6><a class="btn btn-sky btn-xs" href="'+redirect_url+'">View</a></div>'
                    add_notification(
                        site_id,
                        user_id=user_id,
                        added_by=user_id,
                        notification_for=1,
                        template_slug=template_slug,
                        extra_data=notification_extra_data
                    ) 
                    # ------------Add notification for superadmin--------
                    if step == 1:
                        redirect_url = network.domain_url+"admin/listing/"
                        notification_extra_data = {'image_name': 'review.svg', 'property_name': prop_name, 'property_name_ar': prop_name_ar, 'redirect_url': redirect_url}
                        notification_extra_data['app_content'] = 'A new property '+prop_name+' is created for review!'
                        notification_extra_data['app_content_ar'] = 'عقار جديد '+prop_name_ar+' تم إنشاؤه للمراجعة!'
                        notification_extra_data['app_screen_type'] = 7
                        notification_extra_data['app_notification_image'] = 'review.png'
                        notification_extra_data['app_notification_button_text'] = 'View'
                        notification_extra_data['app_notification_button_text_ar'] = 'منظر'
                        notification_extra_data['property_id'] = property_id
                        template_slug = "approval_pending"
                        # content ='<div class="icon orange-bg"><img src="img/review.svg" alt="Reload Icon"></div><div class="text"><h6>A new property "'+prop_name+'" is created for review!</h6><a class="btn btn-sky btn-xs" href="'+redirect_url+'">View</a></div>'
                        add_notification(
                            site_id,
                            user_id=broker_detail.id,
                            added_by=broker_detail.id,
                            notification_for=1,
                            template_slug=template_slug,
                            extra_data=notification_extra_data
                        ) 
            except Exception as exp:
                pass
            all_data = {"property_id": property_id, "auction_id": auction_id}
            return Response(response.parsejson("Property saved successfully.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AdminListingDetailApiView(APIView):
    """
    This api is used for getting listing details
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                return Response(response.parsejson("site_id is required", "", status=403))
            is_super_user = False
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5, 6], status=1).first()
                if users is None:
                    return Response(response.parsejson("You are not authorised user.", "", status=403))
                elif users is not None and users.site_id is not None and users.site_id > 0:
                    is_super_user = True
            else:
                return Response(response.parsejson("user_id is required.", "", status=403))

            # --- Verify that user_id matches the token user ---
            auth_user = request.user  # user from Bearer token
            if int(user_id) != auth_user.id:
                return Response(response.parsejson("Permission denied.", "", status=403))       

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required", "", status=403))

            if "step_id" in data and data['step_id'] != "":
                step_id = int(data['step_id'])
            else:
                return Response(response.parsejson("step_id is required", "", status=403))
            
            property_listing = PropertyListing.objects.filter(id=property_id, domain=site_id)
            if users.user_type_id in [5, 6]:
                property_listing = property_listing.filter(Q(agent=user_id) | Q(developer=user_id))

            if step_id == 1:
                serializer = ListingDetailStepOneSerializer(property_listing.first())
            elif step_id == 2:
                property_listing = property_listing.exclude(seller_status__in=[24, 29])
                serializer = ListingDetailStepTwoSerializer(property_listing.first())
            elif step_id == 3:
                serializer = ListingDetailStepThreeSerializer(property_listing.first())   
            return Response(response.parsejson("Fetch Data.", serializer.data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class AddDariPropertyApiView(APIView):
    """
    Dari system Add/Update Property
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data

            required_fields = [
                "property_id", "property_number", "country", "city",
                "municipality_ar", "municipality_en", "district_ar", "district_en",
                "property_name_ar", "property_name_en", "property_type",  "community_name_ar",
                "community_name_en", "building", "area_size", "bedrooms", "construction_status", "owners"
            ]

            errors = {}

            # Check required fields
            for field in required_fields:
                if field not in data or str(data[field]).strip() == "":
                    errors[field] = f"{field} is required."

            # Validate `area_size`, `bedrooms`
            numeric_fields = ["area_size", "bedrooms"]
            for field in numeric_fields:
                if field in data:
                    try:
                        data[field] = float(data[field]) if field == "area_size" else int(data[field])
                    except ValueError:
                        errors[field] = f"{field} must be a number."

            # Validate `owners` field (list of objects)
            if "owners" in data:
                if not isinstance(data["owners"], list) or not data["owners"]:
                    errors["owners"] = "owners must be a non-empty list."
                else:
                    for index, owner in enumerate(data["owners"]):
                        owner_errors = {}

                        if "full_name" not in owner or not owner["full_name"].strip():
                            owner_errors["full_name"] = "Owner's full name is required."
                        if "eid_passport" not in owner or not owner["eid_passport"].strip():
                            owner_errors["eid_passport"] = "EID/Passport is required."
                        if "ownership_type" not in owner or not owner["ownership_type"].strip():
                            owner_errors["ownership_type"] = "Ownership type is required."

                        # Validate share percentage
                        if "share_percentage" in owner:
                            try:
                                share_percentage = float(owner["share_percentage"])
                                if share_percentage < 0 or share_percentage > 100:
                                    owner_errors["share_percentage"] = "Share percentage must be between 0 and 100."
                            except ValueError:
                                owner_errors["share_percentage"] = "Share percentage must be a number."
                        else:
                            owner_errors["share_percentage"] = "Share percentage is required."

                        if owner_errors:
                            errors[f"owners[{index}]"] = owner_errors

            if errors:
                return Response(response.parsejson(errors, "", status=403))

            # if "site_id" in data and data['site_id'] != "":
            #     site_id = int(data['site_id'])
            #     network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
            #     if network is None:
            #         return Response(response.parsejson("Site not exist.", "", status=403))
            #     data['domain'] = site_id
            # else:
            #     return Response(response.parsejson("site_id is required", "", status=403))
            # 
            # property_id = None
            # check_update = None
            # if "property_id" in data and data['property_id'] != "" and data["property_id"] is not None:
            #     property_id = int(data['property_id'])
            #     check_update = True
            #     property_id = PropertyListing.objects.filter(id=property_id, domain=site_id).first()
            #     if property_id is None:
            #         return Response(response.parsejson("Property not exist.", "", status=403))
            # if "step" in data and data['step'] != "":
            #     step = int(data['step'])
            # else:
            #     return Response(response.parsejson("step is required.", "", status=403))
            # user_domain = None
            # creater_user_type = None
            # if "user_id" in data and data['user_id'] != "":
            #     user_id = int(data['user_id'])
            #     users = Users.objects.filter(id=user_id, status=1).first()
            #     if users is None:
            #         return Response(response.parsejson("User not exist.", "", status=403))
            # 
            #     network_user = NetworkUser.objects.filter(user=user_id, status=1, user__status=1).first()
            #     if network_user is None:
            #         data["developer"] = user_id
            #     else:
            #         data["developer"] = network_user.developer_id if network_user.developer_id is not None else user_id
            # 
            #     if property_id is not None:
            #         user_id = property_id.agent_id
            #         data["developer"] = property_id.developer_id
            # 
            #     data["agent"] = user_id
            #     user_domain = users.site_id
            #     creater_user_type = users.user_type_id
            # else:
            #     return Response(response.parsejson("user_id is required.", "", status=403))
            # 
            # if step == 1:
            #     if "country" in data and data['country'] != "":
            #         data['country'] = data['country']
            #     else:
            #         return Response(response.parsejson("country is required.", "", status=403))
            # 
            #     if "city" in data and data['city'] != "":
            #         data['state'] = int(data['city'])
            #     else:
            #         return Response(response.parsejson("city is required.", "", status=403))
            # 
            #     if "municipality" in data and data['municipality'] != "":
            #         data['municipality'] = int(data['municipality'])
            #     else:
            #         return Response(response.parsejson("municipality is required.", "", status=403))
            # 
            #     if "district" in data and data['district'] != "":
            #         data['district'] = int(data['district'])
            #     else:
            #         return Response(response.parsejson("district is required.", "", status=403))
            # 
            #     if "project" in data and data['project'] is not None:
            #         data['project'] = int(data['project'])
            # 
            #     if "community" in data and data['community'] != "":
            #         data['community'] = data['community']
            #     else:
            #         return Response(response.parsejson("community is required.", "", status=403))
            # 
            #     if "building" in data and data['building'] != "":
            #         data['building'] = data['building']
            #     else:
            #         return Response(response.parsejson("building is required.", "", status=403))
            # 
            #     if "propertyType" in data and data['propertyType'] != "":
            #         data['property_type'] = int(data['propertyType'])
            #     else:
            #         return Response(response.parsejson("property_type is required.", "", status=403))
            # 
            #     if "owners" in data and type(data['owners']) == list and len(data['owners']) > 0:
            #         owners = data['owners']
            #     else:
            #         return Response(response.parsejson("owners is required.", "", status=403))
            # 
            #     if "areaSize" in data and data["areaSize"] != "":
            #         data["square_footage"] = data["areaSize"]
            #     else:
            #         return Response(response.parsejson("areaSize is required.", "", status=403))
            # 
            #     if "numOfBedrooms" in data and data["numOfBedrooms"] != "":
            #         data["beds"] = data["numOfBedrooms"]
            #     else:
            #         return Response(response.parsejson("numOfBedrooms is required.", "", status=403))
            # 
            #     if "numOfBedrooms" in data and data["numOfBedrooms"] != "":
            #         data["baths"] = data["numOfBedrooms"]
            #     else:
            #         return Response(response.parsejson("numOfBedrooms is required.", "", status=403))
            # 
            #     if "numOfParkings" in data and data["numOfParkings"] != "":
            #         data["number_of_outdoor_parking_spaces"] = data["numOfParkings"]
            #     else:
            #         return Response(response.parsejson("numOfBedrooms is required.", "", status=403))
            # 
            #     data["rental_till"] = None
            #     if "vacancy" in data and int(data["vacancy"]) in [1, 2]:
            #         vacancy = int(data['vacancy'])
            #         if vacancy == 1:
            #             if "rentalTill" in data and data['rentalTill'] != "":
            #                 data["rental_till"] = data['rentalTill']
            #             else:
            #                 return Response(response.parsejson("rentalTill is required.", "", status=403))
            #     else:
            #         return Response(response.parsejson("vacancy is required.", "", status=403))
            # 
            #     if "constructionStatus" in data and data["constructionStatus"] != "":
            #         data["construction_status"] = data['constructionStatus']
            #     else:
            #         return Response(response.parsejson("constructionStatus is required.", "", status=403))
            # 
            #     if "description" in data and data["description"] != "":
            #         description = data['description']
            #     else:
            #         return Response(response.parsejson("description is required.", "", status=403))
            # 
            #     if "status" in data and data['status'] != "":
            #         data['status'] = int(data['status'])
            #     else:
            #         data['status'] = 1
            # 
            #     if "seller_status" in data and data['seller_status'] != "":
            #         data['seller_status'] = int(data['seller_status'])
            #     else:
            #         data['seller_status'] = 24
            # 
            #     data["create_step"] = 1
            #     data["title"] = "testing"
            #     if user_domain == site_id or int(creater_user_type) == 2:
            #         data['is_approved'] = 1
            #     serializer = AddPropertySerializer(property_id, data=data)
            #     if serializer.is_valid():
            #         property_id = serializer.save()
            #         property_id = property_id.id
            #     else:
            #         copy_errors = serializer.errors.copy()
            #         return Response(response.parsejson(copy_errors, "", status=403))
            #     # ----------------------Owners---------------------
            #     if "owners" in data and type(data["owners"]) == list:
            #         owners = data["owners"]
            #         PropertyOwners.objects.filter(property=property_id).delete()
            #         for owner in owners:
            #             property_owners = PropertyOwners()
            #             property_owners.property_id = property_id
            #             property_owners.name = owner["ownerName"]
            #             property_owners.eid = owner["eid"]
            #             property_owners.share_percentage = owner["sharePercentage"]
            #             property_owners.nationality = owner["nationality"]
            #             property_owners.dob = owner["dob"]
            #             property_owners.save()
            # 
            #     if "amenities" in data and type(data["amenities"]) == list:
            #         amenities = data["amenities"]
            #         PropertyAmenity.objects.filter(property=property_id).delete()
            #         for amenity in amenities:
            #             property_amenities = PropertyAmenity()
            #             property_amenities.property_id = property_id
            #             property_amenities.amenities_id = amenity
            #             property_amenities.save()
            # 
            #     if "property_pic" in data and type(data["property_pic"]) == list:
            #         property_pic = data["property_pic"]
            #         PropertyUploads.objects.filter(property=property_id, upload_type=1).delete()
            #         cnt = 0
            #         for pic in property_pic:
            #             property_uploads = PropertyUploads()
            #             property_uploads.upload_id = pic["upload_id"]
            #             property_uploads.property_id = property_id
            #             property_uploads.upload_type = 1
            #             property_uploads.status_id = 1
            #             property_uploads.upload_identifier = pic["upload_identifier"]
            #             property_uploads.save()
            #             cnt +=1
            # 
            #     if "property_video" in data and type(data["property_video"]) == list:
            #         property_video = data["property_video"]
            #         PropertyUploads.objects.filter(property=property_id, upload_type=2).delete()
            #         for video in property_video:
            #             property_uploads = PropertyUploads()
            #             property_uploads.upload_id = video["upload_id"]
            #             property_uploads.property_id = property_id
            #             property_uploads.upload_type = 2
            #             property_uploads.upload_identifier = video["upload_identifier"]
            #             property_uploads.status_id = 1
            #             property_uploads.save()
            # 
            #     if "property_documents" in data and type(data["property_documents"]) == list and len(data["property_documents"]) > 0:
            #         property_documents = data["property_documents"]
            #         PropertyUploads.objects.filter(property=property_id, upload_type=3).delete()
            #         for documents in property_documents:
            #             property_uploads = PropertyUploads()
            #             property_uploads.upload_id = documents["upload_id"]
            #             property_uploads.property_id = property_id
            #             property_uploads.upload_type = 3
            #             property_uploads.upload_identifier = documents["upload_identifier"]
            #             property_uploads.status_id = 1
            #             property_uploads.save()
            # elif step == 2:
            #     if property_id is None:
            #         return Response(response.parsejson("property_id is required.", "", status=403))
            #     property_id = property_id.id
            # 
            #     if "reservation_agreement_accepted" in data and data['reservation_agreement_accepted'] == 1:
            #         reservation_agreement_accepted = data['reservation_agreement_accepted']
            #     else:
            #         return Response(response.parsejson("reservation_agreement_accepted is required.", "", status=403))
            # 
            #     if "reservation_agreement_sign" in data and data['reservation_agreement_sign'] != "":
            #         reservation_agreement_sign = data['reservation_agreement_sign']
            #     else:
            #         return Response(response.parsejson("reservation_agreement_sign is required.", "", status=403))
            # 
            #     # if "sale_by_type" in data and data['sale_by_type'] != "":
            #     #     sale_by_type = data['sale_by_type']
            #     # else:
            #     #     return Response(response.parsejson("sale_by_type is required.", "", status=403))
            # 
            #     if "start_time" in data and data['start_time'] != "":
            #         start_time = data['start_time']
            #     else:
            #         return Response(response.parsejson("start_time is required.", "", status=403))
            # 
            #     if "end_time" in data and data['end_time'] != "":
            #         end_time = data['end_time']
            #     else:
            #         return Response(response.parsejson("end_time is required.", "", status=403))
            # 
            #     if "start_date" in data and data["start_date"] != "":
            #         data["start_date"] = f'{data["start_date"]} {data["start_time"]}'
            #     else:
            #         return Response(response.parsejson("start_date is required.", "", status=403))
            # 
            #     if "end_date" in data and data["end_date"] != "":
            #         data["end_date"] = f'{data["end_date"]} {data["end_time"]}'
            #     else:
            #         return Response(response.parsejson("end_date is required.", "", status=403))
            # 
            #     bid_increments = None
            #     if "bid_increment_status" in data and data["bid_increment_status"] in [0, 1]:
            #         bid_increment_status = data['bid_increment_status']
            #         if bid_increment_status == 1 :
            #             if "bid_increments" in data and data['bid_increments'] != "":
            #                 bid_increments = data['bid_increments']
            #             else:
            #                 return Response(response.parsejson("bid_increments is required.", "", status=403))
            #     else:
            #         return Response(response.parsejson("bid_increment_status is not valid.", "", status=403))
            # 
            #     full_amount = None
            #     if "sell_at_full_amount_status" in data and data["sell_at_full_amount_status"] in [0, 1]:
            #         sell_at_full_amount_status = data['sell_at_full_amount_status']
            #         if sell_at_full_amount_status == 1:
            #             if "full_amount" in data and data['full_amount'] != "":
            #                 full_amount = data['full_amount']
            #             else:
            #                 return Response(response.parsejson("full_amount is required.", "", status=403))
            #     else:
            #         return Response(response.parsejson("bid_increment_status is required.", "", status=403))
            # 
            #     if "start_price" in data and data['start_price'] != "":
            #         start_price = data['start_price']
            #     else:
            #         return Response(response.parsejson("start_price is required.", "", status=403))
            # 
            #     if "deposit_amount" in data and data['deposit_amount'] != "":
            #         deposit_amount = data['deposit_amount']
            #     else:
            #         return Response(response.parsejson("deposit_amount is required.", "", status=403))
            # 
            #     if "is_featured" in data and data['is_featured'] != "" and data["is_featured"] in [0, 1]:
            #         is_featured = data['is_featured']
            #     else:
            #         return Response(response.parsejson("is_featured is required.", "", status=403))
            # 
            #     if "buyer_preference" in data and data['buyer_preference'] != "" and data["buyer_preference"] in [1, 2, 3]:
            #         buyer_preference = data['buyer_preference']
            #     else:
            #         return Response(response.parsejson("buyer_preference is required.", "", status=403))
            # 
            #     if "reserve_amount" in data and data['reserve_amount'] != "":
            #         reserve_amount = data['reserve_amount']
            #         if float(start_price) > float(reserve_amount):
            #             return Response(response.parsejson("reserve_amount should be greater than start_price.", "", status=403))
            #     else:
            #         return Response(response.parsejson("reserve_amount is required.", "", status=403))
            # 
            #     property_auction = PropertyAuction.objects.filter(property=property_id).first()
            #     if property_auction is None:
            #         property_auction = PropertyAuction()
            #         property_auction.property_id = property_id
            #     property_auction.start_date = data["start_date"]
            #     property_auction.end_date = data["end_date"]
            #     property_auction.bid_increment_status = bid_increment_status
            #     property_auction.bid_increments = bid_increments
            #     property_auction.reserve_amount = reserve_amount
            #     property_auction.time_zone_id = 575
            #     property_auction.start_price = start_price
            #     property_auction.status_id = 2 #data['auction_status'] if data['auction_status'] is not None else 1
            #     property_auction.auction_id = 1 #sale_by_type
            #     property_auction.domain_id = site_id
            #     property_auction.buyer_preference = buyer_preference
            #     property_auction.sell_at_full_amount_status = sell_at_full_amount_status
            #     property_auction.full_amount = full_amount
            #     property_auction.save()
            # 
            #     property_listing = PropertyListing.objects.get(id=property_id)
            #     property_listing.deposit_amount = deposit_amount
            #     property_listing.is_featured = is_featured
            #     property_listing.seller_status_id = 27
            #     property_listing.create_step = 4
            #     property_listing.save()
            # 
            # 
            #     reservation_agreement = PropertyReservationAgreement.objects.filter(property=property_id).first()
            #     if reservation_agreement is None:
            #         reservation_agreement = PropertyReservationAgreement()
            #     reservation_agreement.property_id = property_id
            #     reservation_agreement.seller_id = user_id
            #     reservation_agreement.signature = reservation_agreement_sign
            #     reservation_agreement.reservation_agreement_accepted = reservation_agreement_accepted
            #     reservation_agreement.save()
            # 
            all_data = {"property_id": data['property_id'], "property_url": f"{settings.REACT_FRONT_URL}/seller/property/{data['property_id']}"}
            return Response(response.parsejson("Property added/updated successfully.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))


class PropertyEventApiView(APIView):
    """
    Property Event
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            type = 1
            if "type" in data and data['type'] != "":
                type = int(data['type'])   

            if "start_date" in data and data['start_date'] != "":
                start_date = data['start_date']
            else:
                return Response(response.parsejson("start_date is required", "", status=403))

            if "end_date" in data and data['end_date'] != "":
                end_date = data['end_date']
            else:
                return Response(response.parsejson("end_date is required", "", status=403))        
            
            user_id = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])

            if type == 1: 
                property_listing = PropertyListing.objects.annotate(tcount=Count("id"), auction_start_date=TruncDate("property_auction__start_date"), auction_end_date=TruncDate("property_auction__end_date")).filter(domain=site_id, status__in=[1, 9, 8])
                if "is_admin" in data and data['is_admin'] != "" and data['is_admin'] == 1:
                    property_listing = property_listing.filter(property_for=2)
                property_listing = property_listing.filter(Q(auction_start_date__range=(start_date, end_date)) | Q(auction_end_date__range=(start_date, end_date)) | (Q(auction_end_date__gte=(end_date)) & Q(auction_start_date__lte=(end_date))))
                total = property_listing.count()
                property_listing = property_listing.only("id")[offset:limit]
                serializer = PropertyEventSerializer(property_listing, many=True, context={"user_id": user_id})
                all_data = {"data": serializer.data, "total": total}
            else:
                # current_date = start_date
                # while current_date <= end_date:
                #     current_date += timedelta(days=1)
                pass
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403)) 


class PropertyTotalFavouriteApiView(APIView):
    """
    Property total favourite
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                # Translators: This message appears when site_id is empty
                return Response(response.parsejson("site_id is required.", "", status=403))
            is_super = False
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
                if users.site_id:
                    is_super = True 
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
                if not is_super:
                    property = PropertyListing.objects.filter(Q(id=property_id) & Q(domain=site_id) & (Q(agent=user_id) | Q(developer=user_id))).last()
                    if property is None:
                        return Response(response.parsejson("You are not authorised to access.", "", status=403))
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required", "", status=403))

            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            property_detail = PropertyListing.objects.get(Q(id=property_id) & Q(domain=site_id))
            property_detail = ViewCountPropertyDetailSerializer(property_detail)

            favourite_property = FavouriteProperty.objects.filter(domain=site_id, property=property_id)
            if "search" in data and data['search'] != "":
                favourite_property = favourite_property.annotate(full_name=Concat('user__first_name', V(' '),'user__last_name')).filter(Q(full_name__icontains=data['search']) | Q(user__email__icontains=data['search']) | Q(user__phone_no__icontains=data['search']))
            total = favourite_property.count()
            favourite_property = favourite_property.order_by("-id").only("id")[offset:limit]
            serializer = PropertyFavouriteSerializer(favourite_property, many=True)
            all_data = {"property_detail": property_detail.data, "data": serializer.data, "total": total}
            return Response(response.parsejson("Fetch data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403)) 


class UserPropertyViewApiView(APIView):
    """
    User property view
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                # Translators: This message appears when site_id is empty
                return Response(response.parsejson("site_id is required.", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            property_listing = PropertyView.objects.filter(domain=site_id, user=user_id).exclude(property__status=5)
            if "filter" in data and data["filter"] == "under_review":
                property_listing = property_listing.filter(Q(property__seller_status=24) & Q(property__status=1))
            elif "filter" in data and data["filter"] == "ready_for_publish":
                property_listing = property_listing.filter(Q(property__seller_status=28) & Q(property__status=1))
            elif "filter" in data and data["filter"] == "on_auction":
                property_listing = property_listing.filter(Q(property__seller_status=27) & Q(property__status=1))
            elif "filter" in data and data["filter"] == "active":
                property_listing = property_listing.filter(Q(property__status=1))
            elif "filter" in data and data["filter"] == "upcoming_listing":
                max_dt = timezone.now()
                property_listing = property_listing.filter(Q(property__property_auction__start_date__gt=max_dt) & Q(property__status=1))
            elif "filter" in data and data["filter"] == "closing_soon_listing":
                min_dt = timezone.now()
                max_dt = timezone.now() + timedelta(hours=48)
                property_listing = property_listing.filter(Q(property__property_auction__end_date__range=(min_dt, max_dt)) & Q(property__property_auction__start_date__lt=min_dt) & Q(property__status=1))
            elif "filter" in data and data["filter"] == "recently_closed_listing":
                min_dt = timezone.now() - timedelta(hours=720)
                # max_dt = timezone.now()
                # property_listing = property_listing.filter(Q(property__date_sold__gte=min_dt) & Q(property__status=9))                
                property_listing = property_listing.filter(property_auction__end_date__gte=min_dt)              


            total = property_listing.count()
            property_listing = property_listing.only("id", "property")[offset:limit]
            serializer = UserPropertyViewSerializer(property_listing, many=True, context={"user_id": user_id})
            all_data = {"data": serializer.data, "total": total}
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))                                  

class BuyNowPropertyApiView(APIView):
    """
    Buy Now Property
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                # Translators: This message appears when site_id is empty
                return Response(response.parsejson("site_id is required.", "", status=403))
            
            user_detail = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                user_detail = Users.objects.filter(id=user_id, status=1).first()
                if user_detail is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required.", "", status=403))

            property_detail = PropertyListing.objects.filter(id=property_id, status_id = 1).first()
            if property_detail is None:
                return Response(response.parsejson("Property deatils not exist.", "", status=403))

            property_auction = PropertyAuction.objects.filter(property_id=property_id, status_id = 1, sell_at_full_amount_status =1).first()
            if property_auction is None:
                return Response(response.parsejson("Property auction not exist.", "", status=403))
            
            buy_now_auction = PropertyBuyNow.objects.filter(property_id=property_id, user_id = user_id).first()
            if buy_now_auction is not None:
                return Response(response.parsejson("Your request is currently under review.", "", status=403))
            
            buy_now_auction = PropertyBuyNow()
            buy_now_auction.user_id = user_id
            buy_now_auction.property_id = property_auction.property_id
            buy_now_auction.buy_now_amount = property_auction.full_amount
            buy_now_auction.save()

            # property_auction.start_date = timezone.now()
            # property_auction.end_date = timezone.now()
            # property_auction.status_id = 9
            # property_auction.save()
            
            try:
                agent_detail = property_detail.agent
                property_agent_user_id = agent_detail.id
                property_agent_name = agent_detail.first_name
                property_agent_email = agent_detail.email
                property_name = property_detail.property_name
                property_name_ar = property_detail.property_name_ar
                buyer_user_name = user_detail.first_name
                property_community = property_detail.community
                property_state = property_detail.state.state_name
                property_type = property_detail.property_type.property_type
                decorator_url = property_detail.property_name.lower() + " " + property_detail.country.country_name.lower()
                decorator_url = re.sub(r"\s+", '-', decorator_url)
                redirect_url = network.domain_react_url+"property/detail/"+str(property_id)+"/"+decorator_url
                web_url = settings.FRONT_BASE_URL
                image_url = web_url+'/static/admin/images/property-default-img.png'
                upload = PropertyUploads.objects.filter(property=property_id, upload_type=1).first()
                if upload is not None:
                    image = upload.upload.doc_file_name
                    bucket_name = upload.upload.bucket_name
                    image_url = settings.AZURE_BLOB_URL + str(bucket_name)+ '/' +str(image)
                    
                template_data = {"domain_id": site_id, "slug": "buy_now_property"}
                extra_data = {
                    'property_user_name': buyer_user_name,
                    'buy_now_price': "AED " + str(number_format(property_auction.full_amount)) if property_auction.full_amount else 'AED 0',
                    'property_name': property_name,
                    'property_image': image_url,
                    'community': property_community,
                    'property_state': property_state,
                    'property_type' : property_type,
                    'dashboard_link': redirect_url,
                    "domain_id": site_id,
                    "redirect_url": redirect_url,
                    'message_1': "Your buy now",
                    'message_2': " is under review"
                }
                compose_email(to_email=[user_detail.email], template_data=template_data, extra_data=extra_data)
                extra_data['property_user_name'] = property_agent_name
                extra_data['message_1'] = "You received a buy now"
                extra_data['message_2'] = ""
                compose_email(to_email=[property_agent_email], template_data=template_data, extra_data=extra_data)


                notification_extra_data = {
                    'image_name': 'success.svg',
                    'property_name': property_name,
                    'property_name_ar': property_name_ar,
                    'redirect_url': redirect_url,
                    'buy_now_price': "AED " + str(number_format(property_auction.full_amount)) if property_auction.full_amount else 'AED 0',
                    'message_1': "Buy now offer",
                    'message_2': " is under review"
                    }
                notification_extra_data['app_content'] = notification_extra_data['message_1']+' '+ notification_extra_data['buy_now_price']+' for '+property_name+''+ notification_extra_data['message_2']+'!'
                notification_extra_data['app_content_ar'] = notification_extra_data['message_1']+' '+ notification_extra_data['buy_now_price']+' ل '+property_name_ar+''+ notification_extra_data['message_2']+'!'
                notification_extra_data['app_screen_type'] = 1
                notification_extra_data['app_notification_image'] = 'success.png'
                notification_extra_data['app_notification_button_text'] = 'View' 
                notification_extra_data['app_notification_button_text_ar'] = 'منظر' 
                notification_extra_data['property_id'] = property_id
                template_slug = "buy_now_property"
                
                add_notification(
                    site_id,
                    user_id=user_id,
                    added_by=user_id,
                    notification_for=1,
                    template_slug=template_slug,
                    extra_data=notification_extra_data
                ) 
                notification_extra_data['message_1'] = "You received a buy now"
                notification_extra_data['message_2'] = ""
                notification_extra_data['app_content'] = notification_extra_data['message_1']+' '+ notification_extra_data['buy_now_price']+' for '+property_name+''+ notification_extra_data['message_2']+'!'
                notification_extra_data['app_content_ar'] = notification_extra_data['message_1']+' '+ notification_extra_data['buy_now_price']+' ل '+property_name_ar+''+ notification_extra_data['message_2']+'!'
                notification_extra_data['app_screen_type'] = 1
                notification_extra_data['app_notification_image'] = 'success.png'
                notification_extra_data['app_notification_button_text'] = 'View'
                notification_extra_data['app_notification_button_text_ar'] = 'منظر'
                
                add_notification(
                    site_id,
                    user_id=property_agent_user_id,
                    added_by=property_agent_user_id,
                    notification_for=1,
                    template_slug=template_slug,
                    extra_data=notification_extra_data
                ) 
                # -------Push Notifications-----
                data = {
                    "title": "Buy Now Offer Received", 
                    "message": 'New offer received on your property! '+ property_name, 
                    "description": 'New offer received on your property! '+ property_name,
                    "notification_to": property_detail.agent_id,
                    "property_id": property_id,
                    "redirect_to": 2
                }
                save_push_notifications(data)

            except Exception as exp:
                pass    
            
            return Response(response.parsejson("Your request has been successfully processed. A representative will contact you shortly for further assistance.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403)) 


class BuyerWonListingApiView(APIView):
    """
    Buyer Won Listings
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
            else:
                return Response(response.parsejson("site_id is required", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
            else:
                return Response(response.parsejson("user_id is required", "", status=403))

            # property_listing = PropertyListing.objects.annotate(cnt=Count('id')).filter(domain=site_id, winner=user_id, sold_price__gt=F('property_auction__reserve_amount')).exclude(status=5)
            property_listing = PropertyListing.objects.annotate(cnt=Count('id')).filter(Q(domain=site_id) & (Q(winner=user_id) | (Q(bid_registration_property__purchase_forefit_status=2) & Q(bid_registration_property__user_id=user_id)))).exclude(status=5)
            # property_listing = PropertyListing.objects.annotate(cnt=Count('id'), purchase_forefit_status=Case(When (bid_registration_property__user_id=user_id, then=F("bid_registration_property__purchase_forefit_status")), default=Value(None), output_field=IntegerField())).filter(Q(domain=site_id) & (Q(winner=user_id) | Q(purchase_forefit_status=2)) & Q(sold_price__gt=F('property_auction__reserve_amount'))).exclude(status=5)
            
            total = property_listing.count()
            property_listing = property_listing.order_by("-date_sold").only("id")[offset:limit]
            serializer = BuyerWonListingSerializer(property_listing, many=True, context={"user_id": user_id})
            all_data = {"data": serializer.data, "total": total}
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))                  


class SendAuctionStartEmailView(APIView):
    """
    Send auction start email
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
                network_domain = NetworkDomain.objects.filter(id=domain_id, is_active=1).last()
                if network_domain is None:
                    return Response(response.parsejson("Domain not exist", "", status=403))
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required", "", status=403))
            auction_data = PropertyAuction.objects.get(property=property_id)
            upload = PropertyUploads.objects.filter(property=property_id, upload_type=1).first()
            if upload is not None:
                image_url = settings.AZURE_BLOB_URL + upload.upload.bucket_name + '/' + upload.upload.doc_file_name
            else:
                image_url = settings.FRONT_BASE_URL+'/static/admin/images/property-default-img.png'
            decorator_url = auction_data.property.property_name.lower() + " " + auction_data.property.country.country_name.lower()
            decorator_url = re.sub(r"\s+", '-', decorator_url)
            # domain_url = settings.REACT_FRONT_URL.replace("###", auction_data.domain.domain_name)+"/property/detail/"+str(property_id)+"/"+decorator_url
            domain_url = network_domain.domain_react_url + "property/detail/" + str(property_id) + "/" + decorator_url

            register_interest_property = PropertyRegisterInterest.objects.filter(property=property_id)
            for interest in register_interest_property:
                # send email to buyer
                extra_data = {
                    "property_user_name": f"{interest.user.first_name} {interest.user.last_name}" if interest.user.last_name else interest.user.first_name,
                    'property_name': auction_data.property.property_name,
                    'property_state': auction_data.property.state.state_name,
                    'property_state': auction_data.property.community,
                    'community': auction_data.property.property_name,
                    'property_type': auction_data.property.property_type.property_type,
                    'property_image': image_url,
                    'dashboard_link': domain_url,
                    "domain_id": domain_id,
                    'redirect_url': domain_url,
                    'image_name': 'check-icon.svg'
                }
                template_data = {"domain_id": domain_id, "slug": "auction_started"}
                compose_email(to_email=[interest.user.email], template_data=template_data, extra_data=extra_data) 

                notification_extra_data = {'image_name': 'review.svg', 'property_name': auction_data.property.property_name, 'property_name_ar': auction_data.property.property_name_ar, 'redirect_url': domain_url}
                notification_extra_data['app_content'] = 'Auction started for property '+auction_data.property.property_name+'!'
                notification_extra_data['app_content_ar'] = 'بدأ المزاد على العقار '+auction_data.property.property_name_ar+'!'
                notification_extra_data['app_screen_type'] = 1
                notification_extra_data['app_notification_image'] = 'review.png'
                notification_extra_data['app_notification_button_text'] = 'View'
                notification_extra_data['app_notification_button_text_ar'] = 'منظر'
                notification_extra_data['property_id'] = property_id
                template_slug = "auction_started"
                add_notification(
                    domain_id=domain_id,
                    user_id=interest.user.id,
                    added_by=interest.user.id,
                    notification_for=1,
                    template_slug=template_slug,
                    extra_data=notification_extra_data
                )

            return Response(response.parsejson("Mail sent.", "", status=201))
        except Exception as exp:
            print(exp)
            return Response(response.parsejson(str(exp), exp, status=403))


class SimilarPropertyApiView(APIView):
    """
    Similar Property
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "domain_id" in data and data['domain_id'] != "":
                domain_id = int(data['domain_id'])
            else:
                return Response(response.parsejson("domain_id is required", "", status=403))

            user_id = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])  

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required", "", status=403))
            property_attribute = property_similar_attribute(property_id)
            property_listing = PropertyListing.objects.filter(domain=domain_id, seller_status=27, status=1).exclude(Q(id=property_id) | Q(status=5))
            if len(property_attribute) > 0:
                property_listing = property_listing.filter(Q(project=property_attribute['project']) | Q(state=property_attribute['state']) | Q(community=property_attribute['community']) | Q(property_type=property_attribute['property_type']))
            
            total = property_listing.count()
            property_listing = property_listing.order_by("-id").only("id")[offset:limit]
            serializer = SilimarPropertySerializer(property_listing, many=True, context={"user_id": user_id})
            all_data = {"data": serializer.data, "total": total}
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403)) 


class PropertyInterestApiView(APIView):
    """
    Similar Property
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5, 6], status=1).last()
                if users is None:
                    return Response(response.parsejson("You are not authorised to access.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required", "", status=403))      

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
            else:
                return Response(response.parsejson("property_id is required", "", status=403))
            
            property_interest = PropertyRegisterInterest.objects.filter(property=property_id)
            if "search" in data and data['search'] != "":
                property_interest = property_interest.filter(Q(user__first_name__icontains=data['search']) | Q(user__email__icontains=data['search']) | Q(user__phone_no__icontains=data['search']))
            total = property_interest.count()
            property_interest = property_interest.order_by("-id").only("id")[offset:limit]
            serializer = PropertyInterestSerializer(property_interest, many=True)
            
            property_detail = PropertyListing.objects.filter(id=property_id).last()
            if property_detail is not None:
                property_detail = ViewCountPropertyDetailSerializer(property_detail).data
            else:
                property_detail = {}
            all_data = {"property_detail": property_detail, "data": serializer.data, "total": total}     
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            print(exp)
            return Response(response.parsejson(str(exp), exp, status=403)) 


class PropertyBuyNowApiView(APIView):
    """
    Property Buy Now
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            offset = 0
            if 'page_size' in data and data['page_size'] != "":
                limit = int(data['page_size'])
            else:
                limit = int(settings.LIST_PER_PAGE)

            if 'page' in data and data['page'] != "":
                page = int(data['page'])
            else:
                page = 1
            # -----------Set Pagination Value--------
            if limit > 0:
                offset = (page - 1) * limit
                limit = limit * page

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5, 6], status=1).last()
                if users is None:
                    return Response(response.parsejson("You are not authorised to access.", "", status=403))
            else:
                return Response(response.parsejson("user_id is required", "", status=403))      

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
                property_details = PropertyListing.objects.filter(id=property_id)
                if users.user_type_id == 5:
                    property_details = property_details.filter(agent=user_id)
                elif users.user_type_id == 6:
                    property_details = property_details.filter(Q(agent=user_id) | Q(developer=user_id)) 
                property_details = property_details.last()    
                if property_details is None:
                    return Response(response.parsejson("Not authorised to access.", "", status=403))
            else:
                return Response(response.parsejson("property_id is required", "", status=403))
            
            property_buy_now = PropertyBuyNow.objects.filter(property=property_id)
            if "search" in data and data['search'] != "":
                property_buy_now = property_buy_now.filter(Q(user__first_name__icontains=data['search']) | Q(user__email__icontains=data['search']) | Q(user__phone_no__icontains=data['search']))
            total = property_buy_now.count()
            property_buy_now = property_buy_now.order_by("-id").only("id")[offset:limit]
            serializer = PropertyBuyNowSerializer(property_buy_now, many=True)
            
            property_detail = PropertyListing.objects.filter(id=property_id).last()
            if property_detail is not None:
                property_detail = ViewCountPropertyDetailSerializer(property_detail).data
            else:
                property_detail = {}
            all_data = {"property_detail": property_detail, "data": serializer.data, "total": total}     
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            print(exp)
            return Response(response.parsejson(str(exp), exp, status=403))


class AcceptBuyNowApiView(APIView):
    """
    Accept Buy Now
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                # Translators: This message appears when site_id is empty
                return Response(response.parsejson("site_id is required.", "", status=403))
            
            user_type = None
            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, user_type__in=[2, 4, 5, 6], status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
                # if users.user_type_id == 5:
                #     user_role = "employee"  
                # elif users.user_type_id == 6:
                #     user_role = "developer"  
                user_type = users.user_type_id 
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            # --- Verify that user_id matches the token user ---
            auth_user = request.user  # user from Bearer token
            if int(user_id) != auth_user.id:
                return Response(response.parsejson("Permission denied.", "", status=403))   

            if "requested_user_id" in data and data['requested_user_id'] != "":
                requested_user_id = int(data['requested_user_id'])
                users = Users.objects.filter(id=requested_user_id, status=1).first()
                if users is None:
                    return Response(response.parsejson("Requested User not exist.", "", status=403))
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))    
            

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
                max_dt = timezone.now()
                property_listing = PropertyListing.objects.filter(id=property_id, property_auction__start_date__gte=max_dt, seller_status=27, status=1)
                if user_type == 6:
                    property_listing = property_listing.filter(Q(agent_id=user_id) | Q(developer_id=user_id))
                elif user_type == 5:
                    property_listing = property_listing.filter(agent_id=user_id)
                
                property_listing = property_listing.last()
                if property_listing is None:
                    return Response(response.parsejson("You can't accept buy now request.", "", status=403)) 
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required.", "", status=403))  

            property_buy_now = PropertyBuyNow.objects.filter(property=property_id, buy_now_status=2, user=requested_user_id).last()
            if property_buy_now is None:
                return Response(response.parsejson("Data Aceepted/Rejected.", "", status=403))    

            with transaction.atomic():
                try:
                    property_buy_now.buy_now_status = 1    
                    property_buy_now.accept_by_id = user_id
                    property_buy_now.accept_date = timezone.now()
                    property_buy_now.save()

                    property_listing.status_id = 9
                    property_listing.closing_status_id = 9
                    property_listing.winner_id = property_buy_now.user_id
                    property_listing.date_sold =  timezone.now()
                    property_listing.sold_price =  property_buy_now.buy_now_amount
                    property_listing.save()

                    # ---------Set Auction End Date-------
                    # PropertyAuction.objects.filter(property_id=property_id).update(start_date=None, end_date=None)
                    # ------Reject Remaining Offer ------
                    try:
                        PropertyBuyNow.objects.filter(
                            property=property_id,
                            buy_now_status=2
                        ).exclude(
                            user=requested_user_id
                        ).update(buy_now_status=3)
                    except Exception as exp:
                        transaction.set_rollback(True)  # -----Rollback Transaction----
                        return Response(response.parsejson(str(exp), "", status=403))

                    # -------------Payment Accept--------
                    try:
                        bid_transaction = BidTransaction.objects.filter(user=requested_user_id, property=property_id, authorizationStatus=1).last()
                        capture_result = capture_payment(bid_transaction.id, capture_for="buy_now")
                        if not capture_result['success']:
                            return Response(response.parsejson(str(capture_result['message']), "", status=403))
                    except Exception as exp:
                        transaction.set_rollback(True)  # -----Rollback Transaction----
                        return Response(response.parsejson(str(exp), "", status=403))
                except Exception as exp:
                    transaction.set_rollback(True)  # -----Rollback Transaction----
                    return Response(response.parsejson(str(exp), "", status=403))   
            # ------------------Email and Notifications------------------
            try:
                if site_id is not None and requested_user_id is not None:
                    # ----------Email & Nptification to Accepted------
                    network = NetworkDomain.objects.filter(id=site_id).last()
                    buyer_details = Users.objects.filter(id=requested_user_id).last()
                    property_details = PropertyListing.objects.filter(id=property_id).last()
                    template_data = {"domain_id": site_id, "slug": "buy_now_accepted"}
                    decorator_url = property_details.property_name.lower() + " " + property_details.country.country_name.lower()
                    decorator_url = re.sub(r"\s+", '-', decorator_url)
                    domain_url = network.domain_react_url + "property/detail/"+str(property_id)+"/"+decorator_url

                    web_url = settings.FRONT_BASE_URL
                    image_url = web_url+'/static/admin/images/property-default-img.png'
                    upload = PropertyUploads.objects.filter(property=property_id, upload_type=1).first()
                    if upload is not None:
                        image = upload.upload.doc_file_name
                        bucket_name = upload.upload.bucket_name
                        image_url = settings.AZURE_BLOB_URL + str(bucket_name)+ '/' +str(image)

                    extra_data = {'user_name': buyer_details.first_name,
                                'web_url': web_url,
                                'property_image': image_url,
                                'property_name': property_details.property_name,
                                'property_address': property_details.address_one,
                                'property_city': property_details.city,
                                'property_state': property_details.state.state_name,
                                'prop_link': domain_url,
                                "domain_id": site_id,
                                'agent_name': property_details.agent.first_name,
                                'agent_email': property_details.agent.email,
                                'agent_phone': phone_format(property_details.agent.phone_no),
                                'community': property_details.community,
                                'property_type': property_details.property_type.property_type
                            }
                    compose_email(to_email=[buyer_details.email], template_data=template_data, extra_data=extra_data)

                    #  add notfification to buyer
                    extra_data['image_name'] = 'check-icon.svg'
                    extra_data['app_content'] = 'Your Buy Now It Offer has been accepted.'
                    extra_data['app_content_ar'] = 'لقد تم قبول عرض "اشتر الآن" الخاص بك.'
                    extra_data['app_screen_type'] = 1
                    extra_data['app_notification_image'] = 'check-icon.png'
                    extra_data['property_id'] = property_id
                    extra_data['app_notification_button_text'] = 'View'
                    extra_data['app_notification_button_text_ar'] = 'منظر'
                    add_notification(
                        site_id,
                        user_id=requested_user_id,
                        added_by=user_id,
                        notification_for=1,
                        template_slug="buy_now_accepted",
                        extra_data=extra_data
                    )

                    # -------Push Notifications-----
                    data = {
                        "title": "Buy Now Offer Accepted", 
                        "message": 'Your Buy Now offer has been accepted! '+ property_details.property_name, 
                        "description": 'Your Buy Now offer has been accepted! '+ property_details.property_name,
                        "notification_to": requested_user_id,
                        "property_id": property_id,
                        "redirect_to": 1
                    }
                    save_push_notifications(data)

                    # -------Accepted Email/Notification To Seller-------
                    rejected_buy_now_user = PropertyBuyNow.objects.filter(property=property_id, buy_now_status=2).exclude(user=requested_user_id)
                    # if rejected_buy_now_user is None:
                    #     extra_data['msg'] = "You are accepted Buy It Now Offer."
                    #     extra_data['image_name'] = 'check-icon.svg'
                    #     extra_data['app_content'] = 'Your are accepted Buy Now It Offer.'
                    #     extra_data['app_content_ar'] = 'لقد تم قبول عرض الشراء الآن الخاص بك.'
                    #     extra_data['app_notification_image'] = 'check-icon.png'
                    # else:
                    #     extra_data['msg'] = "You are rejected Buy It Now Offer."
                    #     extra_data['image_name'] = 'reject.svg'
                    #     extra_data['app_content'] = 'Your are rejected Buy Now It Offer.'
                    #     extra_data['app_content_ar'] = 'تم رفض طلبك. اشترِ الآن هذا العرض.'
                    #     extra_data['app_notification_image'] = 'reject.png'

                    extra_data['msg'] = "Buy It Now offer on your property has been accepted."
                    extra_data['image_name'] = 'check-icon.svg'
                    extra_data['app_content'] = 'Buy It Now offer on your property has been accepted.'
                    extra_data['app_content_ar'] = 'لقد تم قبول عرض الشراء الآن على عقارك.'
                    extra_data['app_notification_image'] = 'check-icon.png'

                    extra_data['user_name'] = property_listing.agent.first_name
                    template_data = {"domain_id": site_id, "slug": "buy_now_accepted_seller"}
                    compose_email(to_email=[property_listing.agent.email], template_data=template_data, extra_data=extra_data)
                    #  add notfification to seller
                    extra_data['app_screen_type'] = 1
                    extra_data['property_id'] = property_id
                    extra_data['app_notification_button_text'] = 'View'
                    extra_data['app_notification_button_text_ar'] = 'منظر'
                    add_notification(
                        site_id,
                        user_id=property_listing.agent_id,
                        added_by=user_id,
                        notification_for=1,
                        template_slug="buy_now_accepted_seller",
                        extra_data=extra_data
                    )

                    # ----------Email & Notification to Rejected User Except Accept User------
                    template_data = {"domain_id": site_id, "slug": "buy_now_rejected"}
                    # rejected_buy_now_user = PropertyBuyNow.objects.filter(property=property_id, buy_now_status=2).exclude(user=requested_user_id)
                    if rejected_buy_now_user is not None:
                        for rejected_buyer in rejected_buy_now_user:
                            extra_data['user_name'] = rejected_buyer.user.first_name
                            compose_email(to_email=[rejected_buyer.user.email], template_data=template_data, extra_data=extra_data)
                            
                            extra_data['app_content'] = 'Your Buy Now It Offer has been rejected.'
                            extra_data['app_content_ar'] = 'لقد تم رفض عرض الشراء الآن الخاص بك.'
                            extra_data['image_name'] = 'reject.svg'
                            extra_data['app_notification_image'] = 'reject.png'
                            
                            add_notification(
                                site_id,
                                user_id=rejected_buyer.user_id,
                                added_by=user_id,
                                notification_for=1,
                                template_slug="buy_now_rejected",
                                extra_data=extra_data
                            )
            except Exception as exp:
                pass            
            return Response(response.parsejson("Your request accepted successfully.", "", status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))                                              

class GetQunataAPIDataView(APIView):
    """
    Get Qunata APIs Data
    """
    authentication_classes = [TokenAuthentication, OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def fetch_token(self):
        """Fetch authentication token."""
        # token_url =  f"{settings.QUANTA_API_BASE_URL}auth/clients/token"
        token_url =  f"{settings.QUANTA_API_BASE_URL}auth/clients/token"
        credentials = f"{settings.QUANTA_TOKEN_API_USERNAME}:{settings.QUANTA_TOKEN_API_PASSWORD}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        token_payload = 'grant_type=client_credentials'
        token_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
            "Authorization": f"Basic {encoded_credentials}",
        }

        try:
            response = requests.post(token_url, data=token_payload, headers=token_headers)
            response.raise_for_status()
            return response.json().get("accessToken")
        except Exception as e:
            print(f"Failed to fetch token: {str(e)}")
            return None

    def fetch_data(self, url, data, token):
        """Fetch data from the provided URL using the provided token."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Authorization": f"Bearer {token}",
        }
        try:
            payload = json.dumps(data)
            response = requests.post(url, data=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Failed to fetch data: {str(e)}")
            return None

    def post(self, request):
        # Step 1: Fetch token
        data = request.data
        if "endpoint" in data and data['endpoint'] != "":
            endpoint = data['endpoint']
        else:
            return Response(response.parsejson("endpoint is required.", "", status=403))
        
        token = self.fetch_token()
        if not token:
            return Response({"error": "Failed to get token"}, status=403)

        # Step 2: Fetch quanta apis data
        quanta_url = f"{settings.QUANTA_API_BASE_URL}{endpoint}"
        # quanta_data = self.fetch_data(quanta_url, {
        #     "municipality": "Abu Dhabi City",
        #     "district": "Yas Island",
        #     "community": "YS3_01",
        #     "project": "West Yas",
        #     "propertyLayout": "4 beds",
        #     "propertyType": "villa / townhouse"
        #     }, token)

        quanta_data = self.fetch_data(quanta_url, {
            "municipality":"Abu Dhabi City",
            "district":"Al Saadiyat Island",
            "community":"SDN7",
            "project":"Hidd Al Saadiyat - Al Seef",
            "propertyLayout":"6+ beds",
            "propertyType":"villa"
            }, token)

        if not quanta_data:
            return Response({"error": "Failed to fetch quanta_data"}, status=403)

        return Response({
            "message": "Sync completed successfully",
            "data": quanta_data,
        }, status=201) 



class PropertyRelistApiView(APIView):
    """
    Property Relist
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            if "site_id" in data and data['site_id'] != "":
                site_id = int(data['site_id'])
                network = NetworkDomain.objects.filter(id=site_id, is_active=1).first()
                if network is None:
                    # Translators: This message appears when site not exist
                    return Response(response.parsejson("Site not exist.", "", status=403))
            else:
                # Translators: This message appears when site_id is empty
                return Response(response.parsejson("site_id is required.", "", status=403))

            if "user_id" in data and data['user_id'] != "":
                user_id = int(data['user_id'])
                users = Users.objects.filter(id=user_id, status=1).first()
                if users is None:
                    return Response(response.parsejson("User not exist.", "", status=403))
            else:
                # Translators: This message appears when user_id is empty
                return Response(response.parsejson("user_id is required.", "", status=403))

            # --- Verify that user_id matches the token user ---
            auth_user = request.user  # user from Bearer token
            if int(user_id) != auth_user.id:
                return Response(response.parsejson("Permission denied.", "", status=403))    

            if "property_id" in data and data['property_id'] != "":
                property_id = int(data['property_id'])
                property_cnt = PropertyListing.objects.filter(parent=property_id).exclude(status=5).count()
                if property_cnt:
                    return Response(response.parsejson("Property Already Relisted.", "", status=403))
            else:
                # Translators: This message appears when property_id is empty
                return Response(response.parsejson("property_id is required", "", status=403))

            property_details = PropertyListing.objects.filter(id=property_id).last()

            # ------check property eligible to relist------
            # if property_details.status_id != 9 or property_details.closing_status_id != 16:
            #       return Response(response.parsejson("Property can't be relist", "", status=403))

            # ------Check listing owner------
            if users.user_type_id not in [2, 4] and property_details.agent_id != user_id and property_details.developer_id != user_id :
                return Response(response.parsejson("Not Authorised User To Relist", "", status=403))
            
            with transaction.atomic():
                try:
                    # Get original property
                    original_property = PropertyListing.objects.get(id=property_id)

                    # Duplicate property
                    new_property = PropertyListing.objects.get(id=property_id)
                    new_property.pk = None
                    new_property.parent_id = property_id
                    new_property.status_id = 1
                    new_property.seller_status_id = 28
                    new_property.closing_status_id = None
                    new_property.winner = None
                    new_property.sold_price = 0
                    new_property.date_sold = None
                    new_property.deposit_amount = None
                    new_property.is_featured = 0
                    new_property.payment_settled = False
                    # new_property.property_for = None
                    new_property.save()
                    new_property_id = new_property.id

                    # Duplicate PropertyOwners
                    original_property_owners = PropertyOwners.objects.filter(property_id=property_id)
                    for owner in original_property_owners:
                        new_owner = PropertyOwners.objects.get(id=owner.id)
                        new_owner.pk = None
                        new_owner.property_id = new_property_id
                        new_owner.save()

                    # Duplicate PropertyAuction
                    original_property_auction = PropertyAuction.objects.get(property_id=property_id)
                    new_property_auction = PropertyAuction.objects.get(id=original_property_auction.id)
                    new_property_auction.pk = None
                    new_property_auction.property_id = new_property_id
                    new_property_auction.auction_unique_id = unique_registration_id()
                    new_property_auction.start_date = None
                    new_property_auction.end_date = None
                    new_property_auction.reserve_amount = None
                    new_property_auction.bid_increments = None
                    new_property_auction.start_price = None
                    new_property_auction.sell_at_full_amount_status = 0
                    new_property_auction.full_amount = None
                    new_property_auction.save()

                    # Duplicate PropertyUploads
                    original_property_uploads = PropertyUploads.objects.filter(property_id=property_id)
                    for upload in original_property_uploads:
                        new_upload = PropertyUploads.objects.get(id=upload.id)
                        new_upload.pk = None
                        new_upload.property_id = new_property_id
                        new_upload.save()

                    # Duplicate PropertyAmenity
                    original_property_amenity = PropertyAmenity.objects.filter(property_id=property_id)
                    for amentiy in original_property_amenity:
                        new_amentiy = PropertyAmenity.objects.get(id=amentiy.id)
                        new_amentiy.pk = None
                        new_amentiy.property_id = new_property_id
                        new_amentiy.save()

                    # Duplicate PropertyTags
                    original_property_tags = PropertyTags.objects.filter(property_id=property_id)
                    for tags in original_property_tags:
                        new_tag = PropertyTags.objects.get(id=tags.id)
                        new_tag.pk = None
                        new_tag.property_id = new_property_id
                        new_tag.save() 

                    # Duplicate PropertyReservationAgreement
                    # original_property_reservation_agreement = PropertyReservationAgreement.objects.get(property_id=property_id)
                    # new_property_reservation_agreement = PropertyReservationAgreement.objects.get(id=original_property_reservation_agreement.id)
                    # new_property_reservation_agreement.pk = None
                    # new_property_reservation_agreement.property_id = new_property_id
                    # new_property_reservation_agreement.save() 
                    # 
                    # ----------------Payment Revert--------------
                    p_listing = PropertyListing.objects.filter(id=property_id, payment_settled=False).last()
                    if p_listing is not None:   
                        transactions = BidTransaction.objects.filter(
                            tranid__isnull=False,
                            paymentid__isnull=False,
                            gateway_status="APPROVED",
                            status=34,
                            payment_failed_status=0,
                            authorizationStatus=1,
                            property_id=property_id
                        ).values_list('id', flat=True)
                        if len(transactions):
                            for id in transactions:
                                cron_void_payment(id)
                        PropertyListing.objects.filter(id=property_id).update(payment_settled=True)

                    # ----Update Old Listing Status To Sold---
                    # property_details.status_id = 9
                    # property_details.closing_status_id = 9
                    # property_details.save()      

                    # --------------Email & Notification to registered buyer------------
                    property_detail = PropertyListing.objects.filter(id=new_property_id).select_related('agent', 'state', 'country', 'property_type').last()
                    upload = PropertyUploads.objects.filter(property=new_property_id, upload_type=1).first()
                    web_url = network.domain_url
                    image_url = network.domain_url+'static/images/property-default-img.png'
                    if upload is not None:
                        image = upload.upload.doc_file_name
                        bucket_name = upload.upload.bucket_name
                        image_url = settings.AZURE_BLOB_URL + str(bucket_name)+ '/' +str(image)
                    decorator_url = property_detail.property_name.lower() + " " + property_detail.country.country_name.lower()
                    decorator_url = re.sub(r"\s+", '-', decorator_url)
                    # domain_url = network.domain_react_url+"seller/property/"+str(new_property_id)+"/"+decorator_url
                    domain_url = network.domain_react_url+"property/detail/"+str(new_property_id)+"/"+decorator_url
                    property_state = property_detail.state.state_name
                    property_type = property_detail.property_type.property_type
                    property_name = property_detail.property_name
                    community = property_detail.community
                    template_data = {"domain_id": site_id, "slug": "relist_property"}
                    extra_data = {
                        # 'user_name': user_name,
                        'web_url': web_url,
                        'property_image': image_url,
                        'property_state': property_state,
                        'property_type': property_type,
                        'property_name': property_name,
                        'community': community,
                        'dashboard_link': domain_url,
                        "domain_id": site_id
                    }
                    # ------Notification Content-----
                    notification_extra_data = {'image_name': 'success.svg', 'property_name': property_detail.property_name, 'property_name_ar': property_detail.property_name_ar, 'redirect_url': domain_url}
                    notification_extra_data['app_content'] = 'Property <b>'+property_detail.property_name+'</b> is relisted for bidding.'
                    notification_extra_data['app_content_ar'] = 'ممتلكاتك '+ ' <b>'+ property_detail.property_name_ar+ '</b> ' + ' تم إعادة إدراجه للمزايدة.'
                    notification_extra_data['app_screen_type'] = 4
                    notification_extra_data['app_notification_image'] = 'success.png'
                    notification_extra_data['property_id'] = new_property_id
                    notification_extra_data['app_notification_button_text'] = 'View'
                    notification_extra_data['app_notification_button_text_ar'] = 'منظر'

                    registered_user = BidRegistration.objects.filter(property_id=property_id).select_related('user')
                    for r_user in registered_user:
                        user_name = r_user.user.first_name
                        to_email = r_user.user.email
                        extra_data['user_name'] = user_name
                        # ----Email to buyer---
                        compose_email(to_email=[to_email], template_data=template_data, extra_data=extra_data)
                        
                        # ----Notification to buyer---
                        add_notification(
                            site_id,
                            user_id=r_user.user_id,
                            added_by=user_id,
                            notification_for=1,
                            template_slug="relist_property",
                            extra_data=notification_extra_data
                        )
                    # --------Email/Notification To Seller-------
                    domain_url = network.domain_react_url+"seller/property/"+str(new_property_id)+"/"+decorator_url
                    template_data = {"domain_id": site_id, "slug": "seller_relist_property"}
                    extra_data['user_name'] = property_detail.agent.first_name
                    compose_email(to_email=[property_detail.agent.email], template_data=template_data, extra_data=extra_data)   
                    # ----Notification to Seller---
                    notification_extra_data = {'image_name': 'success.svg', 'property_name': property_detail.property_name, 'property_name_ar': property_detail.property_name_ar, 'redirect_url': domain_url}
                    notification_extra_data['app_content'] = 'Property <b>'+property_detail.property_name+'</b> is relisted for bidding by you.'
                    notification_extra_data['app_content_ar'] = 'ممتلكاتك '+ ' <b>' +property_detail.property_name_ar+ ' </b> ' +' تم إعادة إدراجها للمزايدة من قبلك.'
                    notification_extra_data['app_screen_type'] = 4
                    notification_extra_data['app_notification_image'] = 'success.png'
                    notification_extra_data['property_id'] = new_property_id
                    notification_extra_data['app_notification_button_text'] = 'View'
                    notification_extra_data['app_notification_button_text_ar'] = 'منظر'
                    add_notification(
                        site_id,
                        user_id=property_detail.agent_id,
                        added_by=user_id,
                        notification_for=1,
                        template_slug="seller_relist_property",
                        extra_data=notification_extra_data
                    )

                except Exception as exp:
                    transaction.set_rollback(True)  # -----Rollback Transaction----
                    return Response(response.parsejson(str(exp), exp, status=403))        
                
            return Response(response.parsejson("Property relisted successfully.", {"property_id": new_property_id}, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))   


class PropertyStatApiView(APIView):
    """
    Property Stat
    """
    authentication_classes = [OAuth2Authentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        try:
            data = request.data
            property_listing = PropertyListing.objects
            sold_property_count = property_listing.filter(status=9, closing_status=9).count()
            total_property_count = property_listing.exclude(status=5).count()
            available_auction_count = property_listing.filter(status=1, seller_status=27).count()
            auction_value = property_listing.filter(status=9, closing_status=9).aggregate(total=Sum('sold_price'))['total'] or 0
            all_data = {"sold_property_count": sold_property_count, "total_property_count": total_property_count, "available_auction_count": available_auction_count, "auction_value": auction_value}     
            return Response(response.parsejson("Fetch Data.", all_data, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))                     