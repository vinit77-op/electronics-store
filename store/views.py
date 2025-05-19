from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import models
from .models import Product, CartItem, Order, OrderItem, Category, Review
from django.db.models import Q
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.urls import reverse
from django.db.models import Avg
from django.contrib.auth.views import LogoutView
from django.utils.timezone import now
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse

def home(request):
    category_code = request.GET.get('category')  # renamed for clarity
    query = request.GET.get('q', '')

    categories = Category.objects.all()

    products = Product.objects.all()

    if category_code:
        # Filter products where the related category's code matches category_code
        products = products.filter(category__code=category_code)

    if query:
        products = products.filter(name__icontains=query)

    # Annotate each product with average rating from related reviews
    products = products.annotate(avg_rating=Avg('reviews__rating'))

    context = {
        'products': products,
        'categories': [(cat.code, cat.name) for cat in categories],  # use code here
        'selected_category': category_code,
        'query': query,
        "current_time": timezone.now(),
    }
    return render(request, 'home.html', context)

@login_required
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # Check if product is out of stock
    if product.stock <= 0:
        response_data = {
            'status': 'error',
            'message': f'{product.name} is out of stock.',
        }
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse(response_data, status=400)
        messages.error(request, response_data['message'])
        return redirect('home')

    # Get or create cart item
    cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product)

    # Check if adding more would exceed stock
    if cart_item.quantity >= product.stock:
        response_data = {
            'status': 'warning',
            'message': f'Only {product.stock} of {product.name} available in stock.',
            'cart_quantity': cart_item.quantity,
        }
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse(response_data, status=400)
        messages.warning(request, response_data['message'])
        return redirect('view_cart')

    # Increment quantity safely
    cart_item.quantity += 1
    cart_item.save()

    response_data = {
        'status': 'success',
        'message': f'{product.name} added to cart',
        'cart_quantity': cart_item.quantity,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse(response_data)
    
    messages.success(request, response_data['message'])
    return redirect('view_cart')

@login_required
def view_cart(request):
    if request.method == 'POST':
        for key, value in request.POST.items():
            if key.startswith('quantity_'):
                try:
                    item_id = int(key.split('_')[1])
                    quantity = int(value)
                    # update quantity logic here
                    cart_item = CartItem.objects.get(id=item_id, user=request.user)
                    if quantity > 0:
                        cart_item.quantity = quantity
                        cart_item.save()
                except (ValueError, CartItem.DoesNotExist):
                    pass
        # After updating, reload the cart page (same route)
        return redirect(reverse('view_cart'))

    # GET request - show cart items
    cart_items = CartItem.objects.filter(user=request.user)
    return render(request, 'cart.html', {'cart_items': cart_items})

@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    item.delete()
    return redirect('view_cart')

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'order_history.html', {'orders': orders})

@login_required
def update_cart(request):
    if request.method == 'POST':
        for item in CartItem.objects.filter(user=request.user):
            qty_key = f'quantity_{item.id}'
            if qty_key in request.POST:
                try:
                    new_qty = int(request.POST[qty_key])
                    if new_qty > 0:
                        item.quantity = new_qty
                        item.save()
                except ValueError:
                    pass
    return redirect('view_cart')

@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user)

    if request.method == 'POST' and cart_items.exists():
        order = Order.objects.create(user=request.user, total_price=0)  # temporarily 0
        total = 0

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity
            )
            total += item.get_total_price()

        order.total_price = total  # update the correct total
        order.save()

        cart_items.delete()
        return redirect('order_history')

    total = sum(item.get_total_price() for item in cart_items)
    return render(request, 'checkout.html', {
        'cart_items': cart_items,
        'total': total
    })

# Product Detail
def product_detail(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    reviews = Review.objects.filter(product=product).select_related('user')
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
    current_time = now()

    existing_review = None
    if request.user.is_authenticated:
        existing_review = Review.objects.filter(user=request.user, product=product).first()

    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')

        if rating and comment:
            if existing_review:
                existing_review.rating = rating
                existing_review.comment = comment
                existing_review.save()
            else:
                Review.objects.create(
                    product=product,
                    user=request.user,
                    rating=rating,
                    comment=comment
                )
        return redirect('product_detail', product_id=product_id)

    context = {
        'product': product,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'existing_review': existing_review,
        'current_time': current_time,
    }

    return render(request, 'product_detail.html', context)

# Signup
def signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, 'registration/signup.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return render(request, 'registration/signup.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already in use.")
            return render(request, 'registration/signup.html')

        # Ensure all required fields are filled
        if not all([first_name, last_name, username, email, password1]):
            messages.error(request, "All fields are required.")
            return render(request, 'registration/signup.html')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name
        )
        login(request, user)
        return redirect('home')

    return render(request, 'registration/signup.html')

# Profile
@login_required
def profile(request):
    return render(request, 'registration/profile.html')

# Custom Logout
class CustomLogoutView(LogoutView):
    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

# Add Category
@user_passes_test(lambda u: u.is_staff)
def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        Category.objects.create(name=name, code=code)
        return redirect('category_list')