import React, { useEffect, useRef } from "react";

const PARTICLE_COUNT = 30;

const Particles = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.innerHTML = "";
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const particle = document.createElement("div");
      particle.className = "particle";
      particle.style.left = Math.random() * 100 + "%";
      particle.style.animationDelay = Math.random() * 6 + "s";
      particle.style.animationDuration = Math.random() * 3 + 3 + "s";
      container.appendChild(particle);
    }
  }, []);

  return (
    <div
      ref={containerRef}
      className="particles"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        pointerEvents: "none",
        zIndex: 1,
      }}
    />
  );
};

export default Particles; 