from rest_framework import serializers
from .models import Category, Product, ProductImage, ProductVariant, Review
from accounts.serializers import UserSerializer


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'children']
        # slug is auto-generated in the view — never required from frontend
        extra_kwargs = {
            'slug':   { 'required': False, 'read_only': False },
            'parent': { 'required': False, 'allow_null': True },
        }

    def get_children(self, obj):
        if obj.children.exists():
            return CategorySerializer(obj.children.all(), many=True).data
        return []


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'image_url', 'is_primary', 'order']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        if obj.image:
            return f'http://127.0.0.1:8000{obj.image.url}'
        return None


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ['id', 'size', 'color', 'stock']


class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'user', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']


class ProductListSerializer(serializers.ModelSerializer):
    images           = ProductImageSerializer(many=True, read_only=True)
    category_name    = serializers.CharField(source='category.name', read_only=True)
    primary_image    = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'price', 'original_price',
            'category', 'category_name', 'badge',
            'stock', 'is_featured', 'is_new_arrival',
            'rating', 'review_count', 'images',
            'primary_image', 'discount_percent',
            'created_at',
        ]

    def get_primary_image(self, obj):
        request = self.context.get('request')
        image = obj.images.filter(is_primary=True).first() or obj.images.first()
        if image and image.image:
            if request:
                return request.build_absolute_uri(image.image.url)
            return f'http://127.0.0.1:8000{image.image.url}'
        return None

    def get_discount_percent(self, obj):
        if obj.original_price and obj.original_price > obj.price:
            return round(((obj.original_price - obj.price) / obj.original_price) * 100)
        return 0


class ProductDetailSerializer(serializers.ModelSerializer):
    images           = ProductImageSerializer(many=True, read_only=True)
    variants         = ProductVariantSerializer(many=True, read_only=True)
    reviews          = ReviewSerializer(many=True, read_only=True)
    category         = CategorySerializer(read_only=True)
    discount_percent = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'original_price',
            'category', 'badge', 'stock', 'is_featured', 'is_new_arrival',
            'rating', 'review_count', 'images', 'variants',
            'reviews', 'discount_percent', 'created_at', 'updated_at',
        ]

    def get_discount_percent(self, obj):
        if obj.original_price and obj.original_price > obj.price:
            return round(((obj.original_price - obj.price) / obj.original_price) * 100)
        return 0


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'original_price',
            'category', 'badge', 'stock', 'is_active',
            'is_featured', 'is_new_arrival',
        ]

    def validate_is_active(self, value):
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value)

    def validate_is_featured(self, value):
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value)

    def validate_is_new_arrival(self, value):
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value)

    def create(self, validated_data):
        return Product.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['rating', 'comment']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Rating must be between 1 and 5')
        return value

    def create(self, validated_data):
        product = self.context['product']
        user    = self.context['request'].user
        review, created = Review.objects.update_or_create(
            product=product,
            user=user,
            defaults=validated_data
        )
        reviews = Review.objects.filter(product=product)
        product.rating       = sum(r.rating for r in reviews) / reviews.count()
        product.review_count = reviews.count()
        product.save()
        return review