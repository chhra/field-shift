"use client";

import "leaflet/dist/leaflet.css";
import type { LatLngBoundsExpression, LatLngTuple } from "leaflet";
import { useEffect } from "react";
import {
  CircleMarker,
  GeoJSON,
  MapContainer,
  Polygon,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";
import type { GeoJSONPolygon } from "@/lib/types";

export interface MapProps {
  center: LatLngTuple;
  zoom: number;
  height: number;
  polygon?: GeoJSONPolygon | null;
  marker?: { lat: number; lon: number; label: string } | null;
  drawPoints?: LatLngTuple[];
  onMapClick?: (lat: number, lon: number) => void;
  label: string;
}

const GREEN = "#3f7d3a";

function FitTo({ polygon }: { polygon?: GeoJSONPolygon | null }) {
  const map = useMap();
  useEffect(() => {
    if (!polygon?.coordinates?.[0]?.length) return;
    const bounds = polygon.coordinates[0].map(([lon, lat]) => [lat, lon]) as LatLngBoundsExpression;
    map.fitBounds(bounds, { padding: [28, 28], maxZoom: 16 });
  }, [map, polygon]);
  return null;
}

function Recenter({ center, zoom }: { center: LatLngTuple; zoom: number }) {
  const map = useMap();
  const [lat, lon] = center;
  useEffect(() => {
    map.setView([lat, lon], zoom);
  }, [map, lat, lon, zoom]);
  return null;
}

function Clicks({ onMapClick }: { onMapClick?: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      onMapClick?.(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export default function LeafletMap({
  center,
  zoom,
  height,
  polygon,
  marker,
  drawPoints,
  onMapClick,
  label,
}: MapProps) {
  return (
    <div style={{ height }} role="region" aria-label={label}>
      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom={false}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution="Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics"
          maxZoom={19}
        />
        {polygon ? (
          <>
            <GeoJSON
              key={JSON.stringify(polygon.coordinates)}
              data={polygon}
              style={{ color: "#ffffff", weight: 2.5, fillColor: GREEN, fillOpacity: 0.28 }}
            />
            <FitTo polygon={polygon} />
          </>
        ) : (
          <Recenter center={center} zoom={zoom} />
        )}
        {marker && (
          <CircleMarker
            center={[marker.lat, marker.lon]}
            radius={9}
            pathOptions={{ color: "#ffffff", weight: 3, fillColor: GREEN, fillOpacity: 1 }}
          >
            <Tooltip direction="top" offset={[0, -10]} permanent>
              {marker.label}
            </Tooltip>
          </CircleMarker>
        )}
        {drawPoints && drawPoints.length > 0 && (
          <>
            {drawPoints.length >= 3 ? (
              <Polygon
                positions={drawPoints}
                pathOptions={{ color: "#ffffff", weight: 2.5, fillColor: GREEN, fillOpacity: 0.28 }}
              />
            ) : (
              <Polyline positions={drawPoints} pathOptions={{ color: "#ffffff", weight: 2.5 }} />
            )}
            {drawPoints.map((p, i) => (
              <CircleMarker
                key={i}
                center={p}
                radius={5}
                pathOptions={{ color: GREEN, weight: 2, fillColor: "#ffffff", fillOpacity: 1 }}
              />
            ))}
          </>
        )}
        {onMapClick && <Clicks onMapClick={onMapClick} />}
      </MapContainer>
    </div>
  );
}
