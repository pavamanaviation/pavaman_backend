"""
URL configuration for pavaman_proj project.

The urlpatterns list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from pavaman_backend.views import (add_admin,admin_login,admin_logout,
    add_category,view_categories,edit_category,delete_category,
    add_subcategory,view_subcategories,edit_subcategory,delete_subcategory,
    add_product,add_product_specifications,edit_product_specifications,view_products,
    view_product_details,edit_product,delete_product,retrieve_feedback,
    search_categories,search_subcategories,search_products,download_discount_products_excel,
    apply_discount_by_subcategory_only,order_or_delivery_status,admin_verify_otp,
    report_inventory_summary,top_buyers_report,
    monthly_product_orders,download_feedback_excel,download_average_rating_excel,
    product_discount_inventory_view,download_inventory_products_excel,upload_products_excel
    )
from pavaman_backend.customer_views import (customer_register,customer_login,view_categories_and_discounted_products,
    view_sub_categories_and_discounted_products,
    view_products_details,add_product_to_cart,view_product_cart,delete_product_cart,delete_selected_products_cart,add_customer_address,
    view_customer_address,edit_customer_address,delete_customer_address,order_multiple_products,multiple_order_summary
    ,cancel_multiple_orders,filter_product_price_each_category,sort_products_inside_subcategory,
    get_customer_details_by_admin,verify_email,resend_verification_email,google_login,update_cart_quantity,
    google_submit_mobile,otp_generate,verify_otp,set_new_password,filter_and_sort_products_each_subcategory,
    create_razorpay_order,razorpay_callback,customer_search_categories,customer_search_subcategories,customer_search_products,
    get_payment_details_by_order, download_material_file,customer_get_payment_details_by_order,customer_logout,
    report_monthly_revenue_by_year,report_sales_summary, edit_customer_profile,get_customer_profile,
    top_five_selling_products,get_all_category_subcategory,not_selling_products,filter_my_order,
    generate_invoice_for_customer,admin_order_status,customer_cart_view_search,edit_profile_mobile_otp_handler,
    edit_profile_email_otp_handler,filter_and_sort_products,submit_feedback_rating,edit_feedback_rating,view_rating,
    add_to_wishlist,view_wishlist,latest_products_current_year,view_products_by_category_and_subcategory
)
from django.conf.urls.static import static
from django.conf import settings
urlpatterns = [
    path('admin/', admin.site.urls),
    path('add-admin',add_admin,name='add_admin'),
    path('admin-login',admin_login,name='admin_login'),
    path('admin-verify-otp',admin_verify_otp,name='admin_verify_otp'),
    path('admin-logout',admin_logout,name='admin_logout'),
    path('add-category', add_category, name='add_category'),
    path('view-categories', view_categories, name='view_categories'),
    path('edit-category',edit_category,name='edit_category'),
    path('delete-category',delete_category,name='delete_category'),

    path('add-subcategory', add_subcategory, name='add_subcategory'),
    path('view-subcategories', view_subcategories, name='view_subcategories'),
    path('edit-subcategory',edit_subcategory,name='edit_subcategory'),
    path('delete-subcategory',delete_subcategory,name='delete_subcategory'),

    path('add-product',add_product,name='add_product'),
    path('add-product-specifications',add_product_specifications,name='add_product_specifications'),
    path('edit-product-specifications',edit_product_specifications,name='edit_product_specifications'),
    path('view-products',view_products,name='view_products'),
    path('view-product-details',view_product_details,name='view_product_details'),
    path('edit-product',edit_product,name='edit_product'),
    path('delete-product',delete_product,name='delete_product'),
    path('search-categories',search_categories,name='search_categories'),
    path('search-subcategories',search_subcategories,name='search_subcategories'),
    path('search-products',search_products,name='search_products'),
    path('retrieve-feedback',retrieve_feedback,name= 'retrieve_feedback'),
    path('download-feedback-excel',download_feedback_excel,name= 'download_feedback_excel'),

    path('customer-register', customer_register, name='customer_register'), 
    path('customer-login',customer_login,name='customer_login'), 
    path("google-login", google_login, name="google_login"),
    path('verify-email/<str:verification_link>/',verify_email, name='verify_email'),
    path('resend-verification-email',resend_verification_email, name='resend_verification_email'),
    path('google-submit-mobile',google_submit_mobile,name='google_submit_mobile'),
    path('otp-generate',otp_generate,name='otp_generate'),
    path('verify-otp',verify_otp,name='verify_otp'),
    path("set-new-password", set_new_password, name="set_new_password"),
    path('',view_categories_and_discounted_products,name='view_categories_and_discounted_products'),
    path('categories/view-sub-categories/', view_sub_categories_and_discounted_products, name='view_sub_categories_and_discounted_products'),
    # path('categories/<str:category_name>/<str:sub_category_name>/',view_products_by_category_and_subcategory,name='view_products_by_category_and_subcategory'),
    path('products/<str:product_name>/', view_products_details, name='view_products_details'),
    path('add-cart-product',add_product_to_cart,name='add_product_to_cart'),
    path('view-cart-products',view_product_cart,name='view_product_cart'),
    path('update-cart-quantity',update_cart_quantity,name='update_cart_quantity'),
    path('delete-cart-product',delete_product_cart,name='delete_product_cart'),
    path('delete-selected-products-cart',delete_selected_products_cart,name='delete_selected_products_cart'),
    path('add-customer-address',add_customer_address,name='add_customer_address'),
    path('view-customer-address',view_customer_address,name='view_customer_address'),
    path('edit-customer-address',edit_customer_address,name='edit_customer_address'),
    path('delete-customer-address',delete_customer_address,name='delete_customer_address'),
    path('products/order-multiple-products',order_multiple_products,name='order_multiple_products'),
    path('products/order-multiple-products-summary',multiple_order_summary,name='multiple_order_summary'),
    path('products/cancel-multiple-orders',cancel_multiple_orders,name='cancel_multiple_orders'),
    path('filter-product-price-each-category',filter_product_price_each_category,name= 'filter_product_price_each_category'),
    path('sort-products-inside-subcategory',sort_products_inside_subcategory,name= 'sort_products_inside_subcategory'),
    path("get-customer-by-admin/", get_customer_details_by_admin, name="get_customer_details_by_admin"),
    path('create-razorpay-order',create_razorpay_order,name= 'create_razorpay_order'),
    path("razorpay-callback", razorpay_callback, name="razorpay_callback"),
    path("customer-search-categories",customer_search_categories, name="customer_search_categories"),
    path("customer-search-subcategories",customer_search_subcategories, name="customer_search_subcategories"),
    path("customer-search-products",customer_search_products, name="customer_search_products"),
    path("get-payment-details-by-order",get_payment_details_by_order, name="get_payment_details_by_order"),
    path("customer-my-order",customer_get_payment_details_by_order, name="customer_get_payment_details_by_order"),
    path('download-material/<int:product_id>/', download_material_file, name='download_material'),
    path('edit-customer-profile', edit_customer_profile, name='edit_customer_profile'),
    path('get-customer-profile', get_customer_profile, name='get_customer_profile'),
    path("report-sales-summary",report_sales_summary, name="report_sales_summary"),
    path("report-monthly-revenue-by-year",report_monthly_revenue_by_year, name="report_monthly_revenue_by_year"),    
    path("top-five-selling-products",top_five_selling_products, name="top_five_selling_products"),
    path("get-all-category-subcategory",get_all_category_subcategory, name="get_all_category_subcategory"),
    path("not-selling-products",not_selling_products, name="not_selling_products"),
    path("generate-invoice-for-customer",generate_invoice_for_customer, name="generate_invoice_for_customer"),
    path("order-status-summary",admin_order_status, name="admin_order_status"),
    path('customer-cart-view-search', customer_cart_view_search, name='customer_cart_view_search'),
   
    path('edit-profile-mobile', edit_profile_mobile_otp_handler, name='edit_profile_mobile_otp_handler'),
    path('edit-profile-email',edit_profile_email_otp_handler,name= 'edit_profile_email_otp_handler'),
    path('filter-and-sort-products',filter_and_sort_products,name= 'filter_and_sort_products'),    
    path('download-discount-products-excel',download_discount_products_excel,name= 'download_discount_products_excel'),
    path('apply-discount-subcategory',apply_discount_by_subcategory_only,name= 'apply_discount_by_subcategory_only'),
    path('submit-feedback-rating',submit_feedback_rating,name= 'submit_feedback_rating'),
    path('order-or-delivery-status',order_or_delivery_status,name= 'order_or_delivery_status'),
    path('filter-my-order',filter_my_order,name= 'filter_my_order'),
    path('edit-feedback-rating',edit_feedback_rating,name= 'edit_feedback_rating'),
    path('view-rating',view_rating,name= 'view_rating'),
    path('report-inventory-summary',report_inventory_summary,name= 'report_inventory_summary'),
    path('top-buyers-report',top_buyers_report,name= 'top_buyers_report'),
    path('monthly-product-orders',monthly_product_orders,name= 'monthly_product_orders'),
    path('download-feedback-excel',download_feedback_excel,name= 'download_feedback_excel'),
    path('product-discount-inventory-view',product_discount_inventory_view,name= 'product_discount_inventory_view'),
    path('download-inventory-products-excel',download_inventory_products_excel,name= 'download_inventory_products_excel'),
    path('download-average-rating-excel',download_average_rating_excel,name= 'download_average_rating_excel'),
    path('upload-products-excel',upload_products_excel,name= 'upload_products_excel'),
    path('filter_and_sort_products_each_subcategory',filter_and_sort_products_each_subcategory,name= 'filter_and_sort_products_each_subcategory'),
    path('add-to-wishlist',add_to_wishlist,name= 'add_to_wishlist'),
    path('view-wishlist',view_wishlist,name= 'view_wishlist'),
    path('latest-products', latest_products_current_year, name='latest_products_current_year'),
    path('view-products-by-category-and-subcategory',view_products_by_category_and_subcategory,name='view_products_by_category_and_subcategory')

]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
