from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Логін",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )


class UserRegisterForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ("username", "biography", "avatar") + UserCreationForm.Meta.fields
        labels = {
            'username': "Логін",
            'biography': "Біографія",
            'avatar': "Аватар",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'password1' in self.fields:
            self.fields['password1'].label = "Пароль"
        if 'password2' in self.fields:
            self.fields['password2'].label = "Повторіть пароль"

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'biography', 'avatar']
        labels = {
            'username': 'Логін',
            'biography': 'Біографія',
            'avatar': 'Аватар'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class AddIsbnForm(forms.Form):
    """Проста форма без моделі: лише поле ISBN для сторінки «Моя полиця»."""
    isbn = forms.CharField(
        label="ISBN (10 або 13)",
        max_length=32,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "9780140328721"}),
    )