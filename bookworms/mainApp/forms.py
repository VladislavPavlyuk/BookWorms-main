import logging
import os

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.core.files.base import File

from .models import AvatarCollection

User = get_user_model()
logger = logging.getLogger(__name__)


def _copy_collection_avatar_to_user(user, collection: AvatarCollection | None) -> None:
    """Копіює файл з колекції в user.avatar (upload_to=avatars/), щоб URL був /media/avatars/… як у ручного завантаження."""
    if not collection or not collection.image:
        return
    name = os.path.basename(collection.image.name)
    try:
        with collection.image.open("rb") as src:
            user.avatar.save(name, File(src), save=False)
    except OSError as exc:
        logger.warning("Не вдалося прочитати аватар з колекції id=%s: %s", collection.pk, exc)

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

        for name, field in self.fields.items():
            if name == "avatar_choice":
                field.widget.attrs["class"] = "btn-check"
                continue
            field.widget.attrs["class"] = "form-control"

    def save(self, commit=True):
        user = super().save(commit=False)
        choice = self.cleaned_data.get("avatar_choice")
        if choice and not self.files.get("avatar"):
            _copy_collection_avatar_to_user(user, choice)
        if commit:
            user.save()
        return user

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

        for name, field in self.fields.items():
            if name == "avatar_choice":
                field.widget.attrs["class"] = "btn-check"
                continue
            field.widget.attrs["class"] = "form-control"

    def save(self, commit=True):
        user = super().save(commit=False)
        choice = self.cleaned_data.get("avatar_choice")
        if choice and not self.files.get("avatar"):
            _copy_collection_avatar_to_user(user, choice)
        if commit:
            user.save()
        return user


class AddIsbnForm(forms.Form):
    """Поле ISBN для сторінки "Моя полиця"; вікові групи задаються окремо на картці книги."""
    isbn = forms.CharField(
        label="ISBN (10 або 13)",
        max_length=32,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "9780140328721"}),
    )


class AddBookManualForm(forms.Form):
    """Додавання книги на полицю без Open Library - усі поля вводяться вручну."""

    isbn = forms.CharField(
        label="ISBN (10 або 13 цифр)",
        max_length=32,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "9780140328721"}
        ),
    )
    title = forms.CharField(
        label="Назва",
        max_length=500,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    authors = forms.CharField(
        label="Автори",
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    publisher = forms.CharField(
        label="Видавець",
        max_length=300,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    publish_date = forms.CharField(
        label="Дата видання",
        max_length=64,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "2020 або 15.03.2020"}),
    )
    cover_url = forms.URLField(
        label="URL обкладинки",
        max_length=500,
        required=False,
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://…"}),
    )
    info_url = forms.URLField(
        label="Посилання на сторінку книги (необов’язково)",
        max_length=500,
        required=False,
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://openlibrary.org/…"}),
    )

    def clean_isbn(self):
        raw = (self.cleaned_data.get("isbn") or "").strip().upper()
        compact = raw.replace("-", "").replace(" ", "")
        if len(compact) == 10 and compact[-1] == "X":
            head = "".join(c for c in compact[:9] if c.isdigit())
            if len(head) != 9:
                raise ValidationError(
                    "ISBN-10: 9 цифр і контрольна X, або лише цифри."
                )
            return head + "X"
        digits = "".join(c for c in compact if c.isdigit())
        if len(digits) not in (10, 13):
            raise ValidationError(
                "ISBN має містити 10 або 13 цифр (можна з дефісами; для ISBN-10 допускається X в кінці)."
            )
        return digits


class SendExchangePartnerMessageForm(forms.Form):
    """Лише текст: одержувач задається з контексту обміну/позики (partner id у view)."""
    body = forms.CharField(
        label="Текст повідомлення",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    )