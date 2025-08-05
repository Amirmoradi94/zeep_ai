
import { useState } from 'react';
import { Sidebar } from '@/components/dashboard/Sidebar';
import { Overview } from '@/components/dashboard/Overview';
import { AIModels } from '@/components/dashboard/AIModels';
import { ScrapingAPI } from '@/components/dashboard/ScrapingAPI';
import { Users } from '@/components/dashboard/Users';
import { Feedback } from '@/components/dashboard/Feedback';
import { Performance } from '@/components/dashboard/Performance';
import { DataExport } from '@/components/dashboard/DataExport';
import { Settings } from '@/components/dashboard/Settings';

const Index = () => {
  const [activeSection, setActiveSection] = useState('overview');

  const renderContent = () => {
    switch (activeSection) {
      case 'overview':
        return <Overview />;
      case 'ai-models':
        return <AIModels />;
      case 'scraping':
        return <ScrapingAPI />;
      case 'users':
        return <Users />;
      case 'feedback':
        return <Feedback />;
      case 'performance':
        return <Performance />;
      case 'data-export':
        return <DataExport />;
      case 'settings':
        return <Settings />;
      default:
        return <Overview />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-800 flex relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 cyber-grid opacity-20" />
      <div className="absolute top-20 left-20 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse" />
      <div className="absolute bottom-20 right-20 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse delay-1000" />
      
      <Sidebar activeSection={activeSection} onSectionChange={setActiveSection} />
      <main className="flex-1 p-8 relative z-10">
        <div className="max-w-7xl mx-auto">
          {renderContent()}
        </div>
      </main>
    </div>
  );
};

export default Index;
