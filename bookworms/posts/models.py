from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Post(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='posts',
        verbose_name='Автор'
    )
    content = models.TextField(verbose_name='Текст допису')
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Створено'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Оновлено'
    )

    class Meta:
        verbose_name = 'Допис'
        verbose_name_plural = 'Дописи'
        ordering = ['-created_at']

    def __str__(self):
        return f'Post #{self.pk} by {self.author.username}'
