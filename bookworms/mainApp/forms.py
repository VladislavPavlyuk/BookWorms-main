from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from .models import AvatarCollection
from django.core.exceptions import ValidationError

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
    avatar_choice = forms.ModelChoiceField(
        queryset=AvatarCollection.objects.all(),
        required=False,
        widget=forms.RadioSelect(attrs={'class': 'btn-check'}),
        label="Або оберіть готовий аватар"
    )

    # Добавляем поле email явно, чтобы сделать его обязательным
    email = forms.EmailField(
        required=True,
        label="Електронна пошта",
        widget=forms.EmailInput(attrs={'placeholder': 'example@mail.com'})
    )

    class Meta:
        model = User
        fields = ("username", "email", "biography", "avatar")
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

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Ця електронна адреса вже використовується.")
        return email

class UserUpdateForm(forms.ModelForm):
    avatar_choice = forms.ModelChoiceField(
        queryset=AvatarCollection.objects.all(),
        required=False,
        widget=forms.RadioSelect(attrs={'class': 'btn-check'}),
        label="Або оберіть готовий аватар"
    )

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
    """Поле ISBN для сторінки "Моя полиця"; вікові групи задаються окремо на картці книги."""
    isbn = forms.CharField(
        label="ISBN (10 або 13)",
        max_length=32,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "9780140328721"}),
    )


class SendExchangePartnerMessageForm(forms.Form):
    """Лише текст: одержувач задається з контексту обміну/позики (partner id у view)."""
    body = forms.CharField(
        label="Текст повідомлення",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    )