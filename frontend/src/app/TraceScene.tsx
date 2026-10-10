"use client";

import { useEffect, useRef } from "react";

/** A short, decorative introduction. The SVG stays usable without WebGL. */
export default function TraceScene() {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (motion.matches) return;
    let cancelled = false;
    let dispose = () => {};

    void import("three").then((THREE) => {
      if (cancelled || motion.matches) return;
      let renderer: InstanceType<typeof THREE.WebGLRenderer>;
      try {
        renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" });
      } catch {
        return; // The permanent SVG fallback supplies the same visual.
      }
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
      renderer.setClearColor(0x000000, 0);
      renderer.domElement.setAttribute("aria-hidden", "true");
      element.appendChild(renderer.domElement);
      element.dataset.rendered = "true";
      const scene = new THREE.Scene();
      const camera = new THREE.OrthographicCamera(-3.8, 3.8, 1.5, -1.5, 0.1, 50);
      camera.position.set(0, 0, 12);
      const group = new THREE.Group();
      scene.add(group);
      const points = [-3.1, -1.9, -0.65, 0.65, 1.9, 3.1].map((x, i) =>
        new THREE.Vector3(x, i % 2 ? -0.5 : 0.5, Math.sin(i) * 0.25));
      const curve = new THREE.CatmullRomCurve3(points);
      const geometries: InstanceType<typeof THREE.BufferGeometry>[] = [];
      const materials: InstanceType<typeof THREE.Material>[] = [];
      const lineGeometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(100));
      const lineMaterial = new THREE.LineBasicMaterial({ color: 0x7fa99b, transparent: true, opacity: 0.7 });
      geometries.push(lineGeometry);
      materials.push(lineMaterial);
      group.add(new THREE.Line(lineGeometry, lineMaterial));
      const sphere = new THREE.SphereGeometry(0.13, 12, 8);
      const ring = new THREE.TorusGeometry(0.28, 0.012, 5, 30);
      geometries.push(sphere, ring);
      points.forEach((point, i) => {
        const material = new THREE.MeshBasicMaterial({ color: i === 5 ? 0xe7b786 : 0xb4ddcb });
        const ringMaterial = new THREE.MeshBasicMaterial({ color: 0x6a9484, transparent: true, opacity: 0.8 });
        materials.push(material, ringMaterial);
        const node = new THREE.Mesh(sphere, material);
        node.position.copy(point);
        const halo = new THREE.Mesh(ring, ringMaterial);
        halo.position.copy(point);
        group.add(node, halo);
      });
      const signalMaterial = new THREE.MeshBasicMaterial({ color: 0xf2c393 });
      const signalGeometry = new THREE.SphereGeometry(0.07, 8, 6);
      materials.push(signalMaterial);
      geometries.push(signalGeometry);
      const signal = new THREE.Mesh(signalGeometry, signalMaterial);
      group.add(signal);
      const mixer = new THREE.AnimationMixer(group);
      const tilt = new THREE.NumberKeyframeTrack(".rotation[y]", [0, 2.2, 4.5], [-0.18, 0.18, 0]);
      const action = mixer.clipAction(new THREE.AnimationClip("trace-introduction", 4.5, [tilt]));
      action.setLoop(THREE.LoopOnce, 1);
      action.clampWhenFinished = true;
      action.play();
      let frame = 0;
      let previous = 0;
      let elapsed = 0;
      let visible = true;
      let finished = false;

      function resize() {
        if (!element) return;
        const { width, height } = element.getBoundingClientRect();
        if (!width || !height) return;
        const halfHeight = Math.max(1, 3.8 * height / width);
        const halfWidth = halfHeight * width / height;
        camera.left = -halfWidth; camera.right = halfWidth;
        camera.top = halfHeight; camera.bottom = -halfHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
        renderer.render(scene, camera);
      }
      function animate(time: number) {
        frame = 0;
        if (cancelled || !visible || document.hidden || finished) return;
        if (previous && time - previous < 1000 / 30) {
          frame = requestAnimationFrame(animate);
          return;
        }
        const delta = previous ? Math.min((time - previous) / 1000, 0.1) : 0;
        previous = time;
        elapsed += delta;
        mixer.update(delta);
        signal.position.copy(curve.getPoint(Math.min(elapsed / 4.5, 1)));
        renderer.render(scene, camera);
        finished = elapsed >= 4.5 || motion.matches;
        if (!finished) frame = requestAnimationFrame(animate);
      }
      function resume() {
        cancelAnimationFrame(frame);
        frame = 0;
        previous = 0;
        if (motion.matches) finished = true;
        if (visible && !document.hidden && !finished) frame = requestAnimationFrame(animate);
      }
      const sizing = new ResizeObserver(resize);
      sizing.observe(element);
      const visibility = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; resume(); });
      visibility.observe(element);
      document.addEventListener("visibilitychange", resume);
      motion.addEventListener("change", resume);
      resize();
      resume();
      dispose = () => {
        cancelAnimationFrame(frame);
        sizing.disconnect();
        visibility.disconnect();
        document.removeEventListener("visibilitychange", resume);
        motion.removeEventListener("change", resume);
        mixer.stopAllAction();
        mixer.uncacheRoot(group);
        geometries.forEach(geometry => geometry.dispose());
        materials.forEach(material => material.dispose());
        renderer.dispose();
        renderer.forceContextLoss();
        renderer.domElement.remove();
        delete element.dataset.rendered;
      };
    }).catch(() => {});
    return () => { cancelled = true; dispose(); };
  }, []);

  return <figure className="trace-scene">
    <div className="scene-caption"><span>THE COMPLIANCE CHAIN</span><span>01 — 06</span></div>
    <div className="scene-canvas" ref={host} aria-hidden="true">
      <svg className="scene-fallback" viewBox="0 0 640 180" fill="none">
        <path d="M45 60C90 60 115 120 155 120S230 60 265 60S340 120 375 120S450 60 485 60S565 120 595 120" stroke="#7fa99b" />
        {[45,155,265,375,485,595].map((x,i) => <g key={x}><circle cx={x} cy={i % 2 ? 120 : 60} r="21" stroke="#6a9484"/><circle cx={x} cy={i % 2 ? 120 : 60} r="8" fill={i === 5 ? "#e7b786" : "#b4ddcb"}/></g>)}
      </svg>
    </div>
    <figcaption>Source <span>→</span> Obligation <span>→</span> Control <span>→</span> Evidence <span>→</span> Review <span>→</span> Action</figcaption>
  </figure>;
}
