from .models import Category

def categories(request):
    return {'categories': Category.objects.all()}

def discount_info(request):
    discount_code = request.session.get('discount_code')
    valid_codes = {
        'SALE10': 10,
        'SALE20': 20,
        'SALE30': 30,
        'SALE50': 50,
    }
    discount_percent = valid_codes.get(discount_code, 0) if discount_code else 0
    return {'discount_code': discount_code, 'discount_percent': discount_percent} 