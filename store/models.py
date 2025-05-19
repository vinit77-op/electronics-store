from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP

class Category(models.Model):
    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=50, unique=True, null=True, blank=True)

    def __str__(self):
        return self.name  # <-- This makes admin show the category name

# Product Model
class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    discount_percentage = models.PositiveIntegerField(default=0)
    discount_end_time = models.DateTimeField(null=True, blank=True)
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')

    def __str__(self):
        return self.name

    @property
    def average_rating(self):
        avg = self.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg or 0, 1)

    @property
    def discounted_price(self):
        if self.discount_percentage > 0:
            discount = Decimal(self.discount_percentage) / Decimal(100)
            discounted = self.price * (Decimal(1) - discount)
            return discounted.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return self.price

# Review
class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField()
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

# Cart Items
class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.product.name} (x{self.quantity})"

    def get_total_price(self):
        return self.product.price * self.quantity

# Order
class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    custom_order_id = models.CharField(max_length=50, unique=True, blank=True, null=True)  # New field

    def __str__(self):
        return self.custom_order_id or f"Order #{self.id} by {self.user.username}"

    def save(self, *args, **kwargs):
        if not self.custom_order_id:
            last_order = Order.objects.filter(user=self.user).order_by('-id').first()
            user_order_number = 1
            if last_order and last_order.custom_order_id:
                try:
                    user_order_number = int(last_order.custom_order_id.split('-')[-1]) + 1
                except:
                    pass
            self.custom_order_id = f"ORD-{self.user.id}-{user_order_number:03d}"
        super().save(*args, **kwargs)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def get_total_price(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

def product_detail(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    reviews = Review.objects.filter(product=product).order_by('-created_at')

    if request.method == 'POST' and request.user.is_authenticated:
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')

        # Save the review
        Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            comment=comment
        )
        return redirect('product_detail', product_id=product.id)

    # Pass the average rating and review list
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    context = {
        'product': product,
        'reviews': reviews,
        'avg_rating': avg_rating,
    }
    return render(request, 'product_detail.html', context)