from rest_framework import viewsets, generics
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import Upper, Trim
from .models import HechosAsistenciaHumanitaria
from .serializers import HechosAsistenciaHumanitariaSerializer, TotalAyudasSerializer
from datetime import datetime
from rest_framework.views import APIView
from .serializers import ResumenGeneralSerializer, DistribucionAnualProductoSerializer, ResumenPorDepartamentoSerializer
import django_filters
# from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

# Configuración de paginación
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'per_page'
    max_page_size = None

def _annotate_total_ayudas(queryset):
    """
    Función auxiliar para anotar los totales de ayudas de forma consistente.
    """
    return queryset.annotate(
        kit_sentencia=Sum('kit_sentencia'),
        kit_evento=Sum('kit_evento'),
        chapa_fibrocemento_cantidad=Sum('chapa_fibrocemento_cantidad'),
        chapa_zinc_cantidad=Sum('chapa_zinc_cantidad'),
        colchones_cantidad=Sum('colchones_cantidad'),
        frazadas_cantidad=Sum('frazadas_cantidad'),
        terciadas_cantidad=Sum('terciadas_cantidad'),
        puntales_cantidad=Sum('puntales_cantidad'),
        carpas_plasticas_cantidad=Sum('carpas_plasticas_cantidad'),
        cantidad_registros=Sum('cantidad_registros'),
        cantidad_familias_asistidas=Sum('cantidad_familias_asistidas'),
        cantidad_mujeres=Sum('cantidad_mujeres'),
        cantidad_hombres=Sum('cantidad_hombres'),
        cantidad_otro=Sum('cantidad_otro'),
        cantidad_rural=Sum('cantidad_rural'),
        cantidad_urbana=Sum('cantidad_urbana'),
        cantidad_indigena=Sum('cantidad_indigena'),
        cantidad_no_indigena=Sum('cantidad_no_indigena'),
        total_ayudas=F('kit_sentencia') + F('kit_evento') +
            F('chapa_fibrocemento_cantidad') + F('chapa_zinc_cantidad') +
            F('colchones_cantidad') + F('frazadas_cantidad') +
            F('terciadas_cantidad') + F('puntales_cantidad') +
            F('carpas_plasticas_cantidad')
    )
class HechosAsistenciaHumanitariaFilterSet(django_filters.FilterSet):
    """
    Conjunto de filtros para el modelo HechosAsistenciaHumanitaria.
    """
    departamento = django_filters.CharFilter(field_name='id_ubicacion__departamento', lookup_expr='icontains')
    distrito = django_filters.CharFilter(field_name='id_ubicacion__distrito', lookup_expr='icontains')
    localidad = django_filters.CharFilter(field_name='id_ubicacion__localidad', lookup_expr='icontains')
    evento = django_filters.CharFilter(field_name='id_evento__evento', lookup_expr='icontains')
    anio = django_filters.NumberFilter(field_name='id_fecha__anio')
    mes = django_filters.NumberFilter(field_name='id_fecha__mes')
    fecha_desde = django_filters.DateFilter(field_name='id_fecha__fecha', lookup_expr='gte')
    fecha_hasta = django_filters.DateFilter(field_name='id_fecha__fecha', lookup_expr='lte')
    chapas = django_filters.NumberFilter(method='filter_chapas')
    numeroOcurrencias = django_filters.NumberFilter(method='filter_numero_ocurrencias')
    familias_min = django_filters.NumberFilter(
        field_name='cantidad_familias_asistidas', lookup_expr='gte',
    )
    familias_max = django_filters.NumberFilter(
        field_name='cantidad_familias_asistidas', lookup_expr='lte',
    )
    mujeres_min = django_filters.NumberFilter(
        field_name='cantidad_mujeres', lookup_expr='gte',
    )
    hombres_min = django_filters.NumberFilter(
        field_name='cantidad_hombres', lookup_expr='gte',
    )
    indigena_min = django_filters.NumberFilter(
        field_name='cantidad_indigena', lookup_expr='gte',
    )
    no_indigena_min = django_filters.NumberFilter(
        field_name='cantidad_no_indigena', lookup_expr='gte',
    )
    caracterizacion_informada = django_filters.BooleanFilter(
        method='filter_caracterizacion_informada',
    )

    def filter_caracterizacion_informada(self, queryset, name, value):
        if value:
            return queryset.filter(cantidad_familias_asistidas__gt=0)
        return queryset.filter(cantidad_familias_asistidas=0)

    def filter_chapas(self, queryset, name, value):
        # Si el queryset ya tiene 'chapas' anotado, filtra directo
        annotations = getattr(queryset, 'query', None)
        if annotations and hasattr(annotations, 'annotations') and 'chapas' in annotations.annotations:
            return queryset.filter(chapas=value)
        # Si no, anota y filtra
        queryset = queryset.annotate(
            chapas=F('chapa_fibrocemento_cantidad') + F('chapa_zinc_cantidad')
        )
        return queryset.filter(chapas=value)

    def filter_numero_ocurrencias(self, queryset, name, value):
        # Si el queryset ya tiene 'numeroOcurrencias' anotado, filtra directo
        annotations = getattr(queryset, 'query', None)
        if annotations and hasattr(annotations, 'annotations') and 'numeroOcurrencias' in annotations.annotations:
            return queryset.filter(numeroOcurrencias=value)
        # Si no, anota y filtra (solo tiene sentido en vistas que agregan Count)
        queryset = queryset.annotate(
            numeroOcurrencias=Count('id_evento')
        )
        return queryset.filter(numeroOcurrencias=value)

    class Meta:
        model = HechosAsistenciaHumanitaria
        fields = '__all__'
class AsistenciaDetalladaAPIView(generics.ListAPIView):
    """
    Vista que devuelve el detalle de los registros, incluyendo la ubicación,
    el evento y las cantidades de ayuda. Soporta filtros y paginación.
    """
    queryset = HechosAsistenciaHumanitaria.objects.all().select_related('id_fecha', 'id_ubicacion', 'id_evento')
    serializer_class = HechosAsistenciaHumanitariaSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        return super().get_queryset().order_by('-id_fecha__fecha')

class AsistenciaAnualAPIView(generics.ListAPIView):
    """
    Endpoint para ver la asistencia humanitaria total por año.
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        qs = HechosAsistenciaHumanitaria.objects.exclude(id_evento__evento='ELIMINAR_REGISTRO').values('id_fecha__anio')
        qs = qs.annotate(anio=F('id_fecha__anio'))
        qs = _annotate_total_ayudas(qs)
        return qs.order_by('id_fecha__anio')

class AsistenciaMensualAPIView(generics.ListAPIView):
    """
    Endpoint para ver la asistencia humanitaria total por mes.
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        queryset = HechosAsistenciaHumanitaria.objects.exclude(id_evento__evento='ELIMINAR_REGISTRO').values('id_fecha__anio', 'id_fecha__mes', 'id_fecha__nombre_mes').annotate(
            anio=F('id_fecha__anio'),
            mes=F('id_fecha__mes'),
            nombre_mes=F('id_fecha__nombre_mes'),
        ).order_by('id_fecha__anio', 'id_fecha__mes')
        return _annotate_total_ayudas(queryset)
    
class AsistenciaPorUbicacionAPIView(generics.ListAPIView):
    """
    Endpoint para ver la asistencia humanitaria por departamento y distrito.
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        # Normalizar y agrupar por departamento/distrito usando trim+upper para evitar duplicados
        qs = HechosAsistenciaHumanitaria.objects.exclude(id_evento__evento='ELIMINAR_REGISTRO')
        qs = qs.annotate(
            departamento_norm=Upper(Trim(F('id_ubicacion__departamento'))),
            distrito_norm=Upper(Trim(F('id_ubicacion__distrito'))),
        )

        queryset = qs.values('departamento_norm', 'distrito_norm').annotate(
            departamento=F('departamento_norm'),
            distrito=F('distrito_norm'),
        ).order_by('departamento', 'distrito').distinct()

        return _annotate_total_ayudas(queryset)
class AsistenciaPorDepartamentoAPIView(generics.ListAPIView):
    """
    Endpoint para ver la asistencia humanitaria por departamento.
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        queryset = HechosAsistenciaHumanitaria.objects.exclude(id_evento__evento='ELIMINAR_REGISTRO').values('id_ubicacion__departamento', 'id_ubicacion__orden')
        queryset = queryset.annotate(
            departamento=F('id_ubicacion__departamento'),
            orden=F('id_ubicacion__orden')
        )
        queryset = _annotate_total_ayudas(queryset)
        return queryset.order_by('id_ubicacion__orden', 'id_ubicacion__departamento')
class AsistenciaPorEventoAPIView(generics.ListAPIView):
    """
    Endpoint para ver la asistencia humanitaria por tipo de evento.
    """
    serializer_class = TotalAyudasSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        queryset = HechosAsistenciaHumanitaria.objects.exclude(id_evento__evento='ELIMINAR_REGISTRO').values(
            evento=F('id_evento__evento')
        ).annotate(
            numeroOcurrencias=Count('id_evento'),
        ).order_by('-numeroOcurrencias')

        return _annotate_total_ayudas(queryset)

class EventosPorDepartamentoAPIView(generics.ListAPIView):
    """
    Endpoint para ver las cantidades de ayuda para eventos específicos en cada departamento.
    """
    serializer_class = TotalAyudasSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet
    
    def get_queryset(self):
        queryset = HechosAsistenciaHumanitaria.objects.exclude(id_evento__evento='ELIMINAR_REGISTRO').values('id_ubicacion__departamento', 'id_evento__evento').annotate(
            evento=F('id_evento__evento'),
            departamento=F('id_ubicacion__departamento'),
        ).order_by('id_ubicacion__departamento', 'id_evento__evento')
        
        input_busqueda = self.request.query_params.get('inputBusqueda')
        if input_busqueda:
            queryset = queryset.filter(
                Q(id_ubicacion__departamento__icontains=input_busqueda) |
                Q(id_evento__evento__icontains=input_busqueda)
            )
        return _annotate_total_ayudas(queryset)

@api_view(['GET'])
def total_asistencia(request):
    """
    Devuelve el total acumulado de todos los campos de ayuda, sin discriminar, 
    y el registro más reciente por fecha.
    """
    queryset = HechosAsistenciaHumanitaria.objects.exclude(id_evento__evento='ELIMINAR_REGISTRO')
    
    # Sumar todos los campos de ayuda
    totales = queryset.aggregate(
        total_kit_sentencia=Sum('kit_sentencia'),
        total_kit_evento=Sum('kit_evento'),
        total_chapa_fibrocemento=Sum('chapa_fibrocemento_cantidad'),
        total_chapa_zinc=Sum('chapa_zinc_cantidad'),
        total_colchones=Sum('colchones_cantidad'),
        total_frazadas=Sum('frazadas_cantidad'),
        total_terciadas=Sum('terciadas_cantidad'),
        total_puntales=Sum('puntales_cantidad'),
        total_carpas_plasticas=Sum('carpas_plasticas_cantidad'),
        total_ayudas=Sum('kit_sentencia') + Sum('kit_evento') +
            Sum('chapa_fibrocemento_cantidad') + Sum('chapa_zinc_cantidad') +
            Sum('colchones_cantidad') + Sum('frazadas_cantidad') +
            Sum('terciadas_cantidad') + Sum('puntales_cantidad') +
            Sum('carpas_plasticas_cantidad')
    )

    # Obtener el registro más reciente por fecha
    registro_reciente = queryset.order_by('-id_fecha__fecha').first()
    fecha_ultima = registro_reciente.id_fecha.fecha if registro_reciente else None

    return Response({
        **{k: v or 0 for k, v in totales.items()},
        "fecha_ultima": fecha_ultima
    })

# --- SECCION DE LOS GRAFICOS ---

## Eliminada la definición duplicada de AsistenciaPorDepartamentoAPIView para evitar conflictos y asegurar paginación

class EventosPorLocalidadAPIView(generics.ListAPIView):
    """
    Endpoint para ver las localidades con más eventos registrados.
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        queryset = HechosAsistenciaHumanitaria.objects.values(
            localidad=F('id_ubicacion__localidad')
        )
        # El filtrado por fecha lo hace el FilterSet
        # Excluir localidad 'SIN ESPECIFICAR', anotar y ordenar
        queryset = queryset.exclude(
            id_ubicacion__localidad__in=["SIN ESPECIFICAR", ""]
        )
        queryset = _annotate_total_ayudas(queryset)
        queryset = queryset.annotate(
            numero_eventos=Count('id_evento')
        ).order_by('-cantidad_familias_asistidas')
        return queryset

class AsistenciasPorAnioDepartamentoAPIView(generics.ListAPIView):
    """
    Endpoint para ver las asistencias por año y departamento.
    Útil para mapas de calor.
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet
    def get_queryset(self):
        queryset = HechosAsistenciaHumanitaria.objects.values(
            anio=F('id_fecha__anio'),
            departamento=F('id_ubicacion__departamento')
        )
        # El filtrado por fecha lo hace el FilterSet
        queryset = queryset.annotate(
            chapas=Sum('chapa_fibrocemento_cantidad') + Sum('chapa_zinc_cantidad')
        )
        return _annotate_total_ayudas(queryset).order_by('anio', 'departamento')

# Temporal
class TendenciaMensualAsistenciasAPIView(generics.ListAPIView):
    """
    Endpoint para la tendencia mensual de asistencias (contador de eventos).
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        evento_param = self.request.query_params.get('evento')
        queryset = HechosAsistenciaHumanitaria.objects.values(
            anio=F('id_fecha__anio'),
            nombre_mes=F('id_fecha__nombre_mes'),
            mes=F('id_fecha__mes')
        )
        if evento_param:
            queryset = queryset.filter(id_evento__evento=evento_param)
        
        
        return queryset.annotate(
            numero_asistencias=Sum('cantidad_familias_asistidas'),
            kit_sentencia=Sum('kit_sentencia'),
            kit_evento=Sum('kit_evento'),
            chapa_fibrocemento_cantidad=Sum('chapa_fibrocemento_cantidad'),
            chapa_zinc_cantidad=Sum('chapa_zinc_cantidad'),
            colchones_cantidad=Sum('colchones_cantidad'),
            frazadas_cantidad=Sum('frazadas_cantidad'),
            terciadas_cantidad=Sum('terciadas_cantidad'),
            puntales_cantidad=Sum('puntales_cantidad'),
            carpas_plasticas_cantidad=Sum('carpas_plasticas_cantidad')
        ).order_by('anio', 'mes')

class DistribucionMensualDetalladaAPIView(generics.ListAPIView):
    """
    Endpoint para la distribución mensual de asistencias por elemento.
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        queryset = HechosAsistenciaHumanitaria.objects.values(
            nombre_mes=F('id_fecha__nombre_mes'),
            mes=F('id_fecha__mes')
        )
        # El filtrado por fecha lo hace el FilterSet
        queryset = queryset.annotate(
            chapas=Sum(F('chapa_fibrocemento_cantidad') + F('chapa_zinc_cantidad'))
        )
        return _annotate_total_ayudas(queryset).order_by('mes')

class DistribucionAnualProductoAPIView(generics.ListAPIView):
    """
    Endpoint para la distribución anual de un producto específico.
    Recibe el nombre del producto en los parámetros de la URL.
    """
    serializer_class = DistribucionAnualProductoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet
    
    # Mapeo de nombres de productos a los campos del modelo
    PRODUCT_MAPPING = {
        'kit_sentencia': 'kit_sentencia',
        'kit_evento': 'kit_evento',
        'chapa_fibrocemento': 'chapa_fibrocemento_cantidad',
        'chapa_zinc': 'chapa_zinc_cantidad',
        'colchones': 'colchones_cantidad',
        'frazadas': 'frazadas_cantidad',
        'terciadas': 'terciadas_cantidad',
        'puntales': 'puntales_cantidad',
        'carpas_plasticas': 'carpas_plasticas_cantidad',
    }

    def get_queryset(self):
        producto_param = self.request.query_params.get('producto')
        campo_producto = self.PRODUCT_MAPPING.get(producto_param)

        if not campo_producto:
            return HechosAsistenciaHumanitaria.objects.none()

        queryset = HechosAsistenciaHumanitaria.objects.exclude(id_evento__evento='ELIMINAR_REGISTRO').values(
            anio=F('id_fecha__anio')
        ).annotate(
            unidades_distribuidas=Sum(campo_producto)
        )

        # El filtrado por fecha lo hace el FilterSet

        return queryset.order_by('anio')

# Por eventos
class AsistenciasPorEventoAPIView(generics.ListAPIView):
    """
    Endpoint para ver eventos con mayor número de unidades distribuidas.
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        # El filtrado por fecha y otros campos lo hace el FilterSet
        qs = HechosAsistenciaHumanitaria.objects.all()
        queryset = qs.values(evento=F('id_evento__evento'))
        queryset = queryset.annotate(
            chapas=Sum(F('chapa_fibrocemento_cantidad') + F('chapa_zinc_cantidad'))
        )
        return _annotate_total_ayudas(queryset).order_by('-total_ayudas')

class ComposicionAyudasPorEventoAPIView(generics.ListAPIView):
    """
    Endpoint para ver la composición de ayudas por tipo de evento.
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        queryset = HechosAsistenciaHumanitaria.objects.exclude(id_evento__evento='ELIMINAR_REGISTRO').values(
            evento=F('id_evento__evento')
        )
        # El filtrado por fecha lo hace el FilterSet
        return _annotate_total_ayudas(queryset).order_by('evento')

class OcurrenciasEventoAnualAPIView(generics.ListAPIView):
    """
    Endpoint para la comparación de eventos por año.
    Útil para mapas de calor.
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet

    def get_queryset(self):
        queryset = HechosAsistenciaHumanitaria.objects.exclude(id_evento__evento='ELIMINAR_REGISTRO').values(
            anio=F('id_fecha__anio'),
            evento=F('id_evento__evento')
        )
        # El filtrado por fecha lo hace el FilterSet
        return queryset.annotate(
            numeroOcurrencias=Count('id_asistencia_hum'),
            cantidad_familias_asistidas=Sum('cantidad_familias_asistidas'),
        ).order_by('anio', 'evento')

class IncendiosAnualesPorDepartamentoAPIView(generics.ListAPIView):
    """
    Endpoint para ver el mapa de calor de incendios por año y departamento.
    """
    serializer_class = TotalAyudasSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HechosAsistenciaHumanitariaFilterSet
    def get_queryset(self):
        queryset = HechosAsistenciaHumanitaria.objects.filter(
            id_evento__evento__icontains='incendio'
        ).values(
            anio=F('id_fecha__anio'),
            departamento=F('id_ubicacion__departamento')
        )
        # El filtrado por fecha lo hace el FilterSet
        queryset = queryset.annotate(
            numeroOcurrencias=Count('id_asistencia_hum')
        )
        return _annotate_total_ayudas(queryset).order_by('anio', 'departamento')

class ResumenGeneralAPIView(APIView):
    """
    Endpoint que devuelve un resumen general de la base de datos.
    Incluye: cantidad total de registros, total de kits de evento y cantidad de departamentos únicos.
    Soporta filtro por rango de fechas (YYYY-MM-DD).
    """
    def get(self, request, *args, **kwargs):
        queryset = HechosAsistenciaHumanitaria.objects.all()
        start_date = request.query_params.get('fecha_desde')
        end_date = request.query_params.get('fecha_hasta')
        if start_date and end_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(id_fecha__fecha__range=(start_date_obj, end_date_obj))
            except ValueError:
                return Response({
                    'cantidad_registros_total': 0,
                    'cantidad_kit_evento': 0,
                    'cantidad_departamentos': 0,
                    'cantidad_familias_asistidas': 0,
                    'cantidad_mujeres': 0,
                    'cantidad_hombres': 0,
                    'cantidad_otro': 0,
                    'cantidad_rural': 0,
                    'cantidad_urbana': 0,
                    'cantidad_indigena': 0,
                    'cantidad_no_indigena': 0,
                })
        resumen = queryset.aggregate(
            cantidad_registros_total=Sum('cantidad_registros'),
            cantidad_kit_evento=Sum('kit_evento'),
            cantidad_departamentos=Count('id_ubicacion__departamento', distinct=True),
            cantidad_familias_asistidas=Sum('cantidad_familias_asistidas'),
            cantidad_mujeres=Sum('cantidad_mujeres'),
            cantidad_hombres=Sum('cantidad_hombres'),
            cantidad_otro=Sum('cantidad_otro'),
            cantidad_rural=Sum('cantidad_rural'),
            cantidad_urbana=Sum('cantidad_urbana'),
            cantidad_indigena=Sum('cantidad_indigena'),
            cantidad_no_indigena=Sum('cantidad_no_indigena'),
        )
        data = {
            'cantidad_registros_total': resumen['cantidad_registros_total'] or 0,
            'cantidad_kit_evento': resumen['cantidad_kit_evento'] or 0,
            'cantidad_departamentos': resumen['cantidad_departamentos'] or 0,
            'cantidad_familias_asistidas': resumen['cantidad_familias_asistidas'] or 0,
            'cantidad_mujeres': resumen['cantidad_mujeres'] or 0,
            'cantidad_hombres': resumen['cantidad_hombres'] or 0,
            'cantidad_otro': resumen['cantidad_otro'] or 0,
            'cantidad_rural': resumen['cantidad_rural'] or 0,
            'cantidad_urbana': resumen['cantidad_urbana'] or 0,
            'cantidad_indigena': resumen['cantidad_indigena'] or 0,
            'cantidad_no_indigena': resumen['cantidad_no_indigena'] or 0,
        }
        serializer = ResumenGeneralSerializer(data)
        return Response(serializer.data)

class ResumenPorDepartamentoAPIView(generics.ListAPIView):
    """
    Endpoint que devuelve un resumen detallado por departamento.
    Incluye:
    - Suma total de kits
    - Suma total de chapas
    - Cantidad total de registros por departamento
    - El evento más frecuente en ese departamento
    """
    serializer_class = ResumenPorDepartamentoSerializer
    # No usar DjangoFilterBackend ni filterset_class, filtramos manualmente
    def get_queryset(self):
        # Filtrar manualmente por fecha si se pasan los parámetros
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        base_queryset = HechosAsistenciaHumanitaria.objects.all()
        if fecha_desde:
            base_queryset = base_queryset.filter(id_fecha__fecha__gte=fecha_desde)
        if fecha_hasta:
            base_queryset = base_queryset.filter(id_fecha__fecha__lte=fecha_hasta)

        # Agregación por departamento
        queryset = base_queryset.values(
            departamento=F('id_ubicacion__departamento')
        )
        queryset = _annotate_total_ayudas(queryset).order_by('-cantidad_registros')

        # Evento más frecuente por departamento
        eventos = base_queryset.values(
            'id_ubicacion__departamento', 'id_evento__evento'
        ).annotate(
            evento_count=Count('id_evento')
        ).order_by('id_ubicacion__departamento', '-evento_count')

        mapa_eventos = {}
        for e in eventos:
            depto = e['id_ubicacion__departamento']
            if depto not in mapa_eventos:
                mapa_eventos[depto] = e['id_evento__evento']

        queryset = list(queryset)
        for item in queryset:
            item['evento_mas_frecuente'] = mapa_eventos.get(item.get('departamento'), 'N/A')
        return queryset


class CantidadDistritosAsistidosAPIView(APIView):
    """
    Devuelve la cantidad de distritos distintos que recibieron asistencias.
    Excluye distritos con valor 'SIN ESPECIFICAR' y permite filtros por rango de fechas.
    """
    def get(self, request, *args, **kwargs):
        queryset = HechosAsistenciaHumanitaria.objects.exclude(id_evento__evento='ELIMINAR_REGISTRO')

        # Aplicar filtros opcionales de fecha si se proporcionan
        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')
        if fecha_desde:
            queryset = queryset.filter(id_fecha__fecha__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(id_fecha__fecha__lte=fecha_hasta)

        # Normalizar distrito (trim+upper) y contar distintos excluyendo 'SIN ESPECIFICAR'
        qs = queryset.annotate(distrito_norm=Upper(Trim(F('id_ubicacion__distrito'))))
        qs = qs.exclude(distrito_norm__isnull=True).exclude(distrito_norm__exact='').exclude(distrito_norm='SIN ESPECIFICAR')

        distinct_count = qs.values('distrito_norm').distinct().count()

        return Response({'distritos_asistidos': distinct_count})
    