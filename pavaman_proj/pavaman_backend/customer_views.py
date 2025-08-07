import os
import re
import math
import uuid
import json
import string
import random
import calendar
from datetime import datetime, timedelta
from collections import Counter
from decimal import Decimal
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse, FileResponse, StreamingHttpResponse
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.db import models, IntegrityError
from django.db.models import F, Sum, Min, Max, FloatField, ExpressionWrapper
from django.core.mail import send_mail, EmailMessage, EmailMultiAlternatives
from django.contrib.auth.hashers import make_password, check_password
import requests
import boto3
from botocore.exceptions import ClientError
from email.mime.image import MIMEImage
from dateutil.relativedelta import relativedelta
import razorpay
from .models import (
    CustomerRegisterDetails, PavamanAdminDetails, CategoryDetails, ProductsDetails,
    SubCategoryDetails, CartProducts, CustomerAddress, OrderProducts,
    PaymentDetails, FeedbackRating,Wishlist
)
import threading
from .msg91 import send_bulk_sms,send_verify_mobile,send_order_confirmation_sms


def is_valid_password(password):
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not any(char.isdigit() for char in password):
        return "Password must contain at least one digit."
    if not any(char.isupper() for char in password):
        return "Password must contain at least one uppercase letter."
    if not any(char.islower() for char in password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Password must contain at least one special character."
    return None
def match_password(password, re_password):
    if password != re_password:
        return "Passwords must be same."
    return None 

@csrf_exempt
def customer_register(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            first_name = data.get('first_name')
            last_name = data.get('last_name')
            email = data.get('email')
            mobile_no = data.get('mobile_no')
            password = data.get('password')
            re_password = data.get('re_password')
            status = 1
            register_status = 0
            verification_link = str(uuid.uuid4())
         
            if not all([first_name, last_name, email, mobile_no, password, re_password]):
                return JsonResponse(
                    {"error": "first_name,last_name, email, mobile_no and password are required.", "status_code": 400}, status=400
                )
            password_error = is_valid_password(password)
            if password_error:
                return JsonResponse({"error": password_error, "status_code": 400}, status=400)
            mismatch_error = match_password(password, re_password)
            if mismatch_error:
                return JsonResponse({"error": mismatch_error, "status_code": 400}, status=400)
            existing_customer = CustomerRegisterDetails.objects.filter(email=email).first()
            if existing_customer:
                if existing_customer.password is None:
                    return JsonResponse({"error": "This email was registered using Google Sign-In. Please reset your password to proceed.", "status_code": 409}, status=409)
                return JsonResponse({"error": "Email already exists. Please use a different email.", "status_code": 409}, status=409)
            
            if CustomerRegisterDetails.objects.filter(mobile_no=mobile_no).exists():
                return JsonResponse({"error": "Mobile number already exists. Please use a different mobile number.", "status_code": 409}, status=409)

            admin = PavamanAdminDetails.objects.order_by('id').first()
            if not admin:
                return JsonResponse({"error": "No admin found in the system.", "status_code": 500}, status=500)            
            current_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
            customer = CustomerRegisterDetails(
                first_name=first_name,
                last_name=last_name,
                email=email,
                mobile_no=mobile_no,
                password=make_password(password),
                status=int(status),
                register_status=int(register_status),
                created_on=current_time,
                admin=admin,
                verification_link=verification_link,
                register_type="Mannual"
            )
            customer.save()
            customer.register_status = 1
            customer.save(update_fields=['register_status'])
            send_verification_email(email,first_name,verification_link)

            return JsonResponse(
                {
                    "message": "Account Created Successfully. Verification link sent to email.",
                    "id": customer.id,
                    "status_code": 201,
                }, status=201
            )

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data.", "status_code": 400}, status=400)
        except IntegrityError:
            return JsonResponse({"error": "Database integrity error.", "status_code": 500}, status=500)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST allowed.", "status_code": 405}, status=405)

@csrf_exempt
def verify_email(request, verification_link):
    try:
        
        customer = CustomerRegisterDetails.objects.filter(verification_link=verification_link).first()

        if not customer:
            return JsonResponse({
                "error": "Invalid or expired verification link. Please request a new verification link.",
                "status_code": 400,
            }, status=400)
        
        if customer.verification_link != verification_link:
            return JsonResponse({
                "error": "Verification link has expired. Please request a new verification link.",
                "status_code": 400,
            }, status=400)

        customer.account_status = 1  
        customer.verification_link = None
        customer.save(update_fields=["account_status","verification_link"])
        return JsonResponse({
            "message": "Account successfully verified.",
            "status_code": 200,
        }, status=200)
    
    except CustomerRegisterDetails.DoesNotExist:
        return JsonResponse({
            "error": "Invalid verification link.",
            "status_code": 400,
        }, status=400)
    
def send_verification_email(email, first_name, verification_link):
    subject = "[Pavaman] Please Verify Your Email"

    frontend_url =  settings.FRONTEND_URL
    full_link = f"{frontend_url}/verify-email/{verification_link}"
    logo_url = f"{settings.AWS_S3_BUCKET_URL}/static/images/aviation-logo.png"

    text_content = f"""
    Hello {first_name},
    """
    html_content = f"""
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
            @media only screen and (max-width: 600px) {{
                .container {{
                    width: 90% !important;
                    padding: 20px !important;
                }}
                .logo {{
                    max-width: 180px !important;
                    height: auto !important;
                }}
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', sans-serif; background-color: #f5f5f5;">
        <div class="container" style="margin: 40px auto; background-color: #ffffff; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 40px 30px; max-width: 480px; text-align: left;">
                <div style="text-align: center;">
                <img src="{logo_url}" alt="Pavaman Logo" class="logo" style="max-width: 280px; height: auto; margin-bottom: 20px;" />
                <h2 style="margin-top: 0; color: #222;">Please verify your email</h2>
            </div>
            <div style="margin-bottom: 10px; color: #555; font-size: 14px;">
                Hello {first_name},
            </div>
            <p style="color: #555; margin: 20px 0 30px; font-size:14px">
                To use <strong>Pavaman</strong>, click the verification button. This helps keep your account secure.
            </p>
            <div style="text-align: center;">
                <a href="{full_link}" style="display: inline-block; padding: 14px 28px; background-color: #4450A2; color: #ffffff; font-weight: 600; border-radius: 8px; text-decoration: none; font-size: 16px;">
                    Verify my account
                </a>
            </div>
            <p style="color: #888; font-size: 14px; margin-top: 20px;">
                If you didn't request this, you can safely ignore this email.<br/>
                You're receiving this because you have an account on Pavaman.
            </p>
            <p style="margin-top: 30px; font-size: 14px; color: #888;">This is an automated email. Please do not reply.</p>
        </div>
    </body>
    </html>
    """

    email_message = EmailMultiAlternatives(
        subject, text_content, settings.DEFAULT_FROM_EMAIL, [email]
    )
    email_message.attach_alternative(html_content, "text/html")
    email_message.send()

# @csrf_exempt
# def customer_login(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             email = data.get('email')
#             password = data.get('password')

#             if not email or not password:
#                 return JsonResponse({"error": "Email and Password are required.", "status_code": 400}, status=400)

#             try:
#                 customer = CustomerRegisterDetails.objects.get(email=email)
#             except CustomerRegisterDetails.DoesNotExist:
#                 return JsonResponse({"error": "Invalid email or password.", "status_code": 401}, status=401)
            
#             if customer.password is None:
#                 return JsonResponse({"error": "You registered using Google Sign-In. Please reset your password.", "status_code": 401}, status=401)
            
#             if customer.account_status != 1:
#                 return JsonResponse({"error": "Account is not activated. Please verify your email.", "status_code": 403}, status=403)

#             if not check_password(password, customer.password):
#                 return JsonResponse({"error": "Invalid email or password.", "status_code": 401}, status=401)

#             request.session['customer_id'] = customer.id
#             request.session['email'] = customer.email
#             request.session.set_expiry(3600)

#             return JsonResponse(
#                 {"message": "Login successful.", 
#                 "customer_id": customer.id,
#                 "customer_name":customer.first_name + " " + customer.last_name,
#                 "customer_email":customer.email, 
#                 "status_code": 200}, status=200
#             )

#         except json.JSONDecodeError:
#             return JsonResponse({"error": "Invalid JSON data.", "status_code": 400}, status=400)
#         except Exception as e:
#             return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

#     return JsonResponse({"error": "Invalid HTTP method. Only POST allowed.", "status_code": 405}, status=405)

@csrf_exempt
def customer_login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')

            if not email and not password:
                return JsonResponse({"error": "Email and Password are required.", "status_code": 400}, status=400)

            if not email:
                return JsonResponse({"error": "Please enter your email.", "status_code": 400}, status=400)

            if not password:
                return JsonResponse({"error": "Please enter your password.", "status_code": 400}, status=400)

            try:
                customer = CustomerRegisterDetails.objects.get(email=email)
            except CustomerRegisterDetails.DoesNotExist:
                return JsonResponse({"error": "Invalid email or password.", "status_code": 401}, status=401)
           
            if customer.password is None:
                return JsonResponse({"error": "You registered using Google Sign-In. Please reset your password.", "status_code": 401}, status=401)
           
            if customer.account_status != 1:
                return JsonResponse({"error": "Account is not activated. Please verify your email.", "status_code": 403}, status=403)

            if not check_password(password, customer.password):
                return JsonResponse({"error": "Invalid email or password.", "status_code": 401}, status=401)

            request.session['customer_id'] = customer.id
            request.session['email'] = customer.email
            request.session.set_expiry(3600)

            return JsonResponse(
                {"message": "Login successful.",
                "customer_id": customer.id,
                "customer_name":customer.first_name + " " + customer.last_name,
                "customer_email":customer.email,
                "status_code": 200}, status=200
            )

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST allowed.", "status_code": 405}, status=405)

@csrf_exempt
def google_login(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            token = data.get("token")

            if not token:
                return JsonResponse({"error": "Token is required"}, status=400)
            
            google_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
            response = requests.get(google_url)
            
            if response.status_code != 200:
                return JsonResponse({"error": "Failed to verify token"}, status=400)

            customer_info = response.json()

            if "error" in customer_info:
                return JsonResponse({"error": "Invalid Token"}, status=400)

            email = customer_info.get("email")
            first_name = customer_info.get("given_name", "")
            last_name = customer_info.get("family_name", "")

            if not email:
                return JsonResponse({"error": "Email is required"}, status=400)

            customer = CustomerRegisterDetails.objects.filter(email=email).first()

            if customer:
                if customer.account_status == 1:
                    request.session['customer_id'] = customer.id
                    request.session['email'] = customer.email
                    request.session.set_expiry(3600) 

                    return JsonResponse({
                        "message": "Login successful",
                        "existing_customer": True,
                        "customer_id": customer.id,
                        "email": customer.email,
                        "first_name": customer.first_name,
                        "last_name": customer.last_name,
                        "register_status": customer.register_status,
                    })
                else:
                    return JsonResponse({"error": "Account is not verified","email":customer.email}, status=403)
                   
            admin = PavamanAdminDetails.objects.order_by('id').first()
            if not admin:
                return JsonResponse({"error": "No admin found in the system.", "status_code": 500}, status=500)

            verification_link = str(uuid.uuid4())
            customer = CustomerRegisterDetails.objects.create(
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=None,
                verification_link=verification_link,
                register_type="Google",
                admin=admin,
            )
            
            send_verification_email(email,first_name,verification_link)

            return JsonResponse({
                "message": "Account Created Successfully. Verification email sent. Submit your mobile number after verification.",
                "new_customer": True,
                "customer_id": customer.id,
                "email": customer.email,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "register_status": customer.register_status,
            })
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
def resend_verification_email(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")

            if not email:
                return JsonResponse({"error": "Email is required."}, status=400)
            customer = CustomerRegisterDetails.objects.filter(email=email).first()
            if not customer:
                return JsonResponse({"error": "User not found."}, status=404)

            if customer.account_status == 1:
                return JsonResponse({"error": "Account is already verified."}, status=400)
            verification_link = str(uuid.uuid4())
            customer.verification_link = verification_link
            customer.save(update_fields=["verification_link"])
            first_name = customer.first_name 
            send_verification_email(email,first_name,verification_link)

            return JsonResponse({
                "message": "Verification email resent successfully.",
                "email": email
            })

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
def google_submit_mobile(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            customer_id = data.get("customer_id")
            mobile_no = data.get("mobile_no")

            if not customer_id or not mobile_no:
                return JsonResponse({"error": "User ID and Mobile Number are required."}, status=400)
            if CustomerRegisterDetails.objects.filter(mobile_no=mobile_no).exists():
                return JsonResponse({"error": "Mobile number already exists. Please use a different mobile number.", "status_code": 409}, status=409)
            try:
                customer = CustomerRegisterDetails.objects.get(id=customer_id)
            except CustomerRegisterDetails.DoesNotExist:
                return JsonResponse({"error": "User not found."}, status=404)

            if customer.register_status == 1:
                return JsonResponse({"error": "Mobile number already submitted."}, status=400)
            customer.mobile_no = mobile_no
            customer.register_status = 1 
            customer.save(update_fields=["mobile_no", "register_status"])
            return JsonResponse({
                "message": "Mobile number saved Sucessfully.",
                "customer_id": customer.id,
                "register_status": customer.register_status,
            })

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)

def generate_reset_token():
    return str(uuid.uuid4())

def delete_otp_after_delay(customer_id):
    try:
        customer = CustomerRegisterDetails.objects.filter(id=customer_id).first()
        if customer:
            customer.otp = None
            customer.reset_link = None
            customer.save()
            print(f"OTP for {customer_id} deleted after 2 minutes ")
    except Exception as e:
        print(f"Error deleting OTP: {e}")
@csrf_exempt
def otp_generate(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            identifier = data.get("identifier")

            if not identifier:
                return JsonResponse({"error": "Email or Mobile number is required"}, status=400)

            customer = None
            otp_send_type = None

            if "@" in identifier:
                customer = CustomerRegisterDetails.objects.filter(email=identifier).first()
                otp_send_type = "email"
            else:
                customer = CustomerRegisterDetails.objects.filter(mobile_no=identifier).first()
                otp_send_type = "mobile"

            if not customer:
                return JsonResponse({"error": "User not found"}, status=404)
            
            if customer.account_status != 1:
                return JsonResponse({"error": "Account is not verified. Please verify your email first."}, status=403)
            otp = random.randint(100000, 999999)
            reset_token = str(uuid.uuid4())
            customer.otp = otp
            customer.reset_link = reset_token
            customer.otp_send_type = otp_send_type
            customer.changed_on = timezone.now()
            customer.save()
            threading.Timer(300, delete_otp_after_delay, args=[customer.id]).start()
            if otp_send_type == "email":
                send_password_reset_otp_email(customer)
                return JsonResponse({
                    "message": "OTP sent to email",
                    "reset_token":customer.reset_link
                    })
            else:
                send_bulk_sms([identifier],otp)
                return JsonResponse({
                    "message": "OTP sent to mobile number",
                    "reset_token":customer.reset_link
                    })
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
    return JsonResponse({"error": "Invalid request method"}, status=405)

def send_password_reset_otp_email(customer):
    otp = customer.otp
    email = customer.email
    first_name = customer.first_name or 'Customer'
    reset_token = customer.reset_link
    logo_url = f"{settings.AWS_S3_BUCKET_URL}/static/images/aviation-logo.png"
    subject = "[Pavaman] Your OTP for Password Reset"
    text_content = f"Hello {first_name},\n\nYour OTP for password reset is: {otp}"
    html_content = f"""
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
            @media only screen and (max-width: 600px) {{
                .container {{
                    width: 90% !important;
                    padding: 20px !important;
                }}
                .logo {{
                    max-width: 180px !important;
                    height: auto !important;
                }}
                .otp {{
                    font-size: 24px !important;
                    padding: 10px 20px !important;
                }}
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', sans-serif; background-color: #f5f5f5;">
        <div class="container" style="margin: 40px auto; background-color: #ffffff; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 40px 30px; max-width: 480px; text-align: left;">
            <div style="text-align: center;">
            <img src="{logo_url}" alt="Pavaman Logo" class="logo" style="max-width: 280px; height: auto; margin-bottom: 20px;" />
            <h2 style="margin-top: 0; color: #222;">Your OTP for Password Reset</h2>
            </div>

            <p style="color: #555; margin-bottom: 30px; text-align: left;">
            Hello <strong>{first_name}</strong>,
            </p>

            <p style="color: #555; margin-bottom: 30px;">
                Use the OTP below to reset your password. This OTP is valid for 2 minutes.
            </p>
          
            <p class="otp" style="font-size: 28px; font-weight: bold; color: #4450A2; background: #f2f2f2; display: block; padding: 12px 24px; border-radius: 10px; letter-spacing: 4px; width: fit-content; margin: 0 auto;">
                {otp}
            </p>

            <p style="color: #888; font-size: 14px; margin-top: 20px;">
                If you didn't request this, you can safely ignore this email.<br/>
                You're receiving this because you have an account on Pavaman.
            </p>
            <p style="margin-top: 30px; font-size: 14px; color: #888;">This is an automated email. Please do not reply.</p>
        </div>
    </body>
    </html>
    """

    email_message = EmailMultiAlternatives(
        subject, text_content, settings.DEFAULT_FROM_EMAIL, [email]
    )
    email_message.attach_alternative(html_content, "text/html")

    email_message.send()

@csrf_exempt
def verify_otp(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            identifier = data.get("identifier")
            otp = data.get("otp")
            reset_link = data.get("reset_link")

            if not identifier or not otp or not reset_link:
                return JsonResponse({"error": "Email/Mobile, OTP, and Reset Link are required"}, status=400)
            customer = CustomerRegisterDetails.objects.filter(
                email=identifier
            ).first() or CustomerRegisterDetails.objects.filter(
                mobile_no=identifier
            ).first()

            if not customer:
                return JsonResponse({"error": "User not found with the provided email or mobile number"}, status=404)
            if not customer.reset_link:
                return JsonResponse({"error": "Reset link has expired or is missing"}, status=400)

            if customer.reset_link != reset_link:
                return JsonResponse({"error": "Invalid reset link for this user"}, status=400)
            customer.clear_expired_otp()
            if not customer.otp or str(customer.otp) != str(otp):
                return JsonResponse({"error": "Invalid OTP or OTP has expired"}, status=400)
            customer.otp = None
            customer.reset_link = None
            customer.save()

            return JsonResponse({"message": "OTP verified successfully"})

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@csrf_exempt
def set_new_password(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            identifier = data.get("identifier")
            new_password = data.get("new_password")
            confirm_password = data.get("confirm_password")

            if not identifier or not new_password or not confirm_password:
                return JsonResponse({"error": "Email/Mobile, New Password, and Confirm Password are required."}, status=400)
            customer = CustomerRegisterDetails.objects.filter(
                email=identifier
            ).first() or CustomerRegisterDetails.objects.filter(
                mobile_no=identifier
            ).first()

            if not customer:
                return JsonResponse({"error": "User not found."}, status=404)
            password_error = is_valid_password(new_password)
            if password_error:
                return JsonResponse({"error": password_error}, status=400)
            match_error = match_password(new_password, confirm_password)
            if match_error:
                return JsonResponse({"error": match_error}, status=400)
            customer.password = make_password(new_password)
            customer.save()

            return JsonResponse({"message": "Password updated successfully."})

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data."}, status=400)

    return JsonResponse({"error": "Invalid request method."}, status=405)


@csrf_exempt
def customer_logout(request):
    if request.method == 'POST':
        try:
            customer_id = request.session.get("customer_id")
            if customer_id:
                request.session.flush()
                return JsonResponse({
                    "message": "Logout successful.",
                    "status_code": 200
                }, status=200)
            else:
                return JsonResponse({
                    "error": "User not logged in.",
                    "status_code": 400
                }, status=400)

        except Exception as e:
            return JsonResponse({
                "error": f"An error occurred during logout: {str(e)}",
                "status_code": 500
            }, status=500)

    return JsonResponse({
        "error": "Invalid HTTP method. Only POST allowed.",
        "status_code": 405
    }, status=405)

def get_wishlist_product_ids(customer_id):
    if customer_id:
        return set(
            Wishlist.objects.filter(customer_id=customer_id).values_list('product_id', flat=True)
        )
    return set()

@csrf_exempt
def view_categories_and_discounted_products(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            customer_id = data.get('customer_id')
            categories = CategoryDetails.objects.filter(category_status=1)
            category_list = [
                {
                    "category_id": str(category.id),
                    "category_name": category.category_name,
                    "category_image_url": f"{settings.AWS_S3_BUCKET_URL}/{category.category_image}"
                }
                for category in categories
            ] if categories.exists() else []

            products = ProductsDetails.objects.filter(discount__gt=0, product_status=1).select_related('category', 'sub_category')
            wishlist_product_ids = get_wishlist_product_ids(customer_id)
            product_list = []
            for product in products:
                if isinstance(product.product_images, list) and product.product_images:
                     product_image_url = f"{settings.AWS_S3_BUCKET_URL}/{product.product_images[0]}"
                else:
                    product_image_url = ""

                category_name = product.category.category_name if product.category else None
                sub_category_name = product.sub_category.sub_category_name if product.sub_category else None
                discounted_amount = (product.price * (product.discount or 0)) / 100
                final_price = (product.price - discounted_amount)
                gst = product.gst if product.gst else 0
                
                product_list.append({
                    "product_id": str(product.id),
                    "product_name": product.product_name,
                    "product_image_url": product_image_url,
                    "price": product.price,
                    "gst": f"{gst}%",
                    "discount": f"{int(product.discount)}%" if product.discount else "0%",
                    "discounted_amount": round(discounted_amount, 2),
                    "final_price": round(final_price, 2),
                    "category_id": str(product.category_id) if product.category_id else None,
                    "category_name": category_name,
                    "sub_category_id": str(product.sub_category_id) if product.sub_category_id else None,
                    "sub_category_name": sub_category_name,
                    "quantity":product.quantity,
                    "availability":product.availability,
                    "is_in_wishlist": product.id in wishlist_product_ids
                })

            response_data = {
                "message": "Data retrieved successfully.",
                "categories": category_list,
                "discounted_products": product_list,
                "status_code": 200
            }

            if customer_id:
                response_data["customer_id"] = customer_id

            return JsonResponse(response_data, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

@csrf_exempt
def view_sub_categories_and_discounted_products(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            category_name = data.get('category_name')
            if not category_name:
                return JsonResponse({"error": "Category name is required.", "status_code": 400}, status=400)
            category = CategoryDetails.objects.filter(category_name__iexact=category_name, category_status=1).first()
            if not category:
                return JsonResponse({"error": "Category not found or inactive.", "status_code": 404}, status=404)
            if customer_id:
                customer_exists = CustomerRegisterDetails.objects.filter(id=customer_id, status=1).exists()
                if not customer_exists:
                    return JsonResponse({"error": "Customer not found.", "status_code": 401}, status=401)
            subcategories = SubCategoryDetails.objects.filter(category=category, sub_category_status=1)
            subcategory_list = []
            for subcategory in subcategories:
                product_count = ProductsDetails.objects.filter(
                    sub_category=subcategory, product_status=1
                ).count()
                if product_count > 0:
                    subcategory_list.append({
                        "sub_category_id": str(subcategory.id),
                        "sub_category_name": subcategory.sub_category_name,
                        "sub_category_image_url": f"{settings.AWS_S3_BUCKET_URL}/{subcategory.sub_category_image}" if subcategory.sub_category_image else "",
                        "product_available": True,
                        "product_count": product_count
                    })
            products = ProductsDetails.objects.filter(
                discount__gt=0,
                product_status=1
            )
            wishlist_product_ids = get_wishlist_product_ids(customer_id)
            product_list = []
            for product in products:
                discounted_amount = (product.price * (product.discount or 0)) / 100
                final_price = round(product.price - discounted_amount)
                gst = product.gst if product.gst else 0
                product_image_url = ""
                if isinstance(product.product_images, list) and product.product_images:
                    product_image_url = f"{settings.AWS_S3_BUCKET_URL}/{product.product_images[0]}"
                product_list.append({
                        "product_id": str(product.id),
                        "product_name": product.product_name,
                        "product_image_url": product_image_url,
                        "is_in_wishlist": product.id in wishlist_product_ids,
                        "price": round(product.price, 2),
                        "gst": f"{gst}%",
                        "discount": f"{int(product.discount)}%" if product.discount else "0%",
                        "final_price": round(final_price, 2),
                        "category_id": str(product.category.id),
                        "category_name": product.category.category_name,
                        "sub_category_id": str(product.sub_category.id),
                        "sub_category_name": product.sub_category.sub_category_name
                    })
            all_products = ProductsDetails.objects.filter(category=category, product_status=1)
            if all_products.exists():
                all_prices = [round(p.price - ((p.price * (p.discount or 0)) / 100), 2) for p in all_products]
                min_price = min(all_prices)
                max_price = max(all_prices)
                if min_price == max_price:
                    min_price = 0
            else:
                min_price = 0
                max_price = 0
            all_categories = CategoryDetails.objects.filter(category_status=1)
            all_categories_data = []
            for cat in all_categories:
                subcats_data = []
                subcats = SubCategoryDetails.objects.filter(category=cat, sub_category_status=1)
                for sub in subcats:
                    product_count = ProductsDetails.objects.filter(
                        sub_category=sub, product_status=1
                    ).count()
                    subcats_data.append({
                        "sub_category_id": str(sub.id),
                        "sub_category_name": sub.sub_category_name,
                        "product_available": product_count > 0,
                        "product_count": product_count
                    })
                all_categories_data.append({
                    "category_id": str(cat.id),
                    "category_name": cat.category_name,
                    "subcategories": subcats_data
                })
            response_data = {
                "message": "Data retrieved successfully.",
                "category_id": str(category.id),
                "category_name": category_name,
                "min_price": min_price,
                "max_price": max_price,
                "subcategories": subcategory_list,
                "discounted_products": product_list,
                "all_categories": all_categories_data,
                "status_code": 200
            }
            if customer_id:
                response_data["customer_id"] = customer_id
            return JsonResponse(response_data, status=200)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)
    return JsonResponse({"error": "Invalid request method. Use POST.", "status_code": 405}, status=405)


@csrf_exempt
def view_products_by_category_and_subcategory(request, category_name, sub_category_name):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')

            try:
                category = CategoryDetails.objects.get(category_name=category_name)
                sub_category = SubCategoryDetails.objects.get(sub_category_name=sub_category_name, category=category)
                if customer_id:
                    customer = CustomerRegisterDetails.objects.get(id=customer_id)
            except CustomerRegisterDetails.DoesNotExist:
                return JsonResponse({"error": "Customer not found.", "status_code": 404}, status=404)
            except CategoryDetails.DoesNotExist:
                return JsonResponse({"error": "Category not found.", "status_code": 404}, status=404)
            except SubCategoryDetails.DoesNotExist:
                return JsonResponse({"error": "Subcategory not found.", "status_code": 404}, status=404)
            products = ProductsDetails.objects.filter(
                category=category, sub_category=sub_category, product_status=1
            ).values(
                'id', 'product_name', 'sku_number', 'price', 'availability', 'quantity', 'product_images', 'discount',  'gst','cart_status'
            )

            if not products.exists():
                return JsonResponse({"error": "No products found for the given sub category.", "status_code": 404}, status=404)
        
            all_prices = [
                round(float(product['price']) - float(product.get('discount', 0)), 2)
                for product in products
            ]
            min_price = min(all_prices)
            max_price = max(all_prices)

            if min_price == max_price:
                min_price = 0

            price_range = {
                "product_min_price": min_price,
                "product_max_price": max_price
            }

            product_list = []
            for product in products:
                image_path = product['product_images'][0] if isinstance(product['product_images'], list) and product['product_images'] else None
                image_url = f"{settings.AWS_S3_BUCKET_URL}/{image_path}" if image_path else ""
                price = round(float(product['price']), 2)
                discount = float(product.get('discount') or 0)
                gst = float(product.get('gst') or 0)
                discounted_amount = (price * discount) / 100
                final_price = price - discounted_amount
                final_price = round(final_price, 2)

                product_list.append({
                    "product_id": str(product['id']),
                    "product_name": product['product_name'],
                    "sku_number": product['sku_number'],
                    "price": price,
                    "discount": f"{int(discount)}%",
                    "gst": f"{gst}%", 
                    "discounted_amount": round(discounted_amount, 2),
                    "final_price": final_price,
                    "availability": product['availability'],
                    "quantity": product['quantity'],
                    "product_image_url": image_url,
                    "cart_status": product['cart_status']
                    
                })

            response_data = {
                "message": "Products retrieved successfully.",
                "status_code": 200,
                "category_id":str(category.id),
                "category_name": category_name,
                "sub_category_id":str(sub_category.id),
                "sub_category_name": sub_category_name,
                "product_min_price": price_range["product_min_price"],
                "product_max_price": price_range["product_max_price"],
                "products": product_list
            }

            if customer_id:
                response_data["customer_id"] = str(customer_id)

            return JsonResponse(response_data, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Use POST.", "status_code": 405}, status=405)
@csrf_exempt
def view_products_details(request, product_name):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            category_name = data.get('category_name')
            sub_category_name = data.get('sub_category_name')

            if not all([category_name, sub_category_name, product_name]):
                return JsonResponse({
                    "error": "category_name, sub_category_name, and product_name are required.",
                    "status_code": 400
                }, status=400)

            try:
                category = CategoryDetails.objects.get(category_name=category_name)
                sub_category = SubCategoryDetails.objects.get(sub_category_name=sub_category_name, category=category)
                product = ProductsDetails.objects.get(product_name=product_name, category=category, sub_category=sub_category)
                wishlist_product_ids = get_wishlist_product_ids(customer_id)
                if customer_id:
                    try:
                        customer = CustomerRegisterDetails.objects.get(id=customer_id)
                    except CustomerRegisterDetails.DoesNotExist:
                        return JsonResponse({"error": "Customer not found.", "status_code": 404}, status=404)

            except CategoryDetails.DoesNotExist:
                return JsonResponse({"error": "Category not found.", "status_code": 404}, status=404)
            except SubCategoryDetails.DoesNotExist:
                return JsonResponse({"error": "Subcategory not found.", "status_code": 404}, status=404)
            except ProductsDetails.DoesNotExist:
                return JsonResponse({"error": "Product not found.", "status_code": 404}, status=404)
            
            price = float(product.price)
            discount = float(product.discount or 0)
            gst = float(product.gst or 0)
            discounted_amount = round((price * discount) / 100, 2)
            final_price = price - discounted_amount
            final_price = round(final_price, 2)
            product_images = []
            if isinstance(product.product_images, list):
                for image_path in product.product_images:
                    if image_path:
                        product_images.append(f"{settings.AWS_S3_BUCKET_URL}/{image_path}")

            material_file_url = f"{settings.AWS_S3_BUCKET_URL}/{product.material_file}" if product.material_file else ""

            product_data = {
                "product_id": str(product.id),
                "product_name": product.product_name,
                "sku_number": product.sku_number,
                "price": round(price, 2),
                "gst": f"{int(gst)}%",
                "discount": f"{int(discount)}%",
                "discounted_amount": round(discounted_amount, 2),
                "final_price": final_price,  
                "availability": product.availability,
                "quantity": product.quantity,
                "description": product.description,
                "product_images":product_images,
                "material_file": material_file_url,
                "number_of_specifications": product.number_of_specifications,
                "specifications": product.specifications,
                "is_in_wishlist": product.id in wishlist_product_ids
            }
            response_data = {
                "message": "Product details retrieved successfully.",
                "status_code": 200,
                "category_id": str(category.id),
                "category_name": category.category_name,
                "sub_category_id": str(sub_category.id),
                "sub_category_name": sub_category.sub_category_name,
                "product_details": product_data
            }

            if customer_id:
                response_data["customer_id"] = str(customer_id)

            return JsonResponse(response_data, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)
@csrf_exempt
def add_product_to_cart(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            customer_id = data.get('customer_id')
            product_id = data.get('product_id')
            quantity = max(int(data.get('quantity', 1)), 1)
            if not customer_id or not product_id:
                return JsonResponse({
                    "error": "customer_id and product_id are required.",
                    "status_code": 400
                }, status=400)

            try:
                customer = CustomerRegisterDetails.objects.get(id=customer_id)
                product = ProductsDetails.objects.get(id=product_id)
                admin = PavamanAdminDetails.objects.order_by('id').first()
            
            except CustomerRegisterDetails.DoesNotExist:
                return JsonResponse({"error": "Customer not found.", "status_code": 404}, status=404)
            except ProductsDetails.DoesNotExist:
                return JsonResponse({"error": "Product not found.", "status_code": 404}, status=404)
            except PavamanAdminDetails.DoesNotExist:
                return JsonResponse({"error": "Admin not found.", "status_code": 404}, status=404)

            if not product.category or not product.sub_category:
                return JsonResponse({"error": "Product's category or subcategory is not set.", "status_code": 400}, status=400)

            if "in stock" not in product.availability.lower().strip() and "few" not in product.availability.lower().strip():
                return JsonResponse({
                    "error": "Product is out of stock.",
                    "status_code": 400
                }, status=400)
            if product.quantity < quantity:
                return JsonResponse({
                    "error": f"Only {product.quantity} quantity(s) of this product can be added or less.",
                    "status_code": 400
                }, status=400)
            current_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
            cart_item, created = CartProducts.objects.get_or_create(
                customer=customer,
                product=product,
                admin=admin,
                category=product.category,
                sub_category=product.sub_category,
                defaults={"quantity": quantity, "added_at": current_time}
            )

            if not created:
                cart_item.quantity += quantity
                cart_item.save()
            price = float(product.price)
            discount = float(product.discount or 0)
            gst = float(product.gst or 0)
            discounted_amount = round((price * discount) / 100, 2)
            final_price = price - discounted_amount
            final_price = round(final_price, 2)
            total_price = round(final_price * cart_item.quantity, 2)

            return JsonResponse({
                "message": "Product added to cart successfully.",
                "status_code": 200,
                "cart_id": cart_item.id,
                "product_id": product.id,
                "product_name": product.product_name,
                "quantity": cart_item.quantity,
                "price": round(price, 2),
                "discount": f"{discount}%",
                "gst": f"{gst}%",
                "final_price": final_price,
                "total_price": total_price,
                "cart_status": True,
                "category_id": product.category.id,
                "category_name": product.category.category_name,
                "sub_category_id": product.sub_category.id,
                "sub_category_name": product.sub_category.sub_category_name
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

@csrf_exempt
def view_product_cart(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            customer_id = data.get('customer_id')
            cart_items = CartProducts.objects.filter(customer_id=customer_id)
            if not cart_items.exists():
                return JsonResponse({"message": "Cart is empty.", "status_code": 200}, status=200)
            cart_data = []
            total_price = 0
            for item in cart_items:
                product = item.product
                price = round(float(product.price), 2)
                discount = round(float(product.discount or 0))
                gst = round(float(product.gst or 0))
                discounted_amount = round((price * discount) / 100, 2)
                final_price = round(price - discounted_amount, 2)
                item_total_price = round(final_price * item.quantity, 2)
                total_price += item_total_price
                image_path = product.product_images[0] if isinstance(product.product_images, list) and product.product_images else None
                image_url = f"{settings.AWS_S3_BUCKET_URL}/{image_path}" if image_path else ""
                cart_data.append({
                    "cart_id": item.id,
                    "product_id": product.id,
                    "product_name": product.product_name,
                    "quantity": item.quantity,
                    "price_per_item": price,
                    "discount": f"{discount}%" if discount else "0%",
                    "gst": f"{gst}%" if gst else "0%",
                    "discounted_amount": discounted_amount,
                    "final_price": final_price,
                    "total_price": item_total_price,
                    "original_quantity":product.quantity,
                    "availability":product.availability,
                    "image":image_url,
                    "category": product.category.category_name if product.category else None,
                    "sub_category": product.sub_category.sub_category_name if product.sub_category else None
                })
            return JsonResponse({
                "message": "Cart retrieved successfully.",
                "status_code": 200,
                "customer_id": customer_id,
                "total_cart_value": total_price,
                "cart_items": cart_data
            }, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)
    return JsonResponse({"error": "Invalid HTTP method. Only GET is allowed.", "status_code": 405}, status=405)
@csrf_exempt
def update_cart_quantity(request):
    if request.method == "POST":
        data = json.loads(request.body)
        customer_id = data.get("customer_id")
        product_id = data.get("product_id")
        quantity = data.get("quantity")

        try:
            cart_item = CartProducts.objects.get(customer_id=customer_id, product_id=product_id)
            cart_item.quantity = quantity
            cart_item.save()
            return JsonResponse({"status_code": 200, "message": "Quantity updated successfully"})
        except CartProducts.DoesNotExist:
            return JsonResponse({"status_code": 404, "error": "Cart item not found"})
    return JsonResponse({"status_code": 405, "error": "Invalid request method"})

@csrf_exempt
def delete_product_cart(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            customer_id = data.get("customer_id")
            product_id = data.get("product_id")

            if not customer_id:
                return JsonResponse({"error": "customer_id is required.", "status_code": 400}, status=400)

            if product_id:
                deleted_count, _ = CartProducts.objects.filter(customer_id=customer_id, product_id=product_id).delete()
                
                if deleted_count == 0:
                    return JsonResponse({"error": "Product not found in cart.", "status_code": 404}, status=404)
                if not CartProducts.objects.filter(product_id=product_id).exists():
                    product = ProductsDetails.objects.get(id=product_id)
                    product.cart_status = False
                    product.save()

                return JsonResponse({
                    "message": f"Product {product_id} removed from cart.",
                    "status_code": 200
                }, status=200)
            else:
                cart_items = CartProducts.objects.filter(customer_id=customer_id)
                if not cart_items.exists():
                    return JsonResponse({"message": "Cart is already empty.", "status_code": 200}, status=200)

                product_ids = cart_items.values_list('product_id', flat=True)
                cart_items.delete()
                ProductsDetails.objects.filter(id__in=product_ids).update(cart_status=False)

                return JsonResponse({
                    "message": "All products removed from cart.",
                    "status_code": 200
                }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except ProductsDetails.DoesNotExist:
            return JsonResponse({"error": "Product not found.", "status_code": 404}, status=404)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)
@csrf_exempt
def delete_selected_products_cart(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            customer_id = data.get("customer_id")
            product_ids = data.get("product_ids", [])

            if not customer_id or not product_ids:
                return JsonResponse({"error": "customer_id and product_ids are required.", "status_code": 400}, status=400)

            deleted_count, _ = CartProducts.objects.filter(customer_id=customer_id, product_id__in=product_ids).delete()

            if deleted_count == 0:
                return JsonResponse({"error": "Products not found in cart.", "status_code": 404}, status=404)

            ProductsDetails.objects.filter(id__in=product_ids).update(cart_status=False)

            return JsonResponse({
                "message": f"{deleted_count} product(s) removed from cart.",
                "status_code": 200
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

# PINCODE_API_URL = "https://api.postalpincode.in/pincode/"
# GEOLOCATION_API_URL = "https://nominatim.openstreetmap.org/search"
# @csrf_exempt
# def add_customer_address(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body.decode('utf-8'))
#             customer_id = data.get("customer_id")
#             first_name = data.get("first_name")
#             last_name = data.get("last_name")
#             email = data.get("email")
#             mobile_number = data.get("mobile_number")
#             alternate_mobile = data.get("alternate_mobile", "")
#             address_type = data.get("address_type", "home")
#             pincode = data.get("pincode")
#             street = data.get("street")
#             landmark = data.get("landmark", "")

#             if not all([customer_id, first_name, last_name, email, mobile_number, pincode, street]):
#                 return JsonResponse({"error": "All required fields must be provided.", "status_code": 400}, status=400)

#             try:
#                 customer = CustomerRegisterDetails.objects.get(id=customer_id)
#             except CustomerRegisterDetails.DoesNotExist:
#                 return JsonResponse({"error": "Customer does not exist.", "status_code": 400}, status=400)

#             postoffice = mandal = village = district = state = country = ""
#             latitude = longitude = None

#             response = requests.get(f"{PINCODE_API_URL}{pincode}")
#             if response.status_code == 200:
#                 pincode_data = response.json()
#                 if pincode_data and pincode_data[0].get("Status") == "Success":
#                     post_office_data = pincode_data[0].get("PostOffice", [])[0] if pincode_data[0].get("PostOffice") else {}

#                     postoffice = post_office_data.get("BranchType", "")
#                     village = post_office_data.get("Name", "")
#                     mandal = post_office_data.get("Block", "")
#                     district = post_office_data.get("District", "")
#                     state = post_office_data.get("State", "")
#                     country = post_office_data.get("Country", "India")

#             geo_params = {
#                 "q": f"{pincode},{district},{state},{country}",
#                 "format": "json",
#                 "limit": 1
#             }

#             geo_headers = {
#                 "User-Agent": "MyDjangoApp/1.0 saralkumar.kapilit@gmail.com"
#             }

#             geo_response = requests.get(GEOLOCATION_API_URL, params=geo_params, headers=geo_headers)

#             if geo_response.status_code == 200:
#                 geo_data = geo_response.json()
#                 if geo_data:
#                     latitude = geo_data[0].get("lat")
#                     longitude = geo_data[0].get("lon")
#                 else:
#                     return JsonResponse({"error": "Failed to fetch latitude and longitude for the provided address.", "status_code": 400}, status=400)
#             else:
#                 return JsonResponse({"error": "Geolocation API request failed.", "status_code": geo_response.status_code}, status=geo_response.status_code)

#             customer_address = CustomerAddress.objects.create(
#                 customer=customer,
#                 first_name=first_name,
#                 last_name=last_name,
#                 email=email,
#                 mobile_number=mobile_number,
#                 alternate_mobile=alternate_mobile,
#                 address_type=address_type,
#                 pincode=pincode,
#                 street=street,
#                 landmark=landmark,
#                 village=village,
#                 mandal=mandal,
#                 postoffice=postoffice,
#                 district=district,
#                 state=state,
#                 country=country,
#                 latitude=latitude,
#                 longitude=longitude
#             )

#             return JsonResponse({
#                 "message": "Customer address added successfully.",
#                 "status_code": 200,
#                 "address_id": customer_address.id,
#                 "pincode_details": {
#                     "postoffice": postoffice,
#                     "village": village,
#                     "mandal": mandal,
#                     "district": district,
#                     "state": state,
#                     "country": country,
#                     "landmark": landmark,
#                     "latitude": latitude,
#                     "longitude": longitude
#                 }
#             }, status=200)

#         except json.JSONDecodeError:
#             return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
#         except Exception as e:
#             return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

#     return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import CustomerRegisterDetails, CustomerAddress
import json
import requests

PINCODE_API_URL = "https://api.postalpincode.in/pincode/"
GEOLOCATION_API_URL = "https://nominatim.openstreetmap.org/search"

@csrf_exempt
def add_customer_address(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        customer_id = data.get("customer_id")
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        email = data.get("email")
        mobile_number = data.get("mobile_number")
        alternate_mobile = data.get("alternate_mobile", "")
        address_type = data.get("address_type", "home")
        pincode = data.get("pincode")
        street = data.get("street")
        landmark = data.get("landmark", "")

        if not all([customer_id, first_name, last_name, email, mobile_number, pincode, street]):
            return JsonResponse({"error": "All required fields must be provided.", "status_code": 400}, status=400)

        try:
            customer = CustomerRegisterDetails.objects.get(id=customer_id)
        except CustomerRegisterDetails.DoesNotExist:
            return JsonResponse({"error": "Customer does not exist.", "status_code": 400}, status=400)

        # Initialize location fields
        postoffice = mandal = village = district = state = country = ""
        latitude = longitude = None

        # ✅ Corrected PINCODE API try block
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            response = requests.get(f"{PINCODE_API_URL}{pincode}", headers=headers, timeout=5)
            print(f"[PINCODE API RAW RESPONSE] {response.status_code} {response.text}")

            if response.status_code == 200:
                pincode_data = response.json()
                if pincode_data[0]["Status"] == "Success":
                    post_offices = pincode_data[0].get("PostOffice", [])
                    if post_offices:
                        office = post_offices[0]
                        postoffice = office.get("BranchType", "")
                        village = office.get("Name", "")
                        mandal = office.get("Block", "")
                        district = office.get("District", "")
                        state = office.get("State", "")
                        country = office.get("Country", "India")
        except Exception as e:
            print(f"[PINCODE API ERROR] {str(e)}")

        # Geolocation API call
        try:
            geo_query = ",".join(filter(None, [pincode, district, state, country]))
            geo_params = {
                "q": geo_query,
                "format": "json",
                "limit": 1
            }
            geo_headers = {
                "User-Agent": "MyDjangoApp/1.0 saralkumar.kapilit@gmail.com"
            }
            geo_response = requests.get(GEOLOCATION_API_URL, params=geo_params, headers=geo_headers, timeout=5)
            if geo_response.status_code == 200:
                geo_data = geo_response.json()
                if geo_data:
                    latitude = geo_data[0].get("lat")
                    longitude = geo_data[0].get("lon")
        except Exception as e:
            print(f"[GEOLOCATION ERROR] {str(e)}")

        # Save to DB
        customer_address = CustomerAddress.objects.create(
            customer=customer,
            first_name=first_name,
            last_name=last_name,
            email=email,
            mobile_number=mobile_number,
            alternate_mobile=alternate_mobile,
            address_type=address_type,
            pincode=pincode,
            street=street,
            landmark=landmark,
            village=village,
            mandal=mandal,
            postoffice=postoffice,
            district=district,
            state=state,
            country=country,
            latitude=latitude,
            longitude=longitude
        )

        return JsonResponse({
            "message": "Customer address added successfully.",
            "status_code": 200,
            "address_id": customer_address.id,
            "pincode_details": {
                "postoffice": postoffice,
                "village": village,
                "mandal": mandal,
                "district": district,
                "state": state,
                "country": country,
                "landmark": landmark,
                "latitude": latitude,
                "longitude": longitude
            }
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

@csrf_exempt
def view_customer_address(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            customer_id = data.get("customer_id")

            if not customer_id:
                return JsonResponse({"error": "Customer ID is required.", "status_code": 400}, status=400)
            addresses = CustomerAddress.objects.filter(customer_id=customer_id)

            # if not addresses.exists():
            #     return JsonResponse({"error": "No address found for the given customer ID.", "status_code": 404}, status=404)
            
            if not addresses.exists():
                return JsonResponse({
                    "error": "No addresses found for this customer.",
                    "status_code": 200,
                    "addresses": []
                }, status=200)

            address_list = []
            for address in addresses:
                address_list.append({
                    "address_id": address.id,
                    "first_name": address.first_name,
                    "last_name": address.last_name,
                    "email": address.email,
                    "mobile_number": address.mobile_number,
                    "alternate_mobile": address.alternate_mobile,
                    "address_type": address.address_type,
                    "pincode": address.pincode,
                    "street": address.street,
                    "landmark": address.landmark,
                    "village": address.village,
                    "mandal": address.mandal,
                    "postoffice": address.postoffice,
                    "district": address.district,
                    "state": address.state,
                    "country": address.country,
                    "latitude": address.latitude,
                    "longitude": address.longitude
                })

            return JsonResponse({
                "message": "Customer addresses retrieved successfully.",
                "status_code": 200,
                "addresses": address_list
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)


# GEOLOCATION_API_URL = "https://nominatim.openstreetmap.org/search"

# @csrf_exempt
# def edit_customer_address(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body.decode('utf-8'))
#             address_id = data.get("address_id")
#             customer_id = data.get("customer_id")
#             first_name = data.get("first_name")
#             last_name = data.get("last_name")
#             email = data.get("email")
#             mobile_number = data.get("mobile_number")
#             alternate_mobile = data.get("alternate_mobile", "")
#             address_type = data.get("address_type", "home")
#             pincode = data.get("pincode")
#             street = data.get("street")
#             landmark = data.get("landmark", "")
#             latitude = data.get("latitude")
#             longitude = data.get("longitude")

#             if not all([address_id, customer_id, first_name, last_name, email, mobile_number, pincode, street]):
#                 return JsonResponse({"error": "All required fields must be provided.", "status_code": 400}, status=400)

#             try:
#                 customer_address = CustomerAddress.objects.get(id=address_id, customer_id=customer_id)
#             except CustomerAddress.DoesNotExist:
#                 return JsonResponse({"error": "Address not found.", "status_code": 404}, status=404)
#             try:
#                 response = requests.get(f"https://api.postalpincode.in/pincode/{pincode}")
#                 response_data = response.json()
#                 if response_data[0]['Status'] == 'Success':
#                     post_office_data = response_data[0]['PostOffice'][0]
#                     customer_address.village = post_office_data.get('Name', '')
#                     customer_address.mandal = post_office_data.get('Block', '')
#                     customer_address.postoffice = post_office_data.get('Name', '')
#                     customer_address.district = post_office_data.get('District', '')
#                     customer_address.state = post_office_data.get('State', '')
#                     customer_address.country = post_office_data.get('Country', '')

#                     if not latitude or not longitude:
#                         geo_params = {
#                             "q": f"{pincode},{customer_address.district},{customer_address.state},{customer_address.country}",
#                             "format": "json",
#                             "limit": 1
#                         }
#                         geo_headers = {
#                             "User-Agent": "MyDjangoApp/1.0 saralkumar.kapilit@gmail.com"
#                         }
#                         geo_response = requests.get(GEOLOCATION_API_URL, params=geo_params, headers=geo_headers)

#                         if geo_response.status_code == 200:
#                             geo_data = geo_response.json()
#                             if geo_data:
#                                 latitude = geo_data[0].get("lat", '')
#                                 longitude = geo_data[0].get("lon", '')
#                             else:
#                                 return JsonResponse({"error": "Failed to fetch latitude and longitude for the provided address.", "status_code": 400}, status=400)
#                         else:
#                             return JsonResponse({"error": "Geolocation API request failed.", "status_code": geo_response.status_code}, status=geo_response.status_code)
#             except Exception as e:
#                 return JsonResponse({"error": f"Failed to fetch address details: {str(e)}", "status_code": 500}, status=500)

#             customer_address.first_name = first_name
#             customer_address.last_name = last_name
#             customer_address.email = email
#             customer_address.mobile_number = mobile_number
#             customer_address.alternate_mobile = alternate_mobile
#             customer_address.address_type = address_type
#             customer_address.pincode = pincode
#             customer_address.street = street
#             customer_address.landmark = landmark
#             customer_address.latitude = latitude
#             customer_address.longitude = longitude

#             customer_address.save(update_fields=[
#                 "first_name", "last_name", "email", "mobile_number",
#                 "alternate_mobile", "address_type", "pincode", "street",
#                 "landmark", "village", "mandal", "postoffice", 
#                 "district", "state", "country", "latitude", "longitude"
#             ])

#             return JsonResponse({
#                 "message": "Customer address updated successfully.",
#                 "status_code": 200,
#                 "address_id": customer_address.id,
#                 "pincode_details": {
#                     "postoffice": customer_address.postoffice,
#                     "village": customer_address.village,
#                     "mandal": customer_address.mandal,
#                     "district": customer_address.district,
#                     "state": customer_address.state,
#                     "country": customer_address.country,
#                     "landmark": customer_address.landmark,
#                     "latitude": customer_address.latitude,
#                     "longitude": customer_address.longitude
#                 }
#             }, status=200)

#         except json.JSONDecodeError:
#             return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
#         except Exception as e:
#             return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

#     return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)
GEOLOCATION_API_URL = "https://nominatim.openstreetmap.org/search"

@csrf_exempt
def edit_customer_address(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        address_id = data.get("address_id")
        customer_id = data.get("customer_id")
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        email = data.get("email")
        mobile_number = data.get("mobile_number")
        alternate_mobile = data.get("alternate_mobile", "")
        address_type = data.get("address_type", "home")
        pincode = data.get("pincode")
        street = data.get("street")
        landmark = data.get("landmark", "")
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if not all([address_id, customer_id, first_name, last_name, email, mobile_number, pincode, street]):
            return JsonResponse({"error": "All required fields must be provided.", "status_code": 400}, status=400)

        try:
            customer_address = CustomerAddress.objects.get(id=address_id, customer_id=customer_id)
        except CustomerAddress.DoesNotExist:
            return JsonResponse({"error": "Address not found.", "status_code": 404}, status=404)

        # ------------------- PINCODE API -------------------
        postoffice = mandal = village = district = state = country = ""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            response = requests.get(f"{PINCODE_API_URL}{pincode}", headers=headers, timeout=5)
            print(f"[PINCODE API RAW RESPONSE] {response.status_code} {response.text}")
            
            # response = requests.get(f"https://api.postalpincode.in/pincode/{pincode}", timeout=5)
            if response.status_code == 200:
                response_data = response.json()
                post_offices = response_data[0].get("PostOffice", [])
                if post_offices:
                    office = post_offices[0]
                    village = office.get("Name", "")
                    mandal = office.get("Block", "")
                    postoffice = office.get("BranchType", "")
                    district = office.get("District", "")
                    state = office.get("State", "")
                    country = office.get("Country", "India")
        except Exception as e:
            print(f"[PINCODE API ERROR] {str(e)}")

        # ------------------- GEOLOCATION API -------------------
        if not latitude or not longitude:
            try:
                query_parts = [pincode, district, state, country]
                query_string = ','.join([q for q in query_parts if q]) or pincode
                geo_params = {
                    "q": query_string,
                    "format": "json",
                    "limit": 1
                }
                geo_headers = {
                    "User-Agent": "MyDjangoApp/1.0 saralkumar.kapilit@gmail.com"
                }
                geo_response = requests.get(GEOLOCATION_API_URL, params=geo_params, headers=geo_headers, timeout=5)
                if geo_response.status_code == 200:
                    geo_data = geo_response.json()
                    if geo_data:
                        latitude = geo_data[0].get("lat")
                        longitude = geo_data[0].get("lon")
            except Exception as e:
                print(f"[GEOLOCATION ERROR] {str(e)}")

        # ------------------- UPDATE FIELDS -------------------
        customer_address.first_name = first_name
        customer_address.last_name = last_name
        customer_address.email = email
        customer_address.mobile_number = mobile_number
        customer_address.alternate_mobile = alternate_mobile
        customer_address.address_type = address_type
        customer_address.pincode = pincode
        customer_address.street = street
        customer_address.landmark = landmark
        customer_address.village = village
        customer_address.mandal = mandal
        customer_address.postoffice = postoffice
        customer_address.district = district
        customer_address.state = state
        customer_address.country = country
        customer_address.latitude = latitude
        customer_address.longitude = longitude

        customer_address.save(update_fields=[
            "first_name", "last_name", "email", "mobile_number",
            "alternate_mobile", "address_type", "pincode", "street",
            "landmark", "village", "mandal", "postoffice",
            "district", "state", "country", "latitude", "longitude"
        ])

        return JsonResponse({
            "message": "Customer address updated successfully.",
            "status_code": 200,
            "address_id": customer_address.id,
            "pincode_details": {
                "postoffice": postoffice,
                "village": village,
                "mandal": mandal,
                "district": district,
                "state": state,
                "country": country,
                "landmark": landmark,
                "latitude": latitude,
                "longitude": longitude
            }
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

@csrf_exempt
def delete_customer_address(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            address_id = data.get("address_id")
            customer_id = data.get("customer_id")

            if not address_id or not customer_id:
                return JsonResponse({"error": "Address ID and Customer ID are required.", "status_code": 400}, status=400)

            try:
                customer_address = CustomerAddress.objects.get(id=address_id, customer_id=customer_id)
                customer_address.delete()
                return JsonResponse({"message": "Customer address deleted successfully.", "status_code": 200}, status=200)
            except CustomerAddress.DoesNotExist:
                return JsonResponse({"error": "Address not found.", "status_code": 404}, status=404)
        
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)
@csrf_exempt
def order_multiple_products(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            customer_id = data.get('customer_id')
            products = data.get('products', [])
            from_cart = data.get('from_cart', False)

            if not customer_id or not products:
                return JsonResponse({"error": "customer_id and products are required.", "status_code": 400}, status=400)

            try:
                customer = CustomerRegisterDetails.objects.get(id=customer_id)
                admin = PavamanAdminDetails.objects.order_by('id').first()

            except CustomerRegisterDetails.DoesNotExist:
                return JsonResponse({"error": "Customer not found.", "status_code": 404}, status=404)
            except PavamanAdminDetails.DoesNotExist:
                return JsonResponse({"error": "Admin not found.", "status_code": 404}, status=404)

            successful_orders = []

            for item in products:
                product_id = item.get('product_id')
                quantity = max(int(item.get('quantity', 1)), 1)

                try:
                    product = ProductsDetails.objects.get(id=product_id)
                except ProductsDetails.DoesNotExist:
                    return JsonResponse({"error": "Product not found.", "status_code": 404}, status=404)

                if not product.category or not product.sub_category:
                    return JsonResponse({"error": "Product's category or subcategory is not set.", "status_code": 400}, status=400)

                if "in stock" not in product.availability.lower().strip() and "few" not in product.availability.lower().strip():
                    return JsonResponse({"error": "Product is out of stock.", "status_code": 400}, status=400)
                
                if product.quantity < quantity:
                    return JsonResponse({
                        "error": f"Only {product.quantity} quantity(s) of this product can be added or less.",
                        "status_code": 400
                    }, status=400)
                price = float(product.price)
                discount = float(product.discount or 0)
                gst = float(product.gst or 0)
                discounted_amount = (price * discount) / 100
                final_price = price - discounted_amount
                total_price = round(final_price * quantity, 2)
                current_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
                order = OrderProducts.objects.create(
                    customer=customer,
                    product=product,
                    category=product.category,
                    sub_category=product.sub_category,
                    quantity=quantity,
                    price=price,
                    final_price=total_price,
                    order_status="Pending",
                    created_at=current_time,
                    admin=admin
                )
                if not from_cart:
                    cart_item, created = CartProducts.objects.get_or_create(
                        customer=customer,
                        product=product,
                        admin=admin,
                        category=product.category,
                        sub_category=product.sub_category,
                        defaults={"quantity": quantity, "added_at": current_time}
                    )

                    if not created:
                        cart_item.quantity += quantity
                        cart_item.save()
                image_path = product.product_images[0] if isinstance(product.product_images, list) and product.product_images else None
                image_url = f"{settings.AWS_S3_BUCKET_URL}/{image_path}" if image_path else ""
                successful_orders.append({
                    "order_id": order.id,
                    "product_id": product_id,
                    "product_name": product.product_name,
                    "product_images": image_url,
                    "number_of_quantities": quantity,
                    "product_price": price,
                    "discount_price": round(discounted_amount, 2),
                    "total_price": total_price,
                    "discount":f"{int(product.discount)}%" if product.discount else "0%",
                    "gst": f"{int(gst)}%" if gst else "0%"
                })

            return JsonResponse({
                "message": "Order Created successfully!",
                "orders": successful_orders,
                "status_code": 201
            }, status=201)

        except Exception as e:
            return JsonResponse({"error": str(e), "status_code": 500}, status=500)
    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)
@csrf_exempt
def multiple_order_summary(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            order_ids = data.get('order_ids')
            product_ids = data.get('product_ids')
            customer_id = data.get('customer_id')
            address_id = data.get('address_id')

            if not all([order_ids, product_ids, customer_id, address_id]):
                return JsonResponse({"error": "order_ids, product_ids, customer_id, and address_id are required.", "status_code": 400}, status=400)

            if len(order_ids) != len(product_ids):
                return JsonResponse({"error": "Mismatch between orders and products count.", "status_code": 400}, status=400)

            try:
                customer = CustomerRegisterDetails.objects.get(id=customer_id)
                address = CustomerAddress.objects.get(id=address_id, customer_id=customer_id)

                CustomerAddress.objects.filter(customer_id=customer_id).update(select_address=False)
                address.select_address = True
                address.save()

            except CustomerRegisterDetails.DoesNotExist:
                return JsonResponse({"error": "Customer not found.", "status_code": 404}, status=404)
            except CustomerAddress.DoesNotExist:
                return JsonResponse({"error": "Address not found.", "status_code": 404}, status=404)

            order_list = []
            total_delivery_charge = 0

            for order_id, product_id in zip(order_ids, product_ids):
                try:
                    order = OrderProducts.objects.get(id=order_id, product_id=product_id, customer_id=customer_id)
                    product = ProductsDetails.objects.get(id=product_id)

                    price = float(product.price)
                    discount = float(product.discount or 0)
                    discounted_amount = float((price * discount) / 100)
                    final_price =round((price - discounted_amount),2)
                    image_path = product.product_images[0] if isinstance(product.product_images, list) and product.product_images else None
                    image_url = f"{settings.AWS_S3_BUCKET_URL}/{image_path}" if image_path else ""
                    
                    unit = None
                    kg_value = 0
                    weight_str = product.specifications.get('weight', '').lower() if isinstance(product.specifications, dict) else ''
                    print("weight_str", weight_str)
                    match = re.match(r"([\d.]+)\s*(gm|g|gram|kg|kilogram|kilo)", weight_str)
                    if match:
                        value = float(match.group(1))
                        unit = match.group(2)
                        if unit in ['gm', 'g', 'gram']:
                            kg_value = value / 1000
                        elif unit in ['kg', 'kilogram', 'kilo']:
                            kg_value = value
                        else:
                            kg_value = 0
                    else:
                        kg_value = 0

                    quantity = order.quantity
                    total_weight = kg_value * quantity
                    print("total_weight", total_weight)
                    normalized_state = address.state.lower().strip()
                    if normalized_state in ['andhra pradesh', 'telangana', 'hyderabad']:
                        state_charge = 0
                    else:
                        state_charge = 0

                    unit_weight = kg_value
                    base_delivery_charge = 0

                    if kg_value is not None:
                        unit_weight = kg_value
                        base_delivery_charge = 0
                        for _ in range(quantity):
                            if unit_weight <= 0:
                                unit_charge = 0.00
                            elif 0 < unit_weight <= 0:
                                unit_charge = 0.00
                            else:
                                extra_weight = unit_weight - 20
                                extra_blocks = math.ceil(extra_weight / 10)
                                unit_charge = 150.00 + (extra_blocks * 100)
                            base_delivery_charge += unit_charge
                    else:
                        base_delivery_charge = 0

                    delivery_charge = base_delivery_charge + state_charge
                    order.delivery_charge = delivery_charge
                    order.save()
                    total_delivery_charge += delivery_charge
                    print(f"{product.product_name} - State: {normalized_state}, Base: {base_delivery_charge}, State Charge: {state_charge}, Delivery: {delivery_charge}")

                    order_list.append({
                        "order_id": order.id,
                        "order_name": f"Order {order.id}",
                        "customer_name": f"{address.first_name} {address.last_name}",
                        "customer_email": address.email,
                        "customer_mobile": address.mobile_number,
                        "alternate_customer_mobile": address.mobile_number,
                        "product_name": product.product_name,
                        "product_id": product_id,
                        "product_price": order.price,
                        "quantity": order.quantity,
                        "discount": f"{int(discount)}%" if discount else "0%",
                        "gst": f"{int(product.gst or 0)}%",
                        "final_price": round(final_price, 2),
                        "total_price": order.final_price,
                        "delivery_charges": delivery_charge,
                        "order_status": order.order_status,
                        "order_date": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "product_images": image_url,
                        "weight": f"{round(total_weight, 2)} {unit}" if total_weight is not None else "N/A"

                    })

                except OrderProducts.DoesNotExist:
                    product_name = ProductsDetails.objects.filter(id=product_id).values_list('product_name', flat=True).first() or f"Product {product_id}"
                    return JsonResponse({"error": f"Order {order_id} with product '{product_name}' not found.", "status_code": 404}, status=404)
                except ProductsDetails.DoesNotExist:
                    return JsonResponse({"error": f"Product with ID {product_id} not found.", "status_code": 404}, status=404)

            shipping_address = {
                "address_id": address.id,
                "customer_name": f"{address.first_name} {address.last_name}",
                "select_address": address.select_address,
                "address_type": address.address_type,
                "street": address.street,
                "landmark": address.landmark,
                "village": address.village,
                "mandal": address.mandal,
                "postoffice": address.postoffice,
                "district": address.district,
                "state": address.state,
                "pincode": address.pincode
            }

            return JsonResponse({
                "message": "Multiple order summaries fetched successfully!",
                "orders": order_list,
                "shipping_address": shipping_address,
                "total_delivery_charge": total_delivery_charge,
                "status_code": 200
            }, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e), "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

# @csrf_exempt
# def create_razorpay_order(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body.decode('utf-8'))
#             customer_id = data.get('customer_id')
#             order_products = data.get('order_products', [])

#             if not customer_id or not order_products:
#                 return JsonResponse({"error": "customer_id and order_products are required.", "status_code": 400}, status=400)

#             try:
#                 customer = CustomerRegisterDetails.objects.get(id=customer_id)
#             except CustomerRegisterDetails.DoesNotExist:
#                 return JsonResponse({"error": "Customer not found.", "status_code": 404}, status=404)
           
#             try:
#                 address = CustomerAddress.objects.get(customer_id=customer_id, select_address=True)
#                 address_id = address.id
#             except CustomerAddress.DoesNotExist:
#                 return JsonResponse({
#                     "error": "No selected address found for the customer. Please select an address first.",
#                     "status_code": 404
#                 }, status=404)

#             total_amount = Decimal('0.0')
#             total_delivery_charge = Decimal('0.0')
#             grand_total = Decimal('0.0')

#             valid_orders = []
#             order_ids = [] 
#             product_ids = [] 
        
#             for item in order_products:
#                 order_id = item.get('order_id')
#                 product_id = item.get('product_id')

#                 try:
#                     order = OrderProducts.objects.get(id=order_id, customer=customer, product_id=product_id)
#                     total_amount += Decimal(str(order.final_price))
#                     total_delivery_charge += Decimal(str(order.delivery_charge))
#                     grand_total=total_amount + total_delivery_charge
#                     order_ids.append(str(order.id))  
#                     product_ids.append(str(order.product.id)) 
                    
#                     valid_orders.append({
#                         "order_id": order.id,
#                         "product_id": order.product.id,
#                         "product_name": order.product.product_name,
#                         "category": order.category,
#                         "sub_category": order.sub_category,
#                         "quantity": order.quantity,
#                         "amount": float(order.price),
#                         "total_price": order.final_price,
#                         "total_delivery_charge":total_delivery_charge,
#                         "order_status": order.order_status
#                     })
#                 except OrderProducts.DoesNotExist:
#                     return JsonResponse({"error": f"Order ID {order_id} with Product ID {product_id} not found or does not belong to the customer.", "status_code": 404}, status=404)
#             if total_amount <= 0:
#                 return JsonResponse({"error": "Total amount must be greater than zero.", "status_code": 400}, status=400)
#             product_order_id = f"OD{datetime.now().strftime('%Y%m%d%H%M%S')}{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
#             receipt_id = product_order_id
#             razorpay_order = razorpay_client.order.create({
#                 "amount": int(grand_total * 100),
#                 "currency": "INR",
#                 "receipt": receipt_id,
#                 "payment_capture": 1,
#                 "notes": {  
#                     "order_ids": ",".join(order_ids), 
#                     "product_ids": ",".join(product_ids),  
#                     "customer_id": str(customer.id),
#                     "address_id": str(address_id) 
#                 }
#             })          
#             callback_url = "settings.RAZORPAY_CALLBACK_URL"
#             return JsonResponse({
#                 "message": "Razorpay Order Created Successfully!",
#                 "razorpay_key": settings.RAZORPAY_KEY_ID,
#                 "razorpay_order_id": razorpay_order["id"],
#                 "callback_url": callback_url,
#                 "customer_id": customer.id,
#                 "address_id":address_id,
#                 "total_amount": total_amount,
#                 "orders": valid_orders,
#                 "product_order_id":receipt_id,
#                 "status_code": 201
#             }, status=201)
#         except Exception as e:
#             return JsonResponse({"error": str(e), "status_code": 500}, status=500)
#     return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)
# @csrf_exempt
# def razorpay_callback(request):
#     if request.method != "POST":
#         return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)
#     try:
#         data = json.loads(request.body.decode("utf-8"))
#         required_fields = ["razorpay_payment_id", "razorpay_order_id", "razorpay_signature", "customer_id", "order_products","address_id","product_order_id"]
#         missing_fields = [field for field in required_fields if field not in data]
#         if missing_fields:
#             return JsonResponse({"error": f"Missing required fields: {', '.join(missing_fields)}", "status_code": 400}, status=400)
#         razorpay_payment_id = data["razorpay_payment_id"]
#         razorpay_order_id = data["razorpay_order_id"]
#         razorpay_signature = data["razorpay_signature"]
#         customer_id = data["customer_id"]
#         order_products = data["order_products"]
#         address_id =data["address_id"]
#         product_order_id = data["product_order_id"]
#         if not isinstance(order_products, list) or not order_products:
#             return JsonResponse({"error": "Invalid or missing order_products. It must be a list of order-product mappings.", "status_code": 400}, status=400)
#         client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
#         params = {
#             "razorpay_order_id": razorpay_order_id,
#             "razorpay_payment_id": razorpay_payment_id,
#             "razorpay_signature": razorpay_signature,
#         }
#         try:
#             client.utility.verify_payment_signature(params)
#             payment_details = client.payment.fetch(razorpay_payment_id)
#             payment_status = payment_details.get("status", "failed")
#             payment_mode = payment_details.get("method", "unknown")
#             transaction_id = payment_details.get("id", razorpay_payment_id)
#             order_list = []
#             for item in order_products:
#                 order_id = item.get("order_id")
#                 product_id = item.get("product_id")
#                 if not order_id or not product_id:
#                     return JsonResponse({"error": "Each item in order_products must contain order_id and product_id.", "status_code": 400}, status=400)
#                 order = OrderProducts.objects.filter(id=order_id, product_id=product_id, customer_id=customer_id).first()
#                 if order:
#                     order_list.append(order)
#             if not order_list:
#                 return JsonResponse({"error": "No matching orders found for this payment.", "status_code": 404}, status=404)
#             if payment_status == "captured":
#                 order_product_ids = []
#                 category_ids = []
#                 sub_category_ids = []
#                 product_ids = []
#                 total_quantity = 0
#                 total_amount = Decimal("0.00")
#                 total_delivery_charge = Decimal("0.00")
#                 grand_total=0
#                 first_order = None
#                 for order in order_list:
#                     order.order_status = "Paid"
#                     order.save(update_fields=["order_status"])
#                     product = order.product
#                     if product.quantity >= order.quantity:
#                         product.quantity -= order.quantity
#                     else:
#                         product.quantity = 0  
#                     if product.quantity<= 10 and product.quantity!=0 and product.quantity<0:
#                        product.availability= "Very Few Products Left"
#                     elif product.quantity== 0:
#                        product.availability= "Out of Stock"
#                     else:
#                        product.availability="In Stock"
#                     product.save(update_fields=["quantity","availability"])
#                     if not first_order:
#                         first_order = order
#                     order_product_ids.append(order.id)
#                     category_ids.append(order.product.category.id)
#                     sub_category_ids.append(order.product.sub_category.id)
#                     product_ids.append(order.product.id)
#                     total_quantity += order.quantity
#                     total_amount += Decimal(str(order.final_price))
#                     total_delivery_charge += Decimal(str(order.delivery_charge))
#                     grand_total =total_amount+ total_delivery_charge
#                 try:
#                     customer_address = CustomerAddress.objects.get(id=address_id, customer_id=customer_id)
#                 except CustomerAddress.DoesNotExist:
#                     return JsonResponse({
#                         "error": "Invalid address_id. No such address found for this customer.",
#                         "status_code": 404
#                     }, status=404)
#                 if first_order:
#                     today = timezone.now().date()
#                     date_str = today.strftime("%d%m%Y")
#                     prefix = "PVM"
#                     base_invoice = f"{prefix}{date_str}"
#                     latest_invoice = PaymentDetails.objects.filter(created_at__date=today).order_by('-id').first()
#                     if latest_invoice and latest_invoice.invoice_number:
#                        last_serial = int(latest_invoice.invoice_number[-4:])
#                     else:
#                         last_serial = 0
#                     new_serial = last_serial + 1
#                     new_invoice_number = f"{base_invoice}{str(new_serial).zfill(4)}"
#                     PaymentDetails.objects.create(
#                         admin=first_order.product.admin,
#                         customer=first_order.customer,
#                         customer_address=customer_address,
#                         category_ids=category_ids,
#                         sub_category_ids=sub_category_ids,
#                         product_ids=product_ids,
#                         order_product_ids=order_product_ids,
#                         razorpay_order_id=razorpay_order_id,
#                         razorpay_payment_id=razorpay_payment_id,
#                         razorpay_signature=razorpay_signature,
#                         amount=total_amount,
#                         total_amount=grand_total,
#                         payment_type="online",
#                         payment_mode=payment_mode,
#                         transaction_id=transaction_id,
#                         quantity=total_quantity,
#                         product_order_id= product_order_id, 
#                         invoice_number=new_invoice_number,
#                         Delivery_status="Pending"
#                     )
#                     current_paid_product_ids = [order.product_id for order in order_list]
#                     CartProducts.objects.filter(
#                         product_id__in=current_paid_product_ids,
#                         customer_id=customer_id
#                     ).delete()
#                     product_list = []
#                     for order in order_list:
#                         try:
#                             product_details = ProductsDetails.objects.get(id=order.product.id)
#                             image_path = product_details.product_images[0] if isinstance(product_details.product_images, list) and product_details.product_images else None
#                             image_url = f"{settings.AWS_S3_BUCKET_URL}/{image_path}" if image_path else ""
#                             product_name = product_details.product_name
#                         except ProductsDetails.DoesNotExist:
#                             image_url = ""
#                             product_name = "Product Not Found"
#                         product_list.append({
#                             "image_url": image_url,
#                             "name": product_name,
#                             "quantity": order.quantity,
#                             "price": order.final_price,
#                         })
#                     send_html_order_confirmation(
#                         to_email=first_order.customer.email,
#                         customer_name=f"{first_order.customer.first_name} {first_order.customer.last_name}",
#                         product_list=product_list,
#                         total_amount=grand_total,
#                         order_id=product_order_id,
#                         transaction_id=transaction_id,
#                     )                    
#                     mobile_number = first_order.customer.mobile_no
#                     order_id = product_order_id
#                     amount = grand_total

#                     try:
#                         send_order_confirmation_sms([mobile_number], order_id, amount)
#                     except Exception as e:
#                         print(f"SMS send failed: {str(e)}")
#                     return JsonResponse({
#                         "message": "Payment successful for all orders!",
#                         "razorpay_order_id": razorpay_order_id,
#                         "customer_id": customer_id,
#                         "total_orders_paid": len(order_product_ids),
#                         "payment_mode": payment_mode,
#                         "transaction_id": transaction_id,
#                         "amount": total_amount,
#                         "total_amount":grand_total,
#                         "total_delivery_charge":total_delivery_charge,
#                         "order_product_ids": order_product_ids,  
#                         "category_ids": category_ids,  
#                         "sub_category_ids": sub_category_ids, 
#                         "product_order_id": product_order_id,
#                         "invoice_number": new_invoice_number,
#                         "product_ids": product_ids,
#                         "status_code": 200
#                     }, status=200)

#             else:
#                 OrderProducts.objects.filter(id__in=[order.id for order in order_list]).update(order_status="Failed")
#                 return JsonResponse({"error": "Payment failed.", "razorpay_order_id": razorpay_order_id, "status_code": 400}, status=400)

#         except razorpay.errors.SignatureVerificationError:
#             OrderProducts.objects.filter(id__in=[order.id for order in order_list]).update(order_status="Failed")
#             return JsonResponse({"error": "Signature verification failed.", "razorpay_order_id": razorpay_order_id, "status_code": 400}, status=400)
#     except Exception as e:
#         return JsonResponse({"error": str(e), "status_code": 500}, status=500)
    


razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
@csrf_exempt
def create_razorpay_order(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        customer_id = data.get('customer_id')
        order_products = data.get('order_products', [])

        if not customer_id or not order_products:
            return JsonResponse({"error": "customer_id and order_products are required.", "status_code": 400}, status=400)

        try:
            customer = CustomerRegisterDetails.objects.get(id=customer_id)
        except CustomerRegisterDetails.DoesNotExist:
            return JsonResponse({"error": "Customer not found.", "status_code": 404}, status=404)

        try:
            address = CustomerAddress.objects.get(customer_id=customer_id, select_address=True)
        except CustomerAddress.DoesNotExist:
            return JsonResponse({
                "error": "No selected address found for the customer. Please select an address first.",
                "status_code": 404
            }, status=404)

        # Step 1: Validate order items and collect orders
        order_list = []
        for item in order_products:
            order_id = item.get("order_id")
            product_id = item.get("product_id")

            if not order_id or not product_id:
                return JsonResponse({"error": "Each item in order_products must contain order_id and product_id.", "status_code": 400}, status=400)

            order = OrderProducts.objects.filter(id=order_id, product_id=product_id, customer_id=customer_id).first()
            if order:
                order_list.append(order)

        if not order_list:
            return JsonResponse({"error": "No matching orders found for this payment.", "status_code": 404}, status=404)

        # Step 2: Aggregate order details
        order_product_ids = []
        category_ids = []
        sub_category_ids = []
        product_ids = []
        total_quantity = 0
        total_amount = Decimal("0.00")
        total_delivery_charge = Decimal("0.00")
        first_order = None

        for order in order_list:
            product = order.product
            if not first_order:
                first_order = order

            order_product_ids.append(order.id)
            category_ids.append(product.category.id)
            sub_category_ids.append(product.sub_category.id)
            product_ids.append(product.id)

            total_quantity += order.quantity
            total_amount += Decimal(str(order.final_price))
            total_delivery_charge += Decimal(str(order.delivery_charge))
        print(total_quantity, "total_quantity")
        grand_total = total_amount + total_delivery_charge

        if grand_total <= 0:
            return JsonResponse({"error": "Total amount must be greater than zero.", "status_code": 400}, status=400)

        # Step 3: Create Razorpay order
        product_order_id = f"OD{datetime.now().strftime('%Y%m%d%H%M%S')}{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
        receipt_id = product_order_id

        razorpay_order = razorpay_client.order.create({
            "amount": int(grand_total * 100),
            "currency": "INR",
            "receipt": receipt_id,
            "payment_capture": 1,
            "notes": {
                "order_ids": ",".join(map(str, order_product_ids)),
                "product_ids": ",".join(map(str, product_ids)),
                "customer_id": str(customer.id),
                "address_id": str(address.id),
            }
        })

        # Step 4: Save to PaymentDetails
        PaymentDetails.objects.create(
            admin=first_order.product.admin if first_order else None,
            customer=customer,
            customer_address=address,
            category_ids=category_ids,
            sub_category_ids=sub_category_ids,
            product_ids=product_ids,
            order_product_ids=order_product_ids,
            razorpay_order_id=razorpay_order["id"],
            amount=total_amount,
            total_amount=grand_total,
            payment_type="online",
            payment_status="created",
            payment_mode="unknown",
            quantity=total_quantity,
            product_order_id=product_order_id,
        )

        return JsonResponse({
            "message": "Razorpay Order Created Successfully!",
            "razorpay_key": settings.RAZORPAY_KEY_ID,
            "razorpay_order_id": razorpay_order["id"],
            "customer_id": customer.id,
            "customer_name": f"{customer.first_name} {customer.last_name}",
            "email": customer.email,
            "mobile_no": customer.mobile_no,
            "address_id": address.id,
            "total_amount": str(grand_total),
            "product_order_id": receipt_id,
            "status_code": 201
        }, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e), "status_code": 500}, status=500)
import hmac
import hashlib
import json

from razorpay import Client
import hmac
import hashlib

import traceback
from django.db import transaction

@csrf_exempt
def razorpay_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        payload = request.body
        received_signature = request.META.get("HTTP_X_RAZORPAY_SIGNATURE")
        webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        generated_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(received_signature, generated_signature):
            return HttpResponseBadRequest("Invalid signature")

        data = json.loads(payload)

        payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})
        razorpay_order_id = payment_entity.get("order_id")
        razorpay_payment_id = payment_entity.get("id")
        status = payment_entity.get("status")
        payment_mode = payment_entity.get("method")

        if not razorpay_order_id:
            return JsonResponse({"error": "Invalid payload"}, status=400)
        payment = PaymentDetails.objects.filter(razorpay_order_id=razorpay_order_id).first()

        if not payment:
            return JsonResponse({"error": "Payment record not found"}, status=404)

        if payment.payment_status == "captured":
            return JsonResponse({"status": "Already processed"}, status=200)

        with transaction.atomic():
            payment.razorpay_payment_id = razorpay_payment_id
            payment.payment_status = status
            payment.payment_mode = payment_mode
            payment.transaction_id = razorpay_payment_id
            payment.save()
            order_list = []
            if status == "captured":
                order_ids_raw = payment.order_product_ids
                order_ids = []

                if isinstance(order_ids_raw, list):
                    order_ids = order_ids_raw
                elif isinstance(order_ids_raw, str):
                    order_ids = [int(x) for x in order_ids_raw.split(",") if x.strip().isdigit()]

                order_list = OrderProducts.objects.filter(id__in=order_ids)

                for order in order_list:
                    if order.order_status != "Paid":
                        order.order_status = "Paid"
                        order.save()

                        product = order.product
                        if product.quantity >= order.quantity:
                            product.quantity -= order.quantity
                        else:
                            product.quantity = 0

                        if product.quantity == 0:
                            product.availability = "Out of Stock"
                        elif product.quantity <= 10:
                            product.availability = "Very Few Products Left"
                        else:
                            product.availability = "In Stock"

                        product.save()
                if not payment.invoice_number:
                    today = timezone.now().date()
                    date_str = today.strftime("%d%m%Y")
                    prefix = "PVM"
                    base_invoice = f"{prefix}{date_str}"

                    latest_invoice = PaymentDetails.objects.filter(
                        created_at__date=today,
                        invoice_number__startswith=base_invoice
                    ).exclude(invoice_number=None).order_by('-invoice_number').first()

                    if latest_invoice and latest_invoice.invoice_number:
                        last_serial = int(latest_invoice.invoice_number[-4:])
                    else:
                        last_serial = 0

                    new_serial = last_serial + 1
                    new_invoice_number = f"{base_invoice}{str(new_serial).zfill(4)}"
                    payment.invoice_number = new_invoice_number
                    payment.save()

            payment.save()

            if status == "captured" and order_list:
                current_paid_product_ids = [order.product_id for order in order_list]
                customer_id = payment.customer_id if hasattr(payment, 'customer_id') else payment.customer.id if hasattr(payment, 'customer') else None
                if customer_id:
                    CartProducts.objects.filter(
                        product_id__in=current_paid_product_ids,
                        customer_id=customer_id
                    ).delete()
                first_order = order_list[0]
                grand_total = sum(order.final_price for order in order_list)
                product_order_id = payment.product_order_id
                transaction_id = payment.transaction_id

                product_list = []
                for order in order_list:
                    try:
                        product_details = ProductsDetails.objects.get(id=order.product.id)
                        image_path = product_details.product_images[0] if isinstance(product_details.product_images, list) and product_details.product_images else None
                        image_url = f"{settings.AWS_S3_BUCKET_URL}/{image_path}" if image_path else ""
                        product_name = product_details.product_name
                    except ProductsDetails.DoesNotExist:
                        image_url = ""
                        product_name = "Product Not Found"

                    product_list.append({
                        "image_url": image_url,
                        "name": product_name,
                        "quantity": order.quantity,
                        "price": order.final_price,
                    })

                try:
                    send_html_order_confirmation(
                        to_email=first_order.customer.email,
                        customer_name=f"{first_order.customer.first_name} {first_order.customer.last_name}",
                        product_list=product_list,
                        total_amount=grand_total,
                        order_id=product_order_id,
                        transaction_id=transaction_id,
                    )
                except Exception as e:
                    pass

                try:
                    send_order_confirmation_sms(
                        [first_order.customer.mobile_no],
                        product_order_id,
                        grand_total
                    )
                except Exception as e:
                    pass

        return JsonResponse({"status": "Webhook handled successfully"}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
def send_html_order_confirmation(to_email, customer_name, product_list, total_amount, order_id, transaction_id):
    subject = "[Pavaman] Order Confirmation - Payment Received"
    logo_url = f"{settings.AWS_S3_BUCKET_URL}/static/images/aviation-logo.png"

    product_html = ""
    for product in product_list:
        image_path = product.get('image_url', '')
        if not image_path.startswith('http'):
            image_url = f"{settings.AWS_S3_BUCKET_URL}/{image_path}"
        else:
            image_url = image_path

        product_html += f"""
        <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 10px;">
                <img src="{image_url}" width="80" height="80" style="border-radius: 5px;" />
            </td>
            <td style="padding: 10px; vertical-align: top;">
                <strong>{product['name']}</strong><br>
                Quantity: {product['quantity']}<br>
                Price: ₹{product['price']}
            </td>
        </tr>
        """

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px; background-color: #ffffff;">
        <!-- Logo in top-right -->
        <div style="text-align: right;">
            <img src="{logo_url}" alt="Pavaman Logo" style="max-height: 60px;" />
        </div>

        <h2 style="color: #2E7D32;">Thank You for Your Purchase!</h2>
        <p style="font-size: 15px;">Hello {customer_name},</p>
        <p style="font-size: 15px;">We’re excited to let you know that your payment has been successfully processed. Your order is now being prepared and will be shipped soon.</p>

        <table style="margin: 20px 0;">
            <tr><td><strong>Order ID:</strong></td><td>{order_id}</td></tr>
            <tr><td><strong>Total Paid:</strong></td><td>₹{total_amount}</td></tr>
        </table>

        <h3 style="border-bottom: 1px solid #ddd; padding-bottom: 5px;">Order Summary</h3>
        <table style="width: 100%; border-collapse: collapse;">
            {product_html}
        </table>

        <p style="margin-top: 20px; font-size: 15px;">
            If you have any questions or need assistance, feel free to contact our support team.
        </p>

        <p style="font-size: 15px;">Thank you for choosing <strong>Pavaman</strong>.<br>We hope you enjoy your purchase!</p>

        <p style="margin-top: 30px; font-size: 14px; color: #888;">This is an automated email. Please do not reply.</p>
    </div>
    """
    try:
        email = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email]
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"[Email Error] {e}")
        return False

@csrf_exempt
def cancel_multiple_orders(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            customer_id = data.get('customer_id')
            orders = data.get('orders', [])
            print("Received Data:", data) 
            if not customer_id or not orders:
                return JsonResponse({"error": "customer_id and orders are required.", "status_code": 400}, status=400)

            successful_cancellations = []

            for item in orders:
                order_id = item.get('order_id')
                product_id = item.get('product_id')

                if not order_id or not product_id:
                    return JsonResponse({"error": "order_id and product_id are required for each order.", "status_code": 400}, status=400)

                try:
                    order = OrderProducts.objects.get(id=order_id, customer_id=customer_id, product__id=product_id)
                    product = order.product
                except OrderProducts.DoesNotExist:
                    return JsonResponse({"error": f"Orders not found for customer and product.", "status_code": 404}, status=404)

                product.quantity += order.quantity
                product.save()

                order.delete()

                successful_cancellations.append({
                    "order_id": order_id,
                    "product_id": product_id,
                    "restored_quantity": order.quantity,
                    "product_name": product.product_name
                })

            return JsonResponse({
                "message": "Selected orders cancelled successfully!",
                "cancelled_orders": successful_cancellations,
                "status_code": 200
            }, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e), "status_code": 500}, status=500)
    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)
@csrf_exempt
def filter_and_sort_products_each_subcategory(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))

            category_id = data.get("category_id")
            category_name = data.get("category_name")
            min_price = data.get("min_price")
            max_price = data.get("max_price")
            sort_by = data.get("sort_by")
            customer_id = data.get("customer_id") or request.session.get('customer_id')

            if not category_id or not category_name:
                return JsonResponse({"error": "category_id and category_name are required.", "status_code": 400}, status=400)

            try:
                category = CategoryDetails.objects.get(id=category_id)
                if category.category_name != category_name:
                    return JsonResponse({"error": "Incorrect category_name for the given category_id.", "status_code": 400}, status=400)
            except CategoryDetails.DoesNotExist:
                return JsonResponse({"error": "Invalid category_id. Category not found.", "status_code": 404}, status=404)
            products_query = ProductsDetails.objects.filter(
                category_id=category_id,
                product_status=1
            ).annotate(
                discounted_price=ExpressionWrapper(
                    F('price') - (F('price') * F('discount') / 100),
                    output_field=FloatField()
                )
            )
            
            if min_price is not None:
                products_query = products_query.filter(discounted_price__gte=min_price)
            if max_price is not None:
                products_query = products_query.filter(discounted_price__lte=max_price)

            if sort_by == "latest":
                products_query = products_query.order_by("-created_at")
            elif sort_by == "low_to_high":
                products_query = products_query.order_by("discounted_price")
            elif sort_by == "high_to_low":
                products_query = products_query.order_by("-discounted_price")
            wishlist_product_ids = get_wishlist_product_ids(customer_id)
            products_list = []
            for product in products_query:
                price = float(product.price)
                discount = float(product.discount or 0)
                final_price = round(price - (price * discount / 100), 2)
                image_path = product.product_images[0] if isinstance(product.product_images, list) and product.product_images else None
                image_url = f"{settings.AWS_S3_BUCKET_URL}/{image_path}" if image_path else ""

                product_data = {
                    "product_id": str(product.id),
                    "product_name": product.product_name,
                    "sku_number": product.sku_number,
                    "price": price,
                    "gst": f"{int(product.gst or 0)}%",
                    "discount": f"{int(discount)}%",
                    "final_price": final_price,
                    "availability": product.availability,
                    "quantity": product.quantity,
                    "product_image_url": image_url,
                    "cart_status": product.cart_status,
                    "description": product.description,
                    "material_file": product.material_file,
                    "specifications": product.specifications,
                    "number_of_specifications": product.number_of_specifications,
                    "wishlist_status": product.id in wishlist_product_ids
                }
                products_list.append(product_data)
            all_products = ProductsDetails.objects.filter(
                category_id=category_id,
                product_status=1
            ).annotate(
                discounted_price=ExpressionWrapper(
                    F('price') - (F('price') * F('discount') / 100),
                    output_field=FloatField()
                )
            )
            price_range = all_products.aggregate(
                min_price=Min("discounted_price"),
                max_price=Max("discounted_price")
            )
            if price_range["min_price"] == price_range["max_price"]:
                price_range["min_price"] = 0
            all_categories = CategoryDetails.objects.all()
            all_categories_with_subs = []
            for cat in all_categories:
                subcats = SubCategoryDetails.objects.filter(
                    category_id=cat.id,
                    sub_category_status=1
                ).values('id', 'sub_category_name')
                all_categories_with_subs.append({
                    "category_id": cat.id,
                    "category_name": cat.category_name,
                    "subcategories": list(subcats)
                })

            response_data = {
                "message": "Products filtered and sorted successfully by category.",
                "category_id": category.id,
                "category_name": category.category_name,
                "min_price": price_range["min_price"],
                "max_price": price_range["max_price"],
                "requested_min_price": float(min_price) if min_price is not None else None,
                "requested_max_price": float(max_price) if max_price is not None else None,
                "products": products_list,
                "all_categories": all_categories_with_subs,
                "status_code": 200
            }

            if customer_id:
                response_data["customer_id"] = customer_id

            return JsonResponse(response_data, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e), "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid request method.", "status_code": 405}, status=405)

@csrf_exempt
def filter_product_price_each_category(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            category_id = data.get("category_id")
            category_name = data.get("category_name")
            customer_id = data.get("customer_id")
            min_price = data.get("min_price")
            max_price = data.get("max_price")

            if not category_id or not category_name:
                return JsonResponse({"error": "category_id and category_name are required.", "status_code": 400}, status=400)

            try:
                category = CategoryDetails.objects.get(id=category_id)
            except CategoryDetails.DoesNotExist:
                return JsonResponse({"error": "Invalid category_id. Category not found.", "status_code": 404}, status=404)

            if category.category_name != category_name:
                return JsonResponse({"error": "category_name does not match the given category_id.", "status_code": 400}, status=400)

            subcategories = SubCategoryDetails.objects.filter(category_id=category_id, sub_category_status=1)

            subcategories_list = []

            for subcategory in subcategories:
                products_query = ProductsDetails.objects.filter(
                    category_id=category_id,
                    sub_category_id=subcategory.id,
                    product_status=1
                ).annotate(
                    discounted_price=ExpressionWrapper(
                        F('price') - (F('price') * F('discount') / 100),
                        output_field=FloatField()
                    )
                )

                if min_price is not None:
                    products_query = products_query.filter(discounted_price__gte=min_price)
                if max_price is not None:
                    products_query = products_query.filter(discounted_price__lte=max_price)
                wishlist_product_ids = get_wishlist_product_ids(customer_id)
                products_list = []
                for product in products_query:
                    price = float(product.price)
                    discount = float(product.discount or 0)
                    discounted_amount = (price * discount) / 100
                    final_price = price - discounted_amount
                    image_path = product.product_images[0] if isinstance(product.product_images, list) and product.product_images else None
                    image_url = f"{settings.AWS_S3_BUCKET_URL}/{image_path}" if image_path else ""

                    product_data = {
                        "product_id": str(product.id),
                        "product_name": product.product_name,
                        "sku_number": product.sku_number,
                        "price": price,
                        "gst": f"{int(product.gst or 0)}%",
                        "discount": f"{int(discount)}%" if discount else "0%",
                        "final_price": round(final_price),
                        "availability": product.availability,
                        "quantity": product.quantity,
                        "product_image_url": image_url,
                        "cart_status": product.cart_status,
                        "wishlist_status": product.id in wishlist_product_ids
                        
                    }
                    products_list.append(product_data)

                subcategories_list.append({
                    "sub_category_id": subcategory.id,
                    "sub_category_name": subcategory.sub_category_name,
                    "products": products_list
                })

            all_products = ProductsDetails.objects.filter(category_id=category_id, product_status=1).annotate(
                discounted_price=ExpressionWrapper(
                    F('price') - (F('price') * F('discount') / 100),
                    output_field=FloatField()
                )
            )

            if not all_products.exists():
                return JsonResponse({"error": "No products found for the given category.", "status_code": 404}, status=404)

            price_range = all_products.aggregate(
                min_price=Min("discounted_price"),
                max_price=Max("discounted_price")
            )
            if price_range["min_price"] == price_range["max_price"]:
                price_range["min_price"] = 0

            all_categories = CategoryDetails.objects.all()
            all_categories_with_subs = []

            for cat in all_categories:
                subcats = SubCategoryDetails.objects.filter(
                    category_id=cat.id,
                    sub_category_status=1
                ).values('id', 'sub_category_name')
                all_categories_with_subs.append({
                    "category_id": cat.id,
                    "category_name": cat.category_name,
                    "subcategories": list(subcats)
                })

            response_data = {
                "message": "Price range and product details retrieved successfully.",
                "category_id": category_id,
                "category_name": category_name,
                "min_price": price_range["min_price"],
                "max_price": price_range["max_price"],
                "sub_categories": subcategories_list,
                "all_categories": all_categories_with_subs,
                "status_code": 200
            }

            if customer_id:
                response_data["customer_id"] = customer_id

            return JsonResponse(response_data, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e), "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid request method.", "status_code": 405}, status=405)
@csrf_exempt
def sort_products_inside_subcategory(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            sub_category_id = data.get("sub_category_id")
            sub_category_name = data.get("sub_category_name")
            sort_by = data.get("sort_by")

            customer_id = request.session.get("customer_id") or data.get("customer_id")

            if not all([sub_category_id, sub_category_name, sort_by]):
                return JsonResponse({
                    "error": "sub_category_id, sub_category_name, and sort_by are required.",
                    "status_code": 400
                }, status=400)

            sub_category = SubCategoryDetails.objects.filter(id=sub_category_id, sub_category_name=sub_category_name, sub_category_status=1).first()
            if not sub_category:
                return JsonResponse({"error": "Subcategory not found.", "status_code": 404}, status=404)
            products = ProductsDetails.objects.filter(
                sub_category=sub_category, product_status=1
            ).annotate(
                discounted_price=ExpressionWrapper(
                    F('price') - (F('price') * F('discount') / 100),
                    output_field=FloatField()
                )
            )

            if sort_by == "latest":
                order_by_field = "-created_at"
            elif sort_by == "low_to_high":
                order_by_field = "discounted_price" 
            elif sort_by == "high_to_low":
                order_by_field = "-discounted_price"
            else:
                return JsonResponse({"error": "Invalid sort_by value. Use 'latest', 'low_to_high', or 'high_to_low'.", "status_code": 400}, status=400)

            products = products.order_by(order_by_field)

            if not products.exists():
                return JsonResponse({"error": "No products found for the given sub category.", "status_code": 404}, status=404)
            wishlist_product_ids = get_wishlist_product_ids(customer_id)
            price_range = products.aggregate(
                product_min_price=Min("discounted_price"),
                product_max_price=Max("discounted_price")
            )
            min_price = price_range["product_min_price"]
            max_price = price_range["product_max_price"]

            if min_price == max_price:
                min_price = 0
            all_categories = CategoryDetails.objects.all()
            all_categories_with_subs = []
            for cat in all_categories:
                subcats = SubCategoryDetails.objects.filter(
                    category_id=cat.id,
                    sub_category_status=1
                ).values("id", "sub_category_name")
                all_categories_with_subs.append({
                    "category_id": cat.id,
                    "category_name": cat.category_name,
                    "subcategories": list(subcats)
                })
            response_data = {
                "message": f"Products sorted by {sort_by.replace('_', ' ')} successfully.",
                "status_code": 200,
                "sub_category_id": str(sub_category.id),
                "sub_category_name": sub_category_name,
                "product_min_price": min_price,
                "product_max_price": max_price,
                "products": format_product_list(products, wishlist_product_ids),
                "all_categories": all_categories_with_subs,
            }

            if customer_id:
                response_data["customer_id"] = str(customer_id)

            return JsonResponse(response_data, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid request method. Use POST.", "status_code": 405}, status=405)
def format_product_list(products, wishlist_product_ids):
    return [
        {
            "product_id": str(product.id),
            "product_name": product.product_name,
            "sku_number": product.sku_number,
            "price": round(float(product.price), 2),
            "gst": f"{int(product.gst or 0)}%",
            "discount": f"{int(product.discount)}%" if product.discount else "0%",
            "final_price": round(product.discounted_price, 2),
            "availability": product.availability,
            "quantity": product.quantity,
            "wishlist_status": product.id in wishlist_product_ids,
            "product_image_url": (
                f"{settings.AWS_S3_BUCKET_URL}/{product.product_images[0]}"
                if isinstance(product.product_images, list) and product.product_images
                else ""
            ),
            "cart_status": product.cart_status
        }
        for product in products
    ]
@csrf_exempt
def get_customer_details_by_admin(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            admin_id = data.get("admin_id")

            if not admin_id:
                return JsonResponse({"error": "admin_id is required.", "status_code": 400}, status=400)

            customers = CustomerRegisterDetails.objects.filter(admin_id=admin_id).order_by("-created_on").values(
                "id", "first_name", "last_name", "email", "mobile_no", "account_status","created_on","register_type","register_status"
            )

            customers_list = list(customers)

            if not customers_list:
                return JsonResponse({"error": "No matching customer found.", "status_code": 404}, status=404)
        
            activated_count = sum(1 for c in customers_list if c["account_status"] == 1)
            inactivated_count = sum(1 for c in customers_list if c["account_status"] == 0)
            total_count = activated_count + inactivated_count

            response_data = {
                "status": "success",
                "customers": customers_list,
                "activated_count": activated_count,
                "inactivated_count": inactivated_count,
                "total_count": total_count,
                "status_code": 200
            }
            if admin_id:
                response_data["admin_id"] = str(admin_id)
            return JsonResponse(response_data, status=200)
        
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid request method. Only POST is allowed.", "status_code": 405}, status=405)


@csrf_exempt
def customer_search_categories(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            search_query = data.get('category_name', '').strip()

            if not search_query:
                return JsonResponse({"error": "Atleast one character is required.", "status_code": 400}, status=400)

            categories = CategoryDetails.objects.filter(
                
                category_status=1,
                category_name__icontains=search_query
            )
            if not categories.exists():
                response_data = {"message": "No category details found", "status_code": 200}
                if customer_id:
                    response_data["customer_id"] = customer_id
                return JsonResponse(response_data, status=200)  


            category_list = [
                {
                    "category_id": str(category.id),
                    "category_name": category.category_name,
                    "category_image_url": f"{settings.AWS_S3_BUCKET_URL}/{category.category_image.replace('\\', '/')}" if category.category_image else ""
                }
                for category in categories
            ]

            response_data = {
                "message": "Categories retrieved successfully.",
                "categories": category_list,
                "status_code": 200
            }
            if customer_id:
                response_data["customer_id"] = str(customer_id)
            return JsonResponse(response_data, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)


@csrf_exempt
def customer_search_subcategories(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            category_id = data.get('category_id')
            sub_category_name = data.get('sub_category_name', '').strip()
         
            if not category_id:
                return JsonResponse({"error": "Category Id is required.", "status_code": 400}, status=400)

            if sub_category_name == "": 
                return JsonResponse({"error": "Atleast one character is required.", "status_code": 400}, status=400)

            subcategories = SubCategoryDetails.objects.filter(
                category_id=category_id,
                sub_category_status=1,
                sub_category_name__icontains=sub_category_name
            )
           
            if not subcategories.exists():
                response_data = {"message": "No subcategory details found", "status_code": 200}
                if customer_id:
                    response_data["customer_id"] = customer_id
                return JsonResponse(response_data, status=200)           

            subcategory_list = [
    {
        "sub_category_id": str(subcategory.id),
        "sub_category_name": subcategory.sub_category_name,
        "sub_category_image_url": f"{settings.AWS_S3_BUCKET_URL}/{subcategory.sub_category_image.replace('\\', '/')}" if subcategory.sub_category_image else "",
        "category_id": str(subcategory.category_id)
    }
    for subcategory in subcategories
]
            response_data = {
                "message": "Subcategories retrieved successfully.",
                "categories": subcategory_list,
                "status_code": 200
            }
            if customer_id:
                response_data["customer_id"] = str(customer_id)
            return JsonResponse(response_data, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

@csrf_exempt
def customer_search_products(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            category_id = data.get('category_id')
            sub_category_id = data.get('sub_category_id')
            product_name = data.get('product_name', '').strip() 

            if not category_id:
                return JsonResponse({"error": "Category ID are required.", "status_code": 400}, status=400)
            if not sub_category_id:
                return JsonResponse({"error": "Sub Category ID are required.", "status_code": 400}, status=400)

            if product_name == "":
                return JsonResponse({"error": "Atleast one character is required.", "status_code": 400}, status=400)

            products = ProductsDetails.objects.filter(
                
                category_id=category_id,
                sub_category_id=sub_category_id,
                product_status=1
            )
            wishlist_product_ids = get_wishlist_product_ids(customer_id)
            if product_name:
                products = products.filter(product_name__icontains=product_name)


            if not products.exists():
                response_data = {"message": "No products details found", "status_code": 200}
                if customer_id:
                    response_data["customer_id"] = customer_id 
                return JsonResponse(response_data, status=200)    

            product_list = []
            for product in products:
                product_images = product.product_images
                if isinstance(product_images, list):
                    product_image_url = (
                         f"{settings.AWS_S3_BUCKET_URL}/{product_images[0].replace('\\', '/')}"
                        if product_images else ""
                    )
                elif isinstance(product_images, str):
                      product_image_url = f"{settings.AWS_S3_BUCKET_URL}/{product_images.replace('\\', '/')}"
                else:
                    product_image_url = ""      

                product_list.append({
                    "category_id": str(product.category_id),
                    "sub_category_id": str(product.sub_category_id),
                    "product_id": str(product.id),
                    "product_name": product.product_name,       
                    "product_image_url": product_image_url,
                    "sku_number": product.sku_number,
                    "price": float(product.price),
                    "gst": f"{int(product.gst or 0)}%",
                    "discount":f"{int(product.discount)}%" if product.discount else "0%",
                    "final_price": round(float(product.price) - (float(product.price) * float(product.discount or 0) / 100), 2),
                    "availability": product.availability,
                    "quantity": product.quantity,
                    "cart_status": product.cart_status,
                    "wishlist_status": product.id in wishlist_product_ids,
                })
        
            response_data = {
                "message": "Products retrieved successfully.",
                "products": product_list,
                "status_code": 200
            }

            if customer_id:
                response_data["customer_id"] = str(customer_id)
            return JsonResponse(response_data, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)
@csrf_exempt
def get_payment_details_by_order(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        admin_id = data.get('admin_id')
       
        if not admin_id:
                return JsonResponse({"error": "admin_id is required.", "status_code": 400}, status=400)
     
        payments = PaymentDetails.objects.filter(admin_id=admin_id).order_by('-created_at')
        if not payments.exists():
            return JsonResponse({"error": "No payment details found on this admin.", "status_code": 404}, status=404)

        payment_list = []
        for payment in payments:
            order_ids = payment.order_product_ids
            
            order_products = OrderProducts.objects.filter(id__in=order_ids)
            
            order_product_list = []
            for order in order_products:
                product = ProductsDetails.objects.filter(id=order.product_id).first()
                if product and product.product_images:
                   product_image_path = product.product_images[0].replace('\\', '/')
                   product_image_url = f"{settings.AWS_S3_BUCKET_URL}/{product_image_path}"

                else:
                   product_image_url = ""
                
                order_product_list.append({
                    "id": order.id,
                    "quantity": order.quantity,
                    "price": order.price,
                    "gst": f"{int(product.gst or 0)}%",
                    "discount":f"{int(product.discount)}%" if product.discount else "0%",
                    "final_price": "{:.2f}".format(float(product.price) - (float(product.price) * float(product.discount or 0) / 100)),
                    "order_status": order.order_status,
                    "product_id": order.product_id,
                    "product_image": product_image_url,
                    "product_name":product.product_name,
                    "shipping_status":order.shipping_status,
                    "delivery_status":order.delivery_status,
                    "payment_status": get_display_payment_status(payment.payment_status),
                    
                })

            address_data = []
            if payment.customer_address_id:
                address_obj = CustomerAddress.objects.filter(id=payment.customer_address_id).first()
                if address_obj:
                    address_data.append({
                        "address_id": address_obj.id,
                        "customer_name": f"{address_obj.first_name} {address_obj.last_name}",
                        "email": address_obj.email,
                        "mobile_number": address_obj.mobile_number,
                        "alternate_mobile": address_obj.alternate_mobile,
                        "address_type": address_obj.address_type,
                        "pincode": address_obj.pincode,
                        "street": address_obj.street,
                        "landmark": address_obj.landmark,
                        "village": address_obj.village,
                        "mandal": address_obj.mandal,
                        "postoffice": address_obj.postoffice,
                        "district": address_obj.district,
                        "state": address_obj.state,
                        "country": address_obj.country,
                        
                    })
                    
            payment_list.append({
                "razorpay_order_id": payment.razorpay_order_id,
                "customer_name": f"{payment.customer.first_name} {payment.customer.last_name}",
                "customer_id":payment.customer_id,
                "email": payment.customer.email,
                "mobile_number": payment.customer.mobile_no,
                "payment_mode": payment.payment_mode,
                "total_quantity":payment.quantity,
                "total_amount": payment.total_amount,
                "payment_date": payment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "product_order_id":payment.product_order_id,
                "customer_address": address_data,
                "order_products": order_product_list
            })
        response_data = {
            "message": "Placed Order retrieved successfully.",
            "payments": payment_list,
            "status_code": 200
        }

        if admin_id:
            response_data["admin_id"] = str(admin_id)
        return JsonResponse(response_data, status=200)    
    except Exception as e:
        return JsonResponse({"error": str(e), "status_code": 500}, status=500)

@csrf_exempt
def filter_my_order(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        customer_id = data.get('customer_id')
        delivery_status_filter = data.get('delivery_status')
        shipping_status_filter = data.get('shipping_status') 
        delivery_status_filter = data.get('delivery_status')
        shipping_status_filter = data.get('shipping_status')
        order_time_filter = data.get('order_time')

        if shipping_status_filter and delivery_status_filter:
            return JsonResponse({
                "error": "Please provide only one of 'shipping_status' or 'delivery_status', not both.",
                "status_code": 400
            }, status=400)

        if not customer_id:
            return JsonResponse({"error": "customer_id is required.", "status_code": 400}, status=400)

        payments = PaymentDetails.objects.filter(customer_id=customer_id)

        available_years = payments.dates('created_at', 'year', order='DESC')
        year_options = ["Last 30 days"] + [dt.year for dt in available_years if dt.year >= datetime.now().year - 3] + ["Older"]

        now = datetime.now()
        if order_time_filter:
            if order_time_filter == "Last 30 days":
                payments = payments.filter(created_at__gte=now - timedelta(days=30))
            elif order_time_filter == "Older":
                payments = payments.filter(created_at__lt=datetime(now.year - 3, 1, 1))
            elif order_time_filter.isdigit():
                payments = payments.filter(created_at__year=int(order_time_filter))

        payments = payments.order_by('-created_at')

        if not payments.exists():
            return JsonResponse({"error": "No order details found.", "status_code": 404}, status=404)

        payment_list = []
        total_matched_order_products = 0

        for payment in payments:
            order_ids = payment.order_product_ids
            order_products = OrderProducts.objects.filter(id__in=order_ids)
            if delivery_status_filter:
                order_products = order_products.filter(delivery_status=delivery_status_filter)
            elif shipping_status_filter == "Shipped":
                order_products = order_products.filter(
                    shipping_status="Shipped"
                ).exclude(delivery_status="Delivered")

            order_product_list = []
            for order in order_products:
                product = ProductsDetails.objects.filter(id=order.product_id).first()
                if product and product.product_images:
                    product_image_path = product.product_images[0].replace('\\', '/')
                    product_image_url = f"{settings.AWS_S3_BUCKET_URL}/{product_image_path.lstrip('/')}"
                else:
                    product_image_url = ""

                order_product_list.append({
                    "order_product_id": order.id,
                    "quantity": order.quantity,
                    "price": order.price,
                    "discount": f"{int(product.discount)}%" if product.discount else "0%",
                    "final_price": round(float(product.price) - (float(product.price) * float(product.discount or 0) / 100), 2),
                    "order_status": order.order_status,
                    "shipping_status": order.shipping_status,
                    "delivery_status": order.delivery_status,
                    "delivery_charge": order.delivery_charge,
                    "product_id": order.product_id,
                    "product_image": product_image_url,
                    "product_name": product.product_name,
                    "delivery_charge":order.delivery_charge
                })

            if order_product_list:
                total_matched_order_products += len(order_product_list)
            else:
                if delivery_status_filter or shipping_status_filter:
                    continue

            address_data = []
            if payment.customer_address_id:
                address_obj = CustomerAddress.objects.filter(id=payment.customer_address_id).first()
                if address_obj:
                    address_data.append({
                        "address_id": address_obj.id,
                        "customer_name": f"{address_obj.first_name} {address_obj.last_name}",
                        "email": address_obj.email,
                        "mobile_number": address_obj.mobile_number,
                        "alternate_mobile": address_obj.alternate_mobile,
                        "address_type": address_obj.address_type,
                        "pincode": address_obj.pincode,
                        "street": address_obj.street,
                        "landmark": address_obj.landmark,
                        "village": address_obj.village,
                        "mandal": address_obj.mandal,
                        "postoffice": address_obj.postoffice,
                        "district": address_obj.district,
                        "state": address_obj.state,
                        "country": address_obj.country,
                    })

            payment_list.append({
                "customer_name": f"{payment.customer.first_name} {payment.customer.last_name}",
                "email": payment.customer.email,
                "mobile_number": payment.customer.mobile_no,
                "payment_mode": payment.payment_mode,
                "total_quantity": payment.quantity,
                "total_amount": payment.total_amount,
                "payment_date": payment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "time_filters": year_options,
                "product_order_id": payment.product_order_id,
                "customer_address": address_data,
                "order_products": order_product_list,
                "payment_status": get_display_payment_status(payment.payment_status),

            })

        if (delivery_status_filter or shipping_status_filter) and total_matched_order_products == 0:
            return JsonResponse({
                "error": "No products found for the selected filters.",
                "status_code": 404,
                "time_filters": year_options
            }, status=404)

        if not payment_list:
            return JsonResponse({"error": "No order details match filters.", "status_code": 404}, status=404)

        return JsonResponse({
            "message": "Filtered Orders Retrieved Successfully.",
            "payments": payment_list,
            "status_code": 200,
            "customer_id": str(customer_id)
        }, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e), "status_code": 500}, status=500)


@csrf_exempt
def customer_get_payment_details_by_order(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        customer_id = data.get('customer_id')
        action = data.get('action', '').lower().strip()
        search_product_name = data.get('search_product_name', '').strip()

        if not customer_id:
            return JsonResponse({"error": "customer_id is required.", "status_code": 400}, status=400)
        if action not in ['view', 'search']:
            return JsonResponse({"error": "Invalid action. Use 'view' or 'search'.", "status_code": 400}, status=400)
        if action == 'search' and not search_product_name:
            return JsonResponse({"error": "Atleast one character is required for search action.", "status_code": 400}, status=400)

        payments = PaymentDetails.objects.filter(customer_id=customer_id).order_by('-created_at')
        if not payments.exists():
            return JsonResponse({"error": "No order details found.", "status_code": 404}, status=404)

        payment_list = []

        for payment in payments:
            order_ids = payment.order_product_ids
            order_products = OrderProducts.objects.filter(id__in=order_ids)

            order_product_list = []
            for order in order_products:
                product = ProductsDetails.objects.filter(id=order.product_id).first()
                if not product:
                    continue

                if action == 'search' and search_product_name.lower() not in product.product_name.lower():
                    continue

                product_image_url = f"{settings.AWS_S3_BUCKET_URL}/{product.product_images[0].replace('\\', '/')}" if product.product_images else ""

                order_product_list.append({
                    "order_product_id": order.id,
                    "quantity": order.quantity,
                    "price": order.price,
                    "gst": f"{int(product.gst or 0)}%",
                    "discount": f"{int(product.discount)}%" if product.discount else "0%",
                    "final_price": round(float(product.price) - (float(product.price) * float(product.discount or 0) / 100), 2),
                    "order_status": order.order_status,
                    "shipping_status": order.shipping_status,
                    "delivery_status": order.delivery_status,
                    "delivery_charge": order.delivery_charge,
                    "product_id": order.product_id,
                    "product_image": product_image_url,
                    "product_name": product.product_name,
                    "delivery_charge":order.delivery_charge,
                    "payment_status": get_display_payment_status(payment.payment_status),

                })

            if action == 'search' and not order_product_list:
                continue

            address_data = []
            if payment.customer_address_id:
                address = CustomerAddress.objects.filter(id=payment.customer_address_id).first()
                if address:
                    address_data.append({
                        "address_id": address.id,
                        "customer_name": f"{address.first_name} {address.last_name}",
                        "email": address.email,
                        "mobile_number": address.mobile_number,
                        "alternate_mobile": address.alternate_mobile,
                        "address_type": address.address_type,
                        "pincode": address.pincode,
                        "street": address.street,
                        "landmark": address.landmark,
                        "village": address.village,
                        "mandal": address.mandal,
                        "postoffice": address.postoffice,
                        "district": address.district,
                        "state": address.state,
                        "country": address.country,
                    })

            payment_list.append({
                "razorpay_order_id": payment.razorpay_order_id,
                "customer_name": f"{payment.customer.first_name} {payment.customer.last_name}",
                "email": payment.customer.email,
                "mobile_number": payment.customer.mobile_no,
                "payment_mode": payment.payment_mode,
                "total_quantity": payment.quantity,
                "total_amount": payment.total_amount,
                "payment_date": payment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "product_order_id": payment.product_order_id,
                "customer_address": address_data,
                "order_products": order_product_list
            })

        if not payment_list:
            return JsonResponse({"message": "No matching order details found.", "status_code": 404}, status=404)

        return JsonResponse({
            "message": "Orders retrieved successfully." if action == 'view' else "Search results retrieved successfully.",
            "payments": payment_list,
            "status_code": 200
        })

    except Exception as e:
        return JsonResponse({"error": str(e), "status_code": 500}, status=500)

def get_display_payment_status(status):
    status = (status or '').lower()
    return {
        "created": "Waiting for Payment",
        "authorized": "Payment Authorized (Processing)",
        "captured": "Payment Successful",
        "failed": "Payment Failed",
        "pending": "Awaiting Bank Confirmation",
        "refunded": "Refunded to Your Account",
        "cancelled": "Payment Cancelled",
    }.get(status, "Status Unknown")

def download_material_file(request, product_id):
    try:
        product = ProductsDetails.objects.get(id=product_id)
        material_key = product.material_file

        if not material_key:
            return JsonResponse({"error": "Material file not found.", "status_code": 404}, status=404)

        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

        try:
            file_obj = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=material_key)
            file_stream = file_obj['Body']
            content_type = file_obj.get('ContentType', 'application/pdf')

            filename = material_key.replace("\\", "/").split("/")[-1]

            response = StreamingHttpResponse(file_stream, content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            return response

        except ClientError as e:
            return JsonResponse({
                "error": f"Failed to fetch material file from S3: {str(e)}",
                "status_code": 500
            }, status=500)

    except ProductsDetails.DoesNotExist:
        return JsonResponse({"error": "Product not found.", "status_code": 404}, status=404)

    except Exception as e:
        return JsonResponse({"error": f"Unexpected error: {str(e)}", "status_code": 500}, status=500)

@csrf_exempt
def get_customer_profile(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            customer_id = data.get("customer_id")

            if not customer_id:
                return JsonResponse({"error": "Customer ID is required.", "status_code": 400}, status=400)

            try:
                customer = CustomerRegisterDetails.objects.get(id=customer_id)
            except CustomerRegisterDetails.DoesNotExist:
                return JsonResponse({"error": "Customer not found.", "status_code": 404}, status=404)

            return JsonResponse({
                "message": "Customer profile fetched successfully.",
                "status_code": 200,
                "customer_id": customer.id,
                "profile": {
                    "first_name": customer.first_name,
                    "last_name": customer.last_name,
                    "email": customer.email,
                    "mobile_no": customer.mobile_no,
                }
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)


@csrf_exempt
def edit_customer_profile(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            customer_id = data.get("customer_id")

            
            if not customer_id:
                return JsonResponse({"error": "Customer ID is required.", "status_code": 400}, status=400)

       
            try:
                customer = CustomerRegisterDetails.objects.get(id=customer_id)
            except CustomerRegisterDetails.DoesNotExist:
                return JsonResponse({"error": "Customer not found.", "status_code": 404}, status=404)

            
            customer.first_name = data.get("first_name", customer.first_name)
            customer.last_name = data.get("last_name", customer.last_name)

            customer.save(update_fields=["first_name", "last_name"])

            return JsonResponse({
                "message": "Customer profile updated successfully.",
                "status_code": 200,
                "customer_id": customer.id,
                "updated_details": {
                    "first_name": customer.first_name,
                    "last_name": customer.last_name,
                }
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

@csrf_exempt
def report_sales_summary(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        admin_id = data.get('admin_id')

        if not admin_id:
            return JsonResponse({"error": "admin_id is required.", "status_code": 400}, status=400)

        today = now().date()
        this_month = today.month
        this_year = today.year

        todays_sales = PaymentDetails.objects.filter(admin_id=admin_id, created_at__date=today)
        month_sales = PaymentDetails.objects.filter(admin_id=admin_id, created_at__month=this_month, created_at__year=this_year)
        total_sales = PaymentDetails.objects.filter(admin_id=admin_id,created_at__year=this_year)

        todays_amount = todays_sales.aggregate(total=Sum('total_amount'))['total'] or 0
        month_amount = month_sales.aggregate(total=Sum('total_amount'))['total'] or 0
        total_amount = total_sales.aggregate(total=Sum('total_amount'))['total'] or 0

        return JsonResponse({
            "today_sales_amount": todays_amount,
            "this_month_sales_amount": month_amount,
            "total_sales_amount": total_amount,
            "status_code": 200,
            "admin_id":admin_id
        }, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e), "status_code": 500}, status=500)

@csrf_exempt
def report_monthly_revenue_by_year(request):
    print(">>> report_monthly_revenue_by_year view called")
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        admin_id = data.get('admin_id')
        action = data.get('action')

        print(">>> Received data:", data)

        if not admin_id:
            return JsonResponse({"error": "admin_id is required", "status_code": 400}, status=400)

        if action == "month":
            return _report_monthly(data, admin_id)
        elif action == "year":
            return _report_yearly(data,admin_id)
        elif action == "week":
            return _report_weekly(data, admin_id)
        else:
            return JsonResponse({"error": "Invalid action. Use 'month', 'year' or 'week'.", "status_code": 400}, status=400)

    except Exception as e:
        print(">>> Exception occurred:", str(e))
        return JsonResponse({"error": str(e), "status_code": 500})


def _report_monthly(data, admin_id):
    start_date_str = data.get('start_date_str')
    end_date_str = data.get('end_date_str')
    print(">>> Monthly Report Start:", start_date_str, "End:", end_date_str)

    if not start_date_str or not end_date_str:
        current_year = datetime.now().year
        start_date_str = f"{current_year}-01-01"
        end_date_str = f"{current_year}-12-31"

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD.", "status_code": 400}, status=400)

    if end_date < start_date:
        return JsonResponse({"error": "End date must be after start date", "status_code": 400}, status=400)

    diff = relativedelta(end_date, start_date)
    print(">>> Date difference:", diff)
    if diff.years > 1 or (diff.years == 1 and (diff.months > 0)):
        return JsonResponse({"error": "Date range cannot exceed 1 year", "status_code": 400}, status=400)
    monthly_revenue = {}
    current = start_date
    while current <= end_date:
        key = f"{calendar.month_abbr[current.month]} {current.year}"
        monthly_revenue[key] = 0
        current += relativedelta(months=1)

    payments = PaymentDetails.objects.filter(
        admin_id=admin_id,
        created_at__date__gte=start_date.date(),
        created_at__date__lte=end_date.date()
    )

    print(f">>> Found {payments.count()} payments")

    for payment in payments:
        key = f"{calendar.month_abbr[payment.created_at.month]} {payment.created_at.year}"
        if key in monthly_revenue:
            monthly_revenue[key] += float(payment.total_amount)

    dummy_y_axis = [i * 50000 for i in range(1, 11)]

    return JsonResponse({
        "report_type": "monthly",
        "start_date": start_date_str,
        "end_date": end_date_str,
        "monthly_revenue": monthly_revenue,
        "admin_id": admin_id,
        "dummy_y_axis": dummy_y_axis,
        "status_code": 200
    })

def _report_yearly(data, admin_id):
    start_date_str = data.get('start_date_str')
    end_date_str = data.get('end_date_str')

    if not start_date_str or not end_date_str:
        current_year = datetime.now().year
        start_date_str = str(current_year - 11) + "-01-01"
        end_date_str = str(current_year) + "-12-31"

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD.", "status_code": 400}, status=400)

    if (end_date.year - start_date.year) > 12:
        return JsonResponse({"error": "Date range cannot exceed 12 years", "status_code": 400}, status=400)

    yearly_revenue = {}
    start_year = start_date.year
    end_year = end_date.year

    for year in range(start_year, end_year + 1):
        start_date_of_year = datetime(year, 1, 1)
        end_date_of_year = datetime(year, 12, 31)
        total = PaymentDetails.objects.filter(
            admin_id=admin_id,
            created_at__date__gte=start_date_of_year.date(),
            created_at__date__lte=end_date_of_year.date()
        ).aggregate(total_amount=models.Sum('total_amount'))['total_amount'] or 0
        yearly_revenue[str(year)] = float(total)

    dummy_y_axis = [i * 500000 for i in range(1, 11)]

    return JsonResponse({
        "report_type": "yearly",
        "year_range": [start_year, end_year],
        "yearly_revenue": yearly_revenue,
        "admin_id": admin_id,
        "dummy_y_axis": dummy_y_axis,
        "status_code": 200
    })

def _report_weekly(data, admin_id):
    start_date_str = data.get('start_date_str')
    end_date_str = data.get('end_date_str')

    if not start_date_str or not end_date_str:
        end_date = datetime.now().date()
        start_date = end_date - relativedelta(days=6)
    else:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD.", "status_code": 400}, status=400)

    delta_days = (end_date - start_date).days
    if delta_days < 0:
        return JsonResponse({"error": "End date must be after start date", "status_code": 400}, status=400)
    if delta_days > 6:
        return JsonResponse({"error": "Only 7-day range allowed", "status_code": 400}, status=400)

    daywise_revenue = {}
    for i in range(delta_days + 1):
        date = start_date + relativedelta(days=i)
        label = f"{date.strftime('%A')} ({date.strftime('%d %b %Y')})"
        daywise_revenue[label] = 0

    payments = PaymentDetails.objects.filter(
        admin_id=admin_id,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )

    for payment in payments:
        pay_date = payment.created_at.date()
        label = f"{pay_date.strftime('%A')} ({pay_date.strftime('%d %b %Y')})"
        if label in daywise_revenue:
            daywise_revenue[label] += float(payment.total_amount)

    dummy_y_axis = [i * 10000 for i in range(1, 11)]

    return JsonResponse({
        "report_type": "daywise_week",
        "start_date": str(start_date),
        "end_date": str(end_date),
        "daywise_revenue": daywise_revenue,
        "admin_id": admin_id,
        "dummy_y_axis": dummy_y_axis,
        "status_code": 200
    })

@csrf_exempt
def top_five_selling_products(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body)
        admin_id = data.get("admin_id")

        if not admin_id:
            return JsonResponse({"error": "admin_id is required", "status_code": 400}, status=400)

        product_counter = Counter()
        payments = PaymentDetails.objects.filter(admin_id=admin_id)

        for payment in payments:
            product_ids = payment.product_ids
            product_counter.update(product_ids)

        top_5 = product_counter.most_common(5)
        top_product_ids = [pid for pid, _ in top_5]

        order_products = ProductsDetails.objects.filter(id__in=top_product_ids).values('id', 'product_name')
        product_name_map = {item['id']: item['product_name'] for item in order_products}

        response_data = []
        for pid, count in top_5:
            response_data.append({
                "product_id": pid,
                "product_name": product_name_map.get(pid, "Unknown"),
                "total_sold": count
            })

        return JsonResponse({
            "status_code": 200,
            "top_5_products": response_data
        })

    except Exception as e:
        return JsonResponse({"error": str(e), "status_code": 500})


@csrf_exempt
def not_selling_products(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body)
        admin_id = data.get("admin_id")

        if not admin_id:
            return JsonResponse({"error": "admin_id is required", "status_code": 400}, status=400)
        sold_product_ids = []
        payments = PaymentDetails.objects.filter(admin_id=admin_id)
        for payment in payments:
            sold_product_ids.extend(payment.product_ids)
        all_products = ProductsDetails.objects.filter(admin_id=admin_id)
        not_sold_products = all_products.exclude(id__in=sold_product_ids).values('id', 'product_name')

        response_data = list(not_sold_products)

        return JsonResponse({
            "status_code": 200,
            "not_selling_products": response_data
        })

    except Exception as e:
        return JsonResponse({"error": str(e), "status_code": 500})
@csrf_exempt
def get_all_category_subcategory(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        customer_id = data.get('customer_id')

        categories = CategoryDetails.objects.filter(category_status=1)

        if not categories.exists():
            return JsonResponse({"error": "No categories found.", "status_code": 404}, status=404)

        category_list = []
        for category in categories:

            subcategories = SubCategoryDetails.objects.filter(category=category,sub_category_status=1)            
            sub_category_list = []
            for subcategory in subcategories:
              sub_category_image_url = ""
              if subcategory.sub_category_image:
                    sub_category_image_path = subcategory.sub_category_image.replace('\\', '/')
                    sub_category_image_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{sub_category_image_path}"

              sub_category_list.append({
                    "id": subcategory.id,
                    "sub_category_name": subcategory.sub_category_name,
                    "sub_category_image": sub_category_image_url,
                    
                })     
            category_list.append({
                "category_id":category.id,
                "category_name":category.category_name,  
                "sub_categoryies": sub_category_list
            })
        response_data = {
            "message": "Category and subcategory retrieved successfully.",
            "categories": category_list,
            "status_code": 200
        }

        if customer_id:
            response_data["customer_id"] = str(customer_id)
        return JsonResponse(response_data, status=200)    
    except Exception as e:
        return JsonResponse({"error": str(e), "status_code": 500}, status=500)
@csrf_exempt
def generate_invoice_for_customer(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        customer_id = data.get("customer_id")
        product_order_id = data.get("product_order_id")
    
        if not customer_id:
            return JsonResponse({"error": "customer_id is required", "status_code": 400}, status=400)

        payments = PaymentDetails.objects.filter(customer_id=customer_id,product_order_id=product_order_id)

        if not payments.exists():
            return JsonResponse({"error": "No invoices found for this customer", "status_code": 404}, status=404)

        invoice_list = []
        for payment in payments:
            order_ids = payment.order_product_ids
            order_products = OrderProducts.objects.filter(id__in=order_ids)
            customer=CustomerRegisterDetails.objects.filter(id=payment.customer_id).first()
            address = CustomerAddress.objects.filter(id=payment.customer_address_id).first()

            items = []
            for order in order_products:
                product = ProductsDetails.objects.filter(id=order.product_id).first()
                if not product:
                    continue
                price = round(float(product.price),2)
                discount_percent = float(product.discount or 0)
                gst_amount=round(float(price * product.gst/100),2)
                discount_amount =round( (price * discount_percent) / 100,2)
                final_price = price - discount_amount
                items.append({
                    "product_name": product.product_name,
                    "sku":product.sku_number,
                    "hsn":product.hsn_code,
                    "quantity": order.quantity,
                    "price" :price,
                    "gst_amount":gst_amount,
                    "gst": f"{int(product.gst or 0)}%",
                    "discount_percent": f"{int(discount_percent)}%",
                    "discount": discount_amount,
                    "final_price": order.final_price,
                    "total_price": round(order.final_price * order.quantity, 2) 
                })

            invoice_list.append({
                "invoice_number":payment.invoice_number,
                "order_id": payment.product_order_id,
                "order_date": payment.created_at.strftime("%d-%m-%Y"),
                "invoice_date": payment.invoice_date.strftime("%d-%m-%Y"),
                "Billing To": {
                    "name": f"{customer.first_name} {customer.last_name}" if customer else "",
                    "phone": customer.mobile_no if customer else "",
                },
                "Delivery To": {
                    "name": f"{address.first_name} {address.last_name}" if address else "",
                    "address": f"{address.street}, {address.landmark}, {address.village}, {address.district}, {address.state}, {address.pincode}" if address else "",
                    "phone": address.mobile_number if address else "",
                },
                "sold_by": "Pavaman",
                "total_items": len(items),
                "items": items,
                "grand_total": payment.amount,
                "payment_mode": payment.payment_mode,
                
            })

        return JsonResponse({
            "message": "Invoice(s) generated successfully",
            "invoices": invoice_list,
            "status_code": 200
        }, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e), "status_code": 500}, status=500)

@csrf_exempt
def admin_order_status(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        admin_id = data.get("admin_id")

        if not admin_id:
            return JsonResponse({"error": "admin_id is required.", "status_code": 400}, status=400)

        payment_entries = PaymentDetails.objects.filter(admin_id=admin_id)

        if not payment_entries.exists():
            return JsonResponse({
                "error": "No payment records found for this admin.",
                "status_code": 404
            }, status=404)

        all_order_product_ids = []
        for entry in payment_entries:
            if isinstance(entry.order_product_ids, list):
                all_order_product_ids.extend(entry.order_product_ids)

        if not all_order_product_ids:
            return JsonResponse({
                "error": "No order_product_ids found in PaymentDetails for this admin.",
                "status_code": 404
            }, status=404)

        all_order_product_ids = list(set(all_order_product_ids))
        related_orders = OrderProducts.objects.filter(id__in=all_order_product_ids)
        status_counter = Counter(order.order_status for order in related_orders)
        pending_orders = OrderProducts.objects.filter(order_status="Pending").count()
        result = {
            "Paid": status_counter.get("Paid", 0),
            "Pending": pending_orders,
            "Cancelled": status_counter.get("Cancelled", 0),
        }

        return JsonResponse({
            "admin_id": admin_id,
            "total_related_orders": related_orders.count(),
            "order_status_summary": result,
            "status_code": 200
        }, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e), "status_code": 500}, status=500)
@csrf_exempt
def customer_cart_view_search(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            product_name = data.get('product_name', '').strip()

            if not customer_id:
                return JsonResponse({"error": "Customer ID is required.", "status_code": 400}, status=400)

            cart_items = CartProducts.objects.filter(customer_id=customer_id)

            if product_name:
                cart_items = cart_items.filter(product__product_name__icontains=product_name)

            if not cart_items.exists():
                return JsonResponse({
                    "message": "No cart items found.",
                    "status_code": 200,
                    "customer_id": str(customer_id)
                }, status=200)

            cart_list = []
            for item in cart_items:
                product = item.product
                price = float(product.price)
                discount= float(product.discount or 0)  
                discount_amount = (price * discount) / 100  
                final_price = price - discount_amount  
                total_price = final_price * item.quantity 
                product_image_url = ""
                if product.product_images:
                    product_image_path = product.product_images[0].replace('\\', '/')
                    product_image_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{product_image_path}"

                cart_list.append({
                    "cart_id": item.id,
                    "product_id": product.id,
                    "product_name": product.product_name,
                    "quantity": item.quantity,
                    "price": price,
                    "gst": f"{int(product.gst or 0)}%",
                    "discount": f"{int(discount)}%",
                    "final_price": round(final_price, 2),
                    "total_price": round(total_price, 2),
                    "original_quantity": product.quantity,
                    "availability": product.availability,
                    "image": product_image_url,
                    "category": product.category.category_name if product.category else None,
                    "sub_category": product.sub_category.sub_category_name if product.sub_category else None
                })

            return JsonResponse({
                "message": "Cart items retrieved successfully.",
                "cart_items": cart_list,
                "status_code": 200,
                "customer_id": str(customer_id)
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Only POST is allowed.", "status_code": 405}, status=405)
@csrf_exempt
def edit_profile_mobile_otp_handler(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            action = data.get("action")
            customer_id = data.get("customer_id")

            if not action or not customer_id:
                return JsonResponse({"error": "Action and Customer ID are required.", "customer_id": customer_id}, status=400)

            customer = CustomerRegisterDetails.objects.filter(id=customer_id).first()
            if not customer:
                return JsonResponse({"error": "Customer not found.", "customer_id": customer_id}, status=404)

            if action == "send_previous_otp":
                if not customer.mobile_no:
                    return JsonResponse({"error": "Customer does not have a registered mobile number.", "customer_id": customer_id}, status=400)

                otp = random.randint(100000, 999999)
                customer.otp = otp
                customer.save(update_fields=["otp"])
                send_verify_mobile([customer.mobile_no], otp)

                return JsonResponse({
                    "message": "OTP sent to previous mobile number.",
                    "customer_id": customer_id
                })

            elif action == "verify_previous_otp":
                otp = data.get("otp")
                if not otp:
                    return JsonResponse({"error": "OTP is required for verification.", "customer_id": customer_id}, status=400)

                if str(customer.otp) != str(otp):
                    return JsonResponse({"error": "Invalid OTP for previous mobile number.", "customer_id": customer_id}, status=400)

                customer.otp = None
                customer.save(update_fields=["otp"])

                return JsonResponse({
                    "message": "Previous mobile verified.",
                    "customer_id": customer_id,
                    "previous_mobile": customer.mobile_no
                })

            elif action == "send_new_otp":
                new_mobile = data.get("mobile_no")
                if not new_mobile:
                    return JsonResponse({"error": "New mobile number is required.", "customer_id": customer_id}, status=400)

                otp = random.randint(100000, 999999)
                customer.otp = otp
                customer.mobile_no = new_mobile
                customer.save(update_fields=["otp", "mobile_no"])
                send_verify_mobile([new_mobile],otp)

                return JsonResponse({
                    "message": "OTP sent to new mobile number.",
                    "customer_id": customer_id,
                    "new_mobile": new_mobile
                })

            elif action == "verify_new_otp":
                otp = data.get("otp")
                if not otp:
                    return JsonResponse({"error": "OTP is required for verification.", "customer_id": customer_id}, status=400)

                if str(customer.otp) != str(otp):
                    return JsonResponse({"error": "Invalid OTP for new mobile number.", "customer_id": customer_id}, status=400)

                customer.otp = None
                customer.save(update_fields=["otp"])

                return JsonResponse({
                    "message": "New mobile number verified successfully.",
                    "customer_id": customer_id,
                    "new_mobile": customer.mobile_no
                })

            else:
                return JsonResponse({"error": "Invalid action type.", "customer_id": customer_id}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Server error: {str(e)}", "customer_id": customer_id}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=405)


@csrf_exempt
def edit_profile_email_otp_handler(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            action = data.get("action")
            customer_id = data.get("customer_id")

            if not action or not customer_id:
                return JsonResponse({"error": "Action and Customer ID are required.", "customer_id": customer_id}, status=400)

            customer = CustomerRegisterDetails.objects.filter(id=customer_id).first()
            if not customer:
                return JsonResponse({"error": "Customer not found.", "customer_id": customer_id}, status=404)

            if action == "send_previous_otp":
                if not customer.email:
                    return JsonResponse({"error": "Customer does not have a registered email address.", "customer_id": customer_id}, status=400)

                otp = random.randint(100000, 999999)
                customer.otp = otp
                customer.otp_send_type = 'email'
                customer.save(update_fields=["otp", "otp_send_type"])
                send_email_verification_otp_email(customer)

                return JsonResponse({
                    "message": "OTP sent to previous email address.",
                    "customer_id": customer_id
                })

            elif action == "verify_previous_otp":
                otp = data.get("otp")
                if not otp:
                    return JsonResponse({"error": "OTP is required for verification.", "customer_id": customer_id}, status=400)

                if str(customer.otp) != str(otp):
                    return JsonResponse({"error": "Invalid OTP for previous email.", "customer_id": customer_id}, status=400)

                customer.otp = None
                customer.save(update_fields=["otp"])

                return JsonResponse({
                    "message": "Previous email verified.",
                    "customer_id": customer_id,
                    "previous_email": customer.email
                })

            elif action == "send_new_otp":
                new_email = data.get("email")
                if not new_email:
                    return JsonResponse({"error": "New email address is required.", "customer_id": customer_id}, status=400)

                otp = random.randint(100000, 999999)
                customer.otp = otp
                customer.email = new_email
                customer.otp_send_type = 'email'
                customer.save(update_fields=["otp", "email", "otp_send_type"])
                send_email_verification_otp_email(customer)

                return JsonResponse({
                    "message": "OTP sent to new email address.",
                    "customer_id": customer_id,
                    "new_email": new_email
                })

            elif action == "verify_new_otp":
                otp = data.get("otp")
                if not otp:
                    return JsonResponse({"error": "OTP is required for verification.", "customer_id": customer_id}, status=400)

                if str(customer.otp) != str(otp):
                    return JsonResponse({"error": "Invalid OTP for new email address.", "customer_id": customer_id}, status=400)

                customer.otp = None
                customer.save(update_fields=["otp"])

                return JsonResponse({
                    "message": "New email address verified successfully.",
                    "customer_id": customer_id,
                    "new_email": customer.email
                })

            else:
                return JsonResponse({"error": "Invalid action type.", "customer_id": customer_id}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Server error: {str(e)}", "customer_id": customer_id}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=405)

def send_email_verification_otp_email(customer):
    otp = customer.otp
    email = customer.email
    first_name = customer.first_name or 'Customer'
    logo_url = f"{settings.AWS_S3_BUCKET_URL}/static/images/aviation-logo.png"
    subject = "[Pavaman] OTP to Verify Your Email"
    text_content = f"Hello {first_name},\n\nYour OTP for verifying your email is: {otp}"
    
    html_content = f"""
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
            @media only screen and (max-width: 600px) {{
                .container {{
                    width: 90% !important;
                    padding: 20px !important;
                }}
                .logo {{
                    max-width: 180px !important;
                    height: auto !important;
                }}
                .otp {{
                    font-size: 24px !important;
                    padding: 10px 20px !important;
                }}
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Inter', sans-serif; background-color: #f5f5f5;">
        <div class="container" style="margin: 40px auto; background-color: #ffffff; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 40px 30px; max-width: 480px; text-align: left;">
            <div style="text-align: center;">
            <img src="{logo_url}" alt="Pavaman Logo" class="logo" style="max-width: 280px; height: auto; margin-bottom: 20px;" />
            <h2 style="margin-top: 0; color: #222;">Verify Your Email</h2>
            </div>

            <p style="color: #555; margin-bottom: 30px; text-align: left;">
            Hello <strong>{first_name}</strong>,
            </p>

            <p style="color: #555; margin-bottom: 30px;">
                Use the OTP below to verify your email.
            </p>
          
            <p class="otp" style="font-size: 28px; font-weight: bold; color: #4450A2; background: #f2f2f2; display: block; padding: 12px 24px; border-radius: 10px; letter-spacing: 4px; width: fit-content; margin: 0 auto;">
                {otp}
            </p>

            <p style="color: #888; font-size: 14px; margin-top: 20px;">
                If you didn't request this, you can safely ignore this email.<br/>
                You're receiving this because you have an account on Pavaman.
            </p>
            <p style="margin-top: 30px; font-size: 14px; color: #888;">This is an automated email. Please do not reply.</p>
        </div>
    </body>
    </html>
    """

    email_message = EmailMultiAlternatives(
        subject, text_content, settings.DEFAULT_FROM_EMAIL, [email]
    )
    email_message.attach_alternative(html_content, "text/html")
    email_message.send()
@csrf_exempt
def filter_and_sort_products(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))

            category_id = data.get("category_id")
            category_name = data.get("category_name")
            subcategory_id = data.get("sub_category_id")
            sub_category_name = data.get("sub_category_name")
            min_price = data.get("min_price")
            max_price = data.get("max_price")
            sort_by = data.get("sort_by")

            customer_id = data.get("customer_id") or request.session.get('customer_id')

            if not category_id or not category_name:
                return JsonResponse({"error": "category_id and category_name are required.", "status_code": 400}, status=400)

            if not subcategory_id or not sub_category_name:
                return JsonResponse({"error": "sub_category_id and sub_category_name are required.", "status_code": 400}, status=400)

            try:
                category = CategoryDetails.objects.get(id=category_id)
                if category.category_name != category_name:
                    return JsonResponse({"error": "Incorrect category_name for the given category_id.", "status_code": 400}, status=400)
            except CategoryDetails.DoesNotExist:
                return JsonResponse({"error": "Invalid category_id. Category not found.", "status_code": 404}, status=404)

            try:
                subcategory = SubCategoryDetails.objects.get(id=subcategory_id, category_id=category_id, sub_category_status=1)
                if subcategory.sub_category_name != sub_category_name:
                    return JsonResponse({"error": "Incorrect sub_category_name for the given sub_category_id.", "status_code": 400}, status=400)
            except SubCategoryDetails.DoesNotExist:
                return JsonResponse({"error": "Invalid sub_category_id for the given category.", "status_code": 404}, status=404)
            products_query = ProductsDetails.objects.filter(
                category_id=category_id,
                sub_category_id=subcategory_id,
                product_status=1
            ).annotate(
                discounted_price=ExpressionWrapper(
                    F('price') - (F('price') * F('discount') / 100),
                    output_field=FloatField()
                )
            )
            if min_price is not None and isinstance(min_price, (int, float)):
                products_query = products_query.filter(discounted_price__gte=min_price)

            if max_price is not None and isinstance(max_price, (int, float)):
                products_query = products_query.filter(discounted_price__lte=max_price)
            if sort_by == "latest":
                products_query = products_query.order_by("-created_at")
            elif sort_by == "low_to_high":
                products_query = products_query.order_by("discounted_price")
            elif sort_by == "high_to_low":
                products_query = products_query.order_by("-discounted_price")
            else:
                return JsonResponse({"error": "Invalid sort_by value. Use 'latest', 'low_to_high', or 'high_to_low'.", "status_code": 400}, status=400)
            wishlist_product_ids = get_wishlist_product_ids(customer_id)
            products_list = []
            for product in products_query:
                product_images_url = []
                if product.product_images:
                    if isinstance(product.product_images, str):
                        product_images = product.product_images.split(',')
                    elif isinstance(product.product_images, list):
                        product_images = product.product_images
                    else:
                        product_images = []

                    for image in product_images:
                        image_path = image.replace('\\', '/')
                        product_images_url.append(f"{settings.AWS_S3_BUCKET_URL}/{image_path.lstrip('/')}")

                else:
                    product_images_url = []

                product_data = {
                    "product_id": str(product.id),
                    "product_name": product.product_name,
                    "sku_number": product.sku_number,
                    "price": float(product.price),
                    "gst": f"{int(product.gst or 0)}%",
                    "discount": f"{int(product.discount)}%" if product.discount else "0%",
                    "final_price": round(product.discounted_price, 2),
                    "availability": product.availability,
                    "quantity": product.quantity,
                    "description": product.description,
                    "product_image_url": product_images_url,
                    "material_file": product.material_file,
                    "number_of_specifications": product.number_of_specifications,
                    "specifications": product.specifications,
                    "wishlist": product.id in wishlist_product_ids,
                }

                products_list.append(product_data)
            price_range = products_query.aggregate(
                min_price=Min("discounted_price"),
                max_price=Max("discounted_price")
            )

            if price_range["min_price"] is None:
                price_range["min_price"] = min_price if min_price is not None else 0
            if price_range["max_price"] is None:
                price_range["max_price"] = max_price if max_price is not None else 0
            all_categories = CategoryDetails.objects.all()
            all_categories_with_subs = []
            for cat in all_categories:
                subcats = SubCategoryDetails.objects.filter(
                    category_id=cat.id,
                    sub_category_status=1
                ).values("id", "sub_category_name")
                all_categories_with_subs.append({
                    "category_id": cat.id,
                    "category_name": cat.category_name,
                    "subcategories": list(subcats)
                })

            response_data = {
                "message": "Filtered products retrieved successfully.",
                "category_id": category_id,
                "category_name": category.category_name,
                "sub_category_id": subcategory_id,
                "sub_category_name": subcategory.sub_category_name,
                "min_price": price_range["min_price"],
                "max_price": price_range["max_price"],
                "products": products_list,
                "all_categories": all_categories_with_subs,
                "status_code": 200,
            }

            if customer_id:
                response_data["customer_id"] = customer_id

            return JsonResponse(response_data, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format.", "status_code": 400}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Server error: {str(e)}", "status_code": 500}, status=500)

    return JsonResponse({"error": "Invalid request method. Use POST.", "status_code": 405}, status=405)
@csrf_exempt
def submit_feedback_rating(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))

            customer_id = data.get('customer_id')
            product_id = data.get('product_id')
            product_order_id = data.get('product_order_id')
            rating = data.get('rating')
            feedback = data.get('feedback', "")
            if not all([customer_id, product_id, product_order_id]):
                return JsonResponse({
                    "error": "customer_id, product_id, and product_order_id are required.",
                    "status_code": 400
                }, status=400)
            try:
                customer = CustomerRegisterDetails.objects.get(id=customer_id)
                product = ProductsDetails.objects.get(id=product_id)
                admin = product.admin
                payment = PaymentDetails.objects.filter(
                    customer=customer, product_order_id=product_order_id
                ).first()
                if not payment:
                    return JsonResponse({
                        "error": "Payment not found for given product_order_id.",
                        "status_code": 404
                    }, status=404)

                order_product = OrderProducts.objects.filter(
                    id__in=payment.order_product_ids,
                    product=product,
                    customer=customer
                ).first()
                if not order_product:
                    return JsonResponse({
                        "error": "Matching order product not found.",
                        "status_code": 404
                    }, status=404)

            except Exception as e:
                return JsonResponse({
                    "error": f"Related object fetch error: {str(e)}",
                    "status_code": 404
                }, status=404)

            existing_feedback = FeedbackRating.objects.filter(
                customer=customer, product=product, order_product=order_product
            ).first()
            if existing_feedback:
                return JsonResponse({
                    "error": "Feedback already submitted for this product and order.",
                    "status_code": 400
                }, status=400)
            current_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
            FeedbackRating.objects.create(
                admin=admin,
                customer=customer,
                payment=payment,
                order_product=order_product,
                order_id=product_order_id,
                product=product,
                category=product.category if product.category else "",
                sub_category=product.sub_category if product.sub_category else "",
                rating=rating if rating else None,
                feedback=feedback,
                created_at=current_time
            )

            return JsonResponse({
                "message": "Feedback submitted successfully.",
                "status_code": 201,
                "customer_id":customer_id,
                "submitted_at": current_time
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({
                "error": "Invalid JSON format.",
                "status_code": 400
            }, status=400)

        except Exception as e:
            return JsonResponse({
                "error": f"Server error: {str(e)}",
                "status_code": 500
            }, status=500)

    else:
        return JsonResponse({
            "error": "Invalid HTTP method. Only POST allowed.",
            "status_code": 405
        }, status=405)


# @csrf_exempt
# def submit_feedback_rating(request):
#     if request.method == "POST":
#         try:
#             data = json.loads(request.body.decode("utf-8"))

#             customer_id = data.get('customer_id')
#             product_id = data.get('product_id')
#             product_order_id = data.get('product_order_id')
#             rating = data.get('rating')
#             feedback = data.get('feedback', "")
#             if not all([customer_id, product_id, product_order_id]):
#                 return JsonResponse({
#                     "error": "customer_id, product_id, and product_order_id are required.",
#                     "status_code": 400
#                 }, status=400)

#             try:
#                 customer = CustomerRegisterDetails.objects.get(id=customer_id)
#                 product = ProductsDetails.objects.get(id=product_id)
#                 admin = product.admin
#                 payment = PaymentDetails.objects.filter(
#                     customer=customer, product_order_id=product_order_id
#                 ).first()
#                 if not payment:
#                     return JsonResponse({
#                         "error": "Payment not found for given product_order_id.",
#                         "status_code": 404
#                     }, status=404)
#                 order_product = OrderProducts.objects.filter(
#                     id__in=payment.order_product_ids,
#                     product=product,
#                     customer=customer
#                 ).first()
#                 if not order_product:
#                     return JsonResponse({
#                         "error": "Matching order product not found.",
#                         "status_code": 404
#                     }, status=404)

#             except Exception as e:
#                 return JsonResponse({
#                     "error": f"Related object fetch error: {str(e)}",
#                     "status_code": 404
#                 }, status=404)
#             existing_feedback = FeedbackRating.objects.filter(
#                 customer=customer, product=product, order_product=order_product
#             ).first()
#             if existing_feedback:
#                 return JsonResponse({
#                     "error": "Feedback already submitted for this product and order.",
#                     "status_code": 400
#                 }, status=400)
#             current_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
#             FeedbackRating.objects.create(
#                 admin=admin,
#                 customer=customer,
#                 payment=payment,
#                 order_product=order_product,
#                 order_id=product_order_id,
#                 product=product,
#                 category=product.category.category_name if product.category else "",
#                 sub_category=product.sub_category.sub_category_name if product.sub_category else "",
#                 rating=rating if rating else None,
#                 feedback=feedback,
#                 created_at=current_time
#             )
#             return JsonResponse({
#                 "message": "Feedback submitted successfully.",
#                 "status_code": 201,
#                 "customer_id":customer_id,
#                 "submitted_at": current_time
#             }, status=201)

#         except json.JSONDecodeError:
#             return JsonResponse({
#                 "error": "Invalid JSON format.",
#                 "status_code": 400
#             }, status=400)

#         except Exception as e:
#             return JsonResponse({
#                 "error": f"Server error: {str(e)}",
#                 "status_code": 500
#             }, status=500)

#     else:
#         return JsonResponse({
#             "error": "Invalid HTTP method. Only POST allowed.",
#             "status_code": 405
#         }, status=405)

@csrf_exempt
def edit_feedback_rating(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))

            customer_id = data.get('customer_id')
            product_id = data.get('product_id')
            product_order_id = data.get('product_order_id')
            rating = data.get('rating')
            feedback = data.get('feedback')
            if not all([customer_id, product_id, product_order_id]):
                return JsonResponse({
                    "error": "customer_id, product_id, and product_order_id are required.",
                    "status_code": 400
                }, status=400)
            try:
                customer = CustomerRegisterDetails.objects.get(id=customer_id)
                product = ProductsDetails.objects.get(id=product_id)

                payment = PaymentDetails.objects.filter(
                    customer=customer, product_order_id=product_order_id
                ).first()
                if not payment:
                    return JsonResponse({
                        "error": "Payment not found for given product_order_id.",
                        "status_code": 404
                    }, status=404)

                order_product = OrderProducts.objects.filter(
                    id__in=payment.order_product_ids,
                    product=product,
                    customer=customer
                ).first()
                if not order_product:
                    return JsonResponse({
                        "error": "Matching order product not found.",
                        "status_code": 404
                    }, status=404)

            except Exception as e:
                return JsonResponse({
                    "error": f"Related object fetch error: {str(e)}",
                    "status_code": 404
                }, status=404)
            existing_feedback = FeedbackRating.objects.filter(
                customer=customer,
                product=product,
                order_product=order_product
            ).first()

            if not existing_feedback:
                return JsonResponse({
                    "error": "No existing feedback found to update.",
                    "status_code": 404
                }, status=404)
            if rating is not None:
                existing_feedback.rating = rating
            if feedback is not None:
                existing_feedback.feedback = feedback

            existing_feedback.updated_at = datetime.utcnow() + timedelta(hours=5, minutes=30)
            existing_feedback.save()

            return JsonResponse({
                "message": "Feedback updated successfully.",
                "status_code": 200,
                "customer_id": customer_id,
                "updated_at": existing_feedback.updated_at,
                "customer_id":customer_id
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({
                "error": "Invalid JSON format.",
                "status_code": 400
            }, status=400)

        except Exception as e:
            return JsonResponse({
                "error": f"Server error: {str(e)}",
                "status_code": 500
            }, status=500)

    else:
        return JsonResponse({
            "error": "Invalid HTTP method. Only POST allowed.",
            "status_code": 405
        }, status=405)

@csrf_exempt
def view_rating(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))

            customer_id = data.get('customer_id')
            if not customer_id:
                return JsonResponse({
                    "error": "customer_id is required.",
                    "status_code": 400
                }, status=400)
            customer = CustomerRegisterDetails.objects.get(id=customer_id)

            feedbacks = FeedbackRating.objects.filter(customer=customer)

            if not feedbacks.exists():
                return JsonResponse({
                    "error": "No feedback found for this customer.",
                    "status_code": 404
                }, status=404)

            rating_list = []
            for feedback in feedbacks:
                rating_list.append({
                    "rating": feedback.rating,
                    "product_id": feedback.product.id,
                    "product_name": feedback.product.product_name,
                    "order_product_id": feedback.order_product.id,
                    "order_id": feedback.order_id,
                })

            return JsonResponse({
                "ratings": rating_list,
                "customer_id": customer_id,
                "status_code": 200
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({
                "error": "Invalid JSON format.",
                "status_code": 400
            }, status=400)

        except Exception as e:
            return JsonResponse({
                "error": f"Server error: {str(e)}",
                "status_code": 500
            }, status=500)
    else:
        return JsonResponse({
            "error": "Invalid HTTP method. Only POST allowed.",
            "status_code": 405
        }, status=405)

@csrf_exempt
def add_to_wishlist(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))

            customer_id = data.get("customer_id")
            product_id = data.get("product_id")

            if not customer_id or not product_id :
                return JsonResponse({"status": "error", "message": "All fields are required."})
            admin = PavamanAdminDetails.objects.order_by('id').first()
            if not admin:
                return JsonResponse({"error": "No admin found in the system.", "status_code": 500}, status=500)            

            customer = CustomerRegisterDetails.objects.get(id=customer_id)
            product = ProductsDetails.objects.get(id=product_id)

            wishlist_item, created = Wishlist.objects.get_or_create(
                customer=customer, product=product, admin=admin
            )
            
            response_data = {
                "status": "success" if created else "info",
                "message": "Added to wishlist" if created else "Already in wishlist",
                "status_code": 200
            }

            if customer_id:
                response_data["customer_id"] = str(customer_id)

            return JsonResponse(response_data, status=200)

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})
    
    return JsonResponse({"status": "error", "message": "Only POST method allowed"})

@csrf_exempt
def view_wishlist(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            customer_id = data.get("customer_id")

            if not customer_id:
                return JsonResponse({"status": "error", "message": "Customer ID is required."})
            
            wishlist_items = Wishlist.objects.filter(customer_id=customer_id).select_related("product", "product__category", "product__sub_category")

            if not wishlist_items.exists():
                return JsonResponse({
                    "status": "info",
                    "message": "Wishlist is empty.",
                    "data": [],
                    "count": 0,
                    "customer_id": str(customer_id)
                })
            result = []
            for item in wishlist_items:
                product = item.product
                if product.product_images and len(product.product_images) > 0:
                    first_image_path = product.product_images[0].replace('\\', '/').lstrip('/')
                    product_image_url = f"{settings.AWS_S3_BUCKET_URL}/{first_image_path}"
                else:
                    product_image_url = ""
                result.append({
                    "product_id": product.id,
                    "product_name": product.product_name,
                    "price": product.price,
                    "discount": f"{int(product.discount)}%" if product.discount else "0%",
                    "final_price": round(float(product.price) - (float(product.price) * float(product.discount or 0) / 100), 2),
                    "availability": product.availability,
                    "product_image": product_image_url,
                    "category_id": product.category.id if product.category else None,
                    "category_name": product.category.category_name if product.category else "",
                    "subcategory_id": product.sub_category.id if product.sub_category else None,
                    "subcategory_name": product.sub_category.sub_category_name if product.sub_category else "",
                    
                })
            response_data = {
                "status": "success",
                "count": len(result),
                "data": result,
            }
            if customer_id:
                response_data["customer_id"] = str(customer_id)
            return JsonResponse(response_data, status=200)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return JsonResponse({"status": "error", "message": "Only POST method allowed"})

@csrf_exempt
def latest_products_current_year(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            customer_id = data.get("customer_id", None)

            current_year = timezone.now().year
            products = ProductsDetails.objects.filter(
                created_at__year=current_year
            ).order_by('-created_at')[:50]

            wishlist_product_ids = get_wishlist_product_ids(customer_id)
            if not products.exists():
                return JsonResponse({
                    "status": "info",
                    "message": "No products found for the current year.",
                    "data": [],
                    "count": 0,
                    "customer_id": str(customer_id) if customer_id else None
                }, status=200)

            result = []
            for product in products:
                if product.product_images and len(product.product_images) > 0:
                    first_image_path = product.product_images[0].replace('\\', '/').lstrip('/')
                    product_image_url = f"{settings.AWS_S3_BUCKET_URL}/{first_image_path}"
                else:
                    product_image_url = ""

                result.append({
                    "product_id": product.id,
                    "product_name": product.product_name,
                    "price": product.price,
                    "discount": f"{int(product.discount)}%" if product.discount else "0%",
                    "final_price": round(float(product.price) - (float(product.price) * float(product.discount or 0) / 100), 2),
                    "availability": product.availability,
                    "product_image": product_image_url,
                    "created_at": product.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "wishlist": product.id in wishlist_product_ids,
                    "category": product.category.category_name if product.category else None,
                    "sub_category": product.sub_category.sub_category_name if product.sub_category else None,
                    "category_id": product.category_id,
                    "sub_category_id": product.sub_category_id,
                })

            response_data = {
                "status": "success",
                "message": "Latest products for the current year retrieved successfully.",
                "data": result,
                "count": len(result)
            }

            if customer_id:
                response_data["customer_id"] = str(customer_id)

            return JsonResponse(response_data, status=200)

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Only POST method allowed"}, status=405)

@csrf_exempt
def share_product_preview(request, product_id):
    try:
        product = ProductsDetails.objects.get(id=product_id)
    except ProductsDetails.DoesNotExist:
        raise Http404("Product not found")

    product_images = product.product_images
    if isinstance(product_images, list) and product_images:
        product_image_url = f"{settings.AWS_S3_BUCKET_URL}/{product_images[0].replace('\\', '/')}"
    elif isinstance(product_images, str):
        product_image_url = f"{settings.AWS_S3_BUCKET_URL}/{product_images.replace('\\', '/')}"
    else:
        product_image_url = f"{request.scheme}://{request.get_host()}/static/images/default.jpg"

    price = float(product.price or 0)
    discount = float(product.discount or 0)
    final_price = round(price - ((price * discount) / 100), 2)

    product_url = f"{request.scheme}://{request.get_host()}/products/{product.product_name}/"

    short_description = (product.description[:120] + "...") if product.description and len(product.description) > 120 else product.description or "Top quality product from Dronekits Store"

    og_description = f"Take a look at {product.product_name}! Buy it now for just ₹{final_price}. Premium product from Dronekits Store, available now."

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>{product.product_name} - Buy Now at Dronekits Store</title>
        <meta property="og:title" content="{product.product_name} - Buy Now at Dronekits Store" />
        <meta property="og:description" content="{og_description}" />
        <meta property="og:image" content="{product_image_url}" />
        <meta property="og:url" content="{product_url}" />
        <meta property="og:type" content="product" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta http-equiv="refresh" content="2; url={product_url}" />
    </head>
    <body>
        <p>Redirecting to product page...</p>
        <script>
            setTimeout(function () {{
                window.location.href = "{product_url}";
            }}, 2000);
        </script>
    </body>
    </html>
    """


    return HttpResponse(html)