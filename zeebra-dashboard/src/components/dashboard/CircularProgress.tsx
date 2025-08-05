
import { cn } from '@/lib/utils';

interface CircularProgressProps {
  value: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
  color?: string;
  className?: string;
}

export const CircularProgress = ({
  value,
  size = 120,
  strokeWidth = 8,
  label,
  color = "#8b5cf6",
  className
}: CircularProgressProps) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)}>
      <svg width={size} height={size} className="transform -rotate-90" style={{ background: 'transparent' }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(139, 92, 246, 0.2)"
          strokeWidth={strokeWidth}
          fill="transparent"
          className="opacity-30"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
          style={{
            filter: `drop-shadow(0 0 8px ${color})`
          }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-white glow-text">{value}%</span>
        {label && <span className="text-xs text-purple-300/70 mt-1">{label}</span>}
      </div>
    </div>
  );
};
