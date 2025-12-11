"""
Salla API Sync Service
Fetches products and orders from Salla API and stores them locally
"""
import requests
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from typing import Optional, List, Dict
from decimal import Decimal

from core.models import Merchant, SallaToken
from core.auth_utils import call_salla_api_with_refresh
from .models import Product, Customer, Order, OrderItem


class SallaSyncService:
    """Service to sync data from Salla API with automatic token refresh"""
    
    def __init__(self, merchant: Merchant):
        self.merchant = merchant
        self.token = SallaToken.objects.filter(merchant=merchant).first()
        if not self.token or not self.token.access_token:
            raise ValueError(f"No valid token for merchant {merchant.name}")
        
        self.base_url = settings.SALLA_API_BASE.rstrip('/')
    
    def sync_products(self, limit: int = 100) -> int:
        """Sync products from Salla API with automatic token refresh"""
        synced_count = 0
        page = 1
        per_page = min(limit, 50)  # Salla API typically limits to 50 per page
        
        while synced_count < limit:
            try:
                url = f"{self.base_url}/products"
                params = {
                    "page": page,
                    "per_page": per_page
                }
                
                response, error_msg = call_salla_api_with_refresh(
                    self.merchant, "GET", url, params=params
                )
                
                if error_msg:
                    print(f"Error fetching products: {error_msg}")
                    # If token refresh failed, merchant needs to reconnect
                    raise ValueError(f"API call failed: {error_msg}")
                
                if response.status_code != 200:
                    print(f"Error fetching products: {response.status_code} - {response.text}")
                    break
                
                data = response.json()
                products_data = data.get('data', [])
                
                if not products_data:
                    break
                
                for product_data in products_data:
                    self._sync_product(product_data)
                    synced_count += 1
                    
                    if synced_count >= limit:
                        break
                
                # Check if there are more pages
                pagination = data.get('pagination', {})
                if not pagination.get('has_next', False):
                    break
                
                page += 1
                
            except Exception as e:
                print(f"Error syncing products: {e}")
                break
        
        return synced_count
    
    def _sync_product(self, product_data: Dict):
        """Sync a single product"""
        salla_product_id = str(product_data.get('id', ''))
        if not salla_product_id:
            return
        
        # Extract product information
        name = product_data.get('name', '')
        description = product_data.get('description', '') or product_data.get('description_ar', '')
        
        # Get category
        category_data = product_data.get('category', {})
        category = category_data.get('name', '') if isinstance(category_data, dict) else ''
        
        # Get tags
        tags = []
        tags_data = product_data.get('tags', [])
        if isinstance(tags_data, list):
            tags = [tag.get('name', '') if isinstance(tag, dict) else str(tag) for tag in tags_data]
        
        # Get price
        price_data = product_data.get('price', {})
        if isinstance(price_data, dict):
            price = Decimal(str(price_data.get('amount', 0)))
        else:
            price = Decimal(str(price_data)) if price_data else None
        
        # Get images
        images = product_data.get('images', [])
        image_url = images[0].get('url', '') if images and isinstance(images[0], dict) else ''
        
        # Get product URL
        url = product_data.get('url', '')
        
        # Get SKU
        sku = product_data.get('sku', '')
        
        # Get status
        status = product_data.get('status', '')
        is_active = status == 'available' or status == 'sale'
        is_available = (product_data.get('quantity') or 0) > 0
        
        # Create or update product
        product, created = Product.objects.update_or_create(
            merchant=self.merchant,
            salla_product_id=salla_product_id,
            defaults={
                'name': name,
                'description': description,
                'category': category,
                'tags': tags,
                'price': price,
                'sku': sku,
                'image_url': image_url,
                'url': url,
                'is_active': is_active,
                'is_available': is_available,
                'synced_at': timezone.now(),
            }
        )
        
        return product
    
    def sync_orders(self, limit: int = 100) -> int:
        """Sync orders from Salla API with automatic token refresh"""
        synced_count = 0
        page = 1
        per_page = min(limit, 50)
        
        while synced_count < limit:
            try:
                url = f"{self.base_url}/orders"
                params = {
                    "page": page,
                    "per_page": per_page
                }
                
                response, error_msg = call_salla_api_with_refresh(
                    self.merchant, "GET", url, params=params
                )
                
                if error_msg:
                    print(f"Error fetching orders: {error_msg}")
                    # If token refresh failed, merchant needs to reconnect
                    raise ValueError(f"API call failed: {error_msg}")
                
                if response.status_code != 200:
                    print(f"Error fetching orders: {response.status_code} - {response.text}")
                    break
                
                data = response.json()
                orders_data = data.get('data', [])
                
                if not orders_data:
                    break
                
                for order_data in orders_data:
                    self._sync_order(order_data)
                    synced_count += 1
                    
                    if synced_count >= limit:
                        break
                
                # Check if there are more pages
                pagination = data.get('pagination', {})
                if not pagination.get('has_next', False):
                    break
                
                page += 1
                
            except Exception as e:
                print(f"Error syncing orders: {e}")
                break
        
        return synced_count
    
    def _sync_order(self, order_data: Dict):
        """Sync a single order"""
        salla_order_id = str(order_data.get('id', ''))
        if not salla_order_id:
            return
        
        # Get customer information
        customer_data = order_data.get('customer', {})
        customer = None
        if customer_data:
            salla_customer_id = str(customer_data.get('id', ''))
            if salla_customer_id:
                customer, _ = Customer.objects.get_or_create(
                    merchant=self.merchant,
                    salla_customer_id=salla_customer_id,
                    defaults={
                        'name': customer_data.get('name', ''),
                        'email': customer_data.get('email', ''),
                        'phone': customer_data.get('mobile', ''),
                        'first_seen_at': timezone.now(),
                    }
                )
                customer.last_seen_at = timezone.now()
                customer.save()
        
        # Get order details
        total_amount = Decimal(str(order_data.get('amounts', {}).get('total', {}).get('amount', 0)))
        status = order_data.get('status', '')
        
        # Get order date
        created_at_str = order_data.get('created_at', '')
        ordered_at = None
        if created_at_str:
            try:
                # Try parsing ISO format datetime string
                from datetime import datetime
                ordered_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                if timezone.is_naive(ordered_at):
                    ordered_at = timezone.make_aware(ordered_at)
            except:
                ordered_at = timezone.now()
        else:
            ordered_at = timezone.now()
        
        # Create or update order
        order, _ = Order.objects.update_or_create(
            merchant=self.merchant,
            salla_order_id=salla_order_id,
            defaults={
                'customer': customer,
                'total_amount': total_amount,
                'status': status,
                'ordered_at': ordered_at,
            }
        )
        
        # Sync order items
        items_data = order_data.get('products', [])
        for item_data in items_data:
            salla_product_id = str(item_data.get('product', {}).get('id', '')) if isinstance(item_data.get('product'), dict) else str(item_data.get('product_id', ''))
            
            product = None
            if salla_product_id:
                product = Product.objects.filter(
                    merchant=self.merchant,
                    salla_product_id=salla_product_id
                ).first()
            
            quantity = int(item_data.get('quantity', 1))
            price_data = item_data.get('price', {})
            if isinstance(price_data, dict):
                price = Decimal(str(price_data.get('amount', 0)))
            else:
                price = Decimal(str(price_data)) if price_data else Decimal('0')
            
            product_name = item_data.get('name', '')
            
            OrderItem.objects.update_or_create(
                order=order,
                salla_product_id=salla_product_id,
                defaults={
                    'product': product,
                    'quantity': quantity,
                    'price': price,
                    'product_name': product_name,
                }
            )
        
        return order

