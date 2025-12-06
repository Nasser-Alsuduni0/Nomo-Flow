"""
Recommendation Engine Services
Implements Collaborative Filtering and Content-Based Filtering
"""
try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_ML_LIBS = True
except ImportError:
    HAS_ML_LIBS = False
    # Dummy classes for when libraries aren't installed
    class np:
        @staticmethod
        def zeros(*args, **kwargs):
            raise ImportError("numpy is required. Install with: pip install numpy")
        @staticmethod
        def argsort(*args, **kwargs):
            raise ImportError("numpy is required. Install with: pip install numpy")
    
    class TfidfVectorizer:
        def __init__(self, *args, **kwargs):
            raise ImportError("scikit-learn is required. Install with: pip install scikit-learn")
    
    def cosine_similarity(*args, **kwargs):
        raise ImportError("scikit-learn is required. Install with: pip install scikit-learn")

from collections import defaultdict
from django.db.models import Count, Q
from typing import List, Dict, Optional, Tuple

from .models import Product, Customer, Order, OrderItem, CustomerInteraction


class CollaborativeFilteringEngine:
    """User-User Collaborative Filtering"""
    
    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id
        self.interaction_matrix = None
        self.customer_ids = []
        self.product_ids = []
        self.customer_index_map = {}
        self.product_index_map = {}
    
    def _build_interaction_matrix(self):
        """Build customer × product interaction matrix"""
        if not HAS_ML_LIBS:
            raise ImportError("numpy and scikit-learn are required. Install with: pip install numpy scikit-learn")
        
        # Get all customers and products for this merchant
        customers = Customer.objects.filter(merchant_id=self.merchant_id).values_list('id', flat=True)
        products = Product.objects.filter(merchant_id=self.merchant_id, is_active=True).values_list('id', flat=True)
        
        self.customer_ids = list(customers)
        self.product_ids = list(products)
        
        # Create index maps
        self.customer_index_map = {cid: idx for idx, cid in enumerate(self.customer_ids)}
        self.product_index_map = {pid: idx for idx, pid in enumerate(self.product_ids)}
        
        if not self.customer_ids or not self.product_ids:
            return None
        
        # Initialize matrix with zeros
        matrix = np.zeros((len(self.customer_ids), len(self.product_ids)))
        
        # Fill matrix with interaction scores
        # Purchase = 1.0, Add to Cart = 0.5, View = 0.2
        interactions = CustomerInteraction.objects.filter(
            merchant_id=self.merchant_id,
            customer_id__in=self.customer_ids,
            product_id__in=self.product_ids
        ).select_related('customer', 'product')
        
        for interaction in interactions:
            customer_idx = self.customer_index_map.get(interaction.customer_id)
            product_idx = self.product_index_map.get(interaction.product_id)
            
            if customer_idx is not None and product_idx is not None:
                if interaction.interaction_type == CustomerInteraction.PURCHASE:
                    score = 1.0
                elif interaction.interaction_type == CustomerInteraction.CART:
                    score = 0.5
                else:  # VIEW
                    score = 0.2
                
                # Use max to handle multiple interactions (e.g., view then purchase)
                matrix[customer_idx, product_idx] = max(matrix[customer_idx, product_idx], score)
        
        # Also add order data (purchases)
        order_items = OrderItem.objects.filter(
            order__merchant_id=self.merchant_id,
            order__customer_id__in=self.customer_ids,
            product_id__in=self.product_ids
        ).select_related('order', 'product')
        
        for item in order_items:
            if item.order.customer_id and item.product_id:
                customer_idx = self.customer_index_map.get(item.order.customer_id)
                product_idx = self.product_index_map.get(item.product_id)
                
                if customer_idx is not None and product_idx is not None:
                    matrix[customer_idx, product_idx] = 1.0  # Purchase is always 1.0
        
        self.interaction_matrix = matrix
        return matrix
    
    def get_similar_customers(self, customer_id: int, n: int = 10) -> List[Tuple[int, float]]:
        """Find customers similar to the given customer"""
        if self.interaction_matrix is None:
            self._build_interaction_matrix()
        
        if self.interaction_matrix is None or customer_id not in self.customer_index_map:
            return []
        
        customer_idx = self.customer_index_map[customer_id]
        customer_vector = self.interaction_matrix[customer_idx:customer_idx+1]
        
        # Calculate cosine similarity with all other customers
        similarities = cosine_similarity(customer_vector, self.interaction_matrix)[0]
        
        # Get top N similar customers (excluding self)
        similar_indices = np.argsort(similarities)[::-1]
        similar_customers = []
        
        for idx in similar_indices:
            if idx != customer_idx and similarities[idx] > 0:
                similar_customers.append((self.customer_ids[idx], float(similarities[idx])))
                if len(similar_customers) >= n:
                    break
        
        return similar_customers
    
    def recommend_for_customer(self, customer_id: int, n: int = 10) -> List[Tuple[int, float]]:
        """Recommend products for a customer using collaborative filtering"""
        if self.interaction_matrix is None:
            self._build_interaction_matrix()
        
        if self.interaction_matrix is None or customer_id not in self.customer_index_map:
            return []
        
        customer_idx = self.customer_index_map[customer_id]
        customer_vector = self.interaction_matrix[customer_idx]
        
        # Find similar customers
        similar_customers = self.get_similar_customers(customer_id, n=50)
        
        if not similar_customers:
            return []
        
        # Aggregate recommendations from similar customers
        product_scores = defaultdict(float)
        
        for similar_customer_id, similarity_score in similar_customers:
            similar_customer_idx = self.customer_index_map[similar_customer_id]
            similar_customer_vector = self.interaction_matrix[similar_customer_idx]
            
            # Recommend products that similar customer liked but current customer hasn't tried
            for product_idx, interaction_score in enumerate(similar_customer_vector):
                if interaction_score > 0 and customer_vector[product_idx] == 0:
                    product_scores[self.product_ids[product_idx]] += similarity_score * interaction_score
        
        # Sort by score and return top N
        recommendations = sorted(product_scores.items(), key=lambda x: x[1], reverse=True)[:n]
        return recommendations


class ContentBasedEngine:
    """Content-Based Filtering using TF-IDF"""
    
    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id
        self.vectorizer = None
        self.product_vectors = None
        self.product_ids = []
        self.product_index_map = {}
    
    def _build_product_vectors(self):
        """Build TF-IDF vectors for products"""
        if not HAS_ML_LIBS:
            raise ImportError("scikit-learn is required. Install with: pip install scikit-learn")
        
        products = Product.objects.filter(
            merchant_id=self.merchant_id,
            is_active=True
        ).exclude(
            Q(description__isnull=True) | Q(description='')
        )
        
        if not products.exists():
            return None
        
        self.product_ids = [p.id for p in products]
        self.product_index_map = {pid: idx for idx, pid in enumerate(self.product_ids)}
        
        # Combine name, description, category, and tags into text
        product_texts = []
        for product in products:
            text_parts = [product.name or '']
            if product.description:
                text_parts.append(product.description)
            if product.category:
                text_parts.append(product.category)
            if product.tags:
                text_parts.extend(product.tags)
            
            product_texts.append(' '.join(text_parts))
        
        # Build TF-IDF vectors
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=1000,
            ngram_range=(1, 2)
        )
        
        try:
            self.product_vectors = self.vectorizer.fit_transform(product_texts)
        except Exception as e:
            print(f"Error building TF-IDF vectors: {e}")
            return None
        
        return self.product_vectors
    
    def recommend_similar_products(self, product_id: int, n: int = 10) -> List[Tuple[int, float]]:
        """Find products similar to the given product"""
        if self.product_vectors is None:
            self._build_product_vectors()
        
        if self.product_vectors is None:
            # Fallback: return any other products
            from django.db.models import Count
            other_products = Product.objects.filter(
                merchant_id=self.merchant_id,
                is_active=True
            ).exclude(id=product_id).annotate(
                interaction_count=Count('interactions')
            ).order_by('-interaction_count')[:n]
            
            return [(p.id, float(p.interaction_count or 0)) for p in other_products]
        
        if product_id not in self.product_index_map:
            # Product not in TF-IDF matrix, return other products
            from django.db.models import Count
            other_products = Product.objects.filter(
                merchant_id=self.merchant_id,
                is_active=True
            ).exclude(id=product_id).annotate(
                interaction_count=Count('interactions')
            ).order_by('-interaction_count')[:n]
            
            return [(p.id, float(p.interaction_count or 0)) for p in other_products]
        
        product_idx = self.product_index_map[product_id]
        product_vector = self.product_vectors[product_idx:product_idx+1]
        
        # Calculate cosine similarity with all products
        similarities = cosine_similarity(product_vector, self.product_vectors)[0]
        
        # Get top N similar products (excluding self)
        similar_indices = np.argsort(similarities)[::-1]
        recommendations = []
        
        for idx in similar_indices:
            if idx != product_idx and similarities[idx] > 0:
                recommendations.append((self.product_ids[idx], float(similarities[idx])))
                if len(recommendations) >= n:
                    break
        
        return recommendations
    
    def recommend_for_new_customer(self, viewed_product_ids: List[int], n: int = 10) -> List[Tuple[int, float]]:
        """Recommend products for a new customer based on viewed products"""
        if self.product_vectors is None:
            self._build_product_vectors()
        
        if self.product_vectors is None:
            return []
        
        # If no viewed products, return trending/popular products
        if not viewed_product_ids:
            # Return products with most interactions or orders
            from django.db.models import Count
            popular = Product.objects.filter(
                merchant_id=self.merchant_id,
                is_active=True
            ).annotate(
                interaction_count=Count('interactions')
            ).order_by('-interaction_count')[:n]
            
            return [(p.id, float(p.interaction_count or 0), 'Popular product') for p in popular]
        
        # Aggregate vectors from viewed products
        viewed_indices = [self.product_index_map[pid] for pid in viewed_product_ids if pid in self.product_index_map]
        
        if not viewed_indices:
            # Fallback to trending if viewed products not found
            from django.db.models import Count
            popular = Product.objects.filter(
                merchant_id=self.merchant_id,
                is_active=True
            ).annotate(
                interaction_count=Count('interactions')
            ).order_by('-interaction_count')[:n]
            
            return [(p.id, float(p.interaction_count or 0), 'Popular product') for p in popular]
        
        # Average the vectors of viewed products
        viewed_vectors = self.product_vectors[viewed_indices]
        avg_vector = viewed_vectors.mean(axis=0)
        
        # Calculate similarity with all products
        similarities = cosine_similarity(avg_vector.reshape(1, -1), self.product_vectors)[0]
        
        # Get top N recommendations (excluding already viewed)
        similar_indices = np.argsort(similarities)[::-1]
        recommendations = []
        viewed_set = set(viewed_product_ids)
        
        for idx in similar_indices:
            product_id = self.product_ids[idx]
            if product_id not in viewed_set and similarities[idx] > 0:
                recommendations.append((product_id, float(similarities[idx])))
                if len(recommendations) >= n:
                    break
        
        return recommendations


class HybridRecommendationEngine:
    """Combines Collaborative Filtering and Content-Based Filtering"""
    
    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id
        self.collab_engine = CollaborativeFilteringEngine(merchant_id)
        self.content_engine = ContentBasedEngine(merchant_id)
    
    def recommend_for_customer(
        self,
        customer_id: Optional[int],
        viewed_product_ids: List[int] = None,
        n: int = 10,
        collab_weight: float = 0.7,
        content_weight: float = 0.3
    ) -> List[Tuple[int, float, str]]:
        """
        Hybrid recommendation combining both approaches
        
        Returns: List of (product_id, score, explanation) tuples
        """
        viewed_product_ids = viewed_product_ids or []
        product_scores = defaultdict(lambda: {'score': 0.0, 'sources': []})
        
        # Collaborative filtering (if customer exists and has history)
        if customer_id:
            try:
                collab_recs = self.collab_engine.recommend_for_customer(customer_id, n=n*2)
                for product_id, score in collab_recs:
                    product_scores[product_id]['score'] += score * collab_weight
                    product_scores[product_id]['sources'].append('collaborative')
            except Exception as e:
                print(f"Error in collaborative filtering: {e}")
        
        # Content-based filtering (if customer viewed products)
        if viewed_product_ids:
            try:
                content_recs = self.content_engine.recommend_for_new_customer(viewed_product_ids, n=n*2)
                for product_id, score in content_recs:
                    product_scores[product_id]['score'] += score * content_weight
                    product_scores[product_id]['sources'].append('content')
            except Exception as e:
                print(f"Error in content-based filtering: {e}")
        
        # If no recommendations, fall back to trending products
        if not product_scores:
            return self.get_trending_products(n)
        
        # Sort by score and return top N
        recommendations = []
        for product_id, data in sorted(product_scores.items(), key=lambda x: x[1]['score'], reverse=True)[:n]:
            sources = data['sources']
            if 'collaborative' in sources and 'content' in sources:
                explanation = "Popular among similar customers and similar to products you viewed"
            elif 'collaborative' in sources:
                explanation = "Popular among customers similar to you"
            else:
                explanation = "Similar to products you viewed"
            
            recommendations.append((product_id, data['score'], explanation))
        
        return recommendations
    
    def get_trending_products(self, n: int = 10) -> List[Tuple[int, float, str]]:
        """Get trending/popular products"""
        from django.utils import timezone
        from datetime import timedelta
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Try to get products with most purchases
        trending = Product.objects.filter(
            merchant_id=self.merchant_id,
            is_active=True
        ).annotate(
            purchase_count=Count('order_items', filter=models.Q(order_items__order__ordered_at__gte=thirty_days_ago)),
            interaction_count=Count('interactions', filter=models.Q(interactions__occurred_at__gte=thirty_days_ago))
        ).order_by('-purchase_count', '-interaction_count')[:n]
        
        recommendations = []
        for product in trending:
            score = float(product.purchase_count or 0) + float(product.interaction_count or 0) * 0.5
            if score > 0:
                recommendations.append((
                    product.id,
                    score,
                    "Trending - Popular product"
                ))
        
        # If no trending products, return any active products
        if not recommendations:
            any_products = Product.objects.filter(
                merchant_id=self.merchant_id,
                is_active=True
            )[:n]
            
            for product in any_products:
                recommendations.append((
                    product.id,
                    1.0,
                    "Featured product"
                ))
        
        return recommendations
    
    def recommend_similar_products(self, product_id: int, n: int = 10) -> List[Tuple[int, float, str]]:
        """Recommend products similar to a given product"""
        similar = self.content_engine.recommend_similar_products(product_id, n=n)
        
        # If no similar products found, return trending products
        if not similar:
            trending = self.get_trending_products(n)
            return [(pid, score, "Popular product") for pid, score, _ in trending if pid != product_id][:n]
        
        recommendations = []
        for prod_id, score in similar:
            recommendations.append((
                prod_id,
                score,
                "Similar product"
            ))
        
        return recommendations
    
    def get_frequently_bought_together(self, product_id: int, n: int = 5) -> List[Tuple[int, float, str]]:
        """Get products frequently bought together with given product"""
        # Find orders that contain this product
        orders_with_product = Order.objects.filter(
            merchant_id=self.merchant_id,
            items__product_id=product_id
        ).distinct()
        
        # Count other products in those orders
        product_counts = defaultdict(int)
        
        for order in orders_with_product:
            for item in order.items.exclude(product_id=product_id):
                if item.product_id:
                    product_counts[item.product_id] += 1
        
        # Sort by count and return top N
        recommendations = []
        for prod_id, count in sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:n]:
            recommendations.append((
                prod_id,
                float(count),
                f"Frequently bought together ({count} times)"
            ))
        
        # If we have fewer than requested, fill with similar products
        if len(recommendations) < n:
            similar = self.recommend_similar_products(product_id, n=n*2)
            existing_ids = {pid for pid, _, _ in recommendations}
            for pid, score, _ in similar:
                if pid not in existing_ids and pid != product_id:
                    recommendations.append((pid, score * 0.5, "Similar product"))
                    if len(recommendations) >= n:
                        break
        
        # If still no recommendations, return trending products
        if not recommendations:
            trending = self.get_trending_products(n=n)
            return [(pid, score, "Popular product") for pid, score, _ in trending if pid != product_id][:n]
        
        return recommendations

