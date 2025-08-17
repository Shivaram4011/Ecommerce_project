from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, authenticate, logout
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponse, FileResponse
from decimal import Decimal
import qrcode
import os
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from .models import Product, Order, OrderItem
from .forms import AddToCartForm, CheckoutForm

# --- Auth views ---
def register_view(request):
    if request.user.is_authenticated:
        return redirect('product_list')
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'store/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('product_list')  # Redirect to products after login
        else:
            return render(request, 'store/login.html', {'error': 'Invalid username or password'})
    return render(request, 'store/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

# --- Cart helpers (session-based) ---
def _cart_session(request):
    return request.session.setdefault('cart', {})  

@login_required
def product_list(request):
    products = Product.objects.all()
    return render(request, 'store/product_list.html', {'products': products})

@login_required
def add_to_cart(request):
    if request.method == "POST":
        form = AddToCartForm(request.POST)
        if form.is_valid():
            product = form.cleaned_data['product']
            weight_grams = form.cleaned_data['weight_grams']
            cart = _cart_session(request)
            # support multiple of same product: store as list of dicts per product id
            card_key = str(product.id)
            cart.setdefault(card_key, [])
            cart[card_key].append({'weight_grams': weight_grams})
            request.session.modified = True
    return redirect('product_list')

@login_required
def cart_view(request):
    cart = _cart_session(request)
    items = []
    total = Decimal('0.00')
    for pid, entries in cart.items():
        product = get_object_or_404(Product, pk=int(pid))
        for e in entries:
            w = int(e['weight_grams'])
            price = (product.price_per_kg / Decimal(1000)) * Decimal(w)
            total += price
            items.append({'product': product, 'weight_grams': w, 'price': price})
    return render(request, 'store/cart.html', {'items': items, 'total': total})

@login_required
def remove_from_cart(request, product_id, index):
    
    cart = _cart_session(request)
    key = str(product_id)
    if key in cart:
        try:
            cart[key].pop(index)
            if not cart[key]:
                del cart[key]
            request.session.modified = True
        except IndexError:
            pass
    return redirect('cart')

@login_required
def checkout(request):
    cart = _cart_session(request)
    if not cart:
        return redirect('product_list')
    form = CheckoutForm(request.POST or None)
    items = []
    total = Decimal('0.00')
    for pid, entries in cart.items():
        product = get_object_or_404(Product, pk=int(pid))
        for e in entries:
            w = int(e['weight_grams'])
            price = (product.price_per_kg / Decimal(1000)) * Decimal(w)
            total += price
            items.append({'product': product, 'weight_grams': w, 'price': price})

    if request.method == 'POST' and form.is_valid():
        method = form.cleaned_data['method']
        # create order
        order = Order.objects.create(customer=request.user, total_price=total, payment_method=method)
        # create items
        for it in items:
            OrderItem.objects.create(
                order=order,
                product=it['product'],
                weight_grams=it['weight_grams'],
                price=it['price']
            )

        # handle payment method
        if method == 'cash':
            order.payment_status = True
            order.save()
        elif method == 'online':
            # generate QR code that encodes a payment instruction/text
            qr_text = f"Pay Rs. {order.total_price} to EcomStore Order:{order.id}"
            img = qrcode.make(qr_text)
            qr_filename = f"qr_{order.id}.png"
            qr_path = os.path.join(settings.MEDIA_ROOT, 'qrcodes', qr_filename)
            os.makedirs(os.path.dirname(qr_path), exist_ok=True)
            img.save(qr_path)
            # save path relative to media
            order.qr_code.name = f"qrcodes/{qr_filename}"
            order.save()
        # generate receipt PDF and attach
        generate_receipt_pdf(order)
        # clear cart session
        request.session['cart'] = {}
        request.session.modified = True
        return redirect('receipt', order_id=order.id)

    return render(request, 'store/checkout.html', {'items': items, 'total': total, 'form': form})

@login_required
def receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    return render(request, 'store/receipt.html', {'order': order})

# --- Utilities: generate PDF receipt using ReportLab ---
def generate_receipt_pdf(order: Order):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # header
    p.setFont("Helvetica-Bold", 14)
    p.drawString(40, height - 50, "Ecom Dry Fruits Store - Receipt")
    p.setFont("Helvetica", 10)
    p.drawString(40, height - 70, f"Order ID: {order.id}")
    p.drawString(300, height - 70, f"Date: {order.created_at.strftime('%Y-%m-%d %H:%M')}")

    # customer
    p.drawString(40, height - 100, f"Customer: {order.customer.get_full_name() or order.customer.username}")
    p.drawString(40, height - 115, f"Email: {order.customer.email or 'N/A'}")
    p.drawString(40, height - 135, f"Payment Method: {order.payment_method}    Paid: {'Yes' if order.payment_status else 'No'}")

    # Table headers
    p.setFont("Helvetica-Bold", 11)
    y = height - 165
    p.drawString(40, y, "Product")
    p.drawString(220, y, "Weight (g)")
    p.drawString(320, y, "Price (Rs)")
    p.line(40, y-5, width-40, y-5)
    p.setFont("Helvetica", 10)
    y -= 20

    # items
    for item in order.items.all():
        p.drawString(40, y, str(item.product.name))
        p.drawString(220, y, str(item.weight_grams))
        p.drawString(320, y, f"{item.price:.2f}")
        y -= 18
        if y < 80:
            p.showPage()
            y = height - 50

    # total
    p.setFont("Helvetica-Bold", 12)
    p.drawString(220, y - 10, "Total:")
    p.drawString(320, y - 10, f"{order.total_price:.2f}")

    # if QR exists, show note
    if order.qr_code:
        p.setFont("Helvetica", 9)
        p.drawString(40, 60, f"QR stored at: {order.qr_code.url}")

    p.showPage()
    p.save()
    buffer.seek(0)

    # save to a file in media/receipts/
    receipts_dir = os.path.join(settings.MEDIA_ROOT, 'receipts')
    os.makedirs(receipts_dir, exist_ok=True)
    filename = f"receipt_order_{order.id}.pdf"
    filepath = os.path.join(receipts_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(buffer.read())
    # attach to order
    order.receipt_pdf.name = f"receipts/{filename}"
    order.save()
