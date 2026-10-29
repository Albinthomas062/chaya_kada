from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Item, DailyChallenge

class SimpleUserCreationForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        min_length=2,
        help_text='Just 2+ characters needed',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter any username (min 2 chars)'
        })
    )
    
    password1 = forms.CharField(
        label='Password',
        min_length=8,
        help_text='Just 8 characters needed',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter any password (min 8 chars)'
        })
    )
    
    password2 = forms.CharField(
        label='Confirm Password',
        help_text='Just repeat the same password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repeat the password'
        })
    )

    class Meta:
        model = User
        fields = ("username", "password1", "password2")

    def clean_username(self):
        username = self.cleaned_data['username']
        
        # Only check if username already exists
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken. Try another one.")
        
        return username

    def clean_password1(self):
        password1 = self.cleaned_data['password1']
        
        # Minimal validation - just length
        if len(password1) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
            
        return password1

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        
        if password1 and password2 and password1 != password2:
            raise ValidationError("The two password fields must match.")
            
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

#for custom admin 
class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'emoji', 'image', 'category', 'price', 'description', 'available', 'can_be_shared', 'sort_order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'emoji': forms.TextInput(attrs={'placeholder': '☕'}),
            'price': forms.NumberInput(attrs={'min': 0}),
            'sort_order': forms.NumberInput(attrs={'min': 0}),
        }
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Validate file size (max 5MB)
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file too large ( > 5MB )")
            
            # Validate file type
            valid_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(image, 'content_type') and image.content_type not in valid_types:
                raise forms.ValidationError("Invalid image type. Use JPEG, PNG, GIF, or WebP.")
        
        return image

class AssignChallengeForm(forms.Form):
    challenge_type = forms.ChoiceField(choices=DailyChallenge.CHALLENGE_TYPES)
    coins_earned = forms.IntegerField(min_value=1, initial=10)

