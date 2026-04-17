import React, { useState } from 'react';
import { MapContainer, TileLayer, ZoomControl } from 'react-leaflet';
import HeatmapView from '../components/HeatmapView';
import HotspotPanel from '../components/HotspotPanel';
import TimelineChart from '../components/TimelineChart';
import { Map as MapIcon, Sliders } from 'lucide-react';

const MapDashboard = () => {
  const [gridSize, setGridSize] = useState(500);
  const token = localStorage.getItem('token'); // Simplistic auth retrieval

  return (
    <div className="flex flex-col h-screen bg-slate-50 overflow-hidden font-sans">
      {/* Header */}
      <header className="h-16 flex items-center justify-between px-8 bg-white border-b border-gray-200 shrink-0 z-50">
        <div className="flex items-center gap-3">
          <div className="bg-primary/10 p-2 rounded-lg">
            <MapIcon className="text-primary" size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Road Damage Intelligence Map</h1>
            <p className="text-[10px] text-gray-500 uppercase font-bold tracking-widest">PostGIS Heatmap & Predictive Triage</p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-4 bg-gray-50 px-4 py-2 rounded-xl border border-gray-100">
            <div className="flex items-center gap-2 text-gray-500">
              <Sliders size={16} />
              <span className="text-xs font-bold uppercase">Grid Analysis:</span>
            </div>
            <input 
              type="range" 
              min="100" max="2000" step="100" 
              value={gridSize} 
              onChange={(e) => setGridSize(parseInt(e.target.value))}
              className="w-32 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary"
            />
            <span className="text-xs font-black text-slate-700 w-12">{gridSize}m</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col relative overflow-hidden">
        {/* Map Area */}
        <div className="flex-1 relative">
          <MapContainer 
            center={[12.9716, 77.5946]} // Default: Bengaluru
            zoom={13} 
            zoomControl={false}
            className="h-full w-full"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            />
            <ZoomControl position="bottomleft" />
            
            <HeatmapView gridSize={gridSize} />
            <HotspotPanel token={token} />
          </MapContainer>
        </div>

        {/* Bottom Panel */}
        <div className="h-fit bg-slate-50 p-6 shrink-0 relative z-40 border-t border-gray-200">
          <div className="max-w-6xl mx-auto">
            <TimelineChart />
          </div>
        </div>
      </main>
    </div>
  );
};

export default MapDashboard;
