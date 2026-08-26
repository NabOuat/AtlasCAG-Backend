from rest_framework.pagination import PageNumberPagination


class StandardResultsPagination(PageNumberPagination):
    """Pagination par défaut de l'API — permet au client de demander une page plus grande via
    `?page_size=`, plafonnée à `max_page_size` pour éviter un appel démesuré. Sans ce paramètre,
    le comportement reste identique à l'ancien réglage (25/page)."""
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 1000
