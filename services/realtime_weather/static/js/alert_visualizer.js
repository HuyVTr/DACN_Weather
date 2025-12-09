// File: static/js/alert_visualizer.js
// HIỂN THỊ CẢNH BÁO BÃO & GIÔNG TỰ ĐỘNG

// ========== STATE ==========
let alertMarkers = [];
let alertCircles = [];

// ========== NHẬN ALERTS TỪ WEBSOCKET ==========
function handleAlerts(alertsData) {
    console.log('🚨 Received alerts:', alertsData);
    
    // Xóa alerts cũ
    clearAlerts();
    
    if (!alertsData || !alertsData.alerts || alertsData.alerts.length === 0) {
        console.log('✅ Không có cảnh báo');
        return;
    }
    
    // Hiển thị từng alert
    alertsData.alerts.forEach(alert => {
        addAlertMarker(alert);
    });
    
    // Hiển thị thông báo tổng quan
    showAlertSummary(alertsData);
}

// ========== HIỂN THỊ CHẤM ĐỎ CẢNH BÁO ==========
function addAlertMarker(alert) {
    const lat = alert.lat;
    const lon = alert.lon;
    
    // 1. Tạo vòng tròn pulse (animation)
    const circle = L.circle([lat, lon], {
        color: alert.color,
        fillColor: alert.color,
        fillOpacity: 0.3,
        radius: 50000,  // 50km radius
        className: 'alert-circle-pulse'
    }).addTo(map);
    
    alertCircles.push(circle);
    
    // 2. Tạo marker icon động
    const iconHtml = `
        <div class="alert-marker ${alert.severity.toLowerCase()}" 
             style="background: ${alert.color};">
            <div class="alert-icon">${alert.icon}</div>
            <div class="alert-pulse"></div>
        </div>
    `;
    
    const alertIcon = L.divIcon({
        className: 'custom-alert-icon',
        html: iconHtml,
        iconSize: [40, 40],
        iconAnchor: [20, 20]
    });
    
    // 3. Tạo marker
    const marker = L.marker([lat, lon], { icon: alertIcon })
        .addTo(map)
        .bindPopup(createAlertPopup(alert), {
            maxWidth: 300,
            className: 'alert-popup'
        });
    
    alertMarkers.push(marker);
    
    // 4. Tự động mở popup cho alerts nghiêm trọng
    if (alert.severity === 'EXTREME' || alert.severity === 'HIGH') {
        marker.openPopup();
        
        // Pan map đến vị trí nguy hiểm
        map.panTo([lat, lon], { animate: true, duration: 1 });
    }
    
    console.log(`📍 Added ${alert.type_vi} alert at ${lat}, ${lon}`);
}

// ========== TẠO NỘI DUNG POPUP ==========
function createAlertPopup(alert) {
    const severityColors = {
        'EXTREME': '#8B0000',
        'HIGH': '#FF0000',
        'MEDIUM': '#FF6600',
        'LOW': '#FFA500'
    };
    
    const severityLabels = {
        'EXTREME': 'CỰC KỲ NGUY HIỂM',
        'HIGH': 'NGUY HIỂM CAO',
        'MEDIUM': 'NGUY HIỂM TRUNG BÌNH',
        'LOW': 'CẢNH BÁO'
    };
    
    return `
        <div class="alert-popup-content">
            <div class="alert-header" style="background: ${severityColors[alert.severity]};">
                <span class="alert-icon-big">${alert.icon}</span>
                <div class="alert-title">
                    <h3>${alert.type_vi}</h3>
                    <span class="severity-badge">${severityLabels[alert.severity]}</span>
                </div>
            </div>
            
            <div class="alert-body">
                <div class="alert-info-row">
                    <span class="label">📍 Vị trí:</span>
                    <span class="value">${alert.lat.toFixed(2)}°N, ${alert.lon.toFixed(2)}°E</span>
                </div>
                
                ${alert.pressure ? `
                <div class="alert-info-row">
                    <span class="label">🌡️ Áp suất:</span>
                    <span class="value danger">${alert.pressure.toFixed(1)} hPa</span>
                </div>
                ` : ''}
                
                ${alert.wind_speed_kmh ? `
                <div class="alert-info-row">
                    <span class="label">💨 Gió:</span>
                    <span class="value danger">${alert.wind_speed_kmh.toFixed(1)} km/h</span>
                </div>
                ` : ''}
                
                ${alert.temp ? `
                <div class="alert-info-row">
                    <span class="label">🌡️ Nhiệt độ:</span>
                    <span class="value">${alert.temp.toFixed(1)}°C</span>
                </div>
                ` : ''}
                
                <div class="alert-details">
                    <strong>Chi tiết:</strong> ${alert.details}
                </div>
                
                <div class="alert-time">
                    ⏰ Phát hiện lúc: ${new Date().toLocaleTimeString('vi-VN')}
                </div>
            </div>
        </div>
    `;
}

// ========== HIỂN THỊ TÓNG QUAN CẢNH BÁO ==========
function showAlertSummary(alertsData) {
    const summaryHtml = `
        <div class="alert-summary-box">
            <h4>
                <i class="fas fa-exclamation-triangle"></i>
                ${alertsData.count} CẢNH BÁO ĐANG HOẠT ĐỘNG
            </h4>
            <p>${alertsData.summary}</p>
            <small>Cập nhật: ${new Date(alertsData.timestamp).toLocaleTimeString('vi-VN')}</small>
        </div>
    `;
    
    // Hiển thị trong sidebar
    const container = document.getElementById('stormAlertContainer');
    if (container) {
        container.innerHTML = summaryHtml;
    }
}

// ========== XÓA TẤT CẢ ALERTS ==========
function clearAlerts() {
    // Xóa markers
    alertMarkers.forEach(marker => {
        map.removeLayer(marker);
    });
    alertMarkers = [];
    
    // Xóa circles
    alertCircles.forEach(circle => {
        map.removeLayer(circle);
    });
    alertCircles = [];
    
    console.log('🗑️ Cleared all alerts');
}

// ========== CSS CHO ALERTS (Thêm vào index.html) ==========
const alertStyles = `
<style>
/* Alert Marker Animation */
.alert-marker {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    border: 3px solid white;
    box-shadow: 0 0 20px rgba(0,0,0,0.5);
}

.alert-marker.extreme {
    animation: extremePulse 1s ease-in-out infinite;
}

.alert-marker.high {
    animation: pulse 1.5s ease-in-out infinite;
}

.alert-marker.medium {
    animation: pulse 2s ease-in-out infinite;
}

@keyframes extremePulse {
    0%, 100% { transform: scale(1); box-shadow: 0 0 20px rgba(139,0,0,0.8); }
    50% { transform: scale(1.3); box-shadow: 0 0 40px rgba(139,0,0,1); }
}

@keyframes pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.2); }
}

.alert-icon {
    font-size: 20px;
    z-index: 2;
}

.alert-pulse {
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    background: inherit;
    opacity: 0.5;
    animation: ripple 2s ease-out infinite;
}

@keyframes ripple {
    0% { transform: scale(1); opacity: 0.5; }
    100% { transform: scale(2.5); opacity: 0; }
}

/* Alert Circle Pulse */
.alert-circle-pulse {
    animation: circlePulse 3s ease-in-out infinite;
}

@keyframes circlePulse {
    0%, 100% { opacity: 0.3; }
    50% { opacity: 0.6; }
}

/* Alert Popup */
.alert-popup-content {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.alert-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 15px;
    border-radius: 8px 8px 0 0;
    margin: -10px -10px 10px -10px;
}

.alert-icon-big {
    font-size: 32px;
}

.alert-title h3 {
    margin: 0;
    font-size: 1.1rem;
    color: white;
}

.severity-badge {
    display: inline-block;
    background: rgba(255,255,255,0.3);
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.7rem;
    margin-top: 4px;
    color: white;
    font-weight: 600;
}

.alert-body {
    padding: 10px 0;
}

.alert-info-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid rgba(0,0,0,0.1);
}

.alert-info-row .label {
    font-size: 0.85rem;
    color: #666;
}

.alert-info-row .value {
    font-weight: 600;
    font-size: 0.9rem;
}

.alert-info-row .value.danger {
    color: #FF0000;
}

.alert-details {
    margin-top: 12px;
    padding: 10px;
    background: rgba(255,204,0,0.1);
    border-left: 3px solid #FFCC00;
    font-size: 0.85rem;
}

.alert-time {
    margin-top: 10px;
    font-size: 0.75rem;
    color: #999;
    text-align: right;
}

/* Alert Summary Box (Sidebar) */
.alert-summary-box {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(220, 38, 38, 0.1));
    border: 1px solid #ef4444;
    border-radius: 12px;
    padding: 15px;
    margin-bottom: 20px;
    animation: alertPulse 2s ease-in-out infinite;
}

.alert-summary-box h4 {
    color: #fca5a5;
    font-size: 0.9rem;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.alert-summary-box p {
    font-size: 0.85rem;
    line-height: 1.5;
    color: #fca5a5;
    margin-bottom: 8px;
}

.alert-summary-box small {
    font-size: 0.75rem;
    color: #f87171;
}
</style>
`;

// Export function để dùng ở realtime.js
window.handleAlerts = handleAlerts;
window.clearAlerts = clearAlerts;

console.log('✅ Alert Visualizer loaded');