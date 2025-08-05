import React, { useEffect, useRef } from "react";

const Bee = () => {
  const beeRef = useRef<HTMLDivElement>(null);
  // Current position
  const pos = useRef({ x: window.innerWidth / 2, y: window.scrollY + window.innerHeight / 2 });
  // Target position
  const target = useRef({ x: Math.random() * window.innerWidth, y: window.scrollY + Math.random() * window.innerHeight });

  useEffect(() => {
    let animationFrame: number;
    const speed = 1; // px per frame

    const pickNewTarget = () => {
      target.current = {
        x: Math.random() * (window.innerWidth - 60),
        y: window.scrollY + Math.random() * (window.innerHeight - 60),
      };
    };

    const animate = () => {
      const bee = beeRef.current;
      if (!bee) return;

      // Move towards target
      const dx = target.current.x - pos.current.x;
      const dy = target.current.y - pos.current.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < 5) {
        pickNewTarget();
      } else {
        pos.current.x += (dx / dist) * speed;
        pos.current.y += (dy / dist) * speed;
      }

      bee.style.left = `${pos.current.x}px`;
      bee.style.top = `${pos.current.y}px`;

      animationFrame = requestAnimationFrame(animate);
    };

    pickNewTarget();
    animate();

    // Re-pick target on scroll/resize to stay in viewport
    const handleResizeOrScroll = () => pickNewTarget();
    window.addEventListener("resize", handleResizeOrScroll);
    window.addEventListener("scroll", handleResizeOrScroll);

    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", handleResizeOrScroll);
      window.removeEventListener("scroll", handleResizeOrScroll);
    };
  }, []);

  return (
    <div
      ref={beeRef}
      style={{
        position: "absolute",
        left: 0,
        top: 0,
        fontSize: "2.5rem",
        zIndex: 0,
        pointerEvents: "none",
        transition: "filter 0.2s",
        opacity: 0.5,
      }}
    >
      🐝
    </div>
  );
};

export default Bee; 