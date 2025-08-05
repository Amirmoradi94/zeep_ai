import React, { useEffect, useState } from 'react';
import { StatCard } from './StatCard';
import { CircularProgress } from './CircularProgress';
import { ChartCard } from './ChartCard';
import { Brain, Zap, DollarSign, TrendingUp, Activity } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { api, AIModelStats, APIState, createInitialAPIState } from '../../lib/api';

export const AIModels = () => {
  const [aiState, setAiState] = useState<APIState<AIModelStats>>(createInitialAPIState());

  useEffect(() => {
    const fetchAIData = async () => {
      try {
        setAiState(prev => ({ ...prev, loading: true, error: null }));
        
        const aiData = await api.getAIModelStats();
        
        setAiState({ data: aiData, loading: false, error: null });
      } catch (error) {
        console.error('Error fetching AI data:', error);
        const errorMessage = error instanceof Error ? error.message : 'An error occurred';
        setAiState(prev => ({ ...prev, loading: false, error: errorMessage }));
      }
    };

    fetchAIData();
  }, []);

  if (aiState.loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg">Loading AI model data...</div>
      </div>
    );
  }

  if (aiState.error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col space-y-4">
        <div className="text-red-500">Error loading data: {aiState.error}</div>
        <button 
          onClick={() => window.location.reload()} 
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!aiState.data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">No AI model data available</div>
      </div>
    );
  }

  const data = aiState.data;

  // Combine OpenAI and Gemini data for comparison charts
  const dailyComparison = data.openai.map((openaiDay, index) => ({
    date: openaiDay.date,
    openai_requests: openaiDay.requests,
    gemini_requests: data.gemini[index]?.requests || 0,
    openai_cost: openaiDay.cost,
    gemini_cost: data.gemini[index]?.cost || 0,
    openai_tokens: openaiDay.tokens,
    gemini_tokens: data.gemini[index]?.tokens || 0,
    openai_frames: openaiDay.frames,
    gemini_frames: data.gemini[index]?.frames || 0,
  }));

  // Calculate totals for each model
  const openaiTotals = data.openai.reduce((acc, day) => ({
    requests: acc.requests + day.requests,
    cost: acc.cost + day.cost,
    tokens: acc.tokens + day.tokens,
    frames: acc.frames + day.frames,
  }), { requests: 0, cost: 0, tokens: 0, frames: 0 });

  const geminiTotals = data.gemini.reduce((acc, day) => ({
    requests: acc.requests + day.requests,
    cost: acc.cost + day.cost,
    tokens: acc.tokens + day.tokens,
    frames: acc.frames + day.frames,
  }), { requests: 0, cost: 0, tokens: 0, frames: 0 });

  return (
    <div className="space-y-6">
      <Tabs defaultValue="openai" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="openai">OpenAI Models</TabsTrigger>
          <TabsTrigger value="gemini">Gemini Models</TabsTrigger>
        </TabsList>

        <TabsContent value="openai" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard
              title="Total Requests"
              value={data.totals.requests.toLocaleString()}
              change={`${openaiTotals.requests} OpenAI + ${geminiTotals.requests} Gemini`}
              changeType="neutral"
              icon={<Brain className="w-6 h-6" />}
            />
            <StatCard
              title="Total Cost"
              value={`$${data.totals.cost.toFixed(2)}`}
              change={`OpenAI: $${openaiTotals.cost.toFixed(2)} | Gemini: $${geminiTotals.cost.toFixed(2)}`}
              changeType="neutral"
              icon={<DollarSign className="w-6 h-6" />}
            />
            <StatCard
              title="Total Tokens"
              value={data.totals.tokens.toLocaleString()}
              change={`${openaiTotals.tokens.toLocaleString()} OpenAI + ${geminiTotals.tokens.toLocaleString()} Gemini`}
              changeType="neutral"
              icon={<Zap className="w-6 h-6" />}
            />
            <StatCard
              title="Total Frames"
              value={data.totals.frames.toLocaleString()}
              change={`${openaiTotals.frames.toLocaleString()} OpenAI + ${geminiTotals.frames.toLocaleString()} Gemini`}
              changeType="neutral"
              icon={<Activity className="w-6 h-6" />}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <ChartCard
                title="Daily Requests: OpenAI vs Gemini"
                data={dailyComparison}
                type="bar"
                dataKey="openai_requests"
                color="hsl(var(--chart-1))"
              />
              <ChartCard
                title="Token Usage Over Time"
                data={dailyComparison}
                type="area"
                dataKey="openai_tokens"
                color="hsl(var(--chart-3))"
              />
            </div>
            <div className="space-y-6">
              <Card className="glass-effect border-border/50">
                <CardHeader>
                  <CardTitle>Failure Rate</CardTitle>
                </CardHeader>
                <CardContent className="flex justify-center">
                  <CircularProgress 
                    value={4} 
                    size={120} 
                    label="4% Failed"
                    color="hsl(var(--destructive))"
                  />
                </CardContent>
              </Card>
              <ChartCard
                title="Daily Cost Comparison"
                data={dailyComparison}
                type="line"
                dataKey="openai_cost"
                color="hsl(var(--chart-2))"
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="gemini" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard
              title="Total Requests"
              value={data.totals.requests.toLocaleString()}
              change={`${openaiTotals.requests} OpenAI + ${geminiTotals.requests} Gemini`}
              changeType="neutral"
              icon={<Brain className="w-6 h-6" />}
            />
            <StatCard
              title="Total Cost"
              value={`$${data.totals.cost.toFixed(2)}`}
              change={`OpenAI: $${openaiTotals.cost.toFixed(2)} | Gemini: $${geminiTotals.cost.toFixed(2)}`}
              changeType="neutral"
              icon={<DollarSign className="w-6 h-6" />}
            />
            <StatCard
              title="Total Tokens"
              value={data.totals.tokens.toLocaleString()}
              change={`${openaiTotals.tokens.toLocaleString()} OpenAI + ${geminiTotals.tokens.toLocaleString()} Gemini`}
              changeType="neutral"
              icon={<Zap className="w-6 h-6" />}
            />
            <StatCard
              title="Total Frames"
              value={data.totals.frames.toLocaleString()}
              change={`${openaiTotals.frames.toLocaleString()} OpenAI + ${geminiTotals.frames.toLocaleString()} Gemini`}
              changeType="neutral"
              icon={<Activity className="w-6 h-6" />}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <ChartCard
                title="Daily Requests: OpenAI vs Gemini"
                data={dailyComparison}
                type="bar"
                dataKey="gemini_requests"
                color="hsl(var(--chart-1))"
              />
              <ChartCard
                title="Frame Processing"
                data={dailyComparison}
                type="bar"
                dataKey="gemini_frames"
                color="hsl(var(--chart-4))"
              />
            </div>
            <div className="space-y-6">
              <Card className="glass-effect border-border/50">
                <CardHeader>
                  <CardTitle>Failure Rate</CardTitle>
                </CardHeader>
                <CardContent className="flex justify-center">
                  <CircularProgress 
                    value={2} 
                    size={120} 
                    label="2% Failed"
                    color="hsl(var(--destructive))"
                  />
                </CardContent>
              </Card>
              <ChartCard
                title="Token Usage Over Time"
                data={dailyComparison}
                type="area"
                dataKey="gemini_tokens"
                color="hsl(var(--chart-3))"
              />
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Model Comparison Table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="p-6 rounded-lg border bg-card">
          <h3 className="text-lg font-semibold mb-4">OpenAI Statistics</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total Requests:</span>
              <span className="font-medium">{openaiTotals.requests.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total Cost:</span>
              <span className="font-medium">${openaiTotals.cost.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total Tokens:</span>
              <span className="font-medium">{openaiTotals.tokens.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total Frames:</span>
              <span className="font-medium">{openaiTotals.frames.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Avg Cost/Request:</span>
              <span className="font-medium">
                ${openaiTotals.requests > 0 ? (openaiTotals.cost / openaiTotals.requests).toFixed(4) : '0.0000'}
              </span>
            </div>
          </div>
        </div>

        <div className="p-6 rounded-lg border bg-card">
          <h3 className="text-lg font-semibold mb-4">Gemini Statistics</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total Requests:</span>
              <span className="font-medium">{geminiTotals.requests.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total Cost:</span>
              <span className="font-medium">${geminiTotals.cost.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total Tokens:</span>
              <span className="font-medium">{geminiTotals.tokens.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total Frames:</span>
              <span className="font-medium">{geminiTotals.frames.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Avg Cost/Request:</span>
              <span className="font-medium">
                ${geminiTotals.requests > 0 ? (geminiTotals.cost / geminiTotals.requests).toFixed(4) : '0.0000'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
