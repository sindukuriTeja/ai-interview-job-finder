(function() {
    const canvas = document.getElementById('bgParticleCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let particles = [];
    let geometricShapes = [];
    let shootingStars = [];
    let mouse = { x: null, y: null, radius: 200 };
    let animationId;
    let frame = 0;

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    resize();
    window.addEventListener('resize', () => { resize(); init(); });

    document.addEventListener('mousemove', function(e) {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });

    document.addEventListener('mouseleave', function() {
        mouse.x = null;
        mouse.y = null;
    });

    // ========== PARTICLE CLASS — Multi-layer depth ==========
    class Particle {
        constructor(layer) {
            this.layer = layer || Math.floor(Math.random() * 3);
            this.reset();
        }

        reset() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            const layerScale = [0.3, 0.6, 1.0][this.layer];
            this.size = (Math.random() * 2.5 + 0.5) * layerScale;
            this.baseSpeedX = (Math.random() - 0.5) * 0.4 * layerScale;
            this.baseSpeedY = (Math.random() - 0.5) * 0.4 * layerScale;
            this.speedX = this.baseSpeedX;
            this.speedY = this.baseSpeedY;
            this.opacity = (Math.random() * 0.5 + 0.1) * layerScale;
            this.maxOpacity = this.opacity;
            this.pulseSpeed = Math.random() * 0.02 + 0.005;
            this.pulsePhase = Math.random() * Math.PI * 2;

            const colors = [
                '34, 211, 238',   // cyan
                '168, 85, 247',   // purple
                '99, 102, 241',   // indigo
                '34, 197, 94',    // green
                '251, 191, 36'    // amber
            ];
            this.color = colors[Math.floor(Math.random() * colors.length)];
        }

        update() {
            // Pulsing opacity
            this.opacity = this.maxOpacity * (0.6 + 0.4 * Math.sin(frame * this.pulseSpeed + this.pulsePhase));

            this.x += this.speedX;
            this.y += this.speedY;

            // Mouse interaction — stronger for front-layer particles
            if (mouse.x !== null) {
                const dx = mouse.x - this.x;
                const dy = mouse.y - this.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const interactRadius = mouse.radius * (1 + this.layer * 0.3);

                if (dist < interactRadius) {
                    const force = (interactRadius - dist) / interactRadius;
                    const angle = Math.atan2(dy, dx);
                    const pushForce = force * 0.8 * (this.layer + 1) * 0.4;
                    this.speedX -= Math.cos(angle) * pushForce;
                    this.speedY -= Math.sin(angle) * pushForce;
                }
            }

            // Damping
            this.speedX += (this.baseSpeedX - this.speedX) * 0.02;
            this.speedY += (this.baseSpeedY - this.speedY) * 0.02;

            // Wrap around
            if (this.x < -50) this.x = canvas.width + 50;
            if (this.x > canvas.width + 50) this.x = -50;
            if (this.y < -50) this.y = canvas.height + 50;
            if (this.y > canvas.height + 50) this.y = -50;
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${this.color}, ${this.opacity})`;
            ctx.fill();

            // Glow effect for front-layer particles
            if (this.layer === 2 && this.size > 1.5) {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size * 3, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(${this.color}, ${this.opacity * 0.1})`;
                ctx.fill();
            }
        }
    }

    // ========== GEOMETRIC SHAPES — Floating 3D wireframes ==========
    class GeometricShape {
        constructor() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.size = Math.random() * 40 + 20;
            this.rotation = Math.random() * Math.PI * 2;
            this.rotationSpeed = (Math.random() - 0.5) * 0.005;
            this.speedX = (Math.random() - 0.5) * 0.15;
            this.speedY = (Math.random() - 0.5) * 0.15;
            this.opacity = Math.random() * 0.06 + 0.02;
            this.sides = Math.floor(Math.random() * 4) + 3; // 3 to 6 sides
            this.color = Math.random() > 0.5 ? '34, 211, 238' : '168, 85, 247';
            this.floatPhase = Math.random() * Math.PI * 2;
            this.floatAmplitude = Math.random() * 20 + 10;
        }

        update() {
            this.rotation += this.rotationSpeed;
            this.x += this.speedX;
            this.y += this.speedY + Math.sin(frame * 0.005 + this.floatPhase) * 0.2;

            if (this.x < -100) this.x = canvas.width + 100;
            if (this.x > canvas.width + 100) this.x = -100;
            if (this.y < -100) this.y = canvas.height + 100;
            if (this.y > canvas.height + 100) this.y = -100;
        }

        draw() {
            ctx.save();
            ctx.translate(this.x, this.y);
            ctx.rotate(this.rotation);
            ctx.beginPath();

            for (let i = 0; i <= this.sides; i++) {
                const angle = (i / this.sides) * Math.PI * 2;
                const px = Math.cos(angle) * this.size;
                const py = Math.sin(angle) * this.size;
                if (i === 0) ctx.moveTo(px, py);
                else ctx.lineTo(px, py);
            }

            ctx.closePath();
            ctx.strokeStyle = `rgba(${this.color}, ${this.opacity})`;
            ctx.lineWidth = 1;
            ctx.stroke();

            // Inner wireframe
            ctx.beginPath();
            for (let i = 0; i <= this.sides; i++) {
                const angle = (i / this.sides) * Math.PI * 2 + this.rotation * 0.5;
                const px = Math.cos(angle) * this.size * 0.5;
                const py = Math.sin(angle) * this.size * 0.5;
                if (i === 0) ctx.moveTo(px, py);
                else ctx.lineTo(px, py);
            }
            ctx.closePath();
            ctx.strokeStyle = `rgba(${this.color}, ${this.opacity * 0.5})`;
            ctx.stroke();

            ctx.restore();
        }
    }

    // ========== SHOOTING STARS ==========
    class ShootingStar {
        constructor() {
            this.reset();
        }

        reset() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height * 0.5;
            this.length = Math.random() * 80 + 40;
            this.speed = Math.random() * 8 + 4;
            this.angle = Math.PI / 4 + (Math.random() - 0.5) * 0.3;
            this.opacity = 0;
            this.fadeIn = true;
            this.life = 0;
            this.maxLife = Math.random() * 60 + 30;
            this.active = false;
            this.color = Math.random() > 0.5 ? '34, 211, 238' : '168, 85, 247';
        }

        update() {
            if (!this.active) {
                if (Math.random() < 0.002) this.active = true;
                return;
            }

            this.life++;
            this.x += Math.cos(this.angle) * this.speed;
            this.y += Math.sin(this.angle) * this.speed;

            if (this.fadeIn && this.opacity < 0.8) {
                this.opacity += 0.05;
            }

            if (this.life > this.maxLife * 0.6) {
                this.opacity -= 0.03;
            }

            if (this.opacity <= 0 || this.life > this.maxLife) {
                this.reset();
            }
        }

        draw() {
            if (!this.active || this.opacity <= 0) return;

            const tailX = this.x - Math.cos(this.angle) * this.length;
            const tailY = this.y - Math.sin(this.angle) * this.length;

            const gradient = ctx.createLinearGradient(tailX, tailY, this.x, this.y);
            gradient.addColorStop(0, `rgba(${this.color}, 0)`);
            gradient.addColorStop(1, `rgba(${this.color}, ${this.opacity})`);

            ctx.beginPath();
            ctx.moveTo(tailX, tailY);
            ctx.lineTo(this.x, this.y);
            ctx.strokeStyle = gradient;
            ctx.lineWidth = 2;
            ctx.stroke();

            // Head glow
            ctx.beginPath();
            ctx.arc(this.x, this.y, 3, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${this.color}, ${this.opacity})`;
            ctx.fill();
        }
    }

    // ========== CONNECTIONS ==========
    function drawConnections() {
        const frontParticles = particles.filter(p => p.layer === 2);
        const connectionDist = 150;

        for (let i = 0; i < frontParticles.length; i++) {
            for (let j = i + 1; j < frontParticles.length; j++) {
                const dx = frontParticles[i].x - frontParticles[j].x;
                const dy = frontParticles[i].y - frontParticles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < connectionDist) {
                    const opacity = (1 - dist / connectionDist) * 0.12;
                    ctx.beginPath();
                    ctx.moveTo(frontParticles[i].x, frontParticles[i].y);
                    ctx.lineTo(frontParticles[j].x, frontParticles[j].y);
                    ctx.strokeStyle = `rgba(34, 211, 238, ${opacity})`;
                    ctx.lineWidth = 0.6;
                    ctx.stroke();
                }
            }

            // Mouse connections
            if (mouse.x !== null) {
                const dx = mouse.x - frontParticles[i].x;
                const dy = mouse.y - frontParticles[i].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 180) {
                    const opacity = (1 - dist / 180) * 0.2;
                    ctx.beginPath();
                    ctx.moveTo(frontParticles[i].x, frontParticles[i].y);
                    ctx.lineTo(mouse.x, mouse.y);
                    ctx.strokeStyle = `rgba(168, 85, 247, ${opacity})`;
                    ctx.lineWidth = 0.8;
                    ctx.stroke();
                }
            }
        }
    }

    // ========== INIT ==========
    function init() {
        const area = canvas.width * canvas.height;
        const particleCount = Math.min(120, Math.floor(area / 12000));
        const shapeCount = Math.min(8, Math.floor(area / 200000));
        const starCount = 5;

        particles = [];
        geometricShapes = [];
        shootingStars = [];

        // Layer distribution: 40% back, 30% mid, 30% front
        for (let i = 0; i < particleCount; i++) {
            const rand = Math.random();
            const layer = rand < 0.4 ? 0 : rand < 0.7 ? 1 : 2;
            particles.push(new Particle(layer));
        }

        for (let i = 0; i < shapeCount; i++) {
            geometricShapes.push(new GeometricShape());
        }

        for (let i = 0; i < starCount; i++) {
            shootingStars.push(new ShootingStar());
        }
    }

    // ========== ANIMATE ==========
    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        frame++;

        // Draw back-layer particles first (depth ordering)
        particles.filter(p => p.layer === 0).forEach(p => { p.update(); p.draw(); });

        // Geometric shapes (mid-ground)
        geometricShapes.forEach(s => { s.update(); s.draw(); });

        // Mid-layer particles
        particles.filter(p => p.layer === 1).forEach(p => { p.update(); p.draw(); });

        // Shooting stars
        shootingStars.forEach(s => { s.update(); s.draw(); });

        // Front-layer particles + connections
        particles.filter(p => p.layer === 2).forEach(p => { p.update(); p.draw(); });
        drawConnections();

        animationId = requestAnimationFrame(animate);
    }

    init();
    animate();
})();
