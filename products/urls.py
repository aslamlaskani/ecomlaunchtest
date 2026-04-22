from django.urls import path
from . import views

urlpatterns = [
    # ── Categories ──────────────────────────────────────
    path('categories/', views.CategoryListView.as_view(), name='categories'),
    # Use <int:pk> so frontend can do /categories/5/ with the numeric id
    path('categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category_detail'),

    # ── Products ────────────────────────────────────────
    path('', views.ProductListView.as_view(), name='products'),
    path('featured/', views.FeaturedProductsView.as_view(), name='featured_products'),
    path('new-arrivals/', views.NewArrivalsView.as_view(), name='new_arrivals'),
    path('flash-sale/', views.FlashSaleProductsView.as_view(), name='flash_sale'),
    path('search/', views.SearchProductsView.as_view(), name='search_products'),
    path('create/', views.ProductCreateView.as_view(), name='product_create'),
    path('<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('<int:pk>/update/', views.ProductUpdateView.as_view(), name='product_update'),
    path('images/<int:pk>/delete/', views.ProductImageDeleteView.as_view(), name='image_delete'),

    # ── Reviews ─────────────────────────────────────────
    path('<int:product_id>/reviews/', views.ReviewListCreateView.as_view(), name='reviews'),
]