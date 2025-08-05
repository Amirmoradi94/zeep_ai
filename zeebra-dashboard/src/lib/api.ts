// API configuration  
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// Response types
export interface OverviewData {
  totalUsers: number;
  userGrowth: number;
  totalCost: number;
  costGrowth: number;
  totalRequests: number;
  requestGrowth: number;
  avgResponseTime: number;
  responseTimeChange: number;
  successRate: number;
  totalFeedback: number;
  positiveFeedbackPct: number;
  dailyUsage: Array<{
    date: string;
    requests: number;
  }>;
}

export interface UserStats {
  totalUsers: number;
  followingUsers: number;
  followingRate: number;
  usersByRegion: Array<{
    region: string;
    count: number;
  }>;
  monthlyNewUsers: Array<{
    month: string;
    count: number;
  }>;
  totalSearches: number;
  avgSearchesPerUser: number;
}

export interface AIModelStats {
  openai: Array<{
    date: string;
    requests: number;
    tokens: number;
    cost: number;
    frames: number;
  }>;
  gemini: Array<{
    date: string;
    requests: number;
    tokens: number;
    cost: number;
    frames: number;
  }>;
  totals: {
    requests: number;
    tokens: number;
    cost: number;
    frames: number;
    avgResponseTime: number;
  };
}

export interface ScrapingAPIDailyStat {
  date: string;
  requests: number;
  responseTime: number;
  successRate: number;
}

export interface ScrapingAPIStats {
  totalRequests: number;
  totalAvgResponseTime: number;
  totalSuccessRate: number;
  daily: ScrapingAPIDailyStat[];
}

export interface FeedbackStats {
  GOOD: number;
  BAD: number;
  NEUTRAL: number;
  daily: Array<{
    date: string;
    good: number;
    bad: number;
    neutral: number;
  }>;
}

// API Error class
export class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'APIError';
  }
}

// Generic API fetch function
async function apiRequest<T>(endpoint: string): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`);
    
    if (!response.ok) {
      throw new APIError(response.status, `API Error: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    if (error instanceof APIError) {
      throw error;
    }
    
    // Network or other errors
    throw new APIError(0, `Network error: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// API functions
export const api = {
  // Overview data
  getOverview: (): Promise<OverviewData> => 
    apiRequest<OverviewData>('/api/overview'),

  // User statistics
  getUserStats: (): Promise<UserStats> => 
    apiRequest<UserStats>('/api/user-stats'),

  // AI model statistics
  getAIModelStats: (): Promise<AIModelStats> => 
    apiRequest<AIModelStats>('/api/ai-model-stats'),

  // Scraping API statistics
  getScrapingAPIStats: (): Promise<ScrapingAPIStats> => 
    apiRequest<ScrapingAPIStats>('/api/scraping-api-stats'),

  // Feedback statistics
  getFeedbackStats: (): Promise<FeedbackStats> => 
    apiRequest<FeedbackStats>('/api/feedback-stats'),

  // Health check
  healthCheck: (): Promise<{ message: string }> => 
    apiRequest<{ message: string }>('/'),
};

// Hook for API state management
export interface APIState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function createInitialAPIState<T>(): APIState<T> {
  return {
    data: null,
    loading: true,
    error: null,
  };
} 