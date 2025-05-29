from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Category, Product, Order, OrderItem, Cart, CartItem, Review
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .forms import ProductForm
from django.http import Http404
import random

# Create your views here.

def get_discount_context(request):
    discount_code = request.session.get('discount_code')
    valid_codes = {
        'SALE10': 10,
        'SALE20': 20,
        'SALE30': 30,
        'SALE50': 50,
    }
    discount_percent = valid_codes.get(discount_code, 0) if discount_code else 0
    return {'discount_code': discount_code, 'discount_percent': discount_percent}

def product_list(request, category_slug=None):
    category = None
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)
    
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
    
    # Search functionality
    query = request.GET.get('q')
    if query:
        products = products.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query)
        )
    
    # Pagination
    paginator = Paginator(products, 12)  # Show 12 products per page
    page = request.GET.get('page')
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)
    
    context = {
        'category': category,
        'categories': categories,
        'products': products,
        'query': query,
    }
    context.update(get_discount_context(request))
    return render(request, 'store/product/list.html', context)

def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id, slug=slug, available=True)
    reviews = product.reviews.all()
    context = {
        'product': product,
        'reviews': reviews,
    }
    context.update(get_discount_context(request))
    return render(request, 'store/product/detail.html', context)

@login_required
def cart_detail(request):
    cart = Cart.objects.filter(user=request.user).first()
    discount = 0
    discount_code = ''
    discount_percent = 0
    valid_codes = {
        'SALE10': 10,
        'SALE20': 20,
        'SALE30': 30,
        'SALE50': 50,
    }
    if request.method == 'POST' and 'discount_code' in request.POST:
        code = request.POST.get('discount_code', '').strip().upper()
        if code in valid_codes:
            request.session['discount_code'] = code
            messages.success(request, f'Áp dụng mã {code} thành công!')
        else:
            request.session.pop('discount_code', None)
            messages.error(request, 'Mã giảm giá không hợp lệ!')
        return redirect('store:cart_detail')
    code = request.session.get('discount_code')
    if code and code in valid_codes:
        discount_percent = valid_codes[code]
        discount = int(cart.get_total_price() * discount_percent / 100) if cart else 0
        discount_code = code
    total_after_discount = cart.get_total_price() - discount if cart else 0
    context = {
        'cart': cart,
        'discount': discount,
        'discount_code': discount_code,
        'discount_percent': discount_percent,
        'total_after_discount': total_after_discount,
    }
    context.update(get_discount_context(request))
    return render(request, 'store/cart/detail.html', context)

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    
    messages.success(request, f'{product.name} đã được thêm vào giỏ hàng.')
    return redirect('store:cart_detail')

@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    messages.success(request, 'Sản phẩm đã được xóa khỏi giỏ hàng.')
    return redirect('store:cart_detail')

@login_required
def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    
    if quantity > cart_item.product.stock:
        messages.error(request, 'Not enough stock available.')
    else:
        cart_item.quantity = quantity
        cart_item.save()
        messages.success(request, 'Cart updated.')
    
    return redirect('store:cart_detail')

@login_required
def checkout(request):
    cart = Cart.objects.filter(user=request.user).first()
    if not cart or not cart.items.exists():
        messages.warning(request, 'Giỏ hàng của bạn đang trống.')
        return redirect('store:cart_detail')
    
    if request.method == 'POST':
        # Create order
        order = Order.objects.create(
            user=request.user,
            full_name=request.POST.get('full_name'),
            email=request.POST.get('email'),
            address=request.POST.get('address'),
            phone=request.POST.get('phone'),
            total_amount=cart.get_total_price()
        )
        
        # Create order items
        for item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=item.product,
                price=item.product.price,
                quantity=item.quantity
            )
        
        # Clear cart
        cart.delete()
        
        messages.success(request, 'Đặt hàng thành công!')
        return redirect('store:order_detail', order_id=order.id)
    
    context = {'cart': cart}
    context.update(get_discount_context(request))
    return render(request, 'store/order/checkout.html', context)

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user)
    context = {'orders': orders}
    context.update(get_discount_context(request))
    return render(request, 'store/order/history.html', context)

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    context = {'order': order}
    context.update(get_discount_context(request))
    return render(request, 'store/order/detail.html', context)

@login_required
def add_review(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        raise Http404('Sản phẩm không tồn tại.')
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            comment=comment
        )
        messages.success(request, 'Đánh giá của bạn đã được gửi.')
        return redirect('store:product_detail', id=product.id, slug=product.slug)
    return render(request, 'store/product/add_review.html', {'product': product})

@user_passes_test(lambda u: u.is_staff)
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã thêm sản phẩm mới!')
            return redirect('store:product_list')
    else:
        form = ProductForm()
    return render(request, 'store/product/add_product.html', {'form': form})

@login_required
def spin_wheel(request):
    prizes = [
        {'label': 'Giảm 10%', 'code': 'SALE10', 'percent': 10},
        {'label': 'Giảm 20%', 'code': 'SALE20', 'percent': 20},
        {'label': 'Giảm 30%', 'code': 'SALE30', 'percent': 30},
        {'label': 'Không trúng', 'code': None, 'percent': 0},
        {'label': 'Giảm 50%', 'code': 'SALE50', 'percent': 50},
        {'label': 'Không trúng', 'code': None, 'percent': 0},
    ]
    result = None
    if request.method == 'POST':
        result = random.choice(prizes)
        request.session['spin_result'] = result
    else:
        result = request.session.pop('spin_result', None)
    return render(request, 'store/spin_wheel.html', {'result': result})

def home(request):
    context = get_discount_context(request)
    return render(request, 'store/home.html', context)
