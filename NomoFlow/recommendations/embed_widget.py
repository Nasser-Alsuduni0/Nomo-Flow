"""
Embeddable JavaScript widget for product recommendations
"""
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET


@csrf_exempt
@require_GET
def recommendations_widget_js(request):
    """Generate JavaScript embed code for product recommendations widget"""
    js = """
(function(){
  // Idempotency guard
  if (window.__NOMO_RECOMMENDATIONS_LOADED__) {
    return;
  }
  window.__NOMO_RECOMMENDATIONS_LOADED__ = true;

  // Configuration
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
    // Method 1: From script URL parameter
    var storeIdParam = (scriptEl.src || '').match(/[?&]store_id=([^&]+)/);
    if (storeIdParam) STORE_ID = decodeURIComponent(storeIdParam[1]);
    
    // Method 2: From data attribute
    if (!STORE_ID && scriptEl) STORE_ID = scriptEl.getAttribute('data-store-id');
    
    // Method 3: From Salla global object (if available)
    if (!STORE_ID && window.Salla && window.Salla.store) {
      STORE_ID = window.Salla.store.id || window.Salla.store.store_id;
    }
    
    // Method 4: From Salla config
    if (!STORE_ID && window.Salla && window.Salla.config) {
      STORE_ID = window.Salla.config.store_id || window.Salla.config.storeId;
    }
    
    // Method 5: From meta tag
    if (!STORE_ID) {
      var metaStoreId = document.querySelector('meta[name="salla-store-id"]') || 
                        document.querySelector('meta[property="salla:store_id"]');
      if (metaStoreId) STORE_ID = metaStoreId.getAttribute('content');
    }
    
    // Method 6: From data attribute on body/html
    if (!STORE_ID) {
      var bodyStoreId = document.body.getAttribute('data-store-id') || 
                        document.documentElement.getAttribute('data-store-id');
      if (bodyStoreId) STORE_ID = bodyStoreId;
    }
    
    // Method 7: Try to extract from current URL (Salla store URLs)
    if (!STORE_ID) {
      var hostname = window.location.hostname;
      // Some Salla stores might have store ID in subdomain or path
      var urlMatch = window.location.pathname.match(/\\/stores\\/(\\d+)/);
      if (urlMatch) STORE_ID = urlMatch[1];
    }
  }
  
  if (!BASE_URL) {
    try {
      var url = new URL(scriptEl.src);
      BASE_URL = url.origin;
    } catch(e) {}
  }
  
  // Log warning if store ID still not found
  if (!STORE_ID) {
    console.warn('Nomo Recommendations: Store ID not found. Please set window.__NOMO_STORE_ID__ or add data-store-id attribute to the script tag.');
  }

  // Generate session ID if not exists
  if (!window.__NOMO_SESSION_ID__) {
    window.__NOMO_SESSION_ID__ = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  }

  // Widget container with better styling
  function createRecommendationsWidget(products, title, containerId) {
    if (!products || products.length === 0) return null;
    
    var container = document.createElement('div');
    container.id = containerId || 'nomo-recommendations-widget';
    container.className = 'nomo-recommendations-widget';
    container.style.cssText = 'margin: 30px 0; padding: 0; width: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;';
    
    // Title section
    var titleSection = document.createElement('div');
    titleSection.style.cssText = 'margin-bottom: 20px; text-align: center;';
    
    var titleEl = document.createElement('h2');
    titleEl.textContent = title || 'موصى به لك';
    titleEl.style.cssText = 'font-size: 1.75rem; font-weight: 700; margin: 0; color: #1e293b;';
    titleSection.appendChild(titleEl);
    
    container.appendChild(titleSection);
    
    // Products grid
    var grid = document.createElement('div');
    grid.className = 'nomo-products-grid';
    grid.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto;';
    
    // Responsive adjustments
    if (window.innerWidth < 768) {
      grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(150px, 1fr))';
      grid.style.gap = '15px';
    }
    
    products.slice(0, 8).forEach(function(product) {
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
      
      // Product image
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
      
      // Product content
      var content = document.createElement('div');
      content.style.cssText = 'padding: 16px;';
      
      // Product name
      var name = document.createElement('div');
      name.className = 'nomo-product-name';
      name.textContent = product.name || 'Product';
      name.style.cssText = 'font-weight: 600; margin-bottom: 8px; color: #1e293b; font-size: 0.95rem; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.8em;';
      content.appendChild(name);
      
      // Product price
      if (product.price) {
        var priceWrapper = document.createElement('div');
        priceWrapper.style.cssText = 'display: flex; align-items: center; gap: 8px;';
        
        var price = document.createElement('div');
        price.className = 'nomo-product-price';
        price.textContent = product.price + ' ر.س';
        price.style.cssText = 'color: #0ea5e9; font-weight: 700; font-size: 1.1rem;';
        priceWrapper.appendChild(price);
        
        content.appendChild(priceWrapper);
      }
      
      // Explanation badge (optional)
      if (product.explanation) {
        var badge = document.createElement('div');
        badge.textContent = '✨';
        badge.title = product.explanation;
        badge.style.cssText = 'position: absolute; top: 8px; right: 8px; background: rgba(14, 165, 233, 0.9); color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px;';
        card.style.position = 'relative';
        card.appendChild(badge);
      }
      
      link.appendChild(content);
      card.appendChild(link);
      grid.appendChild(card);
      
      // Track click
      link.onclick = function() {
        if (product.salla_product_id) {
          trackInteraction(product.salla_product_id, 'view');
        }
      };
    });
    
    container.appendChild(grid);
    return container;
  }

  // Load recommendations
  function loadRecommendations() {
    if (!STORE_ID) {
      console.warn('Nomo Recommendations: Store ID not found. Trying to detect from page...');
      
      // Last resort: Try to find store ID from page content
      var pageText = document.documentElement.innerHTML;
      
      // Pattern 1: Look for store ID in JSON-LD or script tags
      var jsonLdMatch = pageText.match(/"store[_-]?id"\\s*:\\s*"?([0-9]+)"?/i);
      if (jsonLdMatch) STORE_ID = jsonLdMatch[1];
      
      // Pattern 2: Look for store ID in window object
      if (!STORE_ID && window.store && window.store.id) {
        STORE_ID = window.store.id;
      }
      
      if (!STORE_ID) {
        console.error('Nomo Recommendations: Could not detect store ID. Please set window.__NOMO_STORE_ID__ manually.');
        return;
      } else {
        console.log('Nomo Recommendations: Store ID detected:', STORE_ID);
      }
    }
    
    var url = BASE_URL + '/api/recommendations/customer/';
    if (CUSTOMER_ID) {
      url += CUSTOMER_ID + '/';
    }
    
    var viewedProducts = window.__NOMO_VIEWED_PRODUCTS__ || [];
    if (viewedProducts.length > 0) {
      url += '?viewed_products=' + viewedProducts.join(',');
    }
    
    fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'ngrok-skip-browser-warning': 'true'
      }
    })
    .then(function(response) {
      if (!response.ok) {
        if (response.status === 404) {
          console.warn('Nomo Recommendations: No recommendations available yet. Sync products first.');
        }
        throw new Error('HTTP ' + response.status);
      }
      return response.json();
    })
    .then(function(data) {
      if (data.recommendations && data.recommendations.length > 0) {
        var widget = createRecommendationsWidget(data.recommendations, 'موصى به لك');
        if (widget) {
          // Insert widget in specific container or find best location
          var target = document.querySelector('[data-nomo-recommendations]');
          
          if (!target) {
            // Try common Salla theme locations
            target = document.querySelector('.products-section') || 
                     document.querySelector('.related-products') ||
                     document.querySelector('main .container') ||
                     document.querySelector('main') ||
                     document.querySelector('.page-content') ||
                     document.body;
          }
          
          if (target) {
            // Insert before end of target
            target.appendChild(widget);
          }
        }
      }
    })
    .catch(function(error) {
      console.warn('Nomo Recommendations: Failed to load', error);
    });
  }

  // Track product interaction
  function trackInteraction(productId, type) {
    if (!STORE_ID || !productId) return;
    
    fetch(BASE_URL + '/api/recommendations/track/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true'
      },
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

  // Track product views on page load
  function trackCurrentProduct() {
    var productId = window.__NOMO_CURRENT_PRODUCT_ID__;
    
    // Try to get product ID from Salla theme variables
    if (!productId && window.Salla && window.Salla.product) {
      productId = window.Salla.product.id;
    }
    
    // Try to get from URL or page data
    if (!productId) {
      var urlMatch = window.location.pathname.match(/\\/products\\/(\\d+)/);
      if (urlMatch) productId = urlMatch[1];
    }
    
    if (productId) {
      trackInteraction(productId, 'view');
    }
  }

  // Initialize when DOM is ready
  function init() {
    trackCurrentProduct();
    
    // Wait a bit for page to fully load
    setTimeout(function() {
      loadRecommendations();
    }, 500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
"""
    response = HttpResponse(js, content_type='application/javascript')
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
    return response

