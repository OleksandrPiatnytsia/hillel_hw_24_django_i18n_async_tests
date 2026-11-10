from django.urls import path

from . import views

# Namespace: names are used as "books:list", "books:detail", ...
app_name = "books"

urlpatterns = [
    path("", views.BookListView.as_view(), name="list"),
    path("create/", views.BookCreateView.as_view(), name="create"),
    # JSON suggestions for the navbar search (async view)
    path("search/", views.book_search, name="search"),
    path("<int:pk>/", views.BookDetailView.as_view(), name="detail"),
    path("<int:pk>/update/", views.BookUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.BookDeleteView.as_view(), name="delete"),
    path("authors/", views.AuthorListView.as_view(), name="author_list"),
    path("authors/<int:pk>/", views.AuthorDetailView.as_view(), name="author_detail"),
]
