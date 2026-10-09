from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from .models import AvatarCollection, UserSubProfile
from django.core.exceptions import ValidationError

User = get_user_model()


def _apply_avatar_choice(user, choice: AvatarCollection | None) -> None:
    """Copy selected collection image into user.avatar (no file browse)."""
    if not choice or not choice.image:
        return
    choice.image.open("rb")
    try:
        data = choice.image.read()
    finally:
        choice.image.close()
    name = choice.image.name.rsplit("/", 1)[-1] or f"avatar_{choice.pk}.png"
    user.avatar.save(name, ContentFile(data), save=False)


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Логін",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "username",
                "lang": "uk",
                "spellcheck": "false",
            }
        ),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "current-password",
                "lang": "uk",
                "spellcheck": "false",
            }
        ),
    )



class UserRegisterForm(UserCreationForm):
    avatar_choice = forms.ModelChoiceField(
        queryset=AvatarCollection.objects.all(),
        required=False,
        empty_label=None,
        widget=forms.RadioSelect(attrs={"class": "avatar-pick__radio"}),
        label="Оберіть аватар",
    )

    email = forms.EmailField(
        required=True,
        label="Електронна пошта",
        widget=forms.EmailInput(attrs={"placeholder": "example@mail.com"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "biography")
        labels = {
            "username": "Логін",
            "biography": "Про себе",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "password1" in self.fields:
            self.fields["password1"].label = "Пароль"
            self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
            self.fields["password1"].widget.attrs["lang"] = "uk"
        if "password2" in self.fields:
            self.fields["password2"].label = "Повторіть пароль"
            self.fields["password2"].widget.attrs["autocomplete"] = "new-password"
            self.fields["password2"].widget.attrs["lang"] = "uk"
        if "username" in self.fields:
            self.fields["username"].widget.attrs["lang"] = "uk"
        if "email" in self.fields:
            self.fields["email"].widget.attrs["lang"] = "uk"

        for name, field in self.fields.items():
            if name == "avatar_choice":
                continue
            field.widget.attrs["class"] = "form-control"

    def clean_email(self):
        from .registration_availability import email_taken

        email = (self.cleaned_data.get("email") or "").strip()
        if email_taken(email):
            raise ValidationError("Ця електронна адреса вже використовується.")
        return email

    def clean_username(self):
        from .registration_availability import suggest_usernames, username_taken

        username = (self.cleaned_data.get("username") or "").strip()
        if username_taken(username):
            suggestions = suggest_usernames(username)
            msg = "Цей логін уже зайнятий."
            if suggestions:
                msg += (
                    " Оберіть і підтвердіть запропонований унікальний логін "
                    f"(напр. {suggestions[0]})."
                )
            raise ValidationError(msg)
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        _apply_avatar_choice(user, self.cleaned_data.get("avatar_choice"))
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    avatar_choice = forms.ModelChoiceField(
        queryset=AvatarCollection.objects.all(),
        required=False,
        empty_label=None,
        widget=forms.RadioSelect(attrs={"class": "avatar-pick__radio"}),
        label="Оберіть аватар",
    )
    preferred_subjects = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "theme-pick"}),
        label="Теми / жанри",
        help_text="Список зростає разом із темами в каталозі книг.",
    )

    class Meta:
        model = User
        fields = ["username", "biography", "birthday", "place", "preferred_subjects"]
        labels = {
            "username": "Логін",
            "biography": "Про себе",
            "birthday": "Дата народження",
            "place": "Місце проживання",
        }
        widgets = {
            "birthday": forms.DateInput(
                attrs={"type": "date", "max": "9999-12-31"},
                format="%Y-%m-%d",
            ),
            "place": forms.TextInput(attrs={"placeholder": "місто / країна"}),
            "biography": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .book_subjects import catalog_subjects

        catalog = catalog_subjects()
        current = []
        if self.instance and getattr(self.instance, "pk", None):
            current = list(self.instance.preferred_subjects or [])
        # Keep selected themes even if temporarily missing from catalog.
        choices_map = {c.casefold(): c for c in catalog}
        for c in current:
            key = (c or "").casefold()
            if key and key not in choices_map:
                choices_map[key] = c
        choices = [(v, v) for _, v in sorted(choices_map.items(), key=lambda x: x[0])]
        self.fields["preferred_subjects"].choices = choices
        if not self.is_bound:
            self.initial["preferred_subjects"] = current

        for name, field in self.fields.items():
            if name in ("avatar_choice", "preferred_subjects"):
                continue
            field.widget.attrs["class"] = "form-control"
        if "username" in self.fields:
            self.fields["username"].widget.attrs["lang"] = "uk"
        if "birthday" in self.fields:
            self.fields["birthday"].input_formats = ["%Y-%m-%d"]
            self.fields["birthday"].required = False

    def clean_preferred_subjects(self):
        return list(self.cleaned_data.get("preferred_subjects") or [])

    def clean_birthday(self):
        from datetime import date

        bday = self.cleaned_data.get("birthday")
        if bday is None or bday == "":
            return None
        if bday > date.today():
            raise ValidationError("Дата народження не може бути в майбутньому.")
        return bday

    def save(self, commit=True):
        user = super().save(commit=False)
        user.preferred_subjects = self.cleaned_data.get("preferred_subjects") or []
        choice = self.cleaned_data.get("avatar_choice")
        if choice:
            _apply_avatar_choice(user, choice)
        if commit:
            user.save()
        return user


class SubProfileForm(forms.ModelForm):
    preferred_subjects = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "theme-pick"}),
        label="Теми / жанри",
    )

    class Meta:
        model = UserSubProfile
        fields = ["name", "birthday", "place", "preferred_subjects"]
        labels = {
            "name": "Назва",
            "birthday": "Дата народження",
            "place": "Місце проживання",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "напр. Для сина"}),
            "birthday": forms.DateInput(
                attrs={"type": "date", "max": "9999-12-31"},
                format="%Y-%m-%d",
            ),
            "place": forms.TextInput(attrs={"placeholder": "місто / країна"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .book_subjects import catalog_subjects

        catalog = catalog_subjects()
        current = []
        if self.instance and getattr(self.instance, "pk", None):
            current = list(self.instance.preferred_subjects or [])
        choices_map = {c.casefold(): c for c in catalog}
        for c in current:
            key = (c or "").casefold()
            if key and key not in choices_map:
                choices_map[key] = c
        self.fields["preferred_subjects"].choices = [
            (v, v) for _, v in sorted(choices_map.items(), key=lambda x: x[0])
        ]
        if not self.is_bound:
            self.initial["preferred_subjects"] = current
        for name, field in self.fields.items():
            if name == "preferred_subjects":
                continue
            field.widget.attrs["class"] = "form-control"
        if "birthday" in self.fields:
            self.fields["birthday"].input_formats = ["%Y-%m-%d"]
            self.fields["birthday"].required = False

    def clean_preferred_subjects(self):
        return list(self.cleaned_data.get("preferred_subjects") or [])

    def clean_birthday(self):
        from datetime import date

        bday = self.cleaned_data.get("birthday")
        if bday is None or bday == "":
            return None
        if bday > date.today():
            raise ValidationError("Дата народження не може бути в майбутньому.")
        return bday

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.preferred_subjects = self.cleaned_data.get("preferred_subjects") or []
        if commit:
            obj.save()
        return obj


class AddIsbnForm(forms.Form):
    """Поле ISBN для сторінки "Моя полиця"; вікові групи задаються окремо на картці книги."""
    isbn = forms.CharField(
        label="ISBN (10 або 13)",
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "class": "form-control isbn-add-input",
                "placeholder": "9780140328721",
                "maxlength": "17",
                "size": "17",
                "inputmode": "numeric",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
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


class AddBookManualForm(forms.Form):
    """Додавання книги на полицю вручну — ISBN необов'язковий (локальний код якщо немає)."""

    isbn = forms.CharField(
        label="ISBN (необов’язково)",
        max_length=32,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "id": "manualIsbn",
                "placeholder": "якщо є — інакше збережемо з фото",
            }
        ),
    )
    title = forms.CharField(
        label="Назва",
        max_length=500,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "id": "manualTitle",
                "placeholder": "або залиште порожнім — «Книга (локальний запис)»",
            }
        ),
    )
    authors = forms.CharField(
        label="Автори",
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "manualAuthors"}),
    )
    publisher = forms.CharField(
        label="Видавець",
        max_length=300,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "manualPublisher"}),
    )
    publish_date = forms.CharField(
        label="Дата видання",
        max_length=64,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "id": "manualPublishDate",
                "placeholder": "2020 або 15.03.2020",
            }
        ),
    )
    cover_text = forms.CharField(
        label="Текст з обкладинки (AI)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "id": "manualCoverText",
                "rows": 8,
                "placeholder": "Після знімка тут з’явиться весь розпізнаний текст обкладинки",
            }
        ),
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
        if not raw:
            return ""
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


class EditBookManualForm(AddBookManualForm):
    """Same fields as manual add; used to patch an owned manual shelf book."""

    pass


class SendExchangePartnerMessageForm(forms.Form):
    """Лише текст: одержувач задається з контексту обміну/позики (partner id у view)."""
    body = forms.CharField(
        label="",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "aria-label": "Текст повідомлення",
                "placeholder": "Повідомлення…",
            }
        ),
    )


CONTACT_TOPIC_CHOICES = (
    ("bug", "Bug / Помилка"),
    ("feature", "Feature / Ідея"),
    ("account", "Account / Акаунт"),
    ("books", "Books / Полиця / ISBN"),
    ("other", "Other / Інше"),
)

CONTACT_MAX_SCREENSHOTS = 10
CONTACT_MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB
CONTACT_MESSAGE_MAX = 500


class ContactDevelopersForm(forms.Form):
    name = forms.CharField(
        label="Ім’я",
        max_length=120,
        widget=forms.TextInput(
            attrs={"class": "form-control", "autocomplete": "name", "required": True}
        ),
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "email",
                "placeholder": "you@example.com",
            }
        ),
    )
    topic = forms.ChoiceField(
        label="Тема",
        choices=CONTACT_TOPIC_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    message = forms.CharField(
        label="Повідомлення",
        max_length=CONTACT_MESSAGE_MAX,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 6,
                "maxlength": str(CONTACT_MESSAGE_MAX),
                "placeholder": f"До {CONTACT_MESSAGE_MAX} символів",
            }
        ),
    )
    # Screenshots are handled by a raw <input multiple> in the template +
    # browser → Web3Forms FormData (Django FileInput forbids multiple=True).

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user
        if user is not None and getattr(user, "is_authenticated", False):
            # Ім’я / email з профілю — поля приховані в шаблоні.
            if not self.is_bound:
                self.fields["name"].initial = user.username or ""
                self.fields["email"].initial = (user.email or "").strip()
            self.fields["name"].widget = forms.HiddenInput()
            self.fields["email"].widget = forms.HiddenInput()
            self.fields["email"].required = False
            self.fields["email"].help_text = ""
        else:
            self.fields["email"].required = True
            self.fields["email"].help_text = "Обов’язково для незареєстрованих."

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if self._user is not None and getattr(self._user, "is_authenticated", False):
            name = (self._user.username or "").strip() or name
        if not name:
            raise ValidationError("Немає імені користувача в профілі.")
        return name

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if self._user is not None and getattr(self._user, "is_authenticated", False):
            email = (self._user.email or "").strip() or email
        if not email:
            raise ValidationError("У профілі немає email для відповіді.")
        return email

    def clean_message(self):
        msg = (self.cleaned_data.get("message") or "").strip()
        if not msg:
            raise ValidationError("Напишіть повідомлення.")
        if len(msg) > CONTACT_MESSAGE_MAX:
            raise ValidationError(f"Максимум {CONTACT_MESSAGE_MAX} символів.")
        return msg