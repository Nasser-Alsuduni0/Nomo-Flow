"""
Separate widget files for different recommendation types
Following the same pattern as other features (notifications, purchase display, etc.)
"""
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET


def _get_common_widget_code():
    """Common code shared by all widgets"""
    return """
  // Common configuration and utilities
  var BASE_URL = window.__NOMO_BASE__ || '';
  var STORE_ID = window.__NOMO_STORE_ID__ || null;
  var CUSTOMER_ID = window.__NOMO_CUSTOMER_ID__ || null;
  
  // Get store ID from script src or data attribute
  var scriptEl = document.currentScript || (function(){
    var scripts = document.getElementsByTagName('script');
    return scripts[scripts.length - 1];
  })();
  
  // Try multiple methods to get store ID
  if (!STORE_ID) {
    var storeIdParam = (scriptEl.src || '').match(/[?&]store_id=([^&]+)/);
    if (storeIdParam) STORE_ID = decodeURIComponent(storeIdParam[1]);
    if (!STORE_ID && scriptEl) STORE_ID = scriptEl.getAttribute('data-store-id');
    if (!STORE_ID && window.Salla && window.Salla.store) {
      STORE_ID = window.Salla.store.id || window.Salla.store.store_id;
    }
    if (!STORE_ID && window.Salla && window.Salla.config) {
      STORE_ID = window.Salla.config.store_id || window.Salla.config.storeId;
    }
    var metaStoreId = document.querySelector('meta[name="salla-store-id"]');
    if (!STORE_ID && metaStoreId) STORE_ID = metaStoreId.getAttribute('content');
  }
  
  if (!BASE_URL) {
    try {
      var url = new URL(scriptEl.src);
      BASE_URL = url.origin;
    } catch(e) {}
  }
  
  if (!window.__NOMO_SESSION_ID__) {
    window.__NOMO_SESSION_ID__ = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  }
  
  // Check if recommendations feature is enabled
  function checkFeatureEnabled(callback) {
    if (!STORE_ID) {
      console.warn('Nomo Recommendations: Store ID not found');
      callback(false);
      return;
    }
    
    fetch(BASE_URL + '/features/is-enabled/?feature=recommendations&store_id=' + encodeURIComponent(STORE_ID), {
      headers: {'ngrok-skip-browser-warning': 'true'}
    })
    .then(function(response) {
      if (!response.ok) {
        console.warn('Nomo Recommendations: Feature check failed:', response.status);
        return {enabled: false};
      }
      return response.json();
    })
    .then(function(data) {
      if (!data.enabled) {
        console.log('Nomo Recommendations: Feature is disabled for this store');
      }
      callback(data.enabled || false);
    })
    .catch(function(error) {
      console.warn('Nomo Recommendations: Error checking feature status:', error);
      callback(false);
    });
  }
  
  // Common product card creation function
  function createProductCard(product) {
    var card = document.createElement('div');
    card.className = 'nomo-product-card';
    card.style.cssText = 'background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08); transition: all 0.3s ease; cursor: pointer; border: 1px solid #e5e7eb;';
    
    card.onmouseover = function() { 
      this.style.transform = 'translateY(-6px)';
      this.style.boxShadow = '0 8px 24px rgba(0,0,0,0.12)';
    };
    card.onmouseout = function() { 
      this.style.transform = 'translateY(0)';
      this.style.boxShadow = '0 2px 12px rgba(0,0,0,0.08)';
    };
    
    var link = document.createElement('a');
    link.href = product.url || '#';
    link.style.cssText = 'text-decoration: none; color: inherit; display: block;';
    link.target = '_self';
    
    if (product.image_url) {
      var imgWrapper = document.createElement('div');
      imgWrapper.style.cssText = 'width: 100%; height: 200px; overflow: hidden; background: #f3f4f6; position: relative;';
      var img = document.createElement('img');
      img.src = product.image_url;
      img.alt = product.name || 'Product';
      img.style.cssText = 'width: 100%; height: 100%; object-fit: cover; display: block;';
      img.onerror = function() {
        this.style.display = 'none';
        imgWrapper.innerHTML = '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:#9ca3af;font-size:14px;">No Image</div>';
      };
      imgWrapper.appendChild(img);
      link.appendChild(imgWrapper);
    }
    
    var content = document.createElement('div');
    content.style.cssText = 'padding: 16px;';
    
    var name = document.createElement('div');
    name.textContent = product.name || 'Product';
    name.style.cssText = 'font-weight: 600; margin-bottom: 8px; color: #1e293b; font-size: 0.95rem; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.8em;';
    content.appendChild(name);
    
    if (product.price) {
      var price = document.createElement('div');
      price.textContent = product.price + ' ر.س';
      price.style.cssText = 'color: #0ea5e9; font-weight: 700; font-size: 1.1rem;';
      content.appendChild(price);
    }
    
    link.appendChild(content);
    card.appendChild(link);
    
    link.onclick = function() {
      if (product.salla_product_id) {
        trackInteraction(product.salla_product_id, 'view');
      }
    };
    
    return card;
  }
  
  function trackInteraction(productId, type) {
    if (!STORE_ID || !productId) return;
    fetch(BASE_URL + '/api/recommendations/track/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true'},
      body: JSON.stringify({
        store_id: STORE_ID,
        product_id: productId,
        customer_id: CUSTOMER_ID,
        interaction_type: type || 'view',
        session_id: window.__NOMO_SESSION_ID__
      })
    }).catch(function(e) {
      console.warn('Nomo Recommendations: Failed to track interaction', e);
    });
  }
"""


@csrf_exempt
@require_GET
def recommended_for_you_js(request):
    """Widget 1: Recommended For You - Appears on homepage"""
    js = """
(function(){
  if (window.__NOMO_RECOMMENDED_FOR_YOU_LOADED__) return;
  window.__NOMO_RECOMMENDED_FOR_YOU_LOADED__ = true;
  
""" + _get_common_widget_code() + """
  
  function loadRecommendedForYou() {
    checkFeatureEnabled(function(enabled) {
      if (!enabled) return;
      
      if (!STORE_ID) {
        console.warn('Nomo Recommendations: Store ID not found');
        return;
      }
      
      var url = BASE_URL + '/api/recommendations/customer/';
      if (CUSTOMER_ID) url += CUSTOMER_ID + '/';
      
      // Add query parameters
      var params = [];
      if (STORE_ID) params.push('store_id=' + encodeURIComponent(STORE_ID));
      var viewedProducts = window.__NOMO_VIEWED_PRODUCTS__ || [];
      if (viewedProducts.length > 0) {
        params.push('viewed_products=' + viewedProducts.join(','));
      }
      if (params.length > 0) {
        url += (url.indexOf('?') === -1 ? '?' : '&') + params.join('&');
      }
      
      fetch(url, {
        method: 'GET',
        headers: {'Accept': 'application/json', 'ngrok-skip-browser-warning': 'true'}
      })
      .then(function(response) {
        if (!response.ok) {
          console.warn('Nomo Recommendations: API error', response.status, response.statusText);
          return response.json().then(function(errData) {
            throw new Error(errData.error || 'HTTP ' + response.status);
          }).catch(function() {
            throw new Error('HTTP ' + response.status);
          });
        }
        return response.json();
      })
      .then(function(data) {
        if (data.error === 'no_products') {
          console.log('Nomo Recommendations: ' + (data.message || 'No products synced yet. Please sync products from the dashboard first.'));
          return;
        }
        
        if (data.recommendations && data.recommendations.length > 0) {
          var container = document.createElement('div');
          container.className = 'nomo-recommended-for-you';
          container.style.cssText = 'margin: 30px 0; padding: 0; width: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;';
          
          var titleSection = document.createElement('div');
          titleSection.style.cssText = 'margin-bottom: 20px; text-align: center;';
          var title = document.createElement('h2');
          title.textContent = 'Recommended for You';
          title.style.cssText = 'font-size: 1.75rem; font-weight: 700; margin: 0; color: #1e293b;';
          titleSection.appendChild(title);
          container.appendChild(titleSection);
          
          var grid = document.createElement('div');
          grid.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto;';
          if (window.innerWidth < 768) {
            grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(150px, 1fr))';
            grid.style.gap = '15px';
          }
          
          data.recommendations.slice(0, 8).forEach(function(product) {
            grid.appendChild(createProductCard(product));
          });
          
          container.appendChild(grid);
          
          var target = document.querySelector('[data-nomo-recommended-for-you]') || 
                       document.querySelector('.products-section') ||
                       document.querySelector('main') ||
                       document.body;
          if (target) target.appendChild(container);
        }
      })
      .catch(function(error) {
        console.warn('Nomo Recommendations: Failed to load', error);
      });
    });
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadRecommendedForYou);
  } else {
    setTimeout(loadRecommendedForYou, 500);
  }
})();
"""
    response = HttpResponse(js, content_type='application/javascript')
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
    return response


@csrf_exempt
@require_GET
def similar_products_js(request):
    """Widget 2: Similar Products - Appears on product page"""
    js = """
(function(){
  if (window.__NOMO_SIMILAR_PRODUCTS_LOADED__) return;
  window.__NOMO_SIMILAR_PRODUCTS_LOADED__ = true;
  
""" + _get_common_widget_code() + """
  
  function loadSimilarProducts() {
    checkFeatureEnabled(function(enabled) {
      if (!enabled) return;
      
      if (!STORE_ID) {
        console.warn('Nomo Recommendations: Store ID not found');
        return;
      }
      
      var productId = window.__NOMO_CURRENT_PRODUCT_ID__;
      
      // Validate that it's not an unrendered template variable
      if (productId && typeof productId === 'string' && productId.includes('{{')) {
        productId = null;
      }
      
      // Try multiple methods to detect product ID
      if (!productId && window.Salla) {
        // Method 1: Salla product object
        if (window.Salla.product && window.Salla.product.id) {
          productId = window.Salla.product.id;
        }
        // Method 2: Salla product data
        if (!productId && window.Salla.productData && window.Salla.productData.id) {
          productId = window.Salla.productData.id;
        }
        // Method 3: Salla current product
        if (!productId && window.Salla.currentProduct && window.Salla.currentProduct.id) {
          productId = window.Salla.currentProduct.id;
        }
        // Method 4: Salla page data (Twilight themes)
        if (!productId && window.Salla.page && window.Salla.page.id) {
          productId = window.Salla.page.id;
        }
        // Method 5: Salla config product
        if (!productId && window.Salla.config && window.Salla.config.product) {
          productId = window.Salla.config.product.id || window.Salla.config.product;
        }
      }
      
      // Method 6: window.salla (lowercase - Twilight v2)
      if (!productId && window.salla) {
        if (window.salla.product && window.salla.product.id) {
          productId = window.salla.product.id;
        }
        if (!productId && window.salla.page && window.salla.page.product) {
          productId = window.salla.page.product.id || window.salla.page.product;
        }
      }
      
      // Method 7: URL pattern - Salla uses multiple formats:
      // - /store/product-name/p{id} (e.g., /dev-xxx/فستان/p1856291938)
      // - /products/{slug}
      // - /p/{slug}
      if (!productId) {
        // First try: Match p{numeric_id} at end of URL path
        var urlMatch = window.location.pathname.match(/\\/p(\\d+)(?:\\/|$|\\?)/);
        if (urlMatch) {
          productId = urlMatch[1];
          console.log('Nomo Recommendations: Found product ID from URL:', productId);
        }
      }
      if (!productId) {
        // Second try: Match /products/{slug} or /p/{slug}
        var urlMatch2 = window.location.pathname.match(/\\/(?:products|p)\\/([^\\/\\?]+)/);
        if (urlMatch2) productId = urlMatch2[1];
      }
      
      // Method 8: Meta tags
      if (!productId) {
        var metaProductId = document.querySelector('meta[property="product:id"], meta[name="product-id"], meta[property="og:product:id"], meta[name="twitter:data1"]');
        if (metaProductId) productId = metaProductId.getAttribute('content');
      }
      
      // Method 9: salla-product Web Component
      if (!productId) {
        var sallaProduct = document.querySelector('salla-product, [is="salla-product"]');
        if (sallaProduct) {
          productId = sallaProduct.getAttribute('product-id') || 
                     sallaProduct.getAttribute('data-id') ||
                     sallaProduct.id;
        }
      }
      
      // Method 10: Data attributes on common containers
      if (!productId) {
        var productElement = document.querySelector('[data-product-id], .product[data-id], .product-single[data-id], [data-product]');
        if (productElement) {
          productId = productElement.getAttribute('data-product-id') || 
                     productElement.getAttribute('data-id') ||
                     productElement.getAttribute('data-product');
        }
      }
      
      // Method 11: JSON-LD structured data
      if (!productId) {
        var jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
        for (var i = 0; i < jsonLdScripts.length; i++) {
          try {
            var jsonData = JSON.parse(jsonLdScripts[i].textContent);
            if (jsonData['@type'] === 'Product' && jsonData.productID) {
              productId = jsonData.productID;
              break;
            }
            if (jsonData['@type'] === 'Product' && jsonData.sku) {
              productId = jsonData.sku;
              break;
            }
          } catch(e) {}
        }
      }
      
      if (!productId) {
        // Always log what data sources are available to help with debugging
        console.log('Nomo Recommendations: Product ID not found on this page.');
        console.log('Nomo Recommendations: Available Salla data:', {
          'Salla': typeof window.Salla !== 'undefined' ? 'exists' : 'not found',
          'Salla.product': window.Salla && window.Salla.product,
          'Salla.page': window.Salla && window.Salla.page,
          'Salla.config': window.Salla && window.Salla.config,
          'salla (lowercase)': typeof window.salla !== 'undefined' ? window.salla : 'not found',
          'URL path': window.location.pathname,
          'salla-product elements': document.querySelectorAll('salla-product, [is=\"salla-product\"]').length,
          'data-product-id elements': document.querySelectorAll('[data-product-id]').length
        });
        console.log('Nomo Recommendations: If you are on a product page, please add: window.__NOMO_CURRENT_PRODUCT_ID__ = YOUR_PRODUCT_ID;');
        return;
      }
      
      // Validate product ID - skip if it looks like an unrendered template variable
      if (typeof productId === 'string' && (
          productId.includes('{{') || 
          productId.includes('}}') || 
          productId.includes('{%') ||
          productId === 'undefined' ||
          productId === 'null' ||
          productId === ''
      )) {
        console.warn('Nomo Recommendations: Invalid product ID detected (template variable not rendered):', productId);
        return;
      }
      
      console.log('Nomo Recommendations: Product ID detected:', productId);
      
      // Track current product view
      trackInteraction(productId, 'view');
      
      // Get product recommendations - pass store_id for merchant lookup
      var url = BASE_URL + '/api/recommendations/product/' + encodeURIComponent(productId) + '/';
      if (STORE_ID) {
        url += '?store_id=' + encodeURIComponent(STORE_ID);
      }
      
      fetch(url, {
        method: 'GET',
        headers: {'Accept': 'application/json', 'ngrok-skip-browser-warning': 'true'}
      })
      .then(function(response) {
        if (!response.ok) {
          console.warn('Nomo Recommendations: API error', response.status, response.statusText);
          throw new Error('HTTP ' + response.status);
        }
        return response.json();
      })
      .then(function(data) {
        if (data.error) {
          if (data.error === 'insufficient_products' || data.error === 'no_products') {
            console.log('Nomo Recommendations: ' + (data.message || 'Products need to be synced first.'));
          } else {
            console.warn('Nomo Recommendations:', data.error);
          }
          return;
        }
        
        var products = data.similar_products || [];
        if (products.length > 0) {
          var container = document.createElement('div');
          container.className = 'nomo-similar-products';
          container.style.cssText = 'margin: 40px 0; padding: 0; width: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;';
          
          var titleSection = document.createElement('div');
          titleSection.style.cssText = 'margin-bottom: 20px; text-align: center;';
          var title = document.createElement('h2');
          title.textContent = 'قد يعجبك أيضاً';
          title.style.cssText = 'font-size: 1.75rem; font-weight: 700; margin: 0; color: #1e293b;';
          titleSection.appendChild(title);
          container.appendChild(titleSection);
          
          var grid = document.createElement('div');
          grid.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto;';
          if (window.innerWidth < 768) {
            grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(150px, 1fr))';
            grid.style.gap = '15px';
          }
          
          products.slice(0, 6).forEach(function(product) {
            grid.appendChild(createProductCard(product));
          });
          
          container.appendChild(grid);
          
          var target = document.querySelector('[data-nomo-similar-products]') || 
                       document.querySelector('.related-products') ||
                       document.querySelector('.product-related') ||
                       document.querySelector('main') ||
                       document.body;
          if (target) target.appendChild(container);
        } else {
          console.log('Nomo Recommendations: No similar products found');
        }
      })
      .catch(function(error) {
        console.warn('Nomo Recommendations: Failed to load similar products', error);
      });
    });
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadSimilarProducts);
  } else {
    setTimeout(loadSimilarProducts, 500);
  }
})();
"""
    response = HttpResponse(js, content_type='application/javascript')
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
    return response


@csrf_exempt
@require_GET
def frequently_bought_together_js(request):
    """Widget 3: Frequently Bought Together - Appears on cart page"""
    js = """
(function(){
  if (window.__NOMO_FREQUENTLY_BOUGHT_LOADED__) return;
  window.__NOMO_FREQUENTLY_BOUGHT_LOADED__ = true;
  
""" + _get_common_widget_code() + """
  
  function loadFrequentlyBoughtTogether() {
    checkFeatureEnabled(function(enabled) {
      if (!enabled) return;
      
      if (!STORE_ID) {
        console.warn('Nomo Recommendations: Store ID not found');
        return;
      }
      
      // Get products from cart - try multiple methods
      var cartProducts = window.__NOMO_CART_PRODUCTS__ || [];
      
      // Validate manual cart products aren't template variables
      if (cartProducts.length > 0) {
        cartProducts = cartProducts.filter(function(id) {
          return id && typeof id === 'string' && !id.includes('{{');
        });
      }
      
      // Method 1: Salla cart object (Twilight)
      if (cartProducts.length === 0 && window.Salla) {
        // Twilight uses Salla.cart as a Proxy with .items property or .get() method
        try {
          if (window.Salla.cart) {
            // Try direct items access
            if (window.Salla.cart.items && Array.isArray(window.Salla.cart.items)) {
              cartProducts = window.Salla.cart.items.map(function(item) {
                return item.product ? (item.product.id || item.product.product_id) : 
                       (item.product_id || item.id || item.sku);
              }).filter(function(id) { return id; });
            }
          }
        } catch(e) {
          console.log('Nomo Recommendations: Could not access Salla.cart directly');
        }
        
        // Method 2: Salla cart data
        if (cartProducts.length === 0 && window.Salla.cartData && window.Salla.cartData.items) {
          cartProducts = window.Salla.cartData.items.map(function(item) {
            return item.product_id || item.id || item.sku;
          }).filter(function(id) { return id; });
        }
        // Method 3: Salla store cart
        if (cartProducts.length === 0 && window.Salla.store && window.Salla.store.cart) {
          var storeCart = window.Salla.store.cart;
          if (storeCart.items) {
            cartProducts = storeCart.items.map(function(item) {
              return item.product_id || item.id || item.sku;
            }).filter(function(id) { return id; });
          }
        }
      }
      
      // Method 4: window.salla (lowercase - Twilight v2)
      if (cartProducts.length === 0 && window.salla && window.salla.cart) {
        try {
          if (window.salla.cart.items && Array.isArray(window.salla.cart.items)) {
            cartProducts = window.salla.cart.items.map(function(item) {
              return item.product_id || item.id || (item.product && item.product.id);
            }).filter(function(id) { return id; });
          }
        } catch(e) {}
      }
      
      // Method 5: DOM elements
      if (cartProducts.length === 0) {
        var cartItems = document.querySelectorAll(
          '[data-product-id], .cart-item[data-id], .cart-item[data-product-id], ' +
          '.cart__item[data-product-id], .line-item[data-product-id], ' +
          '[class*="cart"][class*="item"][data-id], salla-cart-item'
        );
        cartProducts = Array.from(cartItems).map(function(item) {
          return item.getAttribute('data-product-id') || 
                 item.getAttribute('data-id') ||
                 item.getAttribute('data-product') ||
                 item.getAttribute('product-id') ||
                 item.getAttribute('data-sku');
        }).filter(function(id) { return id; });
      }
      
      // Method 6: Try to find cart in localStorage/sessionStorage
      if (cartProducts.length === 0) {
        try {
          var storedCart = localStorage.getItem('salla_cart') || 
                          sessionStorage.getItem('salla_cart') ||
                          localStorage.getItem('cart') ||
                          sessionStorage.getItem('cart');
          if (storedCart) {
            var cartData = JSON.parse(storedCart);
            if (cartData.items && Array.isArray(cartData.items)) {
              cartProducts = cartData.items.map(function(item) {
                return item.product_id || item.id || item.sku;
              }).filter(function(id) { return id; });
            }
          }
        } catch(e) {
          console.warn('Nomo Recommendations: Failed to parse stored cart', e);
        }
      }
      
      // Filter out any items that look like unrendered template variables or placeholders
      // Do this BEFORE the URL fallback so placeholders don't prevent fallback
      cartProducts = cartProducts.filter(function(id) {
        if (typeof id !== 'string') id = String(id);
        return id && 
               !id.includes('{{') && 
               !id.includes('}}') && 
               !id.includes('{%') &&
               id !== 'undefined' &&
               id !== 'null' &&
               id !== 'product-id-1' &&
               id !== 'product-id-2';
      });
      
      // Method 7: FALLBACK - If no valid products and on a product page, use current product ID from URL
      if (cartProducts.length === 0) {
        var urlMatch = window.location.pathname.match(/\\/p(\\d+)(?:\\/|$|\\?)/);
        if (urlMatch) {
          cartProducts = [urlMatch[1]];
          console.log('Nomo Recommendations: Using current product from URL:', urlMatch[1]);
        }
      }
      
      if (cartProducts.length === 0) {
        console.log('Nomo Recommendations: No products detected for frequently bought together.');
        console.log('Nomo Recommendations: Cart detection checked:', {
          'Salla.cart': window.Salla && window.Salla.cart,
          'salla.cart': window.salla && window.salla.cart,
          'cart DOM elements': document.querySelectorAll('[data-product-id], salla-cart-item').length,
          'URL path': window.location.pathname
        });
        return;
      }
      
      console.log('Nomo Recommendations: Using products for recommendations:', cartProducts);
      
      // Get recommendations for first product in cart - pass store_id
      var firstProductId = cartProducts[0];
      var url = BASE_URL + '/api/recommendations/product/' + encodeURIComponent(firstProductId) + '/';
      if (STORE_ID) {
        url += '?store_id=' + encodeURIComponent(STORE_ID);
      }
      
      fetch(url, {
        method: 'GET',
        headers: {'Accept': 'application/json', 'ngrok-skip-browser-warning': 'true'}
      })
      .then(function(response) {
        if (!response.ok) {
          console.warn('Nomo Recommendations: API error', response.status, response.statusText);
          throw new Error('HTTP ' + response.status);
        }
        return response.json();
      })
      .then(function(data) {
        if (data.error) {
          if (data.error === 'insufficient_products' || data.error === 'no_products') {
            console.log('Nomo Recommendations: ' + (data.message || 'Products need to be synced first.'));
          } else {
            console.warn('Nomo Recommendations:', data.error);
          }
          return;
        }
        var products = data.frequently_bought_together || [];
        // Filter out products already in cart
        products = products.filter(function(p) {
          return !cartProducts.includes(String(p.salla_product_id || p.id));
        });
        
        if (products.length > 0) {
          var container = document.createElement('div');
          container.className = 'nomo-frequently-bought-together';
          container.style.cssText = 'margin: 40px 0; padding: 0; width: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;';
          
          var titleSection = document.createElement('div');
          titleSection.style.cssText = 'margin-bottom: 20px; text-align: center;';
          var title = document.createElement('h2');
          title.textContent = 'يُشترى معاً عادةً';
          title.style.cssText = 'font-size: 1.75rem; font-weight: 700; margin: 0; color: #1e293b;';
          titleSection.appendChild(title);
          container.appendChild(titleSection);
          
          var grid = document.createElement('div');
          grid.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto;';
          if (window.innerWidth < 768) {
            grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(150px, 1fr))';
            grid.style.gap = '15px';
          }
          
          products.slice(0, 4).forEach(function(product) {
            grid.appendChild(createProductCard(product));
          });
          
          container.appendChild(grid);
          
          var target = document.querySelector('[data-nomo-frequently-bought]') || 
                       document.querySelector('.cart-recommendations') ||
                       document.querySelector('.cart-items') ||
                       document.querySelector('.cart-page') ||
                       document.querySelector('main') ||
                       document.body;
          if (target) target.appendChild(container);
        }
      })
      .catch(function(error) {
        console.warn('Nomo Recommendations: Failed to load frequently bought together', error);
      });
    });
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadFrequentlyBoughtTogether);
  } else {
    setTimeout(loadFrequentlyBoughtTogether, 500);
  }
})();
"""
    response = HttpResponse(js, content_type='application/javascript')
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
    return response

