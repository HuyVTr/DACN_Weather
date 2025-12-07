// ========== TIMELINE ==========
const slider = document.getElementById('timelineSlider');
const dateDisplay = document.getElementById('currentDate');

slider.addEventListener('input', (e) => {
    currentForecastIndex = parseInt(e.target.value);
    updateDateDisplay();
    fetchAndRenderForecast(); // Thay vì chỉ render, hãy fetch dữ liệu mới
});

async function fetchAndRenderForecast() {
    try {
        const hours = currentForecastIndex * 3;
        const res = await fetch(`/forecast?hours=${hours}`);
        if (!res.ok) {
            console.error('Lỗi khi gọi /forecast:', res.status, res.statusText);
            return;
        }
        forecastData = await res.json();
        console.log('fetchAndRenderForecast: hours=', hours, 'forecastData keys=', Object.keys(forecastData || {}));
        renderCurrentForecast(); // Sau khi có dữ liệu mới, render tất cả các layer
    } catch (error) {
        console.error(`Lỗi khi tải dự báo cho giờ thứ ${hours}:`, error);
    }
}

function updateDateDisplay() {
    const hours = currentForecastIndex * 3;
    const days = Math.floor(hours / 24);
    const remainingHours = hours % 24;

    if (days === 0) {
        dateDisplay.textContent = `Hôm nay, ${remainingHours}h`;
    } else {
        dateDisplay.textContent = `+${days} ngày, ${remainingHours}h`;
    }
}

function playTimeline() {
    if (isPlaying) return;
    isPlaying = true;

    playInterval = setInterval(() => {
        currentForecastIndex++;
        if (currentForecastIndex > 56) {
            currentForecastIndex = 0;
        }
        slider.value = currentForecastIndex;
        updateDateDisplay();
        fetchAndRenderForecast();
    }, 1000);
}

function pauseTimeline() {
    isPlaying = false;
    if (playInterval) {
        clearInterval(playInterval);
        playInterval = null;
    }
}

function resetTimeline() {
    pauseTimeline();
    currentForecastIndex = 0;
    slider.value = 0;
    updateDateDisplay();
    fetchAndRenderForecast();
}
