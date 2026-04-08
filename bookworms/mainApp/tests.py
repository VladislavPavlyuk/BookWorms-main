from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Post


class BlogModelsTest(TestCase):
    def setUp(self):
        # Создаем автора с твоим полем biography
        User = get_user_model()
        self.user = User.objects.create_user(
            username='alexi_admin',
            password='password123',
            biography='Тестова біографія користувача'  # ТВОЕ ПОЛЕ
        )

    def test_post_creation(self):
        # Создаем пост с твоими полями: title и text
        post = Post.objects.create(
            author=self.user,
            title='Тестовий заголовок',
            text='Текст тестового повідомлення'  # ТВОЕ ПОЛЕ
        )

        # Проверки соответствия твоим названиям
        self.assertEqual(post.title, 'Тестовий заголовок')
        self.assertEqual(post.text, 'Текст тестового повідомлення')
        self.assertEqual(self.user.biography, 'Тестова біографія користувача')

        print("\nТест создания поста (title/text) и biography пользователя пройден!")

    def test_user_posts_relation(self):
        # Проверяем связь через твой related_name='posts'
        Post.objects.create(author=self.user, title='Запис 1', text='...')
        Post.objects.create(author=self.user, title='Запис 2', text='...')

        # Считаем количество постов через твой related_name
        count = self.user.posts.count()
        self.assertEqual(count, 2)

        print(f"Тест связи (1 автор -> {count} поста) через related_name='posts' пройден!")
