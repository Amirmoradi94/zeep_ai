import React, { useEffect, useState } from 'react';
import { StatCard } from './StatCard';
import { CircularProgress } from './CircularProgress';
import { ChartCard } from './ChartCard';
import { Globe, Zap, AlertTriangle, TrendingUp, Activity } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api, ScrapingAPIStats, APIState, createInitialAPIState } from '../../lib/api';

export const ScrapingAPI = () => {
  const [scrapingState, setScrapingState] = useState<APIState<ScrapingAPIStats>>(createInitialAPIState());

  useEffect(() => {
    const fetchScrapingData = async () => {
      try {
        setScrapingState(prev => ({ ...prev, loading: true, error: null }));
        
        const scrapingData = await api.getScrapingAPIStats();
        
        setScrapingState({ data: scrapingData, loading: false, error: null });
      } catch (error) {
        console.error('Error fetching scraping API data:', error);
        const errorMessage = error instanceof Error ? error.message : 'An error occurred';
        setScrapingState(prev => ({ ...prev, loading: false, error: errorMessage }));
      }
    };

    fetchScrapingData();
  }, []);

  if (scrapingState.loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg">Loading scraping API data...</div>
      </div>
    );
  }

  if (scrapingState.error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col space-y-4">
        <div className="text-red-500">Error loading data: {scrapingState.error}</div>
        <button 
          onClick={() => window.location.reload()} 
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!scrapingState.data || !Array.isArray(scrapingState.data.daily)) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">No scraping API data available</div>
      </div>
    );
  }

  const { totalRequests, totalAvgResponseTime, totalSuccessRate, daily } = scrapingState.data;
  const data = daily;

  // Only consider days with at least one request for averages and charts
  const nonZeroDays = Array.isArray(data) ? data.filter(day => day.requests > 0) : [];

  // Calculate growth trends using nonZeroDays
  const recentData = nonZeroDays.slice(-7); // Last 7 non-zero days
  const previousData = nonZeroDays.slice(-14, -7); // Previous 7 non-zero days

  const recentRequests = recentData.reduce((sum, day) => sum + day.requests, 0);
  const previousRequests = previousData.reduce((sum, day) => sum + day.requests, 0);
  const requestsGrowth = previousRequests > 0 ? 
    Math.round(((recentRequests - previousRequests) / previousRequests) * 100) : 0;

  const recentResponseTime = recentData.length > 0 ? 
    recentData.reduce((sum, day) => sum + day.responseTime, 0) / recentData.length : 0;
  const previousResponseTime = previousData.length > 0 ? 
    previousData.reduce((sum, day) => sum + day.responseTime, 0) / previousData.length : 0;
  const responseTimeChange = previousResponseTime > 0 ? 
    Math.round(((recentResponseTime - previousResponseTime) / previousResponseTime) * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Requests"
          value={totalRequests.toLocaleString()}
          change={requestsGrowth > 0 ? `+${requestsGrowth}% this week` : `${requestsGrowth}% this week`}
          changeType={requestsGrowth >= 0 ? "positive" : "negative"}
          icon={<Globe className="w-6 h-6" />}
        />
        <StatCard
          title="Avg Response Time"
          value={`${totalAvgResponseTime}ms`}
          change={responseTimeChange < 0 ? `${responseTimeChange}% from last week` : `+${responseTimeChange}% from last week`}
          changeType={responseTimeChange <= 0 ? "positive" : "negative"}
          icon={<Zap className="w-6 h-6" />}
        />
        <StatCard
          title="Success Rate"
          value={`${totalSuccessRate}%`}
          change={totalSuccessRate >= 95 ? "Excellent" : totalSuccessRate >= 90 ? "Good" : "Needs attention"}
          changeType={totalSuccessRate >= 95 ? "positive" : totalSuccessRate >= 90 ? "neutral" : "negative"}
          icon={<TrendingUp className="w-6 h-6" />}
        />
        <StatCard
          title="Daily Avg Requests"
          value={Math.round(totalRequests / (data.length || 1)).toLocaleString()}
          change={`Based on ${data.length} days`}
          changeType="neutral"
          icon={<Activity className="w-6 h-6" />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard
          title="Daily API Requests"
          data={nonZeroDays}
          type="bar"
          dataKey="requests"
          color="hsl(var(--chart-1))"
        />
        <ChartCard
          title="Response Time Trend"
          data={nonZeroDays}
          type="line"
          dataKey="responseTime"
          color="hsl(var(--chart-2))"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard
          title="Success Rate Over Time"
          data={nonZeroDays}
          type="area"
          dataKey="successRate"
          color="hsl(var(--chart-3))"
        />
        <div className="p-6 rounded-lg border bg-card">
          <h3 className="text-lg font-semibold mb-4">Performance Summary</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total Requests:</span>
              <span className="font-medium">{totalRequests.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Avg Response Time:</span>
              <span className="font-medium">{totalAvgResponseTime}ms</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Overall Success Rate:</span>
              <span className="font-medium">{totalSuccessRate}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Requests Growth:</span>
              <span className={`font-medium ${requestsGrowth >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {requestsGrowth > 0 ? '+' : ''}{requestsGrowth}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Response Time Change:</span>
              <span className={`font-medium ${responseTimeChange <= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {responseTimeChange > 0 ? '+' : ''}{responseTimeChange}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
