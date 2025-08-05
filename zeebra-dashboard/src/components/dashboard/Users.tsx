import React, { useEffect, useState } from 'react';
import { StatCard } from './StatCard';
import { ChartCard } from './ChartCard';
import { Users as UsersIcon, TrendingUp, Calendar, UserPlus } from 'lucide-react';
import { api, UserStats, APIState, createInitialAPIState } from '../../lib/api';

export const Users = () => {
  const [userState, setUserState] = useState<APIState<UserStats>>(createInitialAPIState());

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        setUserState(prev => ({ ...prev, loading: true, error: null }));
        
        const userData = await api.getUserStats();
        
        setUserState({ data: userData, loading: false, error: null });
      } catch (error) {
        console.error('Error fetching user data:', error);
        const errorMessage = error instanceof Error ? error.message : 'An error occurred';
        setUserState(prev => ({ ...prev, loading: false, error: errorMessage }));
      }
    };

    fetchUserData();
  }, []);

  if (userState.loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg">Loading user data...</div>
      </div>
    );
  }

  if (userState.error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col space-y-4">
        <div className="text-red-500">Error loading data: {userState.error}</div>
        <button 
          onClick={() => window.location.reload()} 
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!userState.data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">No user data available</div>
      </div>
    );
  }

  const data = userState.data;

  // Process monthly data for charts
  const monthlyGrowthData = data.monthlyNewUsers.map(item => ({
    month: item.month,
    users: item.count,
    newUsers: item.count, // Same as count for new users per month
  }));

  // Create regional distribution chart data
  const regionData = data.usersByRegion.map(item => ({
    region: item.region?.toUpperCase() || 'Unknown',
    count: item.count,
    percentage: data.totalUsers > 0 ? Math.round((item.count / data.totalUsers) * 100) : 0
  }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Users"
          value={data.totalUsers.toLocaleString()}
          change=""
          changeType="positive"
          icon={<UsersIcon className="w-6 h-6" />}
        />
        <StatCard
          title="Following Users"
          value={data.followingUsers.toLocaleString()}
          change={`${data.followingRate}% of total users`}
          changeType="positive"
          icon={<UserPlus className="w-6 h-6" />}
        />
        <StatCard
          title="Total Searches"
          value={data.totalSearches.toLocaleString()}
          change={`${data.avgSearchesPerUser} avg per user`}
          changeType="neutral"
          icon={<Calendar className="w-6 h-6" />}
        />
        <StatCard
          title="Following Rate"
          value={`${data.followingRate}%`}
          change={`${data.followingUsers} following users`}
          changeType="positive"
          icon={<TrendingUp className="w-6 h-6" />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard
          title="Monthly New Users"
          data={monthlyGrowthData}
          type="area"
          dataKey="users"
          xAxisKey="month"
          color="hsl(var(--chart-1))"
        />
        <ChartCard
          title="User Registration Trend"
          data={monthlyGrowthData}
          type="bar"
          dataKey="newUsers"
          xAxisKey="month"
          color="hsl(var(--chart-2))"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard
          title="Users by Region"
          data={regionData}
          type="bar"
          dataKey="count"
          xAxisKey="region"
          color="hsl(var(--chart-3))"
        />
        <div className="p-6 rounded-lg border bg-card">
          <h3 className="text-lg font-semibold mb-4">User Statistics Summary</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total Users:</span>
              <span className="font-medium">{data.totalUsers.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Following Users:</span>
              <span className="font-medium">{data.followingUsers.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Following Rate:</span>
              <span className="font-medium">{data.followingRate}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total Searches:</span>
              <span className="font-medium">{data.totalSearches.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Avg Searches/User:</span>
              <span className="font-medium">{data.avgSearchesPerUser}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
