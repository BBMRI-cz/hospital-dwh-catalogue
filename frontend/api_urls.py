from django.urls import path

from frontend import api_views

app_name = 'frontend_api'

urlpatterns = [
    path(
        'jsonld',
        api_views.CatalogueJsonLdApiView.as_view(),
        name='jsonld',
    ),
    path(
        'rdf',
        api_views.CatalogueTurtleApiView.as_view(),
        name='rdf',
    ),
]
