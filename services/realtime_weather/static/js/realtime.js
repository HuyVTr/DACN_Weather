const REALTIME_RT_INTERVAL = 5000;

// --- Initial Data Load ---
async function initialLoad() {
    try {
        console.log('🚀 [INIT] Bắt đầu load dữ liệu ban đầu...');
        
        // 1. Load status
        const statusRes = await fetch('/status');
        if (statusRes.ok) {
            const status = await statusRes.json();
            console.log('📊 [INIT] Status:', status);
            updateStatus(status);
        } else {
            console.warn('⚠️ [INIT] Không thể load status:', statusRes.status);
        }

        // 2. Load dữ liệu forecast
        console.log('📥 [INIT] Đang load forecast data...');
        await fetchAndRenderForecast();

        // 3. ✅ TỰ ĐỘNG LOAD LAYER ÁP SUẤT
        console.log('🎨 [INIT] Kiểm tra active layers:', activeLayers);
        
        if (typeof loadAndRenderLayer === 'function') {
            console.log('✅ [INIT] Function loadAndRenderLayer tồn tại!');
            
            const activeLayer = Object.keys(activeLayers).find(key => activeLayers[key]);
            console.log('🔍 [INIT] Active layer hiện tại:', activeLayer);
            
            if (activeLayer) {
                console.log(`🎨 [INIT] Đang load layer: ${activeLayer}`);
                await loadAndRenderLayer(activeLayer);
            } else {
                console.warn('⚠️ [INIT] Không có layer nào được active!');
            }
        } else {
            console.error('❌ [INIT] Function loadAndRenderLayer KHÔNG TỒN TẠI!');
            console.log('🔍 [INIT] Các functions có sẵn:', Object.keys(window).filter(k => typeof window[k] === 'function').slice(0, 20));
        }

        // 4. Ẩn loading overlay
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
            console.log('✅ [INIT] Đã ẩn loading overlay');
        }

        console.log('✅ [INIT] Hoàn tất load dữ liệu ban đầu');

    } catch (error) {
        console.error('❌ [INIT] Lỗi:', error);
        
        // Vẫn ẩn loading overlay
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
    }
}

// --- WebSocket Connection ---
function connectWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log('🔌 WebSocket connected!');
        const badge = document.querySelector('.realtime-badge');
        if (badge) {
            badge.style.borderColor = '#10b981';
            const dot = badge.querySelector('.realtime-dot');
            if (dot) dot.style.background = '#10b981';
        }
    };

    socket.onmessage = (event) => {
        console.log('📡 Message from server:', event.data);
        const status = JSON.parse(event.data);
        
        updateStatus(status);
        fetchAndRenderForecast(); // Tải lại dữ liệu mới nhất khi có tín hiệu từ server
    };

    socket.onclose = (event) => {
        console.warn('🔌 WebSocket disconnected. Reconnecting in 5s...', event);
        const badge = document.querySelector('.realtime-badge');
        if (badge) {
            badge.style.borderColor = '#facc15';
            const dot = badge.querySelector('.realtime-dot');
            if (dot) dot.style.background = '#facc15';
        }
        setTimeout(connectWebSocket, 5000);
    };

    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        const badge = document.querySelector('.realtime-badge');
        if (badge) {
            badge.style.borderColor = '#ef4444';
            const dot = badge.querySelector('.realtime-dot');
            if (dot) dot.style.background = '#ef4444';
        }
        socket.close();
    };
}

function updateStatus(status) {
    // Xử lý storm info cũ
    if (status.data && Object.keys(status.data).length > 0 && status.data.lat && status.data.lon) {
        showStormAlert(status.data);
        updateStormMarker(status.data.lat, status.data.lon, status.data.name || 'Storm');
    } else {
        hideStormAlert();
        if (stormMarker) {
            map.removeLayer(stormMarker);
            stormMarker = null;
        }
    }
   
    // ← NEW: Xử lý alerts từ bot
    if (status.data && status.data.alerts) {
        handleAlerts(status.data);
    }
}

// ========== STORM ALERT (Sidebar Version) ==========
function showStormAlert(data) {
    const alertHtml = `
        <div class="storm-alert-box">
            <h4><i class="fas fa-exclamation-triangle"></i> CẢNH BÁO KHẨN CẤP</h4>
            <p style="font-size: 0.8rem; line-height: 1.5; color: #fca5a5;">
                ${data.name || 'Bão'} đang hoạt động tại vị trí ${data.lat?.toFixed(2)}°N, ${data.lon?.toFixed(2)}°E
            </p>
        </div>
    `;
    
    const container = document.getElementById('stormAlertContainer');
    if (container) {
        container.innerHTML = alertHtml;
    }

    // Show storm info card
    const infoCard = document.getElementById('stormInfoCard');
    if (infoCard) {
        infoCard.style.display = 'block';
        
        const nameEl = document.getElementById('stormName');
        if (nameEl) nameEl.textContent = data.name || '--';
        
        const classEl = document.getElementById('stormClass');
        if (classEl) classEl.textContent = data.classification || 'Cấp độ không xác định';
        
        const posEl = document.getElementById('stormPos');
        if (posEl) posEl.textContent = `${data.lat?.toFixed(2)}°N, ${data.lon?.toFixed(2)}°E`;
        
        const windEl = document.getElementById('stormWind');
        if (windEl) windEl.textContent = `${data.max_wind_speed_kmh?.toFixed(0) || '--'} km/h`;
        
        const pressureEl = document.getElementById('stormPressure');
        if (pressureEl) pressureEl.textContent = `${data.pressure?.toFixed(0) || '--'} hPa`;
        
        const dirEl = document.getElementById('stormDirection');
        if (dirEl) dirEl.textContent = data.direction || '--';
    }
}

function hideStormAlert() {
    const container = document.getElementById('stormAlertContainer');
    if (container) {
        container.innerHTML = '';
    }
    
    const infoCard = document.getElementById('stormInfoCard');
    if (infoCard) {
        infoCard.style.display = 'none';
    }
}

// ========== STORM MARKER ==========
function updateStormMarker(lat, lon, name) {
    if (stormMarker) {
        stormMarker.setLatLng([lat, lon]);
    } else {
        const stormIcon = L.divIcon({
            className: 'storm-marker',
            html: '<div style="background: rgba(239, 68, 68, 0.9); border: 3px solid #fff; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 20px; box-shadow: 0 0 20px rgba(239, 68, 68, 0.8); animation: pulse 1.5s ease-in-out infinite;">🌀</div>',
            iconSize: [40, 40]
        });

        stormMarker = L.marker([lat, lon], { icon: stormIcon })
            .addTo(map)
            .bindPopup(`<strong>${name}</strong><br/>Lat: ${lat.toFixed(2)}<br/>Lon: ${lon.toFixed(2)}`);
    }
    map.panTo([lat, lon], { animate: true });
}

// ========== WEATHER INFO (Không còn cần thiết cho sidebar UI) ==========
function updateWeatherInfo(data) {
    // Sidebar UI không có weather cards riêng
    // Dữ liệu hiển thị trong storm info card
    console.log('Weather data updated:', data);
}

// ========== INIT ==========
console.log('🌀 Storm Tracker Pro - SIDEBAR UI (REAL-TIME)');
console.log('📡 Data source: NOAA GFS');
console.log('🌊 Region: South China Sea (Biển Đông)');

initialLoad();
connectWebSocket();
updateDateDisplay();