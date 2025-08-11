from django import forms
from .models import Product

class AddToCartForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), widget=forms.HiddenInput())
    weight_grams = forms.IntegerField(min_value=1, label="Weight (grams)",
                                      widget=forms.NumberInput(attrs={'class':'form-control','placeholder':'grams'}))

# Optional: simple checkout form to choose payment method
class CheckoutForm(forms.Form):
    method = forms.ChoiceField(choices=(('cash','Cash'),('online','Online')), widget=forms.RadioSelect)
