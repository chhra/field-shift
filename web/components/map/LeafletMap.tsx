"use client";

import "leaflet/dist/leaflet.css";
import type { LatLngBoundsExpression, LatLngTuple, PointTuple } from "leaflet";
import { useEffect } from "react";
import {
  AttributionControl,
  CircleMarker,
  GeoJSON,
  MapContainer,
  Polygon,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
  ZoomControl,
} from "react-leaflet";
import type { GeoJSONPolygon } from "@/lib/types";

export interface MapProps {
  center: LatLngTuple;
  zoom: number;
  height: number | string;
  polygon?: GeoJSONPolygon | null;
  marker?: { lat: number; lon: number; label: string } | null;
  drawPoints?: LatLngTuple[];
  onMapClick?: (lat: number, lon: number) => void;
  label: string;
  /** false: a still picture (no pan, zoom or controls). */
  interactive?: boolean;
  zoomPosition?: "topleft" | "topright" | "bottomright";
  /** Move the credit line when something is laid over the map's lower edge. */
  attributionPosition?: "bottomright" | "topright";
  /** Pixels kept clear when fitting the outline, e.g. under an overlapping sheet. */
  fitPadding?: { top?: number; right?: number; bottom?: number; left?: number };
  /** Pixel pan after centring, to lift a marker above an overlapping sheet. */
  nudge?: PointTuple;
}

const GREEN = "#3f7d3a";

function FitTo({
  polygon,
  padding,
}: {
  polygon?: GeoJSONPolygon | null;
  padding: Required<NonNullable<MapProps["fitPadding"]>>;
}) {
  const map = useMap();
  const { top, right, bottom, left } = padding;
  useEffect(() => {
    if (!polygon?.coordinates?.[0]?.length) return;
    const bounds = polygon.coordinates[0].map(([lon, lat]) => [lat, lon]) as LatLngBoundsExpression;
    map.fitBounds(bounds, {
      paddingTopLeft: [left, top],
      paddingBottomRight: [right, bottom],
      maxZoom: 16,
    });
  }, [map, polygon, top, right, bottom, left]);
  return null;
}

function Recenter({ center, zoom, nudge }: { center: LatLngTuple; zoom: number; nudge?: PointTuple }) {
  const map = useMap();
  const [lat, lon] = center;
  const [nx, ny] = nudge ?? [0, 0];
  useEffect(() => {
    map.setView([lat, lon], zoom, { animate: false });
    if (nx || ny) map.panBy([nx, ny], { animate: false });
  }, [map, lat, lon, zoom, nx, ny]);
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
  polygon,
  marker,
  drawPoints,
  onMapClick,
  label,
  interactive = true,
  zoomPosition = "topleft",
  attributionPosition = "bottomright",
  fitPadding,
  nudge,
}: MapProps) {
  // One-finger drags on a phone should scroll the page, not pan the map.
  const touch = typeof window !== "undefined" && window.matchMedia("(pointer: coarse)").matches;
  const pad = { top: 28, right: 28, bottom: 28, left: 28, ...fitPadding };
  return (
    <div style={{ height: "100%" }} role="region" aria-label={label}>
      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom={false}
        zoomControl={false}
        dragging={interactive && (!touch || !!onMapClick)}
        touchZoom={interactive}
        doubleClickZoom={interactive}
        boxZoom={interactive}
        keyboard={interactive}
        attributionControl={false}
        style={{ height: "100%", width: "100%" }}
      >
        <AttributionControl position={attributionPosition} />
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution="Imagery © Esri, Maxar, Earthstar Geographics"
          maxZoom={19}
        />
        {interactive && <ZoomControl position={zoomPosition} />}
        {polygon ? (
          <>
            <GeoJSON
              key={JSON.stringify(polygon.coordinates)}
              data={polygon}
              style={{ color: "#ffffff", weight: 2.5, fillColor: GREEN, fillOpacity: 0.28 }}
            />
            <FitTo polygon={polygon} padding={pad} />
          </>
        ) : (
          <Recenter center={center} zoom={zoom} nudge={nudge} />
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
