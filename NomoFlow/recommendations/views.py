"""
Recommendation API Views
"""
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from core.utils import get_current_merchant
from core.models import Merchant
from .models import Product, Customer, CustomerInteraction
from .services import HybridRecommendationEngine
from .sync_service import SallaSyncService
import json


@require_http_methods(["GET"])
def recommend_for_customer(request, customer_id: int = None):
    """Get product recommendations for a customer"""
    merchant = get_current_merchant(request)
    
    # If no merchant in session, try to get from store_id parameter
    if not merchant:
        store_id = request.GET.get('store_id')
        if store_id:
            try:
                merchant = Merchant.objects.get(salla_merchant_id=store_id)
            except Merchant.DoesNotExist:
                return JsonResponse({'error': 'Store not found'}, status=404)
        else:
            return JsonResponse({'error': 'No merchant selected'}, status=400)
    
    # Get customer ID from query param or path
    if not customer_id:
        customer_id = request.GET.get('customer_id')
        if customer_id:
            try:
                customer_id = int(customer_id)
            except ValueError:
                return JsonResponse({'error': 'Invalid customer_id'}, status=400)
    
    # Get viewed products from query params (can be salla_product_ids)
    viewed_product_ids = []
    viewed_param = request.GET.get('viewed_products', '')
    if viewed_param:
        try:
            # Try to convert to integers (internal IDs)
            viewed_product_ids = [int(pid) for pid in viewed_param.split(',') if pid.strip()]
        except ValueError:
            # If conversion fails, they might be salla_product_ids - try to find products
            salla_ids = [pid.strip() for pid in viewed_param.split(',') if pid.strip()]
            for salla_id in salla_ids:
                try:
                    prod = Product.objects.get(salla_product_id=salla_id, merchant=merchant)
                    viewed_product_ids.append(prod.id)
                except Product.DoesNotExist:
                    pass
    
    # Get customer object if customer_id provided
    customer_obj = None
    if customer_id:
        try:
            customer_obj = Customer.objects.get(id=customer_id, merchant=merchant)
            customer_id = customer_obj.id
        except Customer.DoesNotExist:
            # Try to find by Salla customer ID
            try:
                customer_obj = Customer.objects.get(salla_customer_id=str(customer_id), merchant=merchant)
                customer_id = customer_obj.id
            except Customer.DoesNotExist:
                customer_id = None
    
    # Check if merchant has any products synced
    product_count = Product.objects.filter(merchant=merchant, is_active=True).count()
    if product_count == 0:
        return JsonResponse({
            'customer_id': customer_id,
            'recommendations': [],
            'count': 0,
            'message': 'No products synced yet. Please sync products from Salla first.',
            'error': 'no_products'
        })
    
    # Get recommendations
    engine = HybridRecommendationEngine(merchant.id)
    recommendations = engine.recommend_for_customer(
        customer_id=customer_id,
        viewed_product_ids=viewed_product_ids,
        n=10
    )
    
    # Format response
    products_data = []
    for product_id, score, explanation in recommendations:
        try:
            product = Product.objects.get(id=product_id, merchant=merchant)
            products_data.append({
                'id': product.id,
                'salla_product_id': product.salla_product_id,
                'name': product.name,
                'description': product.description,
                'category': product.category,
                'price': float(product.price) if product.price else None,
                'image_url': product.image_url,
                'url': product.url,
                'score': score,
                'explanation': explanation,
            })
        except Product.DoesNotExist:
            continue
    
    # If no recommendations but products exist, return trending products
    if not products_data and product_count > 0:
        trending = engine.get_trending_products(n=10)
        for product_id, score, explanation in trending:
            try:
                product = Product.objects.get(id=product_id, merchant=merchant)
                products_data.append({
                    'id': product.id,
                    'salla_product_id': product.salla_product_id,
                    'name': product.name,
                    'description': product.description,
                    'category': product.category,
                    'price': float(product.price) if product.price else None,
                    'image_url': product.image_url,
                    'url': product.url,
                    'score': score,
                    'explanation': explanation,
                })
            except Product.DoesNotExist:
                continue
    
    return JsonResponse({
        'customer_id': customer_id,
        'recommendations': products_data,
        'count': len(products_data)
    })


@require_http_methods(["GET"])
def recommend_similar_products(request, product_id: int = None):
    """Get products similar to a given product - accepts salla_product_id or internal id"""
    # Try to get merchant from request
    merchant = get_current_merchant(request)
    
    # If no merchant in session, try to get from store_id parameter
    if not merchant:
        store_id = request.GET.get('store_id')
        if store_id:
            try:
                merchant = Merchant.objects.get(salla_merchant_id=store_id)
            except Merchant.DoesNotExist:
                return JsonResponse({'error': 'Store not found'}, status=404)
        else:
            return JsonResponse({'error': 'No merchant selected'}, status=400)
    
    # Get product_id from URL or query param (could be salla_product_id)
    if not product_id:
        product_id = request.GET.get('product_id')
    
    if not product_id:
        return JsonResponse({'error': 'product_id required'}, status=400)
    
    # Try to find product by salla_product_id first (for external calls)
    product = None
    try:
        product = Product.objects.get(salla_product_id=str(product_id), merchant=merchant)
    except Product.DoesNotExist:
        try:
            # Try as internal ID
            product = Product.objects.get(id=int(product_id), merchant=merchant)
        except (Product.DoesNotExist, ValueError):
            return JsonResponse({'error': 'Product not found'}, status=404)
    
    # Check if merchant has enough products for recommendations
    product_count = Product.objects.filter(merchant=merchant, is_active=True).count()
    if product_count < 2:
        return JsonResponse({
            'product_id': product.id,
            'product_name': product.name,
            'similar_products': [],
            'frequently_bought_together': [],
            'message': 'Not enough products synced. Need at least 2 products for recommendations.',
            'error': 'insufficient_products'
        })
    
    # Get recommendations
    engine = HybridRecommendationEngine(merchant.id)
    recommendations = engine.recommend_similar_products(product.id, n=10)
    
    # Also get frequently bought together
    frequently_bought = engine.get_frequently_bought_together(product.id, n=5)
    
    # Format response
    similar_products = []
    for prod_id, score, explanation in recommendations:
        try:
            prod = Product.objects.get(id=prod_id, merchant=merchant)
            similar_products.append({
                'id': prod.id,
                'salla_product_id': prod.salla_product_id,
                'name': prod.name,
                'description': prod.description,
                'category': prod.category,
                'price': float(prod.price) if prod.price else None,
                'image_url': prod.image_url,
                'url': prod.url,
                'score': score,
                'explanation': explanation,
            })
        except Product.DoesNotExist:
            continue
    
    frequently_bought_products = []
    for prod_id, count, explanation in frequently_bought:
        try:
            prod = Product.objects.get(id=prod_id, merchant=merchant)
            frequently_bought_products.append({
                'id': prod.id,
                'salla_product_id': prod.salla_product_id,
                'name': prod.name,
                'description': prod.description,
                'category': prod.category,
                'price': float(prod.price) if prod.price else None,
                'image_url': prod.image_url,
                'url': prod.url,
                'count': count,
                'explanation': explanation,
            })
        except Product.DoesNotExist:
            continue
    
    # If no similar products but products exist, return trending products
    if not similar_products and product_count >= 2:
        trending = engine.get_trending_products(n=6)
        for prod_id, score, explanation in trending:
            if prod_id != product.id:  # Exclude current product
                try:
                    prod = Product.objects.get(id=prod_id, merchant=merchant)
                    similar_products.append({
                        'id': prod.id,
                        'salla_product_id': prod.salla_product_id,
                        'name': prod.name,
                        'description': prod.description,
                        'category': prod.category,
                        'price': float(prod.price) if prod.price else None,
                        'image_url': prod.image_url,
                        'url': prod.url,
                        'score': score,
                        'explanation': explanation or "Popular product",
                    })
                except Product.DoesNotExist:
                    continue
    
    return JsonResponse({
        'product_id': product.id,
        'product_name': product.name,
        'similar_products': similar_products,
        'frequently_bought_together': frequently_bought_products,
    })


@require_http_methods(["GET"])
def recommend_trending(request):
    """Get trending/popular products"""
    merchant = get_current_merchant(request)
    if not merchant:
        return JsonResponse({'error': 'No merchant selected'}, status=400)
    
    limit = int(request.GET.get('limit', 10))
    
    # Get recommendations
    engine = HybridRecommendationEngine(merchant.id)
    recommendations = engine.get_trending_products(n=limit)
    
    # Format response
    products_data = []
    for product_id, score, explanation in recommendations:
        try:
            product = Product.objects.get(id=product_id, merchant=merchant)
            products_data.append({
                'id': product.id,
                'salla_product_id': product.salla_product_id,
                'name': product.name,
                'description': product.description,
                'category': product.category,
                'price': float(product.price) if product.price else None,
                'image_url': product.image_url,
                'url': product.url,
                'score': score,
                'explanation': explanation,
            })
        except Product.DoesNotExist:
            continue
    
    return JsonResponse({
        'trending_products': products_data,
        'count': len(products_data)
    })


@require_http_methods(["POST"])
@csrf_exempt
def track_interaction(request):
    """Track customer interaction with a product"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    merchant = get_current_merchant(request)
    if not merchant:
        # Try to get merchant from store_id
        store_id = data.get('store_id')
        if store_id:
            try:
                merchant = Merchant.objects.get(salla_merchant_id=store_id)
            except Merchant.DoesNotExist:
                return JsonResponse({'error': 'Store not found'}, status=404)
        else:
            return JsonResponse({'error': 'No merchant selected'}, status=400)
    
    # Get product
    salla_product_id = str(data.get('product_id', ''))
    if not salla_product_id:
        return JsonResponse({'error': 'product_id required'}, status=400)
    
    try:
        product = Product.objects.get(salla_product_id=salla_product_id, merchant=merchant)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    
    # Get customer (optional)
    customer = None
    salla_customer_id = data.get('customer_id')
    if salla_customer_id:
        customer, _ = Customer.objects.get_or_create(
            merchant=merchant,
            salla_customer_id=str(salla_customer_id),
            defaults={'first_seen_at': timezone.now()}
        )
        customer.last_seen_at = timezone.now()
        customer.save()
    
    # Get interaction type
    interaction_type = data.get('interaction_type', CustomerInteraction.VIEW)
    if interaction_type not in [CustomerInteraction.VIEW, CustomerInteraction.CART, CustomerInteraction.PURCHASE]:
        interaction_type = CustomerInteraction.VIEW
    
    # Get session ID
    session_id = data.get('session_id', '')
    
    # Create interaction
    CustomerInteraction.objects.create(
        merchant=merchant,
        customer=customer,
        product=product,
        interaction_type=interaction_type,
        session_id=session_id,
    )
    
    return JsonResponse({'success': True, 'message': 'Interaction tracked'})


@require_http_methods(["POST"])
def sync_products(request):
    """Sync products from Salla API"""
    merchant = get_current_merchant(request)
    if not merchant:
        return JsonResponse({'error': 'No merchant selected'}, status=400)
    
    try:
        sync_service = SallaSyncService(merchant)
        limit = int(request.GET.get('limit', 100))
        synced_count = sync_service.sync_products(limit=limit)
        
        return JsonResponse({
            'success': True,
            'synced_count': synced_count,
            'message': f'Synced {synced_count} products'
        })
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
def sync_orders(request):
    """Sync orders from Salla API"""
    merchant = get_current_merchant(request)
    if not merchant:
        return JsonResponse({'error': 'No merchant selected'}, status=400)
    
    try:
        sync_service = SallaSyncService(merchant)
        limit = int(request.GET.get('limit', 100))
        synced_count = sync_service.sync_orders(limit=limit)
        
        return JsonResponse({
            'success': True,
            'synced_count': synced_count,
            'message': f'Synced {synced_count} orders'
        })
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def widget_snippet(request):
    """Display HTML snippet for Salla store integration - works for any merchant"""
    merchant = get_current_merchant(request)
    
    # Try to get merchant from store_id parameter if not in session
    if not merchant:
        store_id = request.GET.get('store_id')
        if store_id:
            try:
                merchant = Merchant.objects.get(salla_merchant_id=store_id)
            except Merchant.DoesNotExist:
                merchant = None  # Continue without merchant - widget will work anyway
    
    # Build base URL - use request to get current domain
    base_url = request.build_absolute_uri('/').rstrip('/')
    
    # If accessed via ngrok or other proxy, try to get the actual domain
    # This allows the snippet to work regardless of how it's accessed
    context = {
        'merchant': merchant,
        'base_url': base_url,
    }
    return render(request, 'recommendations/salla_snippet.html', context)


@require_http_methods(["GET"])
def widget_snippets(request):
    """Display all three widget snippets on one page"""
    merchant = get_current_merchant(request)
    
    # Try to get merchant from store_id parameter if not in session
    if not merchant:
        store_id = request.GET.get('store_id')
        if store_id:
            try:
                merchant = Merchant.objects.get(salla_merchant_id=store_id)
            except Merchant.DoesNotExist:
                merchant = None
    
    base_url = request.build_absolute_uri('/').rstrip('/')
    
    context = {
        'merchant': merchant,
        'base_url': base_url,
    }
    return render(request, 'recommendations/widget_snippets.html', context)
