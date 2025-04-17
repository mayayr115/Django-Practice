from django.core.cache import cache
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
 
class PopularRestaurantViewSet(viewsets.ModelViewSet):
    @action(detail=False, methods=['get'])
    def popular(self, request):
        latitude = request.query_params.get('lat')
        longitude = request.query_params.get('lng')
        radius = request.query_params.get('radius', '5km')
        
        cache_key = f"popular_restaurants:{latitude}:{longitude}:{radius}"
        cached_data = cache.get(cache_key)
 
        if cached_data:
            return Response(cached_data)
 
        # Calculate location-based grid cell
        cell_size = 0.1  # Roughly 11km
        grid_lat = int(float(latitude) / cell_size)
        grid_lng = int(float(longitude) / cell_size)
        
        # Get restaurants from database
        restaurants = Restaurant.objects.filter(
            latitude__range=(grid_lat * cell_size, (grid_lat + 1) * cell_size),
            longitude__range=(grid_lng * cell_size, (grid_lng + 1) * cell_size)
        ).annotate(
            popularity_score=Count('visits') + Count('ratings')
        ).order_by('-popularity_score')[:50]
 
        serialized_data = RestaurantSerializer(restaurants, many=True).data
        
        # Cache the results
        cache.set(
            cache_key,
            serialized_data,
            timeout=300  # 5 minutes
        )
 
        # Store metadata for cache management
        cache.set(
            f"{cache_key}:meta",
            {
                'created_at': timezone.now(),
                'cell': f"{grid_lat}:{grid_lng}",
                'count': len(restaurants)
            },
            timeout=300
        )
 
        return Response(serialized_data)
 
    def update_restaurant_cache(self, restaurant):
        # Find affected cache keys
        affected_cells = self._get_affected_grid_cells(
            restaurant.latitude,
            restaurant.longitude
        )
        
        for cell in affected_cells:
            pattern = f"popular_restaurants:{cell}*"
            keys = cache.keys(pattern)
            cache.delete_many(keys)
 
    def _get_affected_grid_cells(self, lat, lng):
        cell_size = 0.1
        grid_lat = int(float(lat) / cell_size)
        grid_lng = int(float(lng) / cell_size)
        return [f"{grid_lat}:{grid_lng}"]