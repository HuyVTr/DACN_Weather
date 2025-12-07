/* ========================================
   WINDY-STYLE COLOR SCALES (Smooth)
   ======================================== */

// Helper: interpolate 2 colors
function interpolateColor(color1, color2, factor) {
    const c1 = hexToRgb(color1);
    const c2 = hexToRgb(color2);

    const r = Math.round(c1.r + (c2.r - c1.r) * factor);
    const g = Math.round(c1.g + (c2.g - c1.g) * factor);
    const b = Math.round(c1.b + (c2.b - c1.b) * factor);

    return `rgb(${r}, ${g}, ${b})`;
}

function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result
        ? {
              r: parseInt(result[1], 16),
              g: parseInt(result[2], 16),
              b: parseInt(result[3], 16)
          }
        : null;
}

function getColorFromScale(value, min, max, colorStops) {
    if (value <= min) return colorStops[0].color;
    if (value >= max) return colorStops[colorStops.length - 1].color;

    const normalizedValue = (value - min) / (max - min);

    for (let i = 0; i < colorStops.length - 1; i++) {
        const stop1 = colorStops[i];
        const stop2 = colorStops[i + 1];

        if (normalizedValue >= stop1.pos && normalizedValue <= stop2.pos) {
            const localFactor =
                (normalizedValue - stop1.pos) / (stop2.pos - stop1.pos);
            return interpolateColor(stop1.color, stop2.color, localFactor);
        }
    }
    return colorStops[0].color;
}

/* ========================================
   PRESSURE COLOR
   ======================================== */
function pressureColor(p) {
    const colorStops = [
        { pos: 0.0, color: '#8B0000' },
        { pos: 0.15, color: '#FF0000' },
        { pos: 0.25, color: '#FF6600' },
        { pos: 0.35, color: '#FFA500' },
        { pos: 0.45, color: '#FFD700' },
        { pos: 0.55, color: '#FFFF00' },
        { pos: 0.65, color: '#90EE90' },
        { pos: 0.75, color: '#00CED1' },
        { pos: 0.85, color: '#4169E1' },
        { pos: 1.0, color: '#8A2BE2' }
    ];

    return getColorFromScale(p, 940, 1040, colorStops);
}

/* ========================================
   WIND COLOR
   ======================================== */
function windColor(ws) {
    const colorStops = [
        { pos: 0.0, color: '#E0F7FA' },
        { pos: 0.1, color: '#80DEEA' },
        { pos: 0.2, color: '#26C6DA' },
        { pos: 0.3, color: '#00BCD4' },
        { pos: 0.4, color: '#FFEB3B' },
        { pos: 0.5, color: '#FFC107' },
        { pos: 0.6, color: '#FF9800' },
        { pos: 0.7, color: '#FF5722' },
        { pos: 0.8, color: '#F44336' },
        { pos: 0.9, color: '#E91E63' },
        { pos: 1.0, color: '#9C27B0' }
    ];

    return getColorFromScale(ws, 0, 50, colorStops);
}

/* ========================================
   TEMPERATURE COLOR
   ======================================== */
function tempColor(c) {
    const colorStops = [
        { pos: 0.0, color: '#1A237E' },
        { pos: 0.15, color: '#0D47A1' },
        { pos: 0.3, color: '#01579B' },
        { pos: 0.4, color: '#00BCD4' },
        { pos: 0.5, color: '#4CAF50' },
        { pos: 0.6, color: '#FFEB3B' },
        { pos: 0.7, color: '#FFC107' },
        { pos: 0.8, color: '#FF9800' },
        { pos: 0.9, color: '#FF5722' },
        { pos: 1.0, color: '#D32F2F' }
    ];

    return getColorFromScale(c, -10, 45, colorStops);
}

/* ========================================
   CLOUD COVER COLOR
   ======================================== */
function cloudColor(percent) {
    const colorStops = [
        { pos: 0.0, color: 'rgba(255,255,255,0)' },
        { pos: 0.25, color: 'rgba(200,200,200,0.3)' },
        { pos: 0.5, color: 'rgba(150,150,150,0.5)' },
        { pos: 0.75, color: 'rgba(100,100,100,0.7)' },
        { pos: 1.0, color: 'rgba(50,50,50,0.85)' }
    ];

    return getColorFromScale(percent, 0, 100, colorStops);
}

/* ========================================
   LEGEND HANDLER
   ======================================== */
function getColorScaleLegend(type) {
    const legends = {
        pressure: [
            { value: "< 950 hPa", color: "#FF0000", label: "Super Typhoon" },
            { value: "950-970", color: "#FF6600", label: "Typhoon" },
            { value: "970-990", color: "#FFA500", label: "Tropical Storm" },
            { value: "990-1010", color: "#FFFF00", label: "Normal" },
            { value: "1010-1030", color: "#00CED1", label: "High" },
            { value: "> 1030 hPa", color: "#8A2BE2", label: "Very High" }
        ],

        wind: [
            { value: "< 5 m/s", color: "#80DEEA", label: "Calm" },
            { value: "5-15 m/s", color: "#00BCD4", label: "Light" },
            { value: "15-25 m/s", color: "#FFEB3B", label: "Moderate" },
            { value: "25-35 m/s", color: "#FF9800", label: "Strong" },
            { value: "35-45 m/s", color: "#F44336", label: "Storm" },
            { value: "> 45 m/s", color: "#9C27B0", label: "Hurricane" }
        ],

        temp: [
            { value: "< 0°C", color: "#0D47A1", label: "Freezing" },
            { value: "0-15°C", color: "#00BCD4", label: "Cold" },
            { value: "15-25°C", color: "#4CAF50", label: "Mild" },
            { value: "25-35°C", color: "#FFC107", label: "Warm" },
            { value: "35-40°C", color: "#FF5722", label: "Hot" },
            { value: "> 40°C", color: "#D32F2F", label: "Extreme" }
        ],

        clouds: [
            { value: "0-25%", color: "rgba(200,200,200,0.3)", label: "Clear" },
            { value: "25-50%", color: "rgba(150,150,150,0.5)", label: "Partly Cloudy" },
            { value: "50-75%", color: "rgba(100,100,100,0.7)", label: "Cloudy" },
            { value: "75-100%", color: "rgba(50,50,50,0.85)", label: "Overcast" }
        ],

        /* ========================================
           ⚡ NEW — THUNDER LEGEND
           ======================================== */
        thunder: [
            { value: "< 20%", color: "rgba(255,255,100,0.4)", label: "Thấp" },
            { value: "20-35%", color: "rgba(255,200,0,0.6)", label: "Trung bình" },
            { value: "35-50%", color: "rgba(255,128,0,0.7)", label: "Cao" },
            { value: "50-70%", color: "rgba(255,64,0,0.8)", label: "Rất cao" },
            { value: "70-85%", color: "rgba(255,0,0,0.9)", label: "Nguy hiểm" },
            { value: "> 85%", color: "rgba(200,0,128,0.95)", label: "Cực kỳ nguy hiểm" }
        ],

        satellite: [
            { value: "Live", color: "#FFFFFF", label: "Real-time Imagery" }
        ]
    };

    return legends[type] || [];
}

/* ========================================
   EXPORT for Node.js (optional)
   ======================================== */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        pressureColor,
        windColor,
        tempColor,
        cloudColor,
        getColorScaleLegend
    };
}
