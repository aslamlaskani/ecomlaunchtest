from rest_framework import generics, status, permissions, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils.text import slugify
from .models import Category, Product, ProductImage, ProductVariant, Review
from .serializers import (
    CategorySerializer, ProductListSerializer, ProductDetailSerializer,
    ProductCreateUpdateSerializer, ReviewSerializer, ReviewCreateSerializer,
    ProductImageSerializer, ProductVariantSerializer
)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


# ── CATEGORIES ──────────────────────────────────────────────────

class CategoryListView(generics.ListCreateAPIView):
    queryset = Category.objects.filter(parent=None).order_by('id')
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        """Auto-generate slug from name so frontend doesn't need to send it."""
        name = self.request.data.get('name', '')
        slug = slugify(name)
        # make slug unique
        base_slug = slug
        counter = 1
        while Category.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1
        serializer.save(slug=slug)


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Lookup by PK (integer id) — NOT slug.
    Frontend sends /api/products/categories/5/ which matches <int:pk>.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    # default lookup_field is 'pk' — do NOT override to 'slug'

    def perform_update(self, serializer):
        """Re-generate slug if name changed."""
        name = self.request.data.get('name')
        if name:
            slug = slugify(name)
            base_slug = slug
            counter = 1
            instance = self.get_object()
            while Category.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            serializer.save(slug=slug)
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Check if category has active products
        if instance.products.filter(is_active=True).exists():
            return Response(
                {'error': 'Cannot delete — this category has active products.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.delete()
        return Response({'message': 'Category deleted'}, status=status.HTTP_200_OK)


# ── PRODUCTS ────────────────────────────────────────────────────

class ProductListView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'badge', 'is_featured', 'is_new_arrival']
    search_fields = ['name', 'description', 'category__name']
    ordering_fields = ['price', 'rating', 'created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).prefetch_related('images')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        flash_sale = self.request.query_params.get('flash_sale')
        if flash_sale:
            queryset = queryset.filter(badge='sale')
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


def get_list_from_request(request, key):
    if hasattr(request.data, 'getlist'):
        return request.data.getlist(key)
    value = request.data.get(key, [])
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        return [value]
    return []


class ProductCreateView(generics.CreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductCreateUpdateSerializer
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()

        images = (
            request.FILES.getlist('images') or
            request.FILES.getlist('image') or
            list(request.FILES.values())
        )
        for i, image in enumerate(images):
            ProductImage.objects.create(
                product=product, image=image,
                is_primary=(i == 0), order=i
            )
        if product.images.exists() and not product.images.filter(is_primary=True).exists():
            first = product.images.first()
            first.is_primary = True
            first.save()

        sizes = get_list_from_request(request, 'sizes')
        for size in sizes:
            if size:
                ProductVariant.objects.create(
                    product=product, size=size,
                    stock=request.data.get('stock', 0)
                )

        colors = get_list_from_request(request, 'colors')
        for i, color in enumerate(colors):
            if color:
                if i < len(sizes):
                    variant = ProductVariant.objects.filter(
                        product=product, size=sizes[i]
                    ).first()
                    if variant:
                        variant.color = color
                        variant.save()
                        continue
                ProductVariant.objects.create(
                    product=product, color=color,
                    stock=request.data.get('stock', 0)
                )

        return Response(
            ProductDetailSerializer(product, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class ProductUpdateView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductCreateUpdateSerializer
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()

        images = (
            request.FILES.getlist('images') or
            request.FILES.getlist('image') or
            list(request.FILES.values())
        )
        if images:
            for i, image in enumerate(images):
                ProductImage.objects.create(
                    product=product, image=image,
                    is_primary=(i == 0 and not product.images.filter(is_primary=True).exists()),
                    order=product.images.count() + i
                )
        if product.images.exists() and not product.images.filter(is_primary=True).exists():
            first = product.images.first()
            first.is_primary = True
            first.save()

        sizes = get_list_from_request(request, 'sizes')
        if sizes:
            product.variants.all().delete()
            for size in sizes:
                if size:
                    ProductVariant.objects.create(
                        product=product, size=size,
                        stock=request.data.get('stock', product.stock)
                    )

        colors = get_list_from_request(request, 'colors')
        if colors:
            for color in colors:
                if color:
                    variant = product.variants.filter(color='').first()
                    if variant:
                        variant.color = color
                        variant.save()
                    else:
                        ProductVariant.objects.create(
                            product=product, color=color,
                            stock=request.data.get('stock', product.stock)
                        )

        return Response(
            ProductDetailSerializer(product, context={'request': request}).data
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response({'message': 'Product deleted'}, status=status.HTTP_200_OK)


class ProductImageDeleteView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def delete(self, request, pk):
        try:
            image = ProductImage.objects.get(pk=pk)
            image.image.delete()
            image.delete()
            return Response({'message': 'Image deleted'}, status=status.HTTP_200_OK)
        except ProductImage.DoesNotExist:
            return Response({'error': 'Image not found'}, status=status.HTTP_404_NOT_FOUND)


class FeaturedProductsView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Product.objects.filter(
            is_active=True, is_featured=True
        ).prefetch_related('images')[:8]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class NewArrivalsView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Product.objects.filter(
            is_active=True, is_new_arrival=True
        ).prefetch_related('images')[:8]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class FlashSaleProductsView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Product.objects.filter(
            is_active=True, badge='sale'
        ).prefetch_related('images')[:20]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class SearchProductsView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        query = (
            self.request.query_params.get('q', '') or
            self.request.query_params.get('search', '')
        )
        if not query:
            return Product.objects.none()
        return Product.objects.filter(is_active=True).filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query) |
            Q(badge__icontains=query)
        ).prefetch_related('images')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class ReviewListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request, product_id):
        reviews = Review.objects.filter(product_id=product_id)
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    def post(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ReviewCreateSerializer(
            data=request.data,
            context={'request': request, 'product': product}
        )
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)