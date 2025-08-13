// Default to Vijaynagar, Bangalore
const defaultLat = 12.9719;
const defaultLng = 77.5641;
const defaultZoom = 13;

var map = L.map('map').setView([defaultLat, defaultLng], defaultZoom);

// Add OpenStreetMap tile layer
L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
  maxZoom: 20,
  attribution: '© OpenStreetMap, © CartoDB'
}).addTo(map);

// Custom icons for markers
const blueIcon = L.icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const redIcon = L.icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const vehicleIcon = L.icon({
   iconUrl: '../static/images/car.png',
  iconSize: [64, 64],
  iconAnchor: [32, 64],    // bottom center of icon
  popupAnchor: [0, -64]    // popup appears above the icon
});



// Store markers globally so they can be updated later
let userMarker = null;
let searchMarker = null;
let vehicleMarker = null;

// Try to get user's location and recenter
if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(
    (position) => {
      const lat = position.coords.latitude;
      const lng = position.coords.longitude;
      map.setView([lat, lng], 15);

      // Blue user marker with custom icon
      userMarker = L.marker([lat, lng], {icon: blueIcon}).addTo(map)
        .bindPopup("You are here")
        .openPopup();

      // Add vehicle marker at user location
      vehicleMarker = L.marker([lat, lng], {icon: vehicleIcon}).addTo(map);

    },
    (error) => {
      console.warn(`Geolocation failed: ${error.message}`);
      // fallback stays at default
    }
  );
} else {
  console.warn("Geolocation not supported by this browser.");
}

// Search functionality with OpenStreetMap Nominatim API
let searchTimeout;

document.getElementById('searchBox').addEventListener('input', function(e) {
  const query = e.target.value.trim();

  if (searchTimeout) clearTimeout(searchTimeout);

  if (query.length < 3) return; // wait for 3+ chars

  searchTimeout = setTimeout(() => {
    fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=5`)
      .then(res => res.json())
      .then(results => {
        if (results && results.length > 0) {
          const place = results[0];
          const lat = place.lat;
          const lon = place.lon;

          map.setView([lat, lon], 15);

          // Red search marker with custom icon
          if (searchMarker) {
            searchMarker.setLatLng([lat, lon]);
            searchMarker.bindPopup(place.display_name).openPopup();
          } else {
            searchMarker = L.marker([lat, lon], {icon: redIcon}).addTo(map);
            searchMarker.bindPopup(place.display_name).openPopup();
          }
        }
      })
      .catch(err => {
        console.error('Geocoding error:', err);
      });
  }, 500);
});

// Function to move vehicle marker along a route (call this with updated coords)
function moveVehicle(newLat, newLng) {
  if (vehicleMarker) {
    vehicleMarker.setLatLng([newLat, newLng]);
  }
}
