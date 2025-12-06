from django.db import models
from decimal import Decimal


class Product(models.Model):
    """Product from Salla store"""
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="products")
    salla_product_id = models.CharField(max_length=100, db_index=True)
    
    # Product details
    name = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=200, null=True, blank=True)
    tags = models.JSONField(default=list, blank=True, help_text="List of product tags")
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sku = models.CharField(max_length=100, null=True, blank=True)
    
    # Product status
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    
    # Metadata
    image_url = models.URLField(null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "salla_product_id"], name="uq_product_per_merchant"),
        ]
        indexes = [
            models.Index(fields=["merchant", "is_active"]),
            models.Index(fields=["category"]),
        ]
        verbose_name = "Product"
        verbose_name_plural = "Products"
    
    def __str__(self):
        return f"{self.name} ({self.salla_product_id})"


class Customer(models.Model):
    """Customer from Salla store"""
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="customers")
    salla_customer_id = models.CharField(max_length=100, db_index=True)
    
    # Customer details
    name = models.CharField(max_length=200, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    
    # Metadata
    first_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "salla_customer_id"], name="uq_customer_per_merchant"),
        ]
        indexes = [
            models.Index(fields=["merchant"]),
        ]
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
    
    def __str__(self):
        return f"{self.name or self.email or self.salla_customer_id} ({self.merchant.name})"


class Order(models.Model):
    """Order from Salla store"""
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="orders")
    customer = models.ForeignKey("Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    salla_order_id = models.CharField(max_length=100, db_index=True)
    
    # Order details
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=50, null=True, blank=True)
    
    # Timestamps
    ordered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "salla_order_id"], name="uq_recommendations_order_per_merchant"),
        ]
        indexes = [
            models.Index(fields=["merchant", "ordered_at"]),
            models.Index(fields=["customer"]),
        ]
        verbose_name = "Order"
        verbose_name_plural = "Orders"
    
    def __str__(self):
        return f"Order {self.salla_order_id} - {self.total_amount} SAR"


class OrderItem(models.Model):
    """Individual product in an order"""
    order = models.ForeignKey("Order", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items")
    salla_product_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Item details
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    product_name = models.CharField(max_length=500, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["product"]),
        ]
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
    
    def __str__(self):
        return f"{self.product_name or 'Product'} x{self.quantity} in Order {self.order.salla_order_id}"


class CustomerInteraction(models.Model):
    """Track customer interactions with products"""
    VIEW = "view"
    CART = "cart"
    PURCHASE = "purchase"
    INTERACTION_TYPES = [
        (VIEW, "View"),
        (CART, "Add to Cart"),
        (PURCHASE, "Purchase"),
    ]
    
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="interactions")
    customer = models.ForeignKey("Customer", on_delete=models.CASCADE, null=True, blank=True, related_name="interactions")
    product = models.ForeignKey("Product", on_delete=models.CASCADE, related_name="interactions")
    
    # Interaction details
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES, default=VIEW)
    session_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    
    # Timestamps
    occurred_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["merchant", "customer", "occurred_at"]),
            models.Index(fields=["product", "interaction_type"]),
            models.Index(fields=["session_id"]),
        ]
        verbose_name = "Customer Interaction"
        verbose_name_plural = "Customer Interactions"
    
    def __str__(self):
        return f"{self.customer or 'Anonymous'} {self.interaction_type} {self.product.name}"
