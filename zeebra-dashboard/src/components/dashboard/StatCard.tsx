
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface StatCardProps {
  title: string;
  value: string | number;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
  icon?: React.ReactNode;
  className?: string;
}

export const StatCard = ({ title, value, change, changeType = 'neutral', icon, className }: StatCardProps) => {
  return (
    <Card className={cn(
      "p-6 glass-effect hover-lift border-purple-500/30 relative overflow-hidden group",
      className
    )}>
      {/* Animated background gradient */}
      <div className="absolute inset-0 bg-gradient-to-r from-purple-500/5 to-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      
      <div className="relative flex items-center justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium text-purple-300/80">{title}</p>
          <p className="text-3xl font-bold text-white glow-text">{value}</p>
          {change && (
            <p className={cn(
              "text-xs font-medium flex items-center gap-1",
              changeType === 'positive' && "text-green-400",
              changeType === 'negative' && "text-red-400",
              changeType === 'neutral' && "text-purple-300/70"
            )}>
              {changeType === 'positive' && '↗'}
              {changeType === 'negative' && '↘'}
              {change}
            </p>
          )}
        </div>
        {icon && (
          <div className="p-4 rounded-xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 border border-purple-500/30 neon-glow">
            <div className="text-purple-300">
              {icon}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};
