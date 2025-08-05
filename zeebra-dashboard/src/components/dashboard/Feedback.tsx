import React, { useEffect, useState } from 'react';
import { StatCard } from './StatCard';
import { ChartCard } from './ChartCard';
import { MessageSquare, ThumbsUp, ThumbsDown, TrendingUp } from 'lucide-react';
import { api, FeedbackStats, APIState, createInitialAPIState } from '../../lib/api';

export const Feedback = () => {
  const [feedbackState, setFeedbackState] = useState<APIState<FeedbackStats>>(createInitialAPIState());

  useEffect(() => {
    const fetchFeedbackData = async () => {
      try {
        setFeedbackState(prev => ({ ...prev, loading: true, error: null }));
        
        const feedbackData = await api.getFeedbackStats();
        
        setFeedbackState({ data: feedbackData, loading: false, error: null });
      } catch (error) {
        console.error('Error fetching feedback data:', error);
        const errorMessage = error instanceof Error ? error.message : 'An error occurred';
        setFeedbackState(prev => ({ ...prev, loading: false, error: errorMessage }));
      }
    };

    fetchFeedbackData();
  }, []);

  if (feedbackState.loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg">Loading feedback data...</div>
      </div>
    );
  }

  if (feedbackState.error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col space-y-4">
        <div className="text-red-500">Error loading data: {feedbackState.error}</div>
        <button 
          onClick={() => window.location.reload()} 
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!feedbackState.data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">No feedback data available</div>
      </div>
    );
  }

  const data = feedbackState.data;
  const totalFeedback = data.GOOD + data.BAD + data.NEUTRAL;
  
  // Calculate percentages
  const goodPercentage = totalFeedback > 0 ? Math.round((data.GOOD / totalFeedback) * 100) : 0;
  const badPercentage = totalFeedback > 0 ? Math.round((data.BAD / totalFeedback) * 100) : 0;
  const neutralPercentage = totalFeedback > 0 ? Math.round((data.NEUTRAL / totalFeedback) * 100) : 0;

  // Create chart data for pie chart
  const sentimentData = [
    { name: 'Good', value: data.GOOD, percentage: goodPercentage },
    { name: 'Neutral', value: data.NEUTRAL, percentage: neutralPercentage },
    { name: 'Bad', value: data.BAD, percentage: badPercentage },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Feedback"
          value={totalFeedback.toLocaleString()}
          change=""
          changeType="neutral"
          icon={<MessageSquare className="w-6 h-6" />}
        />
        <StatCard
          title="Positive Feedback"
          value={data.GOOD.toLocaleString()}
          change={`${goodPercentage}% of total`}
          changeType="positive"
          icon={<ThumbsUp className="w-6 h-6" />}
        />
        <StatCard
          title="Negative Feedback"
          value={data.BAD.toLocaleString()}
          change={`${badPercentage}% of total`}
          changeType={badPercentage > 20 ? "negative" : "neutral"}
          icon={<ThumbsDown className="w-6 h-6" />}
        />
        <StatCard
          title="Satisfaction Rate"
          value={`${goodPercentage}%`}
          change={goodPercentage >= 80 ? "Excellent" : goodPercentage >= 70 ? "Good" : "Needs improvement"}
          changeType={goodPercentage >= 80 ? "positive" : goodPercentage >= 70 ? "neutral" : "negative"}
          icon={<TrendingUp className="w-6 h-6" />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard
          title="Daily Feedback Trend"
          data={data.daily}
          type="line"
          dataKey="good"
          color="hsl(var(--chart-1))"
        />
        <div className="p-6 rounded-lg border bg-card">
          <h3 className="text-lg font-semibold mb-4">Feedback Distribution</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span className="text-sm">Good</span>
              </div>
              <div className="text-right">
                <div className="font-medium">{data.GOOD.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">{goodPercentage}%</div>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                <span className="text-sm">Neutral</span>
              </div>
              <div className="text-right">
                <div className="font-medium">{data.NEUTRAL.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">{neutralPercentage}%</div>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <span className="text-sm">Bad</span>
              </div>
              <div className="text-right">
                <div className="font-medium">{data.BAD.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">{badPercentage}%</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ChartCard
          title="Good Feedback Over Time"
          data={data.daily}
          type="bar"
          dataKey="good"
          color="hsl(var(--chart-2))"
        />
        <ChartCard
          title="Neutral Feedback Over Time"
          data={data.daily}
          type="bar"
          dataKey="neutral"
          color="hsl(var(--chart-3))"
        />
        <ChartCard
          title="Bad Feedback Over Time"
          data={data.daily}
          type="bar"
          dataKey="bad"
          color="hsl(var(--chart-4))"
        />
      </div>
    </div>
  );
};
