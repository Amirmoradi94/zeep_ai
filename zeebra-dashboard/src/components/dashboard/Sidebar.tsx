import { cn } from '@/lib/utils';
import { 
  BarChart3, 
  Brain, 
  Users, 
  MessageSquare, 
  Globe, 
  Settings, 
  Download,
  Database
} from 'lucide-react';

interface SidebarProps {
  activeSection: string;
  onSectionChange: (section: string) => void;
}

const menuItems = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'ai-models', label: 'AI Models', icon: Brain },
  { id: 'scraping', label: 'Scraping API', icon: Globe },
  { id: 'users', label: 'Users', icon: Users },
  { id: 'feedback', label: 'Feedback', icon: MessageSquare },
  { id: 'data-export', label: 'Data Export', icon: Download },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export const Sidebar = ({ activeSection, onSectionChange }: SidebarProps) => {
  return (
    <div className="w-64 h-screen bg-gradient-to-b from-slate-900/90 to-slate-800/90 backdrop-blur-xl border-r border-purple-500/30 flex flex-col relative overflow-hidden">
      {/* Cyber grid background */}
      <div className="absolute inset-0 cyber-grid opacity-30" />
      
      <div className="relative p-6 border-b border-purple-500/30">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center neon-glow">
            <Database className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-xl font-bold text-white glow-text">AI Dashboard</h1>
        </div>
      </div>
      
      <nav className="relative flex-1 p-4 space-y-2">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeSection === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSectionChange(item.id)}
              className={cn(
                "w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-300 group relative overflow-hidden",
                isActive
                  ? "bg-gradient-to-r from-purple-500/20 to-blue-500/20 text-white border border-purple-500/50 neon-glow"
                  : "text-purple-200/80 hover:bg-purple-500/10 hover:text-white hover:border hover:border-purple-500/30"
              )}
            >
              {isActive && (
                <div className="absolute inset-0 bg-gradient-to-r from-purple-500/10 to-transparent" />
              )}
              <Icon className={cn(
                "w-5 h-5 relative z-10",
                isActive && "text-purple-300"
              )} />
              <span className="relative z-10">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Bottom glow effect */}
      <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-purple-500/10 to-transparent pointer-events-none" />
    </div>
  );
};
