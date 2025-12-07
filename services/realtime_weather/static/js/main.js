// ========== CONFIG ==========
const REALTIME_INTERVAL = 5000; // 5 giây

// ========== STATE ==========
let activeLayers = {
    pressure: true,
    wind: false,
    temp: false,
    thunder: false,    // ← THAY clouds → thunder
    satellite: false
};

let currentForecastIndex = 0;
let isPlaying = false;
let playInterval = null;
let forecastData = null;

// ========== MAP SETUP ==========
const map = L.map('map', {
    center: [12.0, 112.0],
    zoom: 6,
    minZoom: 5,
    maxZoom: 10,
    zoomControl: true,
    attributionControl: false,
    maxBounds: [[0, 95], [30, 125]]
});

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19
}).addTo(map);

// Viền Biển Đông
const bounds = [[3, 100], [26, 100], [26, 121], [3, 121], [3, 100]];
L.polyline(bounds, {
    color: '#60a5fa',
    weight: 2,
    opacity: 0.5,
    dashArray: '10, 5'
}).addTo(map);


async function getLatestGrib() {
    const res = await fetch("/latest-grib");
    const data = await res.json();
    return data.file;
}



let pressureOverlay = null;
let stormMarker = null;
let windParticles = [];
