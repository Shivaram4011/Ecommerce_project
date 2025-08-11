from django.db import models
from django.contrib.auth.models import User

class Product(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="products/")
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2)  # Rs per kg

    def __str__(self):
        return self.name

class Order(models.Model):
    PAYMENT_CHOICES = (('cash','Cash'), ('online','Online'))
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, blank=True, null=True)
    payment_status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    qr_code = models.ImageField(upload_to='qrcodes/', blank=True, null=True)  # saved QR image file path
    receipt_pdf = models.FileField(upload_to='receipts/', blank=True, null=True)

    def __str__(self):
        return f"Order #{self.id} - {self.customer.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    weight_grams = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # price for this item

    def __str__(self):
        return f"{self.product.name} ({self.weight_grams} g)"
