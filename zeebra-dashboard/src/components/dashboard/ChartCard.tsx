
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface ChartCardProps {
  title: string;
  data: any[];
  type: 'line' | 'area' | 'bar';
  dataKey: string;
  xAxisKey?: string;
  color?: string;
  height?: number;
}

export const ChartCard = ({ 
  title, 
  data, 
  type, 
  dataKey, 
  xAxisKey = 'date', 
  color = '#8b5cf6',
  height = 300 
}: ChartCardProps) => {
  const renderChart = () => {
    const commonProps = {
      data,
      margin: { top: 5, right: 30, left: 20, bottom: 5 }
    };

    switch (type) {
      case 'line':
        return (
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(139, 92, 246, 0.2)" />
            <XAxis dataKey={xAxisKey} stroke="#a78bfa" fontSize={12} />
            <YAxis stroke="#a78bfa" fontSize={12} />
            <Tooltip 
              contentStyle={{
                backgroundColor: 'rgba(30, 30, 60, 0.95)',
                border: '1px solid rgba(139, 92, 246, 0.5)',
                borderRadius: '12px',
                color: '#ffffff',
                backdropFilter: 'blur(10px)'
              }}
            />
            <Line 
              type="monotone" 
              dataKey={dataKey} 
              stroke={color} 
              strokeWidth={3}
              dot={{ fill: color, strokeWidth: 2, r: 5, filter: `drop-shadow(0 0 6px ${color})` }}
              activeDot={{ r: 7, stroke: color, strokeWidth: 2, filter: `drop-shadow(0 0 8px ${color})` }}
            />
          </LineChart>
        );
      case 'area':
        return (
          <AreaChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(139, 92, 246, 0.2)" />
            <XAxis dataKey={xAxisKey} stroke="#a78bfa" fontSize={12} />
            <YAxis stroke="#a78bfa" fontSize={12} />
            <Tooltip 
              contentStyle={{
                backgroundColor: 'rgba(30, 30, 60, 0.95)',
                border: '1px solid rgba(139, 92, 246, 0.5)',
                borderRadius: '12px',
                color: '#ffffff',
                backdropFilter: 'blur(10px)'
              }}
            />
            <Area 
              type="monotone" 
              dataKey={dataKey} 
              stroke={color} 
              fill={color}
              fillOpacity={0.2}
              strokeWidth={2}
            />
          </AreaChart>
        );
      case 'bar':
        return (
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(139, 92, 246, 0.2)" />
            <XAxis dataKey={xAxisKey} stroke="#a78bfa" fontSize={12} />
            <YAxis stroke="#a78bfa" fontSize={12} />
            <Tooltip 
              contentStyle={{
                backgroundColor: 'rgba(30, 30, 60, 0.95)',
                border: '1px solid rgba(139, 92, 246, 0.5)',
                borderRadius: '12px',
                color: '#ffffff',
                backdropFilter: 'blur(10px)'
              }}
            />
            <Bar 
              dataKey={dataKey} 
              fill={color} 
              radius={[6, 6, 0, 0]}
              style={{ filter: `drop-shadow(0 0 6px ${color})` }}
            />
          </BarChart>
        );
      default:
        return null;
    }
  };

  return (
    <Card className="glass-effect border-purple-500/30 hover-lift relative overflow-hidden group">
      {/* Animated background */}
      <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      
      <CardHeader className="relative">
        <CardTitle className="text-lg font-semibold text-white glow-text">{title}</CardTitle>
      </CardHeader>
      <CardContent className="relative">
        <ResponsiveContainer width="100%" height={height}>
          {renderChart()}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};
