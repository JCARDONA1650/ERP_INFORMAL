from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """25 por página; el cliente puede pedir hasta 200 con ?page_size= (selectores y listas completas)."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
