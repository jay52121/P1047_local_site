export class AutoClock {
  constructor(cycleMs = 12000) {
    this.cycleMs = cycleMs;
    this.views = new Set();
    this.startedAt = performance.now();
    this.frame = null;
  }

  add(view) {
    this.views.add(view);
    this.start();
    return () => this.views.delete(view);
  }

  start() {
    if (this.frame !== null) return;
    const tick = now => {
      const phase = ((now - this.startedAt) % this.cycleMs) / this.cycleMs;
      this.views.forEach(view => view.renderAt?.(phase));
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  restart() {
    this.startedAt = performance.now();
  }

  destroy() {
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.frame = null;
    this.views.forEach(view => view.destroy?.());
    this.views.clear();
  }
}
