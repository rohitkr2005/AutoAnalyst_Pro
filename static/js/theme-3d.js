/**
 * AutoAnalyst Pro - 3-Mode Theme Manager & Live 3D Background Engine
 * Features:
 *  - 3-Mode Theme: Light, Dark, Device/System (with real-time OS preference change listener)
 *  - High-performance, 60fps 3D Perspective Canvas with:
 *      * 3D data nodes with true (X, Y, Z) perspective projection
 *      * Interactive 3D mouse parallax tilt & rotational orbit
 *      * Floating 3D geometric wireframe polyhedra (data crystals)
 *      * Dynamic depth-attenuated 3D filament connections
 *      * Luminous traveling data pulse packets
 *      * Theme-reactive color palettes (Electric Cyber in Dark, Azure Celestial in Light)
 *      * Battery-efficient pause when tab is inactive
 */

(function () {
  'use strict';

  // =========================================================================
  // 1. THEME MANAGER
  // =========================================================================
  const STORAGE_KEY = 'analytica_theme_pref';

  const ThemeManager = {
    getPreference() {
      return localStorage.getItem(STORAGE_KEY) || 'system';
    },

    resolveEffectiveTheme(pref) {
      if (pref === 'dark') return 'dark';
      if (pref === 'light') return 'light';
      // System default: check OS media query
      const isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      return isDark ? 'dark' : 'light';
    },

    isDark() {
      const current = document.documentElement.getAttribute('data-theme');
      return current !== 'light';
    },

    applyTheme(pref) {
      if (!pref) pref = this.getPreference();
      const effective = this.resolveEffectiveTheme(pref);

      document.documentElement.setAttribute('data-theme', effective);
      document.documentElement.setAttribute('data-theme-pref', pref);

      // Update meta color-scheme
      let metaScheme = document.querySelector('meta[name="color-scheme"]');
      if (metaScheme) {
        metaScheme.content = effective;
      }

      // Update active states on all theme buttons on the page
      document.querySelectorAll('.theme-btn').forEach((btn) => {
        const val = btn.getAttribute('data-theme-val');
        if (val === pref) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });

      // Dispatch custom event for Chart.js and other components to re-theme
      window.dispatchEvent(
        new CustomEvent('analytica-theme-changed', {
          detail: { preference: pref, effectiveTheme: effective }
        })
      );
    },

    setTheme(pref) {
      localStorage.setItem(STORAGE_KEY, pref);
      this.applyTheme(pref);
    },

    init() {
      const initialPref = this.getPreference();
      this.applyTheme(initialPref);

      // Listen for OS system theme changes
      if (window.matchMedia) {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        const listener = () => {
          if (this.getPreference() === 'system') {
            this.applyTheme('system');
          }
        };
        if (mediaQuery.addEventListener) {
          mediaQuery.addEventListener('change', listener);
        } else if (mediaQuery.addListener) {
          mediaQuery.addListener(listener);
        }
      }

      // Sync button states on DOMContentLoaded if buttons were rendered after script
      document.addEventListener('DOMContentLoaded', () => {
        this.applyTheme(this.getPreference());
      });
    }
  };

  // Expose globally
  window.ThemeManager = ThemeManager;
  window.setThemeMode = function (mode) {
    ThemeManager.setTheme(mode);
  };

  // Run immediate theme initialization to prevent flash
  ThemeManager.init();

  // =========================================================================
  // 2. LIVE 3D ANIMATED BACKGROUND ENGINE
  // =========================================================================
  class Live3DBackground {
    constructor(canvasId = 'bg-3d-canvas') {
      this.canvasId = canvasId;
      this.canvas = document.getElementById(canvasId);
      if (!this.canvas) return;

      this.ctx = this.canvas.getContext('2d');
      this.width = window.innerWidth;
      this.height = window.innerHeight;
      this.dpr = Math.min(window.devicePixelRatio || 1, 2);

      // 3D Camera / Perspective Settings
      this.focalLength = 480;
      this.cameraZ = -600;

      // Mouse Parallax & Orbit
      this.mouseX = 0;
      this.mouseY = 0;
      this.targetRotX = 0;
      this.targetRotY = 0;
      this.rotX = 0;
      this.rotY = 0;
      this.autoAngle = 0;

      // 3D Particles & Polyhedra
      this.particles = [];
      this.pulses = [];
      this.polyhedra = [];
      this.numParticles = 75;

      this.isRunning = true;
      this.animFrameId = null;

      this.initCanvas();
      this.initParticles();
      this.initPolyhedra();
      this.initEvents();
      this.start();
    }

    initCanvas() {
      this.width = window.innerWidth;
      this.height = window.innerHeight;
      this.canvas.width = this.width * this.dpr;
      this.canvas.height = this.height * this.dpr;
      this.canvas.style.width = this.width + 'px';
      this.canvas.style.height = this.height + 'px';
      this.ctx.setTransform(1, 0, 0, 1, 0, 0);
      this.ctx.scale(this.dpr, this.dpr);
    }

    initParticles() {
      this.particles = [];
      const boundX = this.width * 0.75;
      const boundY = this.height * 0.75;
      const boundZ = 500;

      for (let i = 0; i < this.numParticles; i++) {
        this.particles.push({
          x: (Math.random() - 0.5) * boundX * 2,
          y: (Math.random() - 0.5) * boundY * 2,
          z: (Math.random() - 0.5) * boundZ * 2,
          vx: (Math.random() - 0.5) * 0.45,
          vy: (Math.random() - 0.5) * 0.45,
          vz: (Math.random() - 0.5) * 0.35,
          radius: 1.8 + Math.random() * 2.2,
          pulse: Math.random() * Math.PI * 2,
          pulseSpeed: 0.02 + Math.random() * 0.03,
          colorType: Math.floor(Math.random() * 3) // 0: primary, 1: cyan, 2: emerald
        });
      }
    }

    initPolyhedra() {
      // Create 2 3D rotating polyhedra (data crystals)
      this.polyhedra = [
        this.createOctahedron(-this.width * 0.35, -this.height * 0.25, 120, 85),
        this.createIcosahedron(this.width * 0.35, this.height * 0.25, -60, 95)
      ];
    }

    createOctahedron(x, y, z, size) {
      const vertices = [
        { x: 0, y: -size, z: 0 },
        { x: size, y: 0, z: 0 },
        { x: 0, y: 0, z: size },
        { x: -size, y: 0, z: 0 },
        { x: 0, y: 0, z: -size },
        { x: 0, y: size, z: 0 }
      ];
      const edges = [
        [0, 1], [0, 2], [0, 3], [0, 4],
        [5, 1], [5, 2], [5, 3], [5, 4],
        [1, 2], [2, 3], [3, 4], [4, 1]
      ];
      return {
        x, y, z,
        size,
        vertices,
        edges,
        rotX: Math.random() * Math.PI,
        rotY: Math.random() * Math.PI,
        rotZ: Math.random() * Math.PI,
        speedX: 0.005,
        speedY: 0.007,
        speedZ: 0.004,
        driftVx: 0.1,
        driftVy: -0.08
      };
    }

    createIcosahedron(x, y, z, size) {
      // Golden ratio phi
      const phi = (1 + Math.sqrt(5)) / 2;
      const s = size / Math.sqrt(1 + phi * phi);
      const sp = s * phi;

      const rawVertices = [
        [-s, sp, 0], [s, sp, 0], [-s, -sp, 0], [s, -sp, 0],
        [0, -s, sp], [0, s, sp], [0, -s, -sp], [0, s, -sp],
        [sp, 0, -s], [sp, 0, s], [-sp, 0, -s], [-sp, 0, s]
      ];

      const vertices = rawVertices.map(v => ({ x: v[0], y: v[1], z: v[2] }));

      // Edges between vertices distance check
      const edges = [];
      const threshold = s * 2 * 1.08;
      for (let i = 0; i < vertices.length; i++) {
        for (let j = i + 1; j < vertices.length; j++) {
          const dx = vertices[i].x - vertices[j].x;
          const dy = vertices[i].y - vertices[j].y;
          const dz = vertices[i].z - vertices[j].z;
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
          if (dist < threshold) {
            edges.push([i, j]);
          }
        }
      }

      return {
        x, y, z,
        size,
        vertices,
        edges,
        rotX: Math.random() * Math.PI,
        rotY: Math.random() * Math.PI,
        rotZ: Math.random() * Math.PI,
        speedX: -0.004,
        speedY: 0.006,
        speedZ: 0.005,
        driftVx: -0.08,
        driftVy: 0.09
      };
    }

    initEvents() {
      // Window resize
      window.addEventListener('resize', () => {
        this.initCanvas();
      });

      // Mouse Parallax & Orbit
      window.addEventListener('mousemove', (e) => {
        const nx = (e.clientX / this.width - 0.5) * 2;
        const ny = (e.clientY / this.height - 0.5) * 2;
        this.targetRotY = nx * 0.45;
        this.targetRotX = -ny * 0.35;
      });

      // Touch interaction
      window.addEventListener('touchmove', (e) => {
        if (e.touches && e.touches[0]) {
          const t = e.touches[0];
          const nx = (t.clientX / this.width - 0.5) * 2;
          const ny = (t.clientY / this.height - 0.5) * 2;
          this.targetRotY = nx * 0.45;
          this.targetRotX = -ny * 0.35;
        }
      }, { passive: true });

      // Tab visibility pause to save CPU
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
          this.stop();
        } else {
          this.start();
        }
      });
    }

    project3D(x, y, z) {
      // Rotate by rotY then rotX
      const radY = this.rotY;
      const radX = this.rotX;

      // Orbit rotation around Y axis
      const cosY = Math.cos(radY);
      const sinY = Math.sin(radY);
      const x1 = x * cosY + z * sinY;
      const z1 = -x * sinY + z * cosY;

      // Orbit rotation around X axis
      const cosX = Math.cos(radX);
      const sinX = Math.sin(radX);
      const y2 = y * cosX - z1 * sinX;
      const z2 = y * sinX + z1 * cosX;

      // Perspective projection
      const distance = z2 - this.cameraZ;
      if (distance <= 10) return null; // Behind camera

      const scale = this.focalLength / distance;
      const screenX = this.width / 2 + x1 * scale;
      const screenY = this.height / 2 + y2 * scale;

      return {
        screenX,
        screenY,
        scale,
        depth: z2
      };
    }

    render() {
      if (!this.isRunning) return;

      const isDark = ThemeManager.isDark();
      const ctx = this.ctx;

      // Smooth damping interpolation for mouse parallax
      this.rotX += (this.targetRotX - this.rotX) * 0.04;
      this.rotY += (this.targetRotY - this.rotY) * 0.04;
      this.autoAngle += 0.002;

      // Clear canvas
      ctx.clearRect(0, 0, this.width, this.height);

      // 1. Draw Subtle Dynamic Radial Ambient Glows
      const cx1 = this.width * 0.2 + Math.sin(this.autoAngle * 0.8) * 80;
      const cy1 = this.height * 0.25 + Math.cos(this.autoAngle * 0.7) * 60;
      const cx2 = this.width * 0.8 + Math.cos(this.autoAngle * 0.6) * 90;
      const cy2 = this.height * 0.75 + Math.sin(this.autoAngle * 0.5) * 70;

      const g1 = ctx.createRadialGradient(cx1, cy1, 10, cx1, cy1, this.width * 0.45);
      if (isDark) {
        g1.addColorStop(0, 'rgba(99, 102, 241, 0.16)');
        g1.addColorStop(0.5, 'rgba(99, 102, 241, 0.05)');
        g1.addColorStop(1, 'transparent');
      } else {
        g1.addColorStop(0, 'rgba(79, 70, 229, 0.08)');
        g1.addColorStop(0.5, 'rgba(79, 70, 229, 0.02)');
        g1.addColorStop(1, 'transparent');
      }
      ctx.fillStyle = g1;
      ctx.fillRect(0, 0, this.width, this.height);

      const g2 = ctx.createRadialGradient(cx2, cy2, 10, cx2, cy2, this.width * 0.42);
      if (isDark) {
        g2.addColorStop(0, 'rgba(6, 182, 212, 0.12)');
        g2.addColorStop(0.5, 'rgba(6, 182, 212, 0.03)');
        g2.addColorStop(1, 'transparent');
      } else {
        g2.addColorStop(0, 'rgba(2, 132, 199, 0.07)');
        g2.addColorStop(0.5, 'rgba(2, 132, 199, 0.015)');
        g2.addColorStop(1, 'transparent');
      }
      ctx.fillStyle = g2;
      ctx.fillRect(0, 0, this.width, this.height);

      // 2. Update & Project Particles
      const boundX = this.width * 0.75;
      const boundY = this.height * 0.75;
      const boundZ = 500;

      const projectedParticles = [];

      for (let i = 0; i < this.particles.length; i++) {
        const p = this.particles[i];

        // Move
        p.x += p.vx;
        p.y += p.vy;
        p.z += p.vz;
        p.pulse += p.pulseSpeed;

        // Wrap boundaries
        if (p.x < -boundX) p.x = boundX;
        if (p.x > boundX) p.x = -boundX;
        if (p.y < -boundY) p.y = boundY;
        if (p.y > boundY) p.y = -boundY;
        if (p.z < -boundZ) p.z = boundZ;
        if (p.z > boundZ) p.z = -boundZ;

        // Project
        const proj = this.project3D(p.x, p.y, p.z);
        if (proj) {
          projectedParticles.push({
            p,
            proj,
            index: i
          });
        }
      }

      // Sort by depth (far to near)
      projectedParticles.sort((a, b) => b.proj.depth - a.proj.depth);

      // 3. Draw 3D Filament Lines between nearby particles
      const maxDist3D = 210;
      ctx.lineWidth = 1;

      for (let i = 0; i < projectedParticles.length; i++) {
        const itemA = projectedParticles[i];
        const pA = itemA.p;
        const projA = itemA.proj;

        for (let j = i + 1; j < projectedParticles.length; j++) {
          const itemB = projectedParticles[j];
          const pB = itemB.p;
          const projB = itemB.proj;

          // Euclidean 3D distance
          const dx = pA.x - pB.x;
          const dy = pA.y - pB.y;
          const dz = pA.z - pB.z;
          const dist3D = Math.sqrt(dx * dx + dy * dy + dz * dz);

          if (dist3D < maxDist3D) {
            const normDist = 1 - dist3D / maxDist3D;
            // Depth modulation: closer lines slightly more visible
            const depthFactor = Math.max(0.2, Math.min(1.2, (projA.scale + projB.scale) * 0.7));
            const alpha = normDist * 0.38 * depthFactor * (isDark ? 1.0 : 0.65);

            if (alpha > 0.02) {
              ctx.beginPath();
              ctx.moveTo(projA.screenX, projA.screenY);
              ctx.lineTo(projB.screenX, projB.screenY);

              if (isDark) {
                ctx.strokeStyle = `rgba(99, 102, 241, ${alpha.toFixed(3)})`;
              } else {
                ctx.strokeStyle = `rgba(79, 70, 229, ${alpha.toFixed(3)})`;
              }
              ctx.stroke();

              // Spawn occasional glowing data pulse along the filament
              if (Math.random() < 0.0004 && this.pulses.length < 15) {
                this.pulses.push({
                  from: pA,
                  to: pB,
                  progress: 0,
                  speed: 0.015 + Math.random() * 0.02
                });
              }
            }
          }
        }
      }

      // 4. Update & Draw Moving Data Pulses
      for (let i = this.pulses.length - 1; i >= 0; i--) {
        const pulse = this.pulses[i];
        pulse.progress += pulse.speed;

        if (pulse.progress >= 1) {
          this.pulses.splice(i, 1);
          continue;
        }

        const currX = pulse.from.x + (pulse.to.x - pulse.from.x) * pulse.progress;
        const currY = pulse.from.y + (pulse.to.y - pulse.from.y) * pulse.progress;
        const currZ = pulse.from.z + (pulse.to.z - pulse.from.z) * pulse.progress;

        const proj = this.project3D(currX, currY, currZ);
        if (proj) {
          const pulseRadius = 2.4 * proj.scale;
          ctx.beginPath();
          ctx.arc(proj.screenX, proj.screenY, pulseRadius, 0, Math.PI * 2);
          ctx.fillStyle = isDark ? '#38bdf8' : '#2563eb';
          ctx.shadowColor = isDark ? '#38bdf8' : '#2563eb';
          ctx.shadowBlur = 8;
          ctx.fill();
          ctx.shadowBlur = 0; // reset
        }
      }

      // 5. Draw 3D Particle Nodes
      for (let i = 0; i < projectedParticles.length; i++) {
        const { p, proj } = projectedParticles[i];
        const pulseScale = 0.85 + Math.sin(p.pulse) * 0.25;
        const radius = Math.max(1, p.radius * proj.scale * pulseScale);

        let color, glowColor;
        if (isDark) {
          if (p.colorType === 0) {
            color = 'rgba(99, 102, 241, 0.85)';
            glowColor = '#6366f1';
          } else if (p.colorType === 1) {
            color = 'rgba(6, 182, 212, 0.9)';
            glowColor = '#06b6d4';
          } else {
            color = 'rgba(16, 185, 129, 0.85)';
            glowColor = '#10b981';
          }
        } else {
          if (p.colorType === 0) {
            color = 'rgba(79, 70, 229, 0.75)';
            glowColor = '#4f46e5';
          } else if (p.colorType === 1) {
            color = 'rgba(2, 132, 199, 0.75)';
            glowColor = '#0284c7';
          } else {
            color = 'rgba(5, 150, 105, 0.75)';
            glowColor = '#059669';
          }
        }

        ctx.beginPath();
        ctx.arc(proj.screenX, proj.screenY, radius, 0, Math.PI * 2);
        ctx.fillStyle = color;

        // Subtle glow on closer particles
        if (proj.scale > 0.8) {
          ctx.shadowColor = glowColor;
          ctx.shadowBlur = isDark ? 10 : 6;
        } else {
          ctx.shadowBlur = 0;
        }

        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // 6. Draw 3D Floating Polyhedra (Data Crystals)
      this.renderPolyhedra(ctx, isDark);

      // Loop
      this.animFrameId = requestAnimationFrame(() => this.render());
    }

    renderPolyhedra(ctx, isDark) {
      for (let k = 0; k < this.polyhedra.length; k++) {
        const poly = this.polyhedra[k];

        // Tumbling rotations
        poly.rotX += poly.speedX;
        poly.rotY += poly.speedY;
        poly.rotZ += poly.speedZ;

        // Slow drift
        poly.x += poly.driftVx;
        poly.y += poly.driftVy;

        const boundX = this.width * 0.45;
        const boundY = this.height * 0.45;
        if (poly.x < -boundX || poly.x > boundX) poly.driftVx *= -1;
        if (poly.y < -boundY || poly.y > boundY) poly.driftVy *= -1;

        // Transform local vertices with rotation matrix
        const cosX = Math.cos(poly.rotX), sinX = Math.sin(poly.rotX);
        const cosY = Math.cos(poly.rotY), sinY = Math.sin(poly.rotY);
        const cosZ = Math.cos(poly.rotZ), sinZ = Math.sin(poly.rotZ);

        const transformed = poly.vertices.map((v) => {
          // Rotate around X
          let y1 = v.y * cosX - v.z * sinX;
          let z1 = v.y * sinX + v.z * cosX;
          // Rotate around Y
          let x2 = v.x * cosY + z1 * sinY;
          let z2 = -v.x * sinY + z1 * cosY;
          // Rotate around Z
          let x3 = x2 * cosZ - y1 * sinZ;
          let y3 = x2 * sinZ + y1 * cosZ;

          // World position
          const wx = poly.x + x3;
          const wy = poly.y + y3;
          const wz = poly.z + z2;

          return this.project3D(wx, wy, wz);
        });

        // Draw wireframe edges
        const edgeAlpha = isDark ? 0.35 : 0.22;
        ctx.lineWidth = 1.2;

        if (isDark) {
          ctx.strokeStyle = k === 0 ? `rgba(6, 182, 212, ${edgeAlpha})` : `rgba(168, 85, 247, ${edgeAlpha})`;
        } else {
          ctx.strokeStyle = k === 0 ? `rgba(2, 132, 199, ${edgeAlpha})` : `rgba(124, 58, 237, ${edgeAlpha})`;
        }

        for (let e = 0; e < poly.edges.length; e++) {
          const [i1, i2] = poly.edges[e];
          const p1 = transformed[i1];
          const p2 = transformed[i2];

          if (p1 && p2) {
            ctx.beginPath();
            ctx.moveTo(p1.screenX, p1.screenY);
            ctx.lineTo(p2.screenX, p2.screenY);
            ctx.stroke();
          }
        }

        // Draw small vertices nodes
        for (let v = 0; v < transformed.length; v++) {
          const pt = transformed[v];
          if (pt) {
            ctx.beginPath();
            ctx.arc(pt.screenX, pt.screenY, 2.2 * pt.scale, 0, Math.PI * 2);
            ctx.fillStyle = isDark ? (k === 0 ? '#06b6d4' : '#c084fc') : (k === 0 ? '#0284c7' : '#7c3aed');
            ctx.fill();
          }
        }
      }
    }

    start() {
      if (!this.isRunning) {
        this.isRunning = true;
        this.animFrameId = requestAnimationFrame(() => this.render());
      } else if (!this.animFrameId) {
        this.animFrameId = requestAnimationFrame(() => this.render());
      }
    }

    stop() {
      this.isRunning = false;
      if (this.animFrameId) {
        cancelAnimationFrame(this.animFrameId);
        this.animFrameId = null;
      }
    }
  }

  // Initialize 3D Background when DOM is ready
  function start3DWhenReady() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        window.live3D = new Live3DBackground();
      });
    } else {
      window.live3D = new Live3DBackground();
    }
  }

  start3DWhenReady();

})();
