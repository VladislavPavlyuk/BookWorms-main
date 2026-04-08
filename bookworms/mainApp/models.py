from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# Діапазон років для рекомендації (18 = "18+" у підписах).
READER_AGE_MIN = 0
READER_AGE_MAX = 18

class AvatarCollection(models.Model):
    name = models.CharField(max_length=100, verbose_name="Назва аватара")
    image = models.ImageField(upload_to='default_avatars/', verbose_name="Файл аватара")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Аватар з колекції"
        verbose_name_plural = "Колекція аватарів"

class CustomUser(AbstractUser):
    biography = models.CharField(max_length=500, blank=True, verbose_name="Біографія")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Аватар")

    def __str__(self):
        return self.username

class Post(models.Model):
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='posts')
    book = models.ForeignKey(
        "Book",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
        verbose_name="Книга у пості",
        help_text="Якщо пост про прочитану книгу з полиці.",
    )
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    text = models.TextField(verbose_name="Текст")
    created_ad =models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Book(models.Model):
    """
    Книга як "довідник": один ISBN = один запис у всій базі.
    Навіщо окремо від Shelf: щоб не дублювати назву/авторів для кожного користувача -
    усі читають ті самі поля з Open Library, а полиця лише посилається на цей запис.
    """

    isbn = models.CharField(max_length=13, unique=True, db_index=True, verbose_name="ISBN")
    title = models.CharField(max_length=500, verbose_name="Назва")
    authors = models.CharField(max_length=500, blank=True, verbose_name="Автори")
    publisher = models.CharField(max_length=300, blank=True, verbose_name="Видавець")
    publish_date = models.CharField(max_length=64, blank=True, verbose_name="Дата видання")
    cover_url = models.URLField(max_length=500, blank=True, verbose_name="Обкладинка (URL)")
    info_url = models.URLField(max_length=500, blank=True, verbose_name="Open Library")
    min_readers_age = models.PositiveSmallIntegerField(
        default=READER_AGE_MIN,
        validators=[MinValueValidator(READER_AGE_MIN), MaxValueValidator(READER_AGE_MAX)],
        verbose_name="Мінімальний рекомендований вік читача (років)",
        help_text="0–18; 18 у полі 'максимум' означає 18+.",
    )
    max_readers_age = models.PositiveSmallIntegerField(
        default=READER_AGE_MAX,
        validators=[MinValueValidator(READER_AGE_MIN), MaxValueValidator(READER_AGE_MAX)],
        verbose_name="Максимальний рекомендований вік читача (років)",
        help_text="0–18; значення 18 — '18+'.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "книга"
        verbose_name_plural = "книги"
        ordering = ["title"]

    def __str__(self):
        return f"{self.title} ({self.isbn})"

    def clean(self):
        super().clean()
        if self.min_readers_age > self.max_readers_age:
            raise ValidationError(
                {
                    "min_readers_age": "Мінімальний вік не може бути більшим за максимальний.",
                    "max_readers_age": "Максимальний вік не може бути меншим за мінімальний.",
                }
            )

    def reader_age_summary(self) -> str:
        """Короткий текст для списків (максимум 18 = 18+)."""
        lo, hi = self.min_readers_age, self.max_readers_age
        if lo == hi:
            if hi >= READER_AGE_MAX:
                return "18+"
            return f"{lo} років"
        if hi >= READER_AGE_MAX:
            return f"{lo}–18+"
        return f"{lo}–{hi} років"


class Shelf(models.Model):
    """
    Запис "ця книга (Book) зараз лежить на полиці цього користувача (user)".
    Унікальність user+book: одна й та сама книга не може бути двічі на одній полиці.
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="shelf_entries")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="shelf_entries")
    # Якщо заповнено - user не власник, а позичальник, повернути можна лише власнику (логіка в views / exchange_service).
    borrowed_from = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="books_lent_out",
        verbose_name="Позичено у",
        help_text="Якщо заповнено - user є позичальником, книгу можна лише повернути, не видалити з полиці.",
    )
    # Позичальник натиснув "повернути"; перенос на полицю позикодавця - лише після confirm_borrow_return.
    return_pending = models.BooleanField(default=False, verbose_name="Очікує підтвердження повернення")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "полиця"
        verbose_name_plural = "полиці"
        constraints = [
            # Заборона дублікатів: один користувач - один рядок на одну книгу.
            models.UniqueConstraint(fields=["user", "book"], name="unique_shelf_user_book"),
        ]
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user.username} -{self.book.title}"


class BookExchangeRequest(models.Model):
    """
    Один запит між двома людьми щодо конкретного рядка Shelf (чужа книга).
    Без offer_shelf після згоди - позика (див. Shelf.borrowed_from).
    З offer_shelf - обмін двома книгами без позики.
    shelf_owner фіксує власника на момент створення запиту (для історії та прав доступу).
    """
    class Status(models.TextChoices):
        PENDING = "pending", "Очікує"
        ACCEPTED = "accepted", "Прийнято"
        REJECTED = "rejected", "Відхилено"
        CANCELLED = "cancelled", "Скасовано"

    # Який саме запис на полиці "цілять" (чия книга).
    target_shelf = models.ForeignKey(
        Shelf,
        on_delete=models.CASCADE,
        related_name="incoming_exchange_requests",
        verbose_name="Чия книга запитується",
    )
    # Копія власника на момент запиту; після обміну target_shelf.user може змінитись, а тут - для перевірок та історії.
    shelf_owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="Власник на момент запиту",
        help_text="Не змінюється після обміну (для історії).",
    )
    requester = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sent_exchange_requests",
        verbose_name="Хто запитує",
    )
    # Необов’язково: якщо є - це справжній обмін, якщо ні - лише позика без книги взамін.
    offer_shelf = models.ForeignKey(
        Shelf,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offered_in_exchange_requests",
        verbose_name="Книга з вашої полиці в обмін (необов'язково)",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "запит на обмін"
        verbose_name_plural = "запити на обмін"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.requester} → {self.shelf_owner}: {self.target_shelf.book.title}"


class PrivateMessage(models.Model):
    """
    Приватне повідомлення між користувачами.
    Може бути прив’язане до запиту на обмін/позику (exchange_request) для контексту в скриньці.
    """
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sent_private_messages",
        verbose_name="Від кого",
    )
    recipient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="received_private_messages",
        verbose_name="Кому",
    )
    body = models.TextField(verbose_name="Текст")
    exchange_request = models.ForeignKey(
        BookExchangeRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="private_messages",
        verbose_name="Зв’язаний запит",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Прочитано")

    class Meta:
        verbose_name = "приватне повідомлення"
        verbose_name_plural = "приватні повідомлення"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sender} → {self.recipient}: {self.body[:40]}"
class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author} - {self.text[:20]}"


class Like(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('post', 'user')

    def __str__(self):
        return f'{self.user.username} likes {self.post.title}'
