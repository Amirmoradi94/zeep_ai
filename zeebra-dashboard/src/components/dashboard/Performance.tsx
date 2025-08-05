
import { StatCard } from './StatCard';
import { CircularProgress } from './CircularProgress';
import { ChartCard } from './ChartCard';
import { Zap, Clock, Activity, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export const Performance = () => {
  const responseTimeData = [
    { date: '2024-01-01', openai: 142, gemini: 98, combined: 120 },
    { date: '2024-01-02', openai: 156, gemini: 102, combined: 129 },
    { date: '2024-01-03', openai: 138, gemini: 94, combined: 116 },
    { date: '2024-01-04', openai: 149, gemini: 105, combined: 127 },
    { date: '2024-01-05', openai: 145, gemini: 101, combined: 123 },
    { date: '2024-01-06', openai: 152, gemini: 97, combined: 124 },
    { date: '2024-01-07', openai: 144, gemini: 99, combined: 121 },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Overall Avg Response Time"
          value="123ms"
          change="-8.2% this week"
          changeType="positive"
          icon={<Zap className="w-6 h-6" />}
        />
        <StatCard
          title="OpenAI Avg Response"
          value="147ms"
          change="-3.1% this week"
          changeType="positive"
          icon={<Clock className="w-6 h-6" />}
        />
        <StatCard
          title="Gemini Avg Response"
          value="99ms"
          change="-1.8% this week"
          changeType="positive"
          icon={<Activity className="w-6 h-6" />}
        />
        <StatCard
          title="Performance Score"
          value="A+"
          change="Excellent performance"
          changeType="positive"
          icon={<TrendingUp className="w-6 h-6" />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ChartCard
            title="Vision Model Response Time Comparison"
            data={responseTimeData}
            type="line"
            dataKey="combined"
            color="hsl(var(--chart-1))"
          />
        </div>
        <div className="space-y-6">
          <Card className="glass-effect border-border/50">
            <CardHeader>
              <CardTitle>System Health</CardTitle>
            </CardHeader>
            <CardContent className="flex justify-center">
              <CircularProgress 
                value={97} 
                size={120} 
                label="97% Healthy"
                color="hsl(var(--chart-3))"
              />
            </CardContent>
          </Card>
          <Card className="glass-effect border-border/50">
            <CardHeader>
              <CardTitle>Uptime</CardTitle>
            </CardHeader>
            <CardContent className="flex justify-center">
              <CircularProgress 
                value={99} 
                size={120} 
                label="99.9% Uptime"
                color="hsl(var(--chart-4))"
              />
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="glass-effect border-border/50">
          <CardHeader>
            <CardTitle>Response Time Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-lg bg-card/50 border">
                <div className="flex items-center space-x-3">
                  <div className="w-3 h-3 rounded-full bg-chart-1"></div>
                  <span className="font-medium">OpenAI Models</span>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold">147ms</div>
                  <div className="text-xs text-muted-foreground">Average</div>
                </div>
              </div>
              
              <div className="flex items-center justify-between p-3 rounded-lg bg-card/50 border">
                <div className="flex items-center space-x-3">
                  <div className="w-3 h-3 rounded-full bg-chart-3"></div>
                  <span className="font-medium">Gemini Models</span>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold">99ms</div>
                  <div className="text-xs text-muted-foreground">Average</div>
                </div>
              </div>
              
              <div className="flex items-center justify-between p-3 rounded-lg bg-card/50 border">
                <div className="flex items-center space-x-3">
                  <div className="w-3 h-3 rounded-full bg-chart-4"></div>
                  <span className="font-medium">Combined Average</span>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold">123ms</div>
                  <div className="text-xs text-muted-foreground">Overall</div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-effect border-border/50">
          <CardHeader>
            <CardTitle>Performance Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Response Time</span>
                <span className="text-sm text-chart-3">Excellent</span>
              </div>
              <div className="w-full bg-secondary h-2 rounded-full">
                <div className="bg-chart-3 h-2 rounded-full w-[85%]"></div>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Reliability</span>
                <span className="text-sm text-chart-3">Outstanding</span>
              </div>
              <div className="w-full bg-secondary h-2 rounded-full">
                <div className="bg-chart-3 h-2 rounded-full w-[97%]"></div>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Efficiency</span>
                <span className="text-sm text-chart-1">Very Good</span>
              </div>
              <div className="w-full bg-secondary h-2 rounded-full">
                <div className="bg-chart-1 h-2 rounded-full w-[78%]"></div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
