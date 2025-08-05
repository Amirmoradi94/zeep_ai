import React, { useEffect, useState } from 'react';
import { StatCard } from './StatCard';
import { CircularProgress } from './CircularProgress';
import { ChartCard } from './ChartCard';
import { Brain, Users, MessageSquare, DollarSign, Zap, Globe } from 'lucide-react';
import { api, OverviewData, AIModelStats, APIState, createInitialAPIState } from '../../lib/api';

export const Overview = () => {
  const [overviewState, setOverviewState] = useState<APIState<OverviewData>>(createInitialAPIState());
  const [aiState, setAiState] = useState<APIState<AIModelStats>>(createInitialAPIState());

  // Chart data for frames and tokens
  const [frameUsageData, setFrameUsageData] = useState<any[]>([]);
  const [tokenUsageData, setTokenUsageData] = useState<any[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Reset states
        setOverviewState(prev => ({ ...prev, loading: true, error: null }));
        setAiState(prev => ({ ...prev, loading: true, error: null }));

        // Fetch data in parallel
        const [overviewData, aiData] = await Promise.all([
          api.getOverview(),
          api.getAIModelStats()
        ]);

        // Set data
        setOverviewState({ data: overviewData, loading: false, error: null });
        setAiState({ data: aiData, loading: false, error: null });

        // Process frame and token usage data
        const frameData = overviewData.dailyUsage.map((day, index) => ({
          date: day.date,
          openai: aiData.openai[index]?.frames || 0,
          gemini: aiData.gemini[index]?.frames || 0,
          total: (aiData.openai[index]?.frames || 0) + (aiData.gemini[index]?.frames || 0)
        }));

        const tokenData = overviewData.dailyUsage.map((day, index) => ({
          date: day.date,
          tokens: (aiData.openai[index]?.tokens || 0) + (aiData.gemini[index]?.tokens || 0)
        }));

        setFrameUsageData(frameData);
        setTokenUsageData(tokenData);

      } catch (error) {
        console.error('Error fetching dashboard data:', error);
        const errorMessage = error instanceof Error ? error.message : 'An error occurred';
        
        setOverviewState(prev => ({ ...prev, loading: false, error: errorMessage }));
        setAiState(prev => ({ ...prev, loading: false, error: errorMessage }));
      }
    };

    fetchData();
  }, []);

  if (overviewState.loading || aiState.loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg">Loading dashboard data...</div>
      </div>
    );
  }

  if (overviewState.error || aiState.error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col space-y-4">
        <div className="text-red-500">Error loading data: {overviewState.error || aiState.error}</div>
        <button 
          onClick={() => window.location.reload()} 
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!overviewState.data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">No data available</div>
      </div>
    );
  }

  const data = overviewState.data;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Users"
          value={data.totalUsers?.toLocaleString?.() || '0'}
          change={data.userGrowth > 0 ? `+${data.userGrowth}% from last month` : `${data.userGrowth}% from last month`}
          changeType={data.userGrowth >= 0 ? "positive" : "negative"}
          icon={<Users className="w-6 h-6" />}
        />
        <StatCard
          title="Total Cost"
          value={`$${data.totalCost.toFixed(2)}`}
          change={data.costGrowth > 0 ? `+${data.costGrowth}% from last month` : `${data.costGrowth}% from last month`}
          changeType={data.costGrowth <= 0 ? "positive" : "negative"}
          icon={<DollarSign className="w-6 h-6" />}
        />
        <StatCard
          title="API Requests"
          value={data.totalRequests.toLocaleString()}
          change={data.requestGrowth > 0 ? `+${data.requestGrowth}% from last week` : `${data.requestGrowth}% from last week`}
          changeType={data.requestGrowth >= 0 ? "positive" : "negative"}
          icon={<Globe className="w-6 h-6" />}
        />
        <StatCard
          title="Avg Response Time"
          value={`${Math.round(data.avgResponseTime)}ms`}
          change={data.responseTimeChange < 0 ? `${data.responseTimeChange}% from last week` : `+${data.responseTimeChange}% from last week`}
          changeType={data.responseTimeChange <= 0 ? "positive" : "negative"}
          icon={<Zap className="w-6 h-6" />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ChartCard
            title="Daily API Usage Trend"
            data={data.dailyUsage}
            type="area"
            dataKey="requests"
            color="hsl(var(--chart-1))"
          />
        </div>
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col items-center space-y-2 p-4 rounded-lg bg-card border">
              <CircularProgress 
                value={Math.round(data.successRate)} 
                size={80} 
                label="Success Rate" 
              />
            </div>
            <div className="flex flex-col items-center space-y-2 p-4 rounded-lg bg-card border">
              <CircularProgress 
                value={89} 
                size={80} 
                label="Uptime" 
                color="hsl(var(--chart-3))" 
              />
            </div>
          </div>
          <StatCard
            title="Total Feedback"
            value={data.totalFeedback.toLocaleString()}
            change={`${data.positiveFeedbackPct}% Positive`}
            changeType="positive"
            icon={<MessageSquare className="w-6 h-6" />}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard
          title="Frame Usage (OpenAI vs Gemini)"
          data={frameUsageData}
          type="bar"
          dataKey="total"
          color="hsl(var(--chart-2))"
        />
        <ChartCard
          title="Token Usage Trend"
          data={tokenUsageData}
          type="line"
          dataKey="tokens"
          color="hsl(var(--chart-4))"
        />
      </div>
    </div>
  );
};
