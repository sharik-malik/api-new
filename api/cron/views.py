# -*- coding: utf-8 -*-
from re import escape
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.viewsets import ViewSet
from api.packages.response import Response as response
from api.packages.oauth import *
from api.packages.globalfunction import *
from api.packages.common import *
from api.bid.models import *
from api.bid.serializers import *
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password
import datetime
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count
from django.conf import settings
from rest_framework.authentication import TokenAuthentication
from oauth2_provider.contrib.rest_framework import *
from django.db.models.functions import Concat
from django.db.models import Value as V
from django.db.models import CharField
from django.db.models import Max, Min
from api.packages.mail_service import send_email, compose_email, send_custom_email
from django.db.models import F, Window
from django.db.models.functions.window import FirstValue, LastValue
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import HttpResponseRedirect
from api.payments.services.gateway import void_payment, capture_payment, cron_void_payment
from django.utils import timezone
from datetime import timedelta
from rest_framework.permissions import AllowAny, IsAuthenticated

class PaymentCronApiView(APIView):
    """
    Payment cron setup
    """
    # authentication_classes = [OAuth2Authentication]
    permission_classes = (AllowAny,)

    @staticmethod
    def get(request):
        try:
            data = request.data
            cutoff_time = timezone.now() - timedelta(hours=72)
            property_ids = PropertyListing.objects.filter(
                Q(status=9) &
                ~Q(closing_status=9) &
                Q(property_auction__end_date__lt=cutoff_time)
            ).values_list('id', flat=True)
            with transaction.atomic():
                try:
                    if len(property_ids):
                        transactions = BidTransaction.objects.filter(
                            tranid__isnull=False,
                            paymentid__isnull=False,
                            gateway_status="APPROVED",
                            status=34,
                            payment_failed_status=0,
                            authorizationStatus=1,
                            property__in=property_ids
                        ).values_list('id', flat=True)
                        if len(transactions):
                            for id in transactions:
                                cron_void_payment(id)

                        PropertyListing.objects.filter(id__in=property_ids).update(payment_settled=True) 
                except Exception as exp:
                    transaction.set_rollback(True)  # -----Rollback Transaction----
                    return Response(response.parsejson(str(exp), exp, status=403))          

            return Response(response.parsejson("Cron script executed successfully.", {}, status=201))
        except Exception as exp:
            return Response(response.parsejson(str(exp), exp, status=403))