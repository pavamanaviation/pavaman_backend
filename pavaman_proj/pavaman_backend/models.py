from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password
import uuid
from datetime import datetime, timedelta
from django.contrib.postgres.fields import ArrayField 
from django.db.models import JSONField  

class PavamanAdminDetails(models.Model):
    username = models.CharField(max_length=120, unique=True)
    email = models.EmailField(unique=True)
    mobile_no = models.CharField(max_length=15, default='')
    otp = models.IntegerField(null=True, blank=True)
    password = models.CharField(max_length=255)
    status = models.IntegerField(default=1)

    def __str__(self):
        return self.username

class CategoryDetails(models.Model):
    category_name = models.CharField(max_length=120)
    created_at = models.DateTimeField()
    category_image = models.CharField(max_length=120)
    admin = models.ForeignKey(PavamanAdminDetails, on_delete=models.CASCADE)
    category_status = models.IntegerField(default=1)

    def __str__(self):
        return self.category_name

class SubCategoryDetails(models.Model):
    sub_category_name = models.CharField(max_length=120)
    created_at = models.DateTimeField()
    sub_category_image = models.CharField(max_length=120, blank=True, null=True)
    admin = models.ForeignKey(PavamanAdminDetails, on_delete=models.CASCADE)
    category = models.ForeignKey(CategoryDetails, on_delete=models.CASCADE)
    sub_category_status = models.IntegerField(default=1)

    def __str__(self):
        return self.sub_category_name

class ProductsDetails(models.Model):
    product_name = models.CharField(max_length=200)
    sku_number = models.CharField(max_length=100, unique=True)
    hsn_code = models.CharField(max_length=30, default='')
    price = models.FloatField()
    quantity = models.IntegerField(default=0) 
    discount = models.FloatField(default=0.0)
    material_file = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField()
    number_of_specifications = models.IntegerField(default=0)
    specifications = models.JSONField(blank=True, null=True)
    product_images = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField()
    admin = models.ForeignKey(PavamanAdminDetails, on_delete=models.CASCADE)
    category = models.ForeignKey(CategoryDetails, on_delete=models.CASCADE)
    sub_category = models.ForeignKey(SubCategoryDetails, on_delete=models.CASCADE)
    status = models.IntegerField(default=1)
    availability = models.CharField(max_length=50, default="in_stock")
    product_status = models.IntegerField(default=1)
    cart_status = models.BooleanField(default=False)
    gst = models.FloatField(default=0.0)
    hsn_code = models.CharField(max_length=30, default='')

    def __str__(self):
        return self.product_name

class CustomerRegisterDetails(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    mobile_no = models.CharField(max_length=15, default='')
    password = models.CharField(max_length=255,null=True, blank=True)
    status = models.IntegerField(default=1)
    register_status = models.IntegerField(default=0)
    created_on = models.DateTimeField(auto_now_add=True)
    verification_link = models.CharField(max_length=255, null=True, blank=True)
    admin = models.ForeignKey(PavamanAdminDetails, on_delete=models.CASCADE)
    account_status = models.IntegerField(default=0)
    otp = models.IntegerField(null=True, blank=True)
    otp_send_type = models.CharField(max_length=255, null=True, blank=True)
    reset_link = models.CharField(max_length=255, null=True, blank=True)
    changed_on = models.DateTimeField(null=True, blank=True)
    register_type = models.CharField(max_length=20,default='mannual_acc')
    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith("pbkdf2_sha256$"):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)
        
    def is_otp_valid(self):
        """Check if OTP is still valid (within 2 minutes)."""
        if self.changed_on:
            expiry_time = self.changed_on + timedelta(minutes=2)
            return timezone.now() < expiry_time
        return False

    def clear_expired_otp(self):
        """Set OTP and reset_link to NULL if expired."""
        if not self.is_otp_valid():
            self.otp = None
            self.reset_link = None
            self.changed_on = None
            self.save()

    def _str_(self):
        return self.email
 
class CartProducts(models.Model):
    customer = models.ForeignKey(CustomerRegisterDetails, on_delete=models.CASCADE)
    product = models.ForeignKey(ProductsDetails, on_delete=models.CASCADE)
    category = models.ForeignKey(CategoryDetails, on_delete=models.CASCADE)
    sub_category = models.ForeignKey(SubCategoryDetails, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField()
    admin = models.ForeignKey(PavamanAdminDetails, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.customer} - {self.product} ({self.quantity})"

class CustomerAddress(models.Model):
    ADDRESS_TYPE_CHOICES = [
        ('home', 'Home'),
        ('work', 'Work'),
    ]

    customer = models.ForeignKey(CustomerRegisterDetails, on_delete=models.CASCADE, related_name="addresses")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    mobile_number = models.CharField(max_length=15)
    alternate_mobile = models.CharField(max_length=15, blank=True, null=True)
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPE_CHOICES, default='home')
    pincode = models.CharField(max_length=10)
    street = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255,default="")
    village = models.CharField(max_length=255)
    mandal = models.CharField(max_length=255, blank=True, null=True)
    postoffice = models.CharField(max_length=255, blank=True, null=True)
    district = models.CharField(max_length=255, blank=True, null=True,default="")
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    latitude = models.CharField(max_length=100,default="")
    longitude = models.CharField(max_length=100,default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    select_address = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.address_type} ({self.pincode})"
class OrderProducts(models.Model):
    customer = models.ForeignKey(CustomerRegisterDetails, on_delete=models.CASCADE)
    product = models.ForeignKey(ProductsDetails, on_delete=models.CASCADE)
    category = models.ForeignKey(CategoryDetails, on_delete=models.CASCADE)
    sub_category = models.ForeignKey(SubCategoryDetails, on_delete=models.CASCADE) 
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    final_price = models.DecimalField(max_digits=10, decimal_places=2)
    order_status = models.CharField(max_length=50, default='Pending')
    admin = models.ForeignKey(PavamanAdminDetails, on_delete=models.CASCADE)
    shipping_status= models.CharField(default="")
    delivery_status = models.CharField(default="")
    delivery_charge= models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} - {self.product.name}"
    
class PaymentDetails(models.Model):
    admin = models.ForeignKey(PavamanAdminDetails, on_delete=models.CASCADE)
    customer = models.ForeignKey(CustomerRegisterDetails, on_delete=models.CASCADE)
    customer_address = models.ForeignKey(CustomerAddress, on_delete=models.CASCADE)
    category_ids = JSONField(default=list)
    sub_category_ids = JSONField(default=list)
    product_ids = JSONField(default=list)
    order_product_ids = JSONField(default=list)
    razorpay_order_id = models.CharField(max_length=255, unique=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    PAYMENT_TYPE_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
    ]
    PAYMENT_MODE_TYPE_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('card', 'Card'),
    ]
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='online')
    payment_mode = models.CharField(max_length=40, choices=PAYMENT_MODE_TYPE_CHOICES, default='cash')
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    product_order_id = models.CharField(default="")
    invoice_number = models.CharField(default="")
    invoice_date = models.DateTimeField(auto_now_add=True,null=True)
    
    def str(self):
        return f"Order {self.razorpay_order_id} - {self.payment_type} ({self.payment_mode})"

class FeedbackRating(models.Model):
    admin = models.ForeignKey(PavamanAdminDetails, on_delete=models.CASCADE)
    customer = models.ForeignKey(CustomerRegisterDetails, on_delete=models.CASCADE)
    payment = models.ForeignKey(PaymentDetails, on_delete=models.CASCADE)
    order_product = models.ForeignKey(OrderProducts, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=255) 
    product = models.ForeignKey(ProductsDetails, on_delete=models.CASCADE) 
    category = models.ForeignKey(CategoryDetails, on_delete=models.CASCADE)
    sub_category = models.ForeignKey(SubCategoryDetails, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField() 
    feedback = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def str(self):
        return f"Rating {self.rating} by Customer {self.customer.id} for Product {self.product.name}"
