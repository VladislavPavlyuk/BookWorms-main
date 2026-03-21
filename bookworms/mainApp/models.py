from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
   biography = models.CharField(max_length=500, blank=True, verbose_name="Біографія")
   avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Аватар")

   def __str__(self):
    return self.username

class Post(models.Model):
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    text = models.TextField(verbose_name="Текст")
    created_ad =models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title