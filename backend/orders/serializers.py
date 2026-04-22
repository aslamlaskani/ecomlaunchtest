from rest_framework import serializers
from .models import Order, OrderItem, OrderStatusHistory, Coupon
from products.serializers import ProductListSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'product_name',
            'product_image', 'size', 'color',
            'quantity', 'price', 'total_price',
        ]
        read_only_fields = ['id']


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusHistory
        fields = ['id', 'status', 'note', 'created_at']
        read_only_fields = ['id', 'created_at']


class OrderListSerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()
    first_item_image = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status',
            'payment_method', 'first_name', 'last_name',
            'email', 'phone', 'city', 'total',
            'items_count', 'first_item_image',
            'created_at', 'updated_at',
        ]

    def get_items_count(self, obj):
        return obj.items.count()

    def get_first_item_image(self, obj):
        first_item = obj.items.first()
        if first_item:
            return first_item.product_image
        return None


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status',
            'payment_method', 'first_name', 'last_name',
            'email', 'phone', 'address', 'city',
            'province', 'postal_code', 'subtotal',
            'shipping', 'discount', 'total', 'notes',
            'items', 'status_history',
            'created_at', 'updated_at',
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = [
            'payment_method', 'first_name', 'last_name',
            'email', 'phone', 'address', 'city',
            'province', 'postal_code', 'subtotal',
            'shipping', 'discount', 'total',
            'notes', 'items',
        ]

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        user = self.context['request'].user

        order = Order.objects.create(
            user=user if user.is_authenticated else None,
            **validated_data
        )

        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)

        # Create initial status history
        OrderStatusHistory.objects.create(
            order=order,
            status='Pending',
            note='Order placed by customer'
        )

        return order


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    note = serializers.CharField(write_only=True, required=False, default='')

    class Meta:
        model = Order
        fields = ['status', 'note']

    def update(self, instance, validated_data):
        note = validated_data.pop('note', '')
        new_status = validated_data['status']

        instance.status = new_status
        instance.save()

        # Save status history
        OrderStatusHistory.objects.create(
            order=instance,
            status=new_status,
            note=note or f'Status updated to {new_status}'
        )

        return instance


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['id', 'code', 'discount_percent', 'is_active', 'valid_until']


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField()

    def validate_code(self, value):
        from django.utils import timezone
        try:
            coupon = Coupon.objects.get(
                code=value.upper(),
                is_active=True
            )
            if coupon.valid_until and coupon.valid_until < timezone.now():
                raise serializers.ValidationError('Coupon has expired')
            if coupon.used_count >= coupon.max_uses:
                raise serializers.ValidationError('Coupon has reached maximum uses')
            return value.upper()
        except Coupon.DoesNotExist:
            raise serializers.ValidationError('Invalid coupon code')

    def get_coupon(self):
        return Coupon.objects.get(code=self.validated_data['code'])