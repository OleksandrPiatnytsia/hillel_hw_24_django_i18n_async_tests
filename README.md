# hillel_hw_24 — Django: інтернаціоналізація, асинхронні view і тести

Навчальний Django-проєкт (Hillel). Продовження ДЗ №18 (книгарня в Docker). У цьому ДЗ:

- **кошик у сесії** (`cart/cart.py`, клас `Cart`: додати, видалити, очистити), лічильник у навбарі;
- **моделі `Order` і `OrderItem`**: оформлення в `transaction.atomic` з `select_for_update`
  і резервом книг на складі, скасування повертає книги;
- **оплата через Stripe Checkout Session** + webhook через Stripe CLI; часткові ручні оплати;
- **email через Gmail SMTP**: «order created» і «payment received» після COMMIT;
- **адмінка**: `OrderItem` і платежі як inline в `Order`, ручні платежі, скасування;
- «My orders», дані доставки в профілі (підставляються при оформленні);
- команда `cancel_unpaid_orders`;
- **спільні volume** бази й обкладинок для всіх наступних ДЗ (без перенесення даних).

## Стек

- Python 3.13, Django 6.1
- PostgreSQL 17 (`psycopg` 3), Redis 8 (вбудований у Django `RedisCache`)
- Docker, docker compose; gunicorn; WhiteNoise (статика без nginx)
- Bootstrap 5.3 (через CDN, із перевіркою `integrity`)
- Pillow: перевірка зображень для `ImageField`
- python-dotenv: налаштування з `.env`
- Stripe: `stripe` 16 (Checkout Session, перевірка підпису webhook), Stripe CLI 1.55 у Docker
- Gmail SMTP через `MAILERS` (новий формат налаштувань пошти в Django 6.1)
- django-debug-toolbar 8.0 (тільки для розробки, `requirements-dev.txt`)

## Сторінки сайту

| URL | Ім'я маршруту | View | Доступ | Що робить |
|---|---|---|---|---|
| `/` | `books:list` | `BookListView` | усі | каталог: фільтри, сортування, пагінація по 10 книг |
| `/<pk>/` | `books:detail` | `BookDetailView` | усі | сторінка книги |
| `/create/` | `books:create` | `BookCreateView` | `books.add_book` | додавання книги |
| `/<pk>/update/` | `books:update` | `BookUpdateView` | `books.change_book` | редагування книги |
| `/<pk>/delete/` | `books:delete` | `BookDeleteView` | `books.delete_book` | підтвердження й видалення |
| `/authors/` | `books:author_list` | `AuthorListView` | усі | автори з кількістю книг |
| `/authors/<pk>/` | `books:author_detail` | `AuthorDetailView` | усі | автор, біографія та його книги |
| `/accounts/login/` | `users:login` | `UserLoginView` | усі | вхід (за username) |
| `/accounts/logout/` | `users:logout` | `UserLogoutView` | POST | вихід |
| `/accounts/signup/` | `users:signup` | `SignUpView` | гості | реєстрація |
| `/accounts/profile/` | `users:profile` | `ProfileView` | залогінені | дані доставки, групи й права поточного користувача |
| `/accounts/profile/edit/` | `users:profile_edit` | `ProfileEditView` | залогінені | ім'я, телефон, адреса доставки |
| `/cart/` | `cart:detail` | `cart_detail` | усі | кошик |
| `/cart/add/<book_id>/` | `cart:add` | `cart_add` | POST | додати книгу або задати кількість (`override`) |
| `/cart/remove/<book_id>/` | `cart:remove` | `cart_remove` | POST | прибрати книгу з кошика |
| `/cart/clear/` | `cart:clear` | `cart_clear` | POST | очистити кошик |
| `/orders/` | `orders:list` | `OrderListView` | залогінені | My orders: власні замовлення, по 20 |
| `/orders/checkout/` | `orders:checkout` | `checkout` | залогінені | форма доставки й створення замовлення |
| `/orders/<pk>/` | `orders:detail` | `order_detail` | власник (інакше 404) | замовлення, кнопки Pay і Cancel |
| `/orders/<pk>/cancel/` | `orders:cancel` | `order_cancel` | POST, власник | скасувати нове неоплачене замовлення |
| `/payments/pay/<order_id>/` | `payments:pay` | `pay` | POST, власник | на сторінку оплати Stripe |
| `/payments/success/` | `payments:success` | `payment_success` | залогінені | повернення зі Stripe, `?session_id=...` |
| `/payments/cancelled/<payment_id>/` | `payments:cancelled` | `payment_cancelled` | залогінені | «назад» зі Stripe |
| `/payments/webhook/<provider>/` | `payments:webhook` | `webhook` | POST, підпис Stripe | події від Stripe |
| `/admin/` | `admin:index` | | `is_staff` | адмінка |
| `/health/` | `health` | `health` (`config/views.py`) | усі, GET | стан PostgreSQL і Redis: 200 або 503, JSON |
| `/__debug__/` | | | `DEBUG` + `INTERNAL_IPS` | службові адреси Debug Toolbar |

Маршрути описані в `urls.py` кожного застосунку (`app_name` = `books`, `users`,
`cart`, `orders`, `payments`) і підключені в `config/urls.py` через `include()`. У шаблонах і коді адреси
будуються тільки за іменами: `{% url 'books:detail' book.pk %}`,
`reverse_lazy("books:list")`.

## Структура

```
config/
├── settings.py              # PostgreSQL, Redis, WhiteNoise, AUTH_USER_MODEL, Debug Toolbar, LOGGING
├── urls.py                  # admin + books + accounts/ + cart/ + orders/ + payments/ + health/
├── views.py                 # health: перевірка PostgreSQL і Redis
├── middleware.py            # RequestTimingMiddleware
└── logging_filters.py       # HideClientErrorTraceback (403/404 без traceback)
users/
├── models.py                # User(AbstractUser): email lowercase і унікальний; phone, address
├── forms.py                 # LoginForm, SignUpForm, ProfileForm (+ Bootstrap-класи)
├── phone.py                 # normalize_phone(): спільна перевірка телефону
├── views.py                 # UserLoginView, UserLogoutView, SignUpView, ProfileView, ProfileEditView
├── urls.py                  # app_name = "users"
├── admin.py                 # UserAdmin з email на сторінці «Add user»
├── signals.py               # логування входу, виходу й невдалих спроб
├── apps.py                  # підключення сигналів у ready()
├── migrations/
│   ├── 0001_initial.py
│   ├── 0002_lowercase_email.py    # дані → lowercase + CheckConstraint
│   ├── 0003_create_groups.py      # групи Customers / Editors / Managers
│   └── 0004_user_address_user_phone.py
└── templates/users/
    ├── auth_form.html       # спільний для входу й реєстрації
    ├── profile.html
    └── profile_edit.html
books/
├── models.py                # Category, Author, Book (+ cover), BookCategory, BookQuerySet
├── forms.py                 # BookForm, BookFilterForm, CoverInput
├── views.py                 # Class-Based Views для книг і авторів
├── urls.py                  # app_name = "books"
├── admin.py                 # адмінка (+ мініатюри обкладинок)
├── templates/books/
│   ├── book_list.html
│   ├── book_detail.html
│   ├── book_form.html             # спільний для Create і Update
│   ├── book_confirm_delete.html
│   ├── author_list.html
│   ├── author_detail.html
│   ├── includes/stock_badge.html  # бейдж наявності
│   └── widgets/cover_input.html   # поле обкладинки з прев'ю
└── management/commands/
    ├── seed_books.py
    └── book_stats.py
cart/
├── cart.py                  # Cart: кошик у сесії
├── forms.py                 # CartAddForm (quantity, override)
├── views.py                 # cart_detail, cart_add, cart_remove, cart_clear
├── context_processors.py    # "cart" у кожному шаблоні (лічильник у навбарі)
└── templates/cart/cart_detail.html
orders/
├── models.py                # Order, OrderItem; paid_amount, amount_due, refresh_payment_status()
├── services.py              # create_order(), cancel_order(): транзакції й блокування
├── forms.py                 # CheckoutForm
├── views.py                 # checkout, OrderListView, order_detail, order_cancel
├── emails.py                # send_order_email(), лист «order created»
├── admin.py                 # OrderAdmin: inline позицій і платежів, скасування
├── migrations/0002_managers_order_permissions.py   # права групи Managers
├── management/commands/cancel_unpaid_orders.py
└── templates/orders/        # checkout, order_detail, order_list, includes/, emails/
payments/
├── models.py                # Payment
├── services.py              # ручні платежі, start_online_payment(), webhook-статуси
├── providers/
│   ├── base.py              # PaymentProvider: контракт провайдера
│   ├── stripe_checkout.py   # StripeProvider: Checkout Session, webhook
│   ├── manual.py            # ManualProvider: платежі від менеджера
│   └── registry.py          # "stripe" / "manual" -> об'єкт провайдера
├── views.py                 # pay, payment_success, payment_cancelled, webhook
├── emails.py                # лист «payment received»
├── admin.py                 # inline для замовлення, список платежів
└── templates/payments/      # payment_success, emails/
templates/                   # спільні шаблони проєкту
├── base.html
├── 403.html                 # «Access denied»
├── 404.html                 # «Page not found» (лише при DEBUG=False)
└── includes/
    ├── navbar.html
    ├── messages.html
    └── pagination.html
static/                      # статика проєкту
├── css/styles.css
└── img/
    ├── no-cover.svg         # заглушка, коли обкладинки немає
    └── favicon.svg
media/                       # завантажені обкладинки (не в git)
logs/                        # app.log і його ротації (не в git)
requirements.txt             # залежності проєкту
requirements-dev.txt         # + django-debug-toolbar
Dockerfile                   # образ web: python:3.13-slim, користувач app, gunicorn
.dockerignore                # що не потрапляє в образ (.env, .venv, бази, media)
docker-entrypoint.sh         # migrate + collectstatic, потім exec команди
docker-compose.yml           # web + db + redis + stripe-cli, volumes, healthchecks
.gitattributes               # *.sh завжди з LF
```

## Користувачі та автентифікація

### Custom User Model

`users.User` наслідується від `AbstractUser`: усе вбудоване (username,
пароль, імена, `is_staff`, групи, права) лишається, змінено тільки email.

```python
# config/settings.py
AUTH_USER_MODEL = "users.User"
```

`AUTH_USER_MODEL` треба задати **до першого** `migrate`: таблиці адмінки, груп
і прав отримують зовнішній ключ саме на цю модель. Тому проєкт стартував з
нової бази (дані книжок перенесено через `dumpdata` / `loaddata`).

**Email:**
- обов'язковий і унікальний (`unique=True`, текст помилки в `error_messages`);
- завжди в нижньому регістрі: `User.clean()` (форми, адмінка) і `User.save()`
  (`createsuperuser`, `create_user()`, скрипти) переводять його в lowercase,
  тому `Ann@Mail.com` і `ann@mail.com` вважаються однією адресою;
- `CheckConstraint` `users_user_email_lowercase` гарантує це на рівні бази,
  навіть для `QuerySet.update()` і сирого SQL;
- міграція `0002_lowercase_email` спершу переводить наявні email у lowercase,
  а вже потім додає обмеження.

Вхід за **username** (як у вбудованого користувача).

### Вхід, вихід, реєстрація

| Сторінка | Як зроблено |
|---|---|
| Вхід | `LoginView` + `AuthenticationForm`; `redirect_authenticated_user = True`; повертає на `?next=...` |
| Вихід | `LogoutView`, **тільки POST** (Django 5+): у меню це кнопка всередині `<form>` з CSRF-токеном, а не посилання |
| Реєстрація | `CreateView` + `SignUpForm(UserCreationForm)`; після збереження `login()`, новий користувач потрапляє в групу Customers |

```python
LOGIN_URL = "users:login"            # куди Login/PermissionRequiredMixin відправляють гостей
LOGIN_REDIRECT_URL = "books:list"    # після входу, якщо немає ?next=
LOGOUT_REDIRECT_URL = "books:list"
```

`SignUpView` теж поважає `?next=`, але перевіряє адресу через
`url_has_allowed_host_and_scheme`, щоб не було переадресації на чужий сайт
(open redirect). Перевірку паролів (`AUTH_PASSWORD_VALIDATORS`), хешування і
перевірку username без урахування регістру робить сама `UserCreationForm`.

## Права доступу та групи

### Групи

Створюються data migration `users/0003_create_groups.py`:

| Група | Права (застосунок `books`) | Що може |
|---|---|---|
| **Customers** | `view_book`, `view_author`, `view_category` | лише переглядати; дається кожному новому користувачу |
| **Editors** | Customers + `add/change_book`, `add/change_author`, права на `bookcategory` | додавати й редагувати книжки й авторів |
| **Managers** | Editors + `delete_book`, `delete_author`, `add/change/delete_category`, `manage_stock`; замовлення: `view/change_order`, `view_orderitem`, `view_payment`, `add_payment` | усе в каталозі; замовлення в адмінці: статус, доставка, скасування, ручні платежі |

Суперкористувач має всі права без груп. Додати користувача в групу:
адмінка → Users → користувач → Groups.

Permissions зазвичай створює сигнал `post_migrate`, тобто **після** всіх
міграцій. На новій базі їх ще немає в момент `0003`, тому міграція спершу
викликає `create_permissions()` сама. Якщо в назві права помилка, міграція
падає з `RuntimeError`. Відкат (`migrate users 0002`) видаляє групи.

Права на замовлення додає окрема міграція `orders/0002_managers_order_permissions.py`
(тим самим способом). Вона робить `group.permissions.add()`, а не `set()`, тому
каталожні права групи лишаються; відкат прибирає лише ці 5 прав. Права на
видалення замовлень і на зміну чи видалення платежів не даються нікому:
замовлення скасовують, а платежі змінює лише `payments/services.py`.

### Перевірка прав

- **Views:** `PermissionRequiredMixin` стоїть першим у списку батьківських класів:
  ```python
  class BookCreateView(PermissionRequiredMixin, BookFormUserMixin, SuccessMessageMixin, CreateView):
      permission_required = "books.add_book"
  ```
  Гість отримує переадресацію на `LOGIN_URL?next=...`, а залогінений
  користувач без права отримує 403 (`templates/403.html`). Тому окремий
  `LoginRequiredMixin` тут не потрібен.
- **`LoginRequiredMixin`** стоїть на `ProfileView`: сторінка не вимагає
  конкретного права, достатньо бути залогіненим.
- **Шаблони:** `{% if perms.books.change_book %}` ховає кнопки Edit / Delete /
  Add book. Це лише зручність, справжній захист у views.

### Власний permission `manage_stock`

```python
class Book(models.Model):
    class Meta:
        permissions = [("manage_stock", "Can change stock quantity")]
```

`BookForm.__init__(user=...)` робить поле `stock` неактивним (`disabled`),
якщо в користувача немає `books.manage_stock`. Для такого поля Django
**ігнорує** значення з POST і бере початкове, тож змінити склад через
DevTools не вийде. Редактор створює книжку з `stock = 0`, а склад виставляє менеджер.

### Профіль

`/accounts/profile/` показує дані доставки (ім'я, телефон, адреса) з кнопкою «Edit»,
групи, статус (superuser / staff), коротке «що я можу» (✅/❌) і повний список
`user.get_all_permissions()`.

`/accounts/profile/edit/` (`ProfileEditView`): ім'я, прізвище, телефон, адреса.
`get_object()` повертає `request.user`, `<pk>` в адресі немає, тому чужий профіль
не відкриєш. Телефон перевіряє та сама `normalize_phone()`, що й при оформленні.

## Django Debug Toolbar

Лише для розробки. Вмикається, коли виконуються всі три умови:

```python
ENABLE_DEBUG_TOOLBAR = (
    DEBUG and find_spec("debug_toolbar") is not None and "test" not in sys.argv
)
```

- `DEBUG=True`: у продакшні тулбара немає взагалі (ні в `INSTALLED_APPS`, ні в URL);
- пакет встановлено (`requirements-dev.txt`): з одним `requirements.txt` проєкт працює;
- не `manage.py test`.

Тулбар бачать лише запити з `INTERNAL_IPS = ["127.0.0.1", "::1"]`, незалежно
від того, хто залогінений. Так можна дивитися SQL і шаблони очима гостя чи
звичайного покупця. `DebugToolbarMiddleware` стоїть одразу після `SecurityMiddleware`.

Тулбар зберігає дані в пам'яті (`MemoryStore`), тому його міграція прихована
і `migrate` її не показує, це нормально.

**У Docker тулбара немає:** образ ставить лише `requirements.txt`, і
`find_spec("debug_toolbar")` повертає `None`. Це навмисно: запити з Mac
приходять у контейнер з адреси шлюзу Docker (`192.168.65.1`), а не з
`127.0.0.1`, тож для тулбара довелося б розширювати `INTERNAL_IPS`. Для
налагодження з тулбаром запускайте `runserver` локально (див. «Встановлення та запуск»).

## Логування

`LOGGING` у `config/settings.py`: вивід у консоль і у файл `logs/app.log`
(`RotatingFileHandler`: 1 МБ, 5 архівних файлів, `utf-8`). Формат:

```
2026-11-07 21:02:39,943 INFO users.signals Login: user=ann ip=127.0.0.1
```

| Логер | Рівень | Що пише |
|---|---|---|
| `users` | DEBUG при `DEBUG=True`, інакше INFO | вхід, вихід, невдалий вхід (WARNING), реєстрація |
| `books` | так само | створення, зміна (`form.changed_data`), видалення книжок, хто це зробив |
| `orders` | DEBUG / INFO | листи (надіслано / помилка з traceback), `cancel_unpaid_orders` |
| `payments` | DEBUG / INFO | створення сторінки оплати, зміни статусів платежів, події webhook |
| `config` | INFO | рядок на кожен запит від `RequestTimingMiddleware` |
| `django` | WARNING | 404, 403 одним рядком; 500 з traceback |

- Події входу й виходу ловлять сигнали `user_logged_in`, `user_logged_out`,
  `user_login_failed` (`users/signals.py`): вони спрацьовують для будь-якого
  входу, зокрема в адмінці.
- У лог **не** пишуться паролі й email (персональні дані).
- `HideClientErrorTraceback` (`config/logging_filters.py`) прибирає traceback з
  записів про 4xx: для 403 це звичайна відмова, а не помилка. Фільтр стоїть на
  обробниках (handlers), бо фільтри логера `django` не діють на записи від
  дочірнього `django.request`.

```bash
tail -f logs/app.log             # локальний runserver
docker compose logs -f web       # у Docker: консольний вивід контейнера
```

У Docker `logs/app.log` пишеться всередині контейнера й зникає, коли контейнер
перестворюється (volume для логів немає). Основне джерело там — `docker compose logs`.
Access log gunicorn вимкнено: рядок на кожен запит уже пише `RequestTimingMiddleware`,
а `/health/` (Docker перевіряє його кожні 10 секунд) middleware не логує.

## Middleware: `RequestTimingMiddleware`

`config/middleware.py`, **перший** у `MIDDLEWARE`, тому вимірює роботу всіх
інших middleware, view і шаблону.

```
INFO config.middleware GET /?page=2&sort=price 200 23.6ms user=anonymous
INFO config.middleware GET /create/ 403 3.6ms user=ann
```

- **Лог:** метод, шлях із query string, статус, час, користувач. Запити довші
  за `REQUEST_SLOW_MS = 500` пишуться як WARNING. `/media/`, `/__debug__/` і `/health/` не логуються.
- **Заголовки:** `X-Request-Duration: 23.6ms` і стандартний
  `Server-Timing: app;dur=23.6` (видно в DevTools → Network → Timing).
- Час рахується через `time.perf_counter()` (монотонний годинник).
- `request.user` доступний, хоча middleware стоїть вище за
  `AuthenticationMiddleware`: та присвоює його тому самому об'єкту `request`
  ще до того, як відповідь повертається до нас.

Реєстрація й вхід займають ~300 мс, решта сторінок кілька мілісекунд: це
хешування пароля (PBKDF2), воно навмисно повільне.

## Class-Based Views

| View | Шаблон за замовчуванням | Особливості |
|---|---|---|
| `BookListView` | `books/book_list.html` | `paginate_by = 10`; фільтри з GET-параметрів через `BookFilterForm`; `prefetch_related("categories")` |
| `BookDetailView` | `books/book_detail.html` | `prefetch_related("categories")` |
| `BookCreateView` | `books/book_form.html` | `PermissionRequiredMixin` (`add_book`); після збереження редирект на `get_absolute_url()` |
| `BookUpdateView` | `books/book_form.html` | `PermissionRequiredMixin` (`change_book`); той самий шаблон; заголовок і кнопки залежать від `object` |
| `BookDeleteView` | `books/book_confirm_delete.html` | `PermissionRequiredMixin` (`delete_book`); видалення тільки через POST; редирект на каталог |
| `AuthorListView` | `books/author_list.html` | `annotate(Count("books"))`, `paginate_by = 20` |
| `AuthorDetailView` | `books/author_detail.html` | книги автора через `author.books` |

Сторінки авторів тільки для перегляду: авторів додають і редагують в адмінці.
Посилання в адмінку видно, якщо користувач має `is_staff` **і** право
`add_author` / `change_author`.

Після створення, редагування й видалення `SuccessMessageMixin` показує
повідомлення (messages framework → Bootstrap alert), а `form_valid()`
пише запис у лог (див. «Логування»).

## Шаблони

- `base.html`: каркас сторінки з блоками `title` і `content`. Сторінки
  наслідуються від нього через `{% extends "base.html" %}`.
- `navbar.html`: прилипає до верху під час прокручування (`sticky-top`),
  підсвічує активний пункт меню (`request.resolver_match.url_name`), має
  швидкий пошук і на вузькому екрані згортається в «бургер». Праворуч:
  «🛒 Cart» з кількістю примірників (і для гостей), «Log in» / «Sign up» для гостей
  або меню користувача (email, «My profile», «My orders», «Log out»). «Add book» видно
  лише з правом `add_book`, «Admin» лише при `is_staff`.
- `pagination.html`: універсальна пагінація для будь-якого `ListView`.
  Тег `{% querystring page=N %}` зберігає поточні фільтри при переході між
  сторінками; довгий список сторінок скорочується (`get_elided_page_range`).
- `messages.html`: flash-повідомлення.

### Фільтри каталогу

Форма `BookFilterForm`, метод GET (фільтри видно в адресі, сторінку можна
зберегти в закладки):

| Параметр | Що робить |
|---|---|
| `q` | пошук за назвою або іменем автора (без урахування регістру, зокрема для кирилиці) |
| `category` | категорія за `slug` |
| `author` | автор за `pk` |
| `stock` | наявність: `in_stock` / `low` (≤ 5) / `out` |
| `price_min`, `price_max` | діапазон ціни; якщо «від» більше за «до», форма покаже помилку |
| `sort` | `title`, `-title`, `author__name`, `price`, `-price`, `-created_at` |

Некоректні значення (`?price_min=abc`) не ламають сторінку: форма показує
помилку, а каталог виводить усі книги.

## Статичні файли і media

| | Static | Media |
|---|---|---|
| Що це | CSS, іконки, заглушка обкладинки | обкладинки, завантажені через форму |
| Де лежить | `static/` (у git) | `media/covers/<рік>/<місяць>/` (не в git) |
| Налаштування | `STATIC_URL`, `STATICFILES_DIRS`, `STATIC_ROOT` | `MEDIA_URL`, `MEDIA_ROOT` |
| Хто роздає локально | `runserver` сам | `static()` у `config/urls.py` (тільки при `DEBUG=True`) |
| Хто роздає в Docker | WhiteNoise з `STATIC_ROOT` (volume `static_data`) | `static()`, тому в Docker `DJANGO_DEBUG=True` |

- У шаблонах статика підключається через `{% load static %}` і `{% static '...' %}`.
- `collectstatic` запускає `docker-entrypoint.sh` при кожному старті контейнера.
  `CompressedStaticFilesStorage` (WhiteNoise) додатково створює стиснені `.gz` і `.br` копії.
  Не `CompressedManifestStaticFilesStorage`: при `DEBUG=False` (а `manage.py test`
  завжди працює з ним) він вимагає вже зібраний manifest, і тести з `{% static %}` падали б.
- WhiteNoise роздає лише статику, яка була на диску при старті, а не завантажені
  файли. Тому обкладинки в Docker роздає Django при `DEBUG=True`. Правильне
  рішення для продакшну — nginx (окрема задача).

### Обкладинки книг

- Поле `Book.cover` (`ImageField`, необов'язкове).
- `Book.cover_url` повертає адресу обкладинки, а якщо її немає, то заглушки.
- Перевірки під час завантаження:
  - файл справді є зображенням (Pillow);
  - формат JPG, PNG або WebP (SVG і GIF заборонені);
  - розмір до 2 МБ.
- На сторінці редагування видно прев'ю поточної обкладинки й чекбокс
  «Remove cover» (власний віджет `CoverInput` на основі `ClearableFileInput`).
- Форма відправляється з `enctype="multipart/form-data"`, без нього файл не дійшов би на сервер.

## Моделі

| Модель | Поля | Примітки |
|---|---|---|
| `Category` | `name`, `slug` | обидва унікальні |
| `Author` | `name`, `bio` | `name` унікальне; `bio` необов'язкове |
| `Book` | `title`, `author`, `price`, `description`, `stock`, `cover`, `categories`, `created_at`, `updated_at` | `price ≥ 0`; `author` — ForeignKey на `Author` з `on_delete=PROTECT` (не можна видалити автора, у якого є книги); зв'язок ManyToMany з категоріями через `BookCategory`; `get_absolute_url()`, `cover_url`, `is_low_stock` |
| `BookCategory` | `book`, `category` | проміжна модель; `on_delete=PROTECT` не дає видалити категорію, у якій є книги; пара `book + category` унікальна |

`BookQuerySet.by_stock_status()` фільтрує книги за наявністю. Його
використовують і каталог, і адмінка; поріг «мало» задає `LOW_STOCK_THRESHOLD = 5`.

| Модель | Поля | Примітки |
|---|---|---|
| `User` | + `phone`, `address` | необов'язкові; підставляються у форму оформлення |
| `Order` | `user`, `status`, `payment_status`, `full_name`, `phone`, `address`, `total`, `created_at`, `updated_at` | `user` з `PROTECT`; дані доставки — копія, а не посилання на профіль; `total ≥ 0` (`CheckConstraint`) |
| `OrderItem` | `order`, `book`, `title`, `price`, `quantity` | `order` з `CASCADE`, `book` з `PROTECT`; `title` і `price` — копії на момент замовлення; один рядок на книгу (`UniqueConstraint`), `quantity ≥ 1`; `cost` = `price × quantity` |
| `Payment` | `order`, `provider`, `external_id`, `amount`, `status`, `details` (JSON), `created_at`, `updated_at`, `paid_at` | `order` з `PROTECT`; `provider`: `stripe` / `manual`; `status`: `pending` / `succeeded` / `failed` / `expired`; `(provider, external_id)` унікальні для непорожнього `external_id`; `amount > 0` |

Два незалежні статуси замовлення:
- `status` — що з товаром: `new` → `processing` → `shipped` → `completed`, або `cancelled`;
- `payment_status` — скільки сплачено: `unpaid` / `partially_paid` / `paid`. Зберігається
  в базі (для фільтра в адмінці), але змінює його лише `Order.refresh_payment_status()`
  із суми успішних платежів. Відсоток оплати (`paid_percent`) не зберігається, а рахується.

### Перенесення авторів в окрему модель

Раніше автор був текстовим полем `Book.author`. Перенесення зроблено
чотирма міграціями, щоб не втратити дані:

| Міграція | Що робить |
|---|---|
| `0003_rename_author_book_author_name` | перейменовує текстове поле на `author_name` |
| `0004_author_book_author` | створює `Author` і тимчасовий необов'язковий `Book.author` |
| `0005_move_authors_to_author_model` | data migration: для кожного імені створює `Author` (`get_or_create`) і пов'язує з книгами |
| `0006_remove_book_author_name_alter_book_author` | видаляє `author_name`, робить `author` обов'язковим |

Просто замінити `CharField` на `ForeignKey` під тим самим іменем не можна:
Django згенерував би `AlterField` і спробував би перетворити імена авторів на числові id.
Усі чотири міграції можна відкотити (`python manage.py migrate books 0002`).

## Адмінка

- **Книги:**
  - колонки: мініатюра обкладинки, автор, категорії, ознака наявності;
  - автор вибирається з пошуком під час введення (`autocomplete_fields`);
  - ціну й кількість можна редагувати прямо у списку;
  - фільтри: наявність (є / мало ≤ 5 / немає), категорії, дата;
  - пошук за назвою, іменем автора, описом і категорією;
  - `date_hierarchy`, `fieldsets` із секцією «Cover» (прев'ю обкладинки), inline для категорій.
- **Автори:** кількість книг (із сортуванням), пошук за іменем, біографія.
- **Категорії:** кількість книг (із сортуванням), автозаповнення `slug`,
  inline зі списком книг.
- **Замовлення** (`orders/admin.py`):
  - колонки: номер, користувач, статус, статус оплати, сплачений відсоток (підзапит
    у тому самому SQL), сума, дата; фільтри: статус, оплата, дата; пошук за номером,
    email, username, ім'ям, телефоном;
  - inline: книги замовлення й усі платежі (лише перегляд) і рядки «add a manual payment»;
  - ручний платіж зберігається через `record_manual_payment()` (блокування, перевірка
    залишку, перерахунок статусу), а не через `formset.save()`;
  - статус `cancelled` у формі або дія «Cancel selected orders» викликають
    `cancel_order()`: книги повертаються на склад. Скасоване замовлення не відновлюється;
  - додавати й видаляти замовлення не можна; зберігаються лише змінені поля
    (`update_fields`), щоб не перезаписати оплату, що прийшла, поки сторінка була відкрита.
- **Платежі:** окремий список лише для перегляду (фільтри за провайдером і статусом).
- **Користувачі:** розділ «Delivery details» (телефон, адреса).
- Запити оптимізовано через `select_related` / `prefetch_related` та `annotate`.

## Кошик

`cart/cart.py`, клас `Cart`. Кошик живе в сесії, тому працює й для гостей:

```python
request.session["cart"] = {"15": {"quantity": 2}, "7": {"quantity": 1}}
```

- Ключі — рядки: сесія зберігається як JSON, а в JSON ключі завжди рядки.
- Зберігається лише кількість. Ціна щоразу береться з бази: кошик показує поточну
  ціну, і змінити її через сесію неможливо.
- `add(book, quantity=1, override=False)`: кнопка «Add to cart» додає до наявного,
  поле на сторінці кошика (`override=True`) задає точну кількість. Кількість обмежена
  `book.stock`.
- `remove(book)`, `clear()`; `for item in cart` → `book`, `quantity`, `price`, `cost`,
  `exceeds_stock`. Усі книги одним запитом (`in_bulk`), результат кешується, тож
  `cart.total` другого запиту не робить. Видалені з бази книги тихо зникають з кошика.
- `len(cart)` — кількість примірників, читає лише сесію, без SQL: лічильник у навбарі
  є на кожній сторінці (context processor `cart.context_processors.cart`).
- Зміна вкладеного словника не позначає сесію зміненою, тому `_save()` щоразу
  присвоює `session["cart"]` і ставить `session.modified = True`.
- При вході Django зберігає дані сесії (змінюється лише її id), тож кошик гостя
  лишається після входу. Вихід очищає сесію разом із кошиком.
- Усі зміни — лише POST (`require_POST`); після дії повертає на `next`, перевірений
  через `url_has_allowed_host_and_scheme` (без переадресації на чужий сайт).

## Замовлення

### Оформлення: `orders.services.create_order()`

```
POST /orders/checkout/  (форма: full_name, phone, address)
  transaction.atomic():
    1. SELECT ... FOR UPDATE книг із кошика, ORDER BY id
    2. перевірка залишку кожної книги  -> проблема? OrderError -> ROLLBACK, усі проблеми разом
    3. Order + OrderItem (bulk_create), назви й ціни копіюються з бази
    4. резерв: stock -= quantity (bulk_update)
    5. on_commit(лист «order created»)
  COMMIT -> кошик очищається -> сторінка замовлення з кнопкою «Pay»
```

- **`transaction.atomic()`:** замовлення, позиції й зміни складу зберігаються разом
  або не зберігаються взагалі. Немає замовлення без позицій і не списаних «у нікуди» книг.
- **`select_for_update()`:** без блокування двоє покупців могли б одночасно прочитати
  `stock = 1` і обидва купити останній примірник. З блокуванням другий чекає COMMIT
  першого й бачить `stock = 0`. Перевірено двома потоками: одне замовлення, друге
  отримує «out of stock».
- **`ORDER BY id`:** усі транзакції блокують книги в однаковому порядку, тому не
  чекають одна одну по колу (deadlock).
- **Резерв** при оформленні, а не при оплаті: поки покупець платить, книги ніхто не забере.
- **Лист після COMMIT** (`transaction.on_commit`): після ROLLBACK лист не піде.
- Форма містить лише дані доставки; `user`, `total` і статуси ставить сервіс, тож
  підроблений POST із `total=1` нічого не дасть. Телефон `+380 (67) 123-45-67`
  зберігається як `+380671234567` (`users/phone.py`).
- Поля підставляються з профілю (`first_name` + `last_name`, `phone`, `address`);
  галочка «Save phone and address to my profile» оновлює профіль для наступного разу.

### Скасування: `orders.services.cancel_order()`

- Блокує замовлення, перевіряє правила вже під блокуванням, повертає книги
  (`UPDATE ... SET stock = stock + n` через `F()`), ставить `cancelled`.
- Покупець може скасувати лише своє замовлення в статусі `new` і `unpaid`
  (`can_be_cancelled_by_customer`); менеджер — будь-яке не скасоване.
- Після COMMIT відкрита сторінка оплати Stripe закривається (`close_open_payments`),
  щоб за скасоване замовлення не можна було заплатити.
- Чуже замовлення дає 404 (як і неіснуюче), а не 403: так не видно, що замовлення з таким номером є.

### My orders

`/orders/` (меню користувача): власні замовлення від нових до старих, кількість книг
(`annotate(Sum("items__quantity"))`), сума, бейджі статусів. З `annotate` Django
ігнорує `Meta.ordering`, тому сортування задано явно: `order_by("-created_at", "-pk")`.

## Оплата

### Провайдери

`payments/providers/`: решта проєкту не імпортує Stripe напряму, а працює з контрактом
`PaymentProvider` (`start()`, `fetch_status()`, `cancel()`, `handle_webhook()`).
Новий провайдер — новий клас і рядок у `registry.py`.

| Провайдер | Як платять | Хто створює `Payment` |
|---|---|---|
| `stripe` | картка на сторінці Stripe Checkout | кнопка «Pay» |
| `manual` | готівка, переказ тощо | менеджер в адмінці; сума може бути частиною (→ `partially_paid`) |

Усі зміни платежів (`payments/services.py`) — у транзакції, спочатку блокується
замовлення (те саме блокування, що в `cancel_order()`), в кінці
`refresh_payment_status()`. Два менеджери, що одночасно вносять по 120 ₴ на замовлення
в 200 ₴, не перевищать суму: другий отримає «only 80.00 UAH is due».

### Stripe Checkout

```
«Pay» -> start_online_payment():
   transaction (lock order): своє? не скасоване? є що сплачувати?
       відкрита сторінка на ту саму суму ще жива?  -> її URL (без нової)
       інакше Payment(pending, amount = amount_due)
   після транзакції: Stripe API -> Checkout Session (uah, копійки, 31 хв)
       помилка Stripe -> Payment = failed, замовлення лишається
-> checkout.stripe.com -> покупець платить
-> /payments/success/?session_id=cs_test_...  -> статус питаємо в Stripe -> succeeded
-> Stripe -> stripe-cli -> POST /payments/webhook/stripe/ -> те саме, якщо ще не зроблено
```

- Одна позиція «Bookstore: order #N» на суму `amount_due`: після часткової ручної
  оплати списується лише залишок. UAH — валюта з двома знаками, тому сума в копійках
  (`250.50` → `25050`).
- Запит до Stripe — **після** транзакції: мережевий виклик не тримає замовлення
  заблокованим, а відкотити його однаково неможливо.
- Ключ ідемпотентності (`bookstore-payment-<id>-<час>`): повтор після мережевої
  помилки не створить другу сесію.
- Подвійний клік чи «назад» зі Stripe і знову «Pay» дають ту саму сторінку; застаріла
  (інша сума, менше 5 хв до кінця) закривається через `sessions.expire`.
- `session_id` в адресі повернення — не доказ оплати (її може набрати будь-хто): за
  ним лише знаходимо платіж, а статус беремо в Stripe секретним ключем.
- Сторінка повернення й webhook ведуть до тих самих ідемпотентних функцій: хто
  перший, той зараховує оплату, другий нічого не змінює (і другого листа немає).

### Webhook

`/payments/webhook/stripe/`, `csrf_exempt` (запит іде від Stripe, не з нашої форми).
Справжність перевіряє `stripe.Webhook.construct_event()`: HMAC-SHA256 сирого тіла
(`request.body`) із `STRIPE_WEBHOOK_SECRET` і час не старший 5 хвилин.

| Подія | Що робимо |
|---|---|
| `checkout.session.completed` + `payment_status = paid` | платіж `succeeded` |
| `checkout.session.completed` + `unpaid` | чекаємо (банківські списання приходять пізніше) |
| `checkout.session.async_payment_succeeded` / `_failed` | `succeeded` / `failed` |
| `checkout.session.expired` | `expired` (лише з `pending`; замовлення не скасовується) |

- 400 — лише без підпису, з чужим підписом чи зламаним JSON. На інші події й чужі
  сесії відповідь 200: на будь-яку не-2xx Stripe повторює запит кілька днів.
- Повтор тієї самої події нічого не змінює; запізніле `expired` не скасує оплату.

**Stripe CLI** (сервіс `stripe-cli` у compose): Stripe не може достукатися до
`localhost:8000` з інтернету, тому CLI тримає вихідне з'єднання зі Stripe і пересилає
4 потрібні події на `web:8000/payments/webhook/stripe/` з правильним підписом.
`web` має `web` в `ALLOWED_HOSTS` (compose додає до `DJANGO_ALLOWED_HOSTS`). Лише для
розробки: у продакшні Stripe викликає публічний HTTPS-endpoint із Dashboard → Webhooks.

```bash
docker compose logs -f stripe-cli    # <-- [200] POST http://web:8000/payments/webhook/stripe/
```

### Акаунт Stripe

- Тестовий режим (`sk_test_...`): реальних грошей немає. Картка `4242 4242 4242 4242`,
  будь-яка майбутня дата й CVC.
- Україна не входить до країн, де Stripe-акаунт можна активувати, тому акаунт
  зареєстровано з підтримуваною країною й ніколи не активовано: лише тестові ключі.
- UAH Stripe підтримує як валюту платежу. Мінімальна сума — еквівалент 0.50 у валюті
  виплат акаунта (близько 25 ₴).
- Publishable key не потрібен: сторінка оплати на боці Stripe, Stripe.js на сайті немає.

## Email

Gmail SMTP через `MAILERS` (Django 6.1; старі `EMAIL_BACKEND`, `EMAIL_HOST`, ...
застарілі й зникнуть у 7.0):

```python
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {"host": "smtp.gmail.com", "port": 587, "use_tls": True,
                    "username": EMAIL_USER, "password": EMAIL_PASSWORD, "timeout": 10},
    },
}
```

- Пароль — **App Password** Google (16 літер; потрібна двоетапна перевірка), не пароль
  акаунта. Пробіли з нього прибираються. Ліміт Gmail — близько 500 листів на добу.
- Без `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` листи друкуються в консоль
  (`docker compose logs web`). Тести самі підміняють усі mailers на `locmem`.
- `DEFAULT_FROM_EMAIL = "Bookstore <адреса Gmail>"`: Gmail відправляє лише від імені
  акаунта, під яким входить.
- Посилання в листах будуються від `SITE_URL`: лист відправляється без запиту
  (після COMMIT, з webhook), `request.build_absolute_uri()` там недоступний.

| Лист | Коли |
|---|---|
| «order created» | після COMMIT оформлення: позиції, сума, доставка, посилання |
| «payment received» | Stripe: кожен успішний платіж; ручний: коли замовлення сплачене повністю |

- Кожен лист має текстову й HTML-версії (`EmailMultiAlternatives`); HTML зі стилями
  в атрибутах `style`, бо Gmail і Outlook ігнорують `<style>`.
- Відправка ніколи не кидає виняток: помилку SMTP (пароль, мережа, таймаут) записує
  лог з traceback, а замовлення вже збережене.
- Відправка синхронна (у межах запиту); Celery — у наступних ДЗ.
- Перевірити SMTP: `docker compose exec web python manage.py sendtestemail адреса@gmail.com`.
- Тестові користувачі: адреси з `+` (`адреса+ann@gmail.com`) приходять у ту саму
  скриньку, а для сайту це різні email.

## Встановлення та запуск

### У Docker

```bash
cp .env.example .env
# згенерувати SECRET_KEY і вставити в .env В ОДИНАРНИХ ЛАПКАХ (див. нижче):
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# заповнити POSTGRES_PASSWORD, EMAIL_HOST_USER / EMAIL_HOST_PASSWORD (Gmail), STRIPE_SECRET_KEY

# спільні volume створюються один раз (див. «Спільні volume»)
docker volume create hillel_bookstore_postgres_data && docker volume create hillel_bookstore_media_data

docker compose run --rm --no-deps stripe-cli listen --print-secret   # whsec_... -> STRIPE_WEBHOOK_SECRET у .env
docker compose up --build -d                                   # зібрати образ і запустити
docker compose ps                                              # db, redis, web healthy; stripe-cli running
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_books            # якщо база порожня
```

- Сайт: http://localhost:8000/
- Адмінка: http://localhost:8000/admin/
- Стан: http://localhost:8000/health/
- Лог: `docker compose logs -f web`, події Stripe: `docker compose logs -f stripe-cli`

```
docker compose up
  ├─ db          postgres:17-alpine  ──┐ healthcheck: pg_isready
  ├─ redis       redis:8-alpine      ──┤ healthcheck: redis-cli ping
  │                                    ▼ обидва healthy (depends_on: condition: service_healthy)
  ├─ web         Dockerfile → docker-entrypoint.sh → migrate → collectstatic → exec gunicorn
  │                                    healthcheck: GET /health/
  │                                    ▼ healthy
  └─ stripe-cli  stripe listen --forward-to web:8000/payments/webhook/stripe/
```

| Сервіс | Порт на Mac | Volume | Healthcheck |
|---|---|---|---|
| `db` | 5432 | `hillel_bookstore_postgres_data` (спільний) → `/var/lib/postgresql/data` | `pg_isready` |
| `redis` | 6379 | немає (кеш можна втратити, сесії є і в PostgreSQL) | `redis-cli ping` |
| `web` | 8000 | `static_data` → `/app/staticfiles`, `hillel_bookstore_media_data` (спільний) → `/app/media` | `GET /health/` (Python `urllib`, у slim-образі немає curl) |
| `stripe-cli` | немає | немає | немає: від нього ніхто не залежить, стан видно в `logs` |

Корисні команди:

```bash
docker compose logs -f web                         # вивід Django / gunicorn
docker compose exec web python manage.py shell     # команда в запущеному контейнері
docker compose restart web                         # перезапуск (entrypoint знову зробить migrate)
docker compose down                                # зупинити й видалити контейнери, volumes лишаються
docker compose down -v                             # ... і видалити static_data (спільні база й обкладинки лишаються)
docker compose exec web python manage.py cancel_unpaid_orders --dry-run
```

**Що варто знати:**

- `docker-entrypoint.sh` має `set -e`: якщо `migrate` впаде, gunicorn не стартує.
  `exec "$@"` робить gunicorn процесом PID 1, тому він отримує `SIGTERM` від
  `docker compose stop` і завершується коректно.
- Контейнер працює від користувача `app` (не root). Писати він може лише в
  `staticfiles/`, `media/`, `logs/`. Файли, скопійовані через `docker compose cp`,
  належать root: `docker compose exec -u root web chown -R app:app /app/media`.
- `.env` не потрапляє в образ (`.dockerignore`), compose передає змінні через
  `env_file`. Хости в `.env` — `localhost` (для локального запуску);
  `docker-compose.yml` перевизначає їх для `web`: `POSTGRES_HOST=db`,
  `REDIS_URL=redis://redis:6379/0` (сервіси бачать один одного за іменем).
- **`$` у значеннях `.env`.** Docker compose сприймає `$abc` як змінну й підставляє
  порожній рядок (`WARN The "abc" variable is not set`). Ключ від
  `get_random_secret_key()` може містити `$`, тому його беремо в **одинарні**
  лапки: `DJANGO_SECRET_KEY='...'`. Подвійні лапки не допомагають.
- gunicorn запускається з `--no-control-socket`: з версії 25.1 він відкриває сокет
  для `gunicornc` у `$HOME`, а в користувача `app` немає домашньої папки.

### Спільні volume

База й обкладинки лежать у volume з фіксованими іменами, однакових для всіх наступних ДЗ:

```yaml
volumes:
  postgres_data:
    name: hillel_bookstore_postgres_data
    external: true
  media_data:
    name: hillel_bookstore_media_data
    external: true
```

- `name:` — ім'я volume як є. Без нього compose додає префікс проєкту (назву папки),
  і кожна нова папка ДЗ отримувала б нові порожні volume.
- `external: true` — compose не створює й не видаляє ці volume: `down -v` спільну
  базу не зітре. Якщо volume немає, `up` зупиниться з `external volume not found`;
  тоді `docker volume create ...` (команда в «У Docker»).
- `static_data` лишається окремим для проєкту: `collectstatic` заповнює його при кожному старті.
- Одночасно запустити два ДЗ не вийде: обидва займають порти 5432, 6379 і 8000.
- `.env` однаковий в усіх ДЗ: пароль PostgreSQL записаний у самій базі при першому старті.

Перенесення з volume ДЗ №18 (один раз, контейнери hw_18 зупинені):

```bash
docker run --rm -v hillel_hw_18_django_postgres_docker_postgres_data:/from -v hillel_bookstore_postgres_data:/to alpine cp -a /from/. /to/
docker run --rm -v hillel_hw_18_django_postgres_docker_media_data:/from -v hillel_bookstore_media_data:/to alpine cp -a /from/. /to/
```

`cp -a` зберігає власників файлів (`postgres` для бази, `app` для обкладинок).

### Локально (runserver + PostgreSQL і Redis з Docker)

Для розробки з Debug Toolbar. PostgreSQL і Redis беруться з контейнерів через
опубліковані порти (`POSTGRES_HOST=localhost`, `REDIS_URL=redis://localhost:6379/0` у `.env`).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # або requirements.txt без Debug Toolbar

docker compose up -d db redis         # тільки база й Redis
python manage.py migrate
python manage.py runserver
```

- Сайт: http://127.0.0.1:8000/ (саме `127.0.0.1`, щоб з'явився Debug Toolbar)
- Лог: `logs/app.log`
- Якщо контейнер `web` теж запущений, він уже займає порт 8000:
  `docker compose stop web` або `runserver 8001`.

### Перенесення даних із SQLite у PostgreSQL

Так дані з ДЗ №16 (`db.sqlite3`, `media/`) переїхали в Docker:

```bash
# 1. Поки settings.py ще на SQLite (до перемикання на PostgreSQL):
DJANGO_DEBUG=False python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --exclude admin.logentry --exclude sessions --indent 2 -o data.json

# 2. У запущений контейнер web (migrate вже створив таблиці й групи):
docker compose cp data.json web:/tmp/data.json
docker compose exec web python manage.py loaddata /tmp/data.json
docker compose exec -u root web rm /tmp/data.json

# 3. Обкладинки у volume media_data:
docker compose cp media/. web:/app/media/
docker compose exec -u root web chown -R app:app /app/media
```

- `DJANGO_DEBUG=False`: щоб у дамп не потрапив `debug_toolbar` (змінна з
  командного рядка важливіша за `.env`, `load_dotenv()` її не перезаписує).
- `--natural-foreign`: зв'язки за природними ключами, а не за `id`: група як
  `["Editors"]`, permission як `["manage_stock", "books", "book"]`. `id` permissions
  у PostgreSQL інші, тому інакше не можна.
- `--natural-primary`: у `User` і `Group` немає `pk`. Групи вже створила
  міграція `users.0003`, `loaddata` знаходить їх за назвою й оновлює, а не дублює.
- `contenttypes`, `auth.permission` створює `migrate`; лог адмінки й сесії не переносимо.
- Книги, автори, категорії переносяться зі своїми `id` (адреси `/15/` не змінюються).
  `loaddata` на PostgreSQL сам скидає sequences: нова книга отримує наступний `id`.
- `data.json` містить хеші паролів і email, тому він у `.gitignore` і `.dockerignore`.
- Перевірка: кількість записів кожної моделі збігається з дампом
  (`bookcategory 18`, `book 12`, `author 10`, `category 5`, `group 3`, `user 3`).

### Змінні оточення (`.env`)

| Змінна | Опис | Приклад |
|---|---|---|
| `DJANGO_SECRET_KEY` | секретний ключ (обов'язковий), в одинарних лапках | `'change-me'` |
| `DJANGO_DEBUG` | режим налагодження; при `False` media не роздаються (і в Docker теж) | `True` |
| `DJANGO_ALLOWED_HOSTS` | хости через кому (`localhost` потрібен і для healthcheck) | `127.0.0.1,localhost` |
| `POSTGRES_DB` | назва бази (обов'язкова); контейнер `db` створює її при першому старті | `bookstore` |
| `POSTGRES_USER` | користувач бази (обов'язковий) | `bookstore` |
| `POSTGRES_PASSWORD` | пароль (обов'язковий) | |
| `POSTGRES_HOST` | `localhost` для runserver; у Docker compose ставить `db` | `localhost` |
| `POSTGRES_PORT` | порт | `5432` |
| `REDIS_URL` | Redis для кешу й сесій; у Docker compose ставить `redis://redis:6379/0` | `redis://localhost:6379/0` |
| `EMAIL_HOST_USER` | адреса Gmail; порожня → листи в консоль | `name@gmail.com` |
| `EMAIL_HOST_PASSWORD` | App Password Google (16 літер), не пароль акаунта | |
| `SITE_URL` | адреса сайту для посилань у листах | `http://localhost:8000` |
| `STRIPE_SECRET_KEY` | секретний ключ Stripe, тестовий режим | `sk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | підпис webhook; друкує `stripe-cli listen --print-secret` | `whsec_...` |

`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` читають і Django, і образ
`postgres`, тому один `.env` обслуговує обидва. Змінювати їх після першого старту
`db` марно: база вже створена у volume.

## Redis

- **Кеш** (`CACHES`, `RedisCache`): один спільний для всіх worker-процесів gunicorn
  (`LocMemCache` за замовчуванням був би окремим у кожному процесі).
- **Сесії** (`SESSION_ENGINE = cached_db`): читаються з Redis, записуються і в
  Redis, і в PostgreSQL. Після перезапуску Redis ніхто не вилогінюється.

## `/health/`

`config/views.py`: `SELECT 1` у PostgreSQL і `cache.set` / `cache.get` випадкового
значення в Redis.

```
200 {"status": "ok", "database": "ok", "cache": "ok"}
503 {"status": "error", "database": "ok", "cache": "error"}
```

- 503, а не 500: Django працює, недоступний сервіс, від якого він залежить.
- Подробиці помилки пишуться тільки в лог (`config.views`), не у відповідь.
- `@never_cache`, `@require_GET`; сесію не читає, тому працює й без Redis.
- Перевірено: `docker compose stop redis` → 503, `web` за ~30 с стає `unhealthy`;
  `docker compose start redis` → знову `healthy` без перезапуску `web`.
  Docker compose сам `unhealthy`-контейнери не перезапускає, лише показує стан.

## Management-команди

### `seed_books`

Створює 5 категорій, 10 авторів і 12 книг. Команду можна запускати повторно,
дублікати не створюються.

```bash
python manage.py seed_books
```

### `cancel_unpaid_orders`

Скасовує старі замовлення `new` + `unpaid` і повертає їхні книги на склад
(через `cancel_order()`; відкрита сторінка Stripe теж закривається).

```bash
python manage.py cancel_unpaid_orders                    # старші за 24 години
python manage.py cancel_unpaid_orders --older-than 12h   # 30m, 12h, 2d
python manage.py cancel_unpaid_orders --dry-run          # лише показати
```

- `cancel_order(only_unpaid=True)` перевіряє «ще не оплачено» вже під блокуванням:
  якщо оплата прийшла між вибіркою й скасуванням, замовлення пропускається («skipped»).
- Мінімум `--older-than 30m`: сторінка Stripe живе 31 хвилину, молодше замовлення
  може саме зараз оплачуватися.
- Поки запускається вручну; за розкладом (Celery beat) — у наступних ДЗ.

### `book_stats`

Виводить статистику книгарні та демонструє можливості ORM:

1. **filter**:
   - у наявності й дешевші за задану ціну;
   - мало на складі, немає на складі;
   - книги певної категорії, книги без категорії;
2. **Q-об'єкти**:
   - пошук за назвою / автором / категорією (OR);
   - «у наявності, але не в категорії» (AND + NOT);
   - складна умова для акції;
3. **annotate**:
   - статистика по категоріях;
   - топ-5 книг за вартістю запасу (`F("price") * F("stock")`);
   - категорії з понад 2 книгами (HAVING);
4. **aggregate**: підсумок по всьому магазину.

```bash
python manage.py book_stats
python manage.py book_stats --max-price 200 --search кінг --category fentezi
python manage.py book_stats --sql   # також показати згенерований SQL
```

| Параметр | За замовчуванням | Опис |
|---|---|---|
| `--max-price` | `300` | максимальна ціна для фільтра |
| `--search` | `Кінг` | рядок пошуку для Q-запиту |
| `--category` | `fentezi` | slug категорії |
| `--sql` | | друкувати SQL кожного запиту |

## Кирилиця в PostgreSQL

**Пошук.** `icontains` на PostgreSQL — це `UPPER(title) LIKE UPPER('%вбив%')`, і
`UPPER` для кирилиці працює правильно. Тому `books/sqlite_functions.py` з ДЗ №16
(власний `LIKE` для SQLite) видалено.

**Сортування.** Образ `postgres:17-alpine` за замовчуванням створює базу з
collation libc (`en_US.utf8`, провайдер `c`). Але musl (бібліотека C в Alpine)
не має правил сортування для мов, тому рядки порівнювались за кодами Unicode,
як у SQLite:

```
Є (U+0404)  І (U+0406)  Ї (U+0407)  А…Я (U+0410–042F)  а…я (U+0430–044F)  Ґ (U+0490)
ORDER BY:  Євген, Іван, Ївга, Андрій, Борис, …, Яна, андрій, Ґанна
```

Рішення — ICU (бібліотека з правилами сортування для мов, вбудована в образ):

```yaml
POSTGRES_INITDB_ARGS: "--locale-provider=icu --icu-locale=uk-UA"
```

```
ORDER BY:  андрій, Андрій, Борис, Гліб, Ґанна, Євген, Ирина, Іван, Ївга, Яна
```

- Діє на всю базу: моделі й `order_by` не змінювались.
- `initdb` виконується лише на порожньому volume. Щоб застосувати до існуючої
  бази: `docker compose down`, `docker volume rm hillel_bookstore_postgres_data`,
  `docker volume create hillel_bookstore_postgres_data`, `docker compose up -d` і знову
  `loaddata` (volume обкладинок не чіпаємо).
- Перевірка: `SELECT datlocprovider FROM pg_database WHERE datname = current_database()`
  повертає `i` (ICU).

## Відомі обмеження

- **Старі файли обкладинок не видаляються.** Django не прибирає файл з
  диска, коли книгу видалено, обкладинку замінено або позначено «Remove».
  Такі файли лишаються в `media/` (у Docker — у volume `media_data`).
- **Docker працює з `DJANGO_DEBUG=True`.** Інакше Django не роздає обкладинки,
  а WhiteNoise вміє лише статику. Для продакшну потрібен nginx (окрема задача):
  він роздаватиме `/media/` і `/static/` з volumes, а Django перейде на `DEBUG=False`.
- **IP у логах — це `REMOTE_ADDR`.** У Docker це адреса шлюзу (`192.168.65.1`),
  за проксі (nginx) буде адреса проксі; справжню треба брати з `X-Forwarded-For`,
  налаштувавши довіру до проксі.
- **`logs/app.log` у контейнері не зберігається** між перестворенням контейнера
  (немає volume); у Docker логи дивимось через `docker compose logs`.
- **Вихід у лозі middleware показується як `user=anonymous`**: `logout()`
  змінює `request.user` раніше, ніж middleware його читає. Хто вийшов, видно в
  рядку `Logout: user=...` від сигналу.
- **Немає скидання пароля й підтвердження email.** Відправка листів уже є,
  лишилось підключити `PasswordResetView`; заплановано.
- **Валюта одна.** Ціни й оплата лише в гривнях (`uah`); кілька валют заплановано
  на наступні домашки.
- **Stripe лише в тестовому режимі.** Акаунт не активовано (Україна не підтримується).
- **Повернення коштів вручну.** Якщо скасовано оплачене замовлення, адмінка лише
  попереджає «return the money to the customer»; refund через Stripe API немає.
- **Листи й скасування неоплачених — синхронно й вручну.** Лист відправляється в
  межах запиту; `cancel_unpaid_orders` запускається руками. Обидва — задачі для Celery.
- **Немає тестів.** Перевірки робились тестовим клієнтом на тимчасовій базі, у
  репозиторії тестів поки немає.

## Плани

- nginx перед gunicorn: роздача static і media, `DEBUG=False` у Docker;
- i18n: українська та англійська мови інтерфейсу;
- валюти: модель `Currency` (UAH, USD);
- скидання пароля й підтвердження email;
- Celery: листи у фоні, `cancel_unpaid_orders` за розкладом (beat);
- тести для кошика, оформлення (зокрема гонок), webhook, views, форм і прав доступу.
