// ========== WIND ANIMATION ==========
const windCanvas = document.getElementById('windCanvas');
const windCtx = windCanvas.getContext('2d');
let windAnimationFrame = null;

function resizeWindCanvas() {
    windCanvas.width = window.innerWidth;
    windCanvas.height = window.innerHeight - 210;
}

function startWindAnimation() {
    if (windParticles.length === 0) {
        for (let i = 0; i < 1000; i++) {
            windParticles.push(new WindParticle());
        }
    }
    if (!windAnimationFrame) {
        animateWind();
    }
}

function stopWindAnimation() {
    if (windAnimationFrame) {
        cancelAnimationFrame(windAnimationFrame);
        windAnimationFrame = null;
    }
    windCtx.clearRect(0, 0, windCanvas.width, windCanvas.height);
}

function animateWind() {
    windCtx.clearRect(0, 0, windCanvas.width, windCanvas.height);

    windParticles.forEach(p => {
        p.update();
        p.draw();
    });

    windAnimationFrame = requestAnimationFrame(animateWind);
}

class WindParticle {
    constructor() {
        this.reset();
    }

    reset() {
        this.x = Math.random() * windCanvas.width;
        this.y = Math.random() * windCanvas.height;
        this.speedX = 2 * (Math.random() - 0.5);
        this.speedY = 2 * (Math.random() - 0.5);
        this.life = Math.random() * 100 + 50;
        this.maxLife = this.life;
    }

    update() {
        this.x += this.speedX;
        this.y += this.speedY;
        this.life--;

        if (this.life <= 0 || this.x < 0 || this.x > windCanvas.width || this.y < 0 || this.y > windCanvas.height) {
            this.reset();
        }
    }

    draw() {
        const alpha = this.life / this.maxLife;
        windCtx.fillStyle = `rgba(96, 165, 250, ${0.5 * alpha})`;
        windCtx.fillRect(this.x, this.y, 2, 2);
    }
}

window.addEventListener('resize', resizeWindCanvas);
resizeWindCanvas();
