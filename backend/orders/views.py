from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count
from .models import Order, OrderItem, OrderStatusHistory, Coupon
from .serializers import (
    OrderListSerializer, OrderDetailSerializer,
    OrderCreateSerializer, OrderStatusUpdateSerializer,
    CouponSerializer, CouponValidateSerializer
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


# ── ORDER VIEWS ──
class OrderCreateView(generics.CreateAPIView):
    serializer_class = OrderCreateSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response({
            'message': 'Order placed successfully',
            'order': OrderDetailSerializer(order).data,
        }, status=status.HTTP_201_CREATED)


class MyOrdersView(generics.ListAPIView):
    serializer_class = OrderListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).prefetch_related('items')


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        order_number = self.kwargs.get('order_number')
        email = self.request.query_params.get('email', '')

        if self.request.user.is_authenticated:
            return get_object_or_404(
                Order,
                order_number=order_number,
                user=self.request.user
            )

        return get_object_or_404(
            Order,
            order_number=order_number,
            email=email
        )


class OrderTrackView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        order_number = request.data.get('order_number', '').strip()
        email = request.data.get('email', '').strip()

        if not order_number or not email:
            return Response(
                {'error': 'Order number and email are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order = Order.objects.get(
                order_number=order_number,
                email__iexact=email
            )
            return Response(OrderDetailSerializer(order).data)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found. Check your order number and email.'},
                status=status.HTTP_404_NOT_FOUND
            )


# ── ADMIN ORDER VIEWS ──
class AdminOrderListView(generics.ListAPIView):
    serializer_class = OrderListSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = Order.objects.all().prefetch_related('items')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                order_number__icontains=search
            ) | queryset.filter(
                first_name__icontains=search
            ) | queryset.filter(
                last_name__icontains=search
            ) | queryset.filter(
                phone__icontains=search
            ) | queryset.filter(
                email__icontains=search
            )
        return queryset


class AdminOrderDetailView(generics.RetrieveAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'order_number'


class AdminOrderStatusUpdateView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number)
        serializer = OrderStatusUpdateSerializer(
            order, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response({
            'message': f'Order status updated to {order.status}',
            'order': OrderDetailSerializer(order).data,
        })


class AdminOrderCancelView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number)
        if order.status == 'Delivered':
            return Response(
                {'error': 'Cannot cancel a delivered order'},
                status=status.HTTP_400_BAD_REQUEST
            )
        order.status = 'Cancelled'
        order.save()
        OrderStatusHistory.objects.create(
            order=order,
            status='Cancelled',
            note=request.data.get('note', 'Order cancelled by admin')
        )
        return Response({
            'message': 'Order cancelled successfully',
            'order': OrderDetailSerializer(order).data,
        })


# ── COUPON VIEWS ──
class CouponValidateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CouponValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        coupon = serializer.get_coupon()
        return Response({
            'valid': True,
            'code': coupon.code,
            'discount_percent': coupon.discount_percent,
            'message': f'{coupon.discount_percent}% discount applied!',
        })


class AdminCouponListCreateView(generics.ListCreateAPIView):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAdminUser]


class AdminCouponDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAdminUser]


# ── DASHBOARD STATS ──
class AdminDashboardStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from products.models import Product

        total_orders = Order.objects.count()
        pending_orders = Order.objects.filter(status='Pending').count()
        confirmed_orders = Order.objects.filter(status='Confirmed').count()
        shipped_orders = Order.objects.filter(status='Shipped').count()
        delivered_orders = Order.objects.filter(status='Delivered').count()
        cancelled_orders = Order.objects.filter(status='Cancelled').count()

        total_revenue = Order.objects.filter(
            status='Delivered'
        ).aggregate(
            total=Sum('total')
        )['total'] or 0

        total_products = Product.objects.filter(is_active=True).count()

        recent_orders = Order.objects.all()[:5]

        return Response({
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'confirmed_orders': confirmed_orders,
            'shipped_orders': shipped_orders,
            'delivered_orders': delivered_orders,
            'cancelled_orders': cancelled_orders,
            'total_revenue': total_revenue,
            'total_products': total_products,
            'recent_orders': OrderListSerializer(recent_orders, many=True).data,
        })