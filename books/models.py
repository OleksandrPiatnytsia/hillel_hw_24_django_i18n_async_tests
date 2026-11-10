from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

LOW_STOCK_THRESHOLD = 5


class BookQuerySet(models.QuerySet):
    STOCK_IN = "in_stock"
    STOCK_LOW = "low"
    STOCK_OUT = "out"
    STOCK_STATUS_CHOICES = [
        (STOCK_IN, _("In stock")),
        # format_lazy: the number is put in when the label is shown, after
        # the translation ("Мало (≤ 5)"); an f-string would be built once,
        # in English, when the module is imported
        (STOCK_LOW, format_lazy(_("Low (≤ {threshold})"), threshold=LOW_STOCK_THRESHOLD)),
        (STOCK_OUT, _("Out of stock")),
    ]

    def by_stock_status(self, status):
        """Filter by one of STOCK_STATUS_CHOICES; unknown/empty value -> no filter."""
        if status == self.STOCK_IN:
            return self.filter(stock__gt=0)
        if status == self.STOCK_LOW:
            return self.filter(stock__gt=0, stock__lte=LOW_STOCK_THRESHOLD)
        if status == self.STOCK_OUT:
            return self.filter(stock=0)
        return self


class Category(models.Model):
    name = models.CharField(_("name"), max_length=100, unique=True)
    slug = models.SlugField(_("slug"), max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("category")
        verbose_name_plural = _("categories")

    def __str__(self):
        return self.name


class Author(models.Model):
    # unique: the data migration and seed_books look authors up by name
    name = models.CharField(_("name"), max_length=255, unique=True)
    bio = models.TextField(_("biography"), blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("author")
        verbose_name_plural = _("authors")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("books:author_detail", kwargs={"pk": self.pk})


class Book(models.Model):
    title = models.CharField(_("title"), max_length=255)
    author = models.ForeignKey(
        Author,
        verbose_name=_("author"),
        on_delete=models.PROTECT,  # can't delete an author who still has books
        related_name="books",  # author.books.all()
    )
    price = models.DecimalField(
        _("price"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    description = models.TextField(_("description"), blank=True)
    stock = models.PositiveIntegerField(_("stock"), default=0)
    # Only the path is stored in the DB; the file goes to MEDIA_ROOT/covers/<year>/<month>/
    cover = models.ImageField(_("cover"), upload_to="covers/%Y/%m/", blank=True)
    categories = models.ManyToManyField(
        Category,
        verbose_name=_("categories"),
        through="BookCategory",
        related_name="books",
        blank=True,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = BookQuerySet.as_manager()

    class Meta:
        ordering = ["title"]
        verbose_name = _("book")
        verbose_name_plural = _("books")
        # Custom permission on top of the 4 default ones (add / change /
        # delete / view_book). Codename -> "books.manage_stock" in has_perm()
        # and perms.books.manage_stock in templates. Editors may edit a book,
        # but only users with this permission may change its stock.
        # NOT translated: the name is copied into the auth_permission table
        # once (at migrate), in the language active at that moment. Django's
        # own names ("Can add book") stay English the same way.
        permissions = [
            ("manage_stock", "Can change stock quantity"),
        ]

    def __str__(self):
        # author is a related object: use select_related("author") in lists,
        # otherwise every str(book) makes an extra query
        return f"{self.title} — {self.author.name}"

    def get_absolute_url(self):
        return reverse("books:detail", kwargs={"pk": self.pk})

    @property
    def cover_url(self):
        """Uploaded cover or the static placeholder — templates don't need if/else."""
        if self.cover:
            return self.cover.url
        return static("img/no-cover.svg")

    @property
    def is_low_stock(self):
        return 0 < self.stock <= LOW_STOCK_THRESHOLD


class BookCategory(models.Model):
    """Link between Book and Category.

    An explicit through model lets us protect categories from deletion
    while they still contain books (plain M2M has no on_delete).
    """

    book = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name=_("book"))
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name=_("category"))

    class Meta:
        verbose_name = _("book category")
        verbose_name_plural = _("book categories")
        constraints = [
            models.UniqueConstraint(
                fields=["book", "category"],
                name="unique_book_category",
            ),
        ]

    def __str__(self):
        return f"{self.book.title} → {self.category.name}"
