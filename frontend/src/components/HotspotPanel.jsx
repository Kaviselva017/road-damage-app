import React, { useEffect, useState } from 'react';
import { useMap } from 'react-leaflet';
import { ChevronRight, ChevronLeft, AlertTriangle_icon, DollarSign, MapPin } from 'lucide-react';

const HotspotPanel = ({ token }) => {
  const map = useMap();
  const [hotspots, setHotspots] = useState([]);
  const [collapsed, setCollapsed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHotspots = async () => {
      try {
        const response = await fetch('/api/map/hotspots?min_count=3', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Auth required');
        const data = await response.json();
        setHotspots(data.slice(0, 10)); // Top 10
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    if (token) fetchHotspots();
  }, [token]);

  const handleFlyTo = (lat, lng) => {
    map.flyTo([lat, lng], 15, { duration: 1 });
  };

  const getSeverityColor = (sev) => {
    switch (sev.toLowerCase()) {
      case 'critical': return 'bg-red-600 text-white';
      case 'high':     return 'bg-orange-500 text-white';
      case 'medium':   return 'bg-yellow-400 text-black';
      default:         return 'bg-blue-500 text-white';
    }
  };

  return (
    <div className={`fixed right-0 top-0 h-screen transition-all duration-300 z-[1001] bg-white shadow-2xl flex ${collapsed ? 'w-0' : 'w-80'}`}>
      <button 
        onClick={() => setCollapsed(!collapsed)}
        className="absolute left-[-40px] top-1/2 -translate-y-1/2 bg-white p-2 rounded-l-xl shadow-lg border-r-0 border border-gray-200"
      >
        {collapsed ? <ChevronLeft size={24} /> : <ChevronRight size={24} />}
      </button>

      {!collapsed && (
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="p-6 border-b bg-slate-900 text-white">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <AlertTriangle_icon className="text-yellow-400" size={20} />
              Damage Hotspots
            </h2>
            <p className="text-xs text-slate-400 mt-1">Highest priority resolution zones</p>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {loading ? (
              <div className="flex flex-col items-center justify-center h-40 gap-2 text-gray-400">
                <div className="animate-spin h-6 w-6 border-2 border-primary border-t-transparent rounded-full" />
                <span className="text-sm">Identifying hotspots...</span>
              </div>
            ) : hotspots.map((h, idx) => (
              <div 
                key={idx}
                onClick={() => handleFlyTo(h.lat, h.lng)}
                className="group p-4 rounded-xl border border-gray-100 hover:border-primary/30 hover:bg-primary/5 cursor-pointer transition-all shadow-sm"
              >
                <div className="flex justify-between items-start mb-2">
                  <span className="text-xs font-bold text-gray-400">#{idx + 1}</span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase font-black ${getSeverityColor(h.max_severity)}`}>
                    {h.max_severity}
                  </span>
                </div>
                
                <h3 className="font-bold text-gray-800 capitalize truncate">{h.dominant_damage_type} Cluster</h3>
                <div className="flex items-center gap-1 text-xs text-gray-500 mt-1">
                  <MapPin size={12} />
                  <span>{h.count} active reports nearby</span>
                </div>

                <div className="mt-4 flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-[10px] text-gray-400 uppercase font-medium">Est. Repair Cost</span>
                    <span className="text-sm font-bold text-slate-900 flex items-center">
                      ₹{h.estimated_repair_cost.toLocaleString()}
                    </span>
                  </div>
                  <div className="h-8 w-8 bg-gray-50 rounded-lg flex items-center justify-center group-hover:bg-primary group-hover:text-white transition-colors">
                    <ChevronRight size={16} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default HotspotPanel;
