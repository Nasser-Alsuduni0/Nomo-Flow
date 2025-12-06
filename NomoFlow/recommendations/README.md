# Product Recommendations System

A hybrid recommendation system combining Collaborative Filtering and Content-Based Filtering for e-commerce product recommendations.

## Features

- **Collaborative Filtering**: User-user similarity based on purchase history and interactions
- **Content-Based Filtering**: Product similarity based on descriptions, categories, and tags using TF-IDF
- **Hybrid Approach**: Combines both methods for maximum accuracy
- **Salla API Integration**: Automatic sync of products and orders
- **Real-time Tracking**: Track customer interactions (views, cart adds, purchases)

## Installation

### Required Dependencies

Add these to your `requirements.txt`:

```
scikit-learn>=1.0.0
numpy>=1.21.0
```

Install with:
```bash
pip install scikit-learn numpy
```

### Database Migrations

Run migrations to create the recommendation tables:

```bash
python manage.py makemigrations recommendations
python manage.py migrate recommendations
```

## Usage

### 1. Sync Data from Salla

First, sync products and orders from your Salla store:

```bash
# Via API
POST /api/recommendations/sync/products/?limit=100
POST /api/recommendations/sync/orders/?limit=100

# Or via dashboard
Navigate to Dashboard > Product Recommendations > Sync Products/Orders
```

### 2. Track Customer Interactions

Track when customers view, add to cart, or purchase products:

```javascript
// Track product view
fetch('/api/recommendations/track/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    store_id: 'your-store-id',
    product_id: 'product-salla-id',
    customer_id: 'customer-salla-id', // optional
    interaction_type: 'view', // 'view', 'cart', or 'purchase'
    session_id: 'session-id' // optional
  })
});
```

### 3. Get Recommendations

#### For a Customer

```bash
GET /api/recommendations/customer/<customer_id>/
GET /api/recommendations/customer/?customer_id=123&viewed_products=1,2,3
```

Response:
```json
{
  "customer_id": 123,
  "recommendations": [
    {
      "id": 456,
      "name": "Product Name",
      "price": 99.99,
      "image_url": "https://...",
      "score": 0.85,
      "explanation": "Popular among customers similar to you"
    }
  ],
  "count": 10
}
```

#### Similar Products

```bash
GET /api/recommendations/product/<product_id>/
```

Response includes:
- Similar products (content-based)
- Frequently bought together (collaborative)

#### Trending Products

```bash
GET /api/recommendations/trending/?limit=10
```

### 4. Embed Widget in Storefront

Add to your Salla store theme:

```html
<script>
  window.__NOMO_BASE__ = 'https://your-domain.com';
  window.__NOMO_STORE_ID__ = 'your-store-id';
  window.__NOMO_CUSTOMER_ID__ = 'customer-id'; // optional
  window.__NOMO_CURRENT_PRODUCT_ID__ = 'current-product-id'; // for product pages
</script>
<script src="https://your-domain.com/api/recommendations/embed.js" defer></script>

<!-- Or specify container -->
<div data-nomo-recommendations></div>
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/recommendations/customer/<id>/` | GET | Get recommendations for customer |
| `/api/recommendations/product/<id>/` | GET | Get similar products |
| `/api/recommendations/trending/` | GET | Get trending products |
| `/api/recommendations/track/` | POST | Track customer interaction |
| `/api/recommendations/sync/products/` | POST | Sync products from Salla |
| `/api/recommendations/sync/orders/` | POST | Sync orders from Salla |

## Models

- **Product**: Stores product information from Salla
- **Customer**: Stores customer information
- **Order**: Stores order information
- **OrderItem**: Individual products in orders
- **CustomerInteraction**: Tracks views, cart adds, purchases

## Recommendation Algorithms

### Collaborative Filtering
- Builds customer × product interaction matrix
- Scores: Purchase = 1.0, Cart = 0.5, View = 0.2
- Uses cosine similarity to find similar customers
- Recommends products liked by similar customers

### Content-Based Filtering
- Uses TF-IDF vectorization on product descriptions
- Computes cosine similarity between products
- Recommends products similar to viewed items

### Hybrid Approach
- Default: 70% collaborative + 30% content-based
- Automatically adjusts based on data availability
- Falls back to trending products if no data

## Dashboard

Access the recommendations dashboard at:
`/dashboard/recommendations/`

Features:
- View sync status
- Sync products and orders
- View recent products
- See statistics (products, customers, orders, interactions)

