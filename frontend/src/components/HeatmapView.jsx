import React, { useEffect, useState } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.heat';

const HeatmapView = ({ gridSize = 500 }) => {
  const map = useMap();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let heatmapLayer = null;

    const fetchHeatmap = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/map/heatmap?grid=${gridSize}`);
        if (!response.ok) throw new Error('Failed to fetch heatmap data');
        const data = await response.json();

        // Transform to [lat, lng, weight]
        // Weights are relative, normalize to 0-1 based on max weight in view if possible 
        // or just use raw weight with a good intensity setting
        const maxWeight = Math.max(...data.map(d => d.weight), 1);
        const points = data.map(d => [
          d.lat, 
          d.lng, 
          d.weight / maxWeight // normalized intensity
        ]);

        if (heatmapLayer) {
          map.removeLayer(heatmapLayer);
        }

        heatmapLayer = L.heatLayer(points, {
          radius: 25,
          blur: 15,
          maxZoom: 17,
          gradient: { 0.2: 'blue', 0.4: 'green', 0.6: 'yellow', 0.8: 'orange', 1.0: 'red' }
        }).addTo(map);

      } catch (err) {
        console.error(err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchHeatmap();

    return () => {
      if (heatmapLayer) {
        map.removeLayer(heatmapLayer);
      }
    };
  }, [map, gridSize]);

  return (
    <div className="absolute top-4 left-16 z-[1000] pointer-events-none">
      {loading && (
        <div className="bg-white/80 backdrop-blur px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 pointer-events-auto">
          <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
          <span className="text-sm font-medium">Recalculating density...</span>
        </div>
      )}
      {error && (
        <div className="bg-red-50 text-red-600 px-4 py-2 rounded-lg shadow-lg text-sm font-medium pointer-events-auto">
          Error: {error}
        </div>
      )}
    </div>
  );
};

export default HeatmapView;
