from django.urls import path

urlpatterns = []

from . import views

urlpatterns = [
    # Customer
    path('', views.OrderCreateView.as_view(), name='order_create'),
    path('my-orders/', views.MyOrdersView.as_view(), name='my_orders'),
    path('track/', views.OrderTrackView.as_view(), name='order_track'),

    # Coupons
    path('coupons/validate/', views.CouponValidateView.as_view(), name='coupon_validate'),

    # Admin
    path('admin/list/', views.AdminOrderListView.as_view(), name='admin_orders'),
    path('admin/stats/', views.AdminDashboardStatsView.as_view(), name='admin_stats'),
    path('admin/coupons/', views.AdminCouponListCreateView.as_view(), name='admin_coupons'),
    path('admin/coupons/<int:pk>/', views.AdminCouponDetailView.as_view(), name='admin_coupon_detail'),
    path('admin/<str:order_number>/', views.AdminOrderDetailView.as_view(), name='admin_order_detail'),
    path('admin/<str:order_number>/status/', views.AdminOrderStatusUpdateView.as_view(), name='admin_order_status'),
    path('admin/<str:order_number>/cancel/', views.AdminOrderCancelView.as_view(), name='admin_order_cancel'),

    # Must be last
    path('<str:order_number>/', views.OrderDetailView.as_view(), name='order_detail'),
]