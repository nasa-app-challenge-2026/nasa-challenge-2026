import { MapContainer, Marker, Rectangle, TileLayer, useMapEvents } from "react-leaflet";
import L from "leaflet";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

const icon = L.icon({ iconUrl: markerIcon, shadowUrl: markerShadow, iconAnchor: [12, 41] });

type Cell = {
  latitude_min: number;
  latitude_max: number;
  longitude_min: number;
  longitude_max: number;
};
type Props = {
  latitude: number;
  longitude: number;
  cell?: Cell;
  onPick: (latitude: number, longitude: number) => void;
};

function ClickHandler({ onPick }: Pick<Props, "onPick">) {
  useMapEvents({ click: (event) => onPick(event.latlng.lat, event.latlng.lng) });
  return null;
}

/** Farm location; the NASA grid cell actually analysed is drawn once known. */
export function FarmMap({ latitude, longitude, cell, onPick }: Props) {
  return (
    <MapContainer
      center={[latitude, longitude]}
      zoom={8}
      className="map"
      aria-label="Carte : cliquez pour placer la ferme"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Marker position={[latitude, longitude]} icon={icon} />
      {cell && (
        <Rectangle
          bounds={[
            [cell.latitude_min, cell.longitude_min],
            [cell.latitude_max, cell.longitude_max],
          ]}
          pathOptions={{ color: "#1d4ed8", weight: 2, fillOpacity: 0.08 }}
        />
      )}
      <ClickHandler onPick={onPick} />
    </MapContainer>
  );
}
